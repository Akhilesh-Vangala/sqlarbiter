"""Checkpointed LangGraph investigator. Only public evidence crosses this boundary."""

import asyncio
import hashlib
import json
import os
import sqlite3
import time
from contextlib import asynccontextmanager
from importlib.metadata import version as package_version
from contextlib import nullcontext
from datetime import datetime
from datetime import timezone
from typing import TypedDict

from langgraph.graph import StateGraph
from langgraph.graph import START
from langgraph.graph import END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from langgraph.types import interrupt

from model import InvestigationFailed
from model import definitions
from model import validate_decision
from agent_policy import GRAPH_SYSTEM
from agent_policy import plan_definition
from agent_policy import validate_plan
from agent_policy import sql_precheck
from agent_policy import findings_definition
from agent_policy import validate_findings
from agent_policy import working_memory
from tools import ToolRejected

GRAPH_VERSION = "sqlarbiter-graph-3"
CONFIG = {"configurable": {"thread_id": "investigation"}, "recursion_limit": 160}


class State(TypedDict):
    version: str
    messages: list
    trace: list
    repeats: dict
    rounds: int
    usage: dict
    metadata: dict
    calls: list
    cursor: int
    replies: list
    decision: dict
    plans: list
    corrections: int
    issues: list
    assessment: dict
    journal: list
    findings: list


def activity(state, stage, status, **fields):
    return state["journal"] + [
        {
            "stage": stage,
            "status": status,
            "round": state["rounds"],
            "at_utc": datetime.now(timezone.utc).isoformat(),
            **fields,
        }
    ]


def evidence_version(workspace):
    digest = hashlib.sha256(GRAPH_VERSION.encode())
    packages = ["langgraph", "langgraph-checkpoint", "langgraph-checkpoint-sqlite", "anthropic"]
    if os.getenv("SQLARBITER_CHECKPOINT_DATABASE_URL"):
        packages.append("langgraph-checkpoint-postgres")
    for package in packages:
        digest.update((package + package_version(package)).encode())
    files = [workspace / "incident.json", workspace / "schema.json"]
    files += list(workspace.glob("source.*")) + list((workspace / "runtime").glob("*.py"))
    for path in sorted(files):
        digest.update(path.name.encode())
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(65536), b""):
                digest.update(chunk)
    return digest.hexdigest()


def graph_config(workspace):
    if not os.getenv("SQLARBITER_CHECKPOINT_DATABASE_URL"):
        thread_id = "investigation"
    else:
        thread_id = os.getenv("SQLARBITER_CHECKPOINT_THREAD_ID")
    if not thread_id:
        thread_id = hashlib.sha256(str(workspace.resolve()).encode()).hexdigest()
    if len(thread_id) > 128:
        raise ValueError("Checkpoint thread identity is too long")
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": 160}


@asynccontextmanager
async def checkpoint_saver(workspace):
    database_url = os.getenv("SQLARBITER_CHECKPOINT_DATABASE_URL")
    if database_url:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        async with AsyncPostgresSaver.from_conn_string(database_url) as saver:
            yield saver
    else:
        async with AsyncSqliteSaver.from_conn_string(
            str(workspace / "graph-checkpoints.sqlite")
        ) as saver:
            yield saver


class Receipts:
    """Persist call results before graph commit; unresolved attempts fail closed."""

    def __init__(self, workspace):
        self.path = workspace / "graph-receipts.sqlite"
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS receipts (id TEXT PRIMARY KEY, payload TEXT)")

    def begin(self, identity):
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT payload FROM receipts WHERE id=?", (identity,)).fetchone()
            if row:
                if row[0] is None:
                    raise InvestigationFailed(
                        "Unresolved call receipt; automatic replay is blocked. Start a new run explicitly."
                    )
                return json.loads(row[0])
            db.execute("INSERT INTO receipts VALUES (?,NULL)", (identity,))
        return None

    def complete(self, identity, payload):
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE receipts SET payload=? WHERE id=?", (json.dumps(payload), identity))

    def accounting(self):
        usage = {"input_tokens": 0, "output_tokens": 0}
        unresolved = False
        with sqlite3.connect(self.path) as db:
            for identity, text in db.execute(
                "SELECT id,payload FROM receipts WHERE id LIKE 'model-%'"
            ):
                if text is None:
                    unresolved = True
                    continue
                payload = json.loads(text)
                result = payload.get("result")
                reported = result.get("usage") if isinstance(result, dict) else None
                for name in usage:
                    value = reported.get(name) if isinstance(reported, dict) else None
                    if type(value) is int and value >= 0:
                        usage[name] += value
                    else:
                        # A complete receipt without complete usage is not a zero-cost call.
                        unresolved = True
        return usage, unresolved


def build_graph(tools, client, saver, receipts):
    def scoped(name):
        telemetry = getattr(tools, "telemetry", None)
        return telemetry.span("graph." + name) if telemetry else nullcontext()

    def prepare(state):
        with scoped("prepare"):
            if state["rounds"] >= 8:
                raise InvestigationFailed("Model round budget exhausted")
            if state["usage"]["output_tokens"] >= 12000:
                raise InvestigationFailed("Output-token budget exhausted")
            if state["metadata"].get("active_seconds", 0) >= 240:
                raise InvestigationFailed("Investigation time budget exhausted")
            return {
                "rounds": state["rounds"] + 1,
                "calls": [],
                "cursor": 0,
                "replies": [],
                "issues": [],
            }

    async def model(state):
        memory = working_memory(state["plans"], state["findings"], state["trace"])
        client.system = (
            GRAPH_SYSTEM + "\nPUBLIC WORKING MEMORY:\n" + json.dumps(memory, sort_keys=True)
        )
        identity = "model-%d" % state["rounds"]
        payload = receipts.begin(identity)
        if payload is None:
            started = time.monotonic()
            with scoped("model") as span:
                if span:
                    span.set_attribute("gen_ai.request.model", getattr(client, "model", "scripted"))
                async with asyncio.timeout(
                    max(0.001, 240 - state["metadata"].get("active_seconds", 0))
                ):
                    result = await client.complete(
                        state["messages"],
                        definitions() + [plan_definition(), findings_definition()],
                        max_tokens=min(2048, 12000 - state["usage"]["output_tokens"]),
                    )
                reported = result.get("usage") if isinstance(result, dict) else None
                if span and isinstance(reported, dict):
                    for name, value in reported.items():
                        if type(value) is int:
                            span.set_attribute("gen_ai.usage." + name, value)
            payload = {
                "result": result,
                "seconds": time.monotonic() - started,
                "client": {
                    name: getattr(client, name, None)
                    for name in (
                        "resolved_model",
                        "context_tokens_requested",
                        "input_tokens",
                        "output_tokens",
                    )
                },
            }
            receipts.complete(identity, payload)
        for name, value in payload["client"].items():
            if value is not None:
                setattr(client, name, value)
        result = payload["result"]
        if not isinstance(result, dict) or not isinstance(result.get("content"), list):
            raise InvestigationFailed("Invalid provider message")
        blocks = result["content"]
        if any(not isinstance(block, dict) for block in blocks):
            raise InvestigationFailed("Invalid provider content")
        reported = result.get("usage")
        if not isinstance(reported, dict):
            raise InvestigationFailed("Invalid provider usage")
        usage = dict(state["usage"])
        for name in usage:
            value = reported.get(name)
            if type(value) is not int or value < 0:
                raise InvestigationFailed("Invalid provider usage")
            usage[name] += value
        if usage["output_tokens"] > 12000:
            raise InvestigationFailed("Output-token budget exhausted")
        metadata = dict(state["metadata"])
        metadata.update(
            reported_model=result.get("model"),
            active_seconds=metadata.get("active_seconds", 0) + payload["seconds"],
            client_budget=payload["client"],
        )
        for name in ("cache_creation_input_tokens", "cache_read_input_tokens"):
            value = reported.get(name)
            if type(value) is int and value >= 0:
                metadata[name] = metadata.get(name, 0) + value
        calls = [block for block in blocks if block.get("type") == "tool_use"]
        if result.get("stop_reason") != "tool_use" or not calls:
            raise InvestigationFailed("Investigator stopped without a complete tool decision")
        ids = [call.get("id") for call in calls]
        if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
            raise InvestigationFailed("Invalid tool call identity")
        if any(not isinstance(call.get("name"), str) or not call["name"] for call in calls):
            raise InvestigationFailed("Invalid tool call name")
        if (
            any(call.get("name") in ("finish", "record_plan", "record_findings") for call in calls)
            and len(calls) != 1
        ):
            raise InvestigationFailed(
                "Finish and record_plan must be submitted separately from evidence calls"
            )
        return {
            "usage": usage,
            "metadata": metadata,
            "calls": calls,
            "journal": activity(state, "model", "completed"),
            "messages": state["messages"] + [{"role": "assistant", "content": blocks}],
        }

    async def evidence(state):
        with scoped("evidence"):
            if state["metadata"].get("active_seconds", 0) >= 240:
                raise InvestigationFailed("Investigation time budget exhausted")
            call = state["calls"][state["cursor"]]
            fingerprint = json.dumps([call.get("name"), call.get("input")], sort_keys=True)
            repeats = dict(state["repeats"])
            repeats[fingerprint] = repeats.get(fingerprint, 0) + 1
            if repeats[fingerprint] > 3:
                raise InvestigationFailed("Repeated identical tool-call limit exceeded")
            tools.trace = list(state["trace"])
            identity = "tool-%d-%d" % (state["rounds"], state["cursor"])
            payload = receipts.begin(identity)
            if payload is None:
                started = time.monotonic()
                try:
                    reply = await asyncio.to_thread(tools.call, call.get("name"), call.get("input"))
                except ToolRejected:
                    raise InvestigationFailed("Evidence tool budget exhausted") from None
                payload = {"reply": reply, "seconds": time.monotonic() - started}
                receipts.complete(identity, payload)
            reply = payload["reply"]
            trace = state["trace"] + [reply]
            tools.trace = trace
            metadata = dict(state["metadata"])
            metadata["active_seconds"] = metadata.get("active_seconds", 0) + payload["seconds"]
            replies = state["replies"] + [
                {
                    "type": "tool_result",
                    "tool_use_id": call["id"],
                    "content": json.dumps(reply),
                    "is_error": not reply["ok"],
                }
            ]
            cursor = state["cursor"] + 1
            messages = state["messages"]
            if cursor == len(state["calls"]):
                messages = messages + [{"role": "user", "content": replies}]
            return {
                "trace": trace,
                "metadata": metadata,
                "repeats": repeats,
                "journal": activity(
                    state,
                    "evidence",
                    "completed" if reply["ok"] else "rejected",
                    tool=reply["method"],
                    evidence_id=reply["evidence_id"],
                ),
                "cursor": cursor,
                "replies": replies,
                "messages": messages,
            }

    def plan(state):
        with scoped("plan"):
            if len(state["plans"]) >= 3:
                return {"issues": ["At most three plan revisions are allowed"]}
            try:
                value = validate_plan(state["calls"][0].get("input"), state["trace"])
            except ValueError as error:
                return {"issues": [str(error)]}
            revision = {"revision": len(state["plans"]) + 1, "round": state["rounds"], **value}
            reply = {
                "type": "tool_result",
                "tool_use_id": state["calls"][0]["id"],
                "content": json.dumps(
                    {
                        "kind": "plan_recorded",
                        "revision": revision["revision"],
                        "scope": "Hypotheses are unverified; execute the planned tests using evidence tools.",
                    }
                ),
            }
            return {
                "plans": state["plans"] + [revision],
                "messages": state["messages"] + [{"role": "user", "content": [reply]}],
                "journal": activity(state, "plan", "recorded", revision=revision["revision"]),
            }

    def decide(state):
        with scoped("decide"):
            tools.trace = list(state["trace"])
            try:
                decision = validate_decision(state["calls"][0].get("input"), tools)
            except InvestigationFailed as error:
                return {"decision": {}, "issues": [str(error)]}
            return {
                "decision": decision,
                "journal": activity(state, "decision", "validated", outcome=decision["status"]),
            }

    def findings(state):
        with scoped("findings"):
            try:
                update = validate_findings(
                    state["calls"][0].get("input"), state["plans"], state["trace"]
                )
            except ValueError as error:
                return {"issues": [str(error)]}
            changed = {f["hypothesis_id"] for f in update["findings"]}
            retained = [
                f
                for f in state["findings"]
                if not (
                    f["plan_revision"] == update["plan_revision"] and f["hypothesis_id"] in changed
                )
            ]
            values = retained + [
                {"plan_revision": update["plan_revision"], "round": state["rounds"], **f}
                for f in update["findings"]
            ]
            reply = {
                "type": "tool_result",
                "tool_use_id": state["calls"][0]["id"],
                "content": json.dumps(
                    {
                        "kind": "findings_recorded",
                        "plan_revision": update["plan_revision"],
                        "scope": "Unverified public interpretations; external correctness verification remains required.",
                    }
                ),
            }
            return {
                "findings": values,
                "messages": state["messages"] + [{"role": "user", "content": [reply]}],
                "journal": activity(
                    state, "findings", "recorded", plan_revision=update["plan_revision"]
                ),
            }

    async def review(state):
        """Public execution/completeness gate. No reference or private grader calls."""
        with scoped("precheck"):
            decision = dict(state["decision"])
            if decision["status"] not in ("candidate", "no_change"):
                return {"assessment": {"status": "not_applicable", "scope": "No SQL submission"}}
            if decision["status"] == "candidate" and not state["plans"]:
                return {
                    "issues": [
                        "Record an evidence-cited hypothesis plan before submitting a repair."
                    ]
                }
            if decision["status"] == "candidate":
                tests = {h["test_sql"] for h in state["plans"][-1]["hypotheses"]}
                tested = [
                    r
                    for r in state["trace"]
                    if r["method"] == "query"
                    and r["ok"]
                    and not r["result"].get("truncated")
                    and r["params"].get("sql") in tests
                    and r["evidence_id"] in decision["evidence_ids"]
                ]
                if not tested:
                    return {
                        "issues": [
                            "Execute and cite at least one SQL test from the latest plan before submitting a repair."
                        ]
                    }
            sql = (
                decision.get("candidate_sql")
                if decision["status"] == "candidate"
                else tools.manifest["current_sql"]
            )
            matching = [
                record
                for record in state["trace"]
                if record["method"] == "query" and record["params"] == {"sql": sql} and record["ok"]
            ]
            trace = list(state["trace"])
            metadata = dict(state["metadata"])
            reused = bool(matching)
            if matching:
                record = matching[-1]
            else:
                if len(trace) >= tools.max_calls:
                    raise InvestigationFailed("Evidence tool budget exhausted before SQL precheck")
                if metadata.get("active_seconds", 0) >= 240:
                    raise InvestigationFailed("Investigation time budget exhausted")
                tools.trace = list(trace)
                identity = "precheck-%d" % state["rounds"]
                payload = receipts.begin(identity)
                if payload is None:
                    started = time.monotonic()
                    record = await asyncio.to_thread(tools.call, "query", {"sql": sql})
                    payload = {"reply": record, "seconds": time.monotonic() - started}
                    receipts.complete(identity, payload)
                record = payload["reply"]
                trace.append(record)
                tools.trace = trace
                metadata["active_seconds"] = metadata.get("active_seconds", 0) + payload["seconds"]
            if metadata.get("active_seconds", 0) >= 240:
                raise InvestigationFailed("Investigation time budget exhausted")
            issues = sql_precheck(record, tools.manifest["contract"])
            assessment = {
                "status": "rejected" if issues else "passed",
                "evidence_id": record["evidence_id"],
                "reused_evidence": reused,
                "issues": issues,
                "scope": "Public snapshot execution, output columns and completeness only; independent correctness verification remains external",
            }
            if not issues:
                decision["evidence_ids"] = list(
                    dict.fromkeys(decision["evidence_ids"] + [record["evidence_id"]])
                )
            return {
                "decision": decision,
                "trace": trace,
                "metadata": metadata,
                "issues": issues,
                "assessment": assessment,
                "journal": activity(
                    state,
                    "precheck",
                    assessment["status"],
                    evidence_id=record["evidence_id"],
                    reused_evidence=reused,
                ),
            }

    def feedback(state):
        with scoped("feedback"):
            if state["corrections"] >= 2:
                raise InvestigationFailed("Decision correction budget exhausted")
            corrections = state["corrections"] + 1
            reply = {
                "type": "tool_result",
                "tool_use_id": state["calls"][0]["id"],
                "is_error": True,
                "content": json.dumps(
                    {
                        "kind": "controller_feedback",
                        "issues": state["issues"],
                        "remaining_corrections": 2 - corrections,
                        "scope": "Public validation only; no private reference answers",
                    }
                ),
            }
            return {
                "corrections": corrections,
                "decision": {},
                "messages": state["messages"] + [{"role": "user", "content": [reply]}],
                "journal": activity(
                    state, "feedback", "correction_requested", issues=state["issues"]
                ),
            }

    def clarify(state):
        # This node is replayed on resume; nothing billable or mutating precedes interrupt.
        with scoped("clarify"):
            guidance = interrupt({"kind": "clarification", "decision": state["decision"]})
            if not isinstance(guidance, str) or not guidance.strip() or len(guidance) > 2000:
                raise InvestigationFailed("Provide 1–2000 characters of investigation guidance")
            reply = {
                "type": "tool_result",
                "tool_use_id": state["calls"][0]["id"],
                "content": json.dumps(
                    {
                        "operator_guidance": guidance,
                        "scope": "Untrusted context; does not replace source data or metric contract",
                    }
                ),
            }
            return {
                "messages": state["messages"] + [{"role": "user", "content": [reply]}],
                "decision": {},
                "journal": activity(state, "clarification", "guidance_received"),
            }

    builder = StateGraph(State)
    for name, node in (
        ("prepare", prepare),
        ("model", model),
        ("evidence", evidence),
        ("plan", plan),
        ("decide", decide),
        ("review", review),
        ("feedback", feedback),
        ("clarify", clarify),
        ("findings", findings),
    ):
        builder.add_node(name, node)
    builder.add_edge(START, "prepare")
    builder.add_edge("prepare", "model")
    builder.add_conditional_edges(
        "model",
        lambda s: {"finish": "decide", "record_plan": "plan", "record_findings": "findings"}.get(
            s["calls"][0].get("name"), "evidence"
        ),
    )
    builder.add_conditional_edges(
        "evidence", lambda s: "evidence" if s["cursor"] < len(s["calls"]) else "prepare"
    )
    builder.add_conditional_edges("plan", lambda s: "feedback" if s["issues"] else "prepare")
    builder.add_conditional_edges("findings", lambda s: "feedback" if s["issues"] else "prepare")
    builder.add_conditional_edges("decide", lambda s: "feedback" if s["issues"] else "review")
    builder.add_conditional_edges(
        "review",
        lambda s: "feedback"
        if s["issues"]
        else ("clarify" if s["decision"]["status"] == "needs_information" else END),
    )
    builder.add_edge("feedback", "prepare")
    builder.add_edge("clarify", "prepare")
    return builder.compile(checkpointer=saver)


async def investigate(tools, client, *, guidance=None, recover=False):
    """New run, explicit interrupted-run recovery, or version-checked human continuation."""
    version = evidence_version(tools.workspace)
    client.system = GRAPH_SYSTEM
    receipts = Receipts(tools.workspace)
    started = time.monotonic()
    config = graph_config(tools.workspace)
    async with checkpoint_saver(tools.workspace) as saver:
        graph = build_graph(tools, client, saver, receipts)
        saved = await graph.aget_state(config)
        if saved.values:
            state = saved.values
            if state["version"] != version:
                raise InvestigationFailed(
                    "Evidence or graph code changed; start a new investigation"
                )
            tools.trace = list(state["trace"])
            for name, value in state["metadata"].get("client_budget", {}).items():
                if value is not None:
                    setattr(client, name, value)
            if not saved.next:
                raise InvestigationFailed(
                    "Graph is already completed; duplicate continuation rejected"
                )
            if saved.interrupts:
                if guidance is None:
                    raise InvestigationFailed("Paused graph requires explicit operator guidance")
                if not isinstance(guidance, str) or not guidance.strip() or len(guidance) > 2000:
                    raise InvestigationFailed("Provide 1–2000 characters of investigation guidance")
                graph_input = Command(resume=guidance)
            elif recover and guidance is None:
                graph_input = None
            else:
                raise InvestigationFailed("Existing graph requires explicit recovery")
        else:
            if guidance is not None or recover:
                raise InvestigationFailed("No checkpoint exists to resume")
            graph_input = {
                "version": version,
                "messages": [
                    {
                        "role": "user",
                        "content": "Investigate the available metric incident. Submit via finish.",
                    }
                ],
                "trace": [],
                "repeats": {},
                "rounds": 0,
                "usage": {"input_tokens": 0, "output_tokens": 0},
                "metadata": {
                    "requested_model": getattr(client, "model", None),
                    "started_at_utc": datetime.now(timezone.utc).isoformat(),
                    "prompt_version": hashlib.sha256(GRAPH_SYSTEM.encode()).hexdigest(),
                    "sdk_max_retries": getattr(client, "sdk_max_retries", 0),
                    "active_seconds": 0,
                },
                "calls": [],
                "cursor": 0,
                "replies": [],
                "decision": {},
                "plans": [],
                "corrections": 0,
                "issues": [],
                "assessment": {},
                "journal": [],
                "findings": [],
            }

        def report(state, status):
            metadata = dict(state["metadata"])
            receipt_usage, unresolved = receipts.accounting()
            metadata.update(
                status=status,
                rounds=state["rounds"],
                usage=receipt_usage,
                tool_calls=len(state["trace"]),
                framework="langgraph",
                graph_version=GRAPH_VERSION,
                latency_seconds=state["metadata"].get("active_seconds", 0),
                invocation_seconds=time.monotonic() - started,
                resolved_model=getattr(client, "resolved_model", None),
                partial_usage=getattr(client, "latest_partial_usage", {}),
                additional_billing_unknown=unresolved
                or getattr(client, "failure_billing_unknown", False),
            )
            metadata.update(
                plan_revisions=len(state["plans"]),
                decision_corrections=state["corrections"],
                public_precheck=state["assessment"].get("status"),
            )
            (tools.workspace / "model-run.json").write_text(json.dumps(metadata, indent=2))
            return metadata

        try:
            result = await graph.ainvoke(graph_input, config, durability="sync")
            paused = bool(result.get("__interrupt__"))
            metadata = report(result, "paused" if paused else "completed")
            tools.trace = list(result["trace"])
            return {
                "decision": result["decision"],
                "trace": result["trace"],
                "model_run": metadata,
                "agent_workflow": {
                    "plans": result["plans"],
                    "activity": result["journal"],
                    "findings": result["findings"],
                    "working_memory": working_memory(
                        result["plans"], result["findings"], result["trace"]
                    ),
                    "corrections": result["corrections"],
                    "public_precheck": result["assessment"],
                },
                "graph_run": {
                    "status": "paused" if paused else "completed",
                    "version": GRAPH_VERSION,
                },
            }
        except BaseException:
            saved = await graph.aget_state(config)
            if saved.values:
                report(saved.values, "failed")
            raise
