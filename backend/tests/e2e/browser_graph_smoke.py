"""Real browser/API/graph flow with scripted provider responses; never live AI."""
import asyncio
import json
import os
import socket
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import uvicorn
from playwright.sync_api import sync_playwright
from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "agent/investigator"))
sys.path.insert(0, str(ROOT / "backend" / "tests"))
from graph import investigate
from tools import EvidenceTools
from baseline import LATEST_SQL
from vdir.domain.cases import JOIN_SQL
from fixtures.model_fixtures import ScriptedClient
from fixtures.model_fixtures import completion
from fixtures.model_fixtures import call
from vdir.evaluation import evaluation
from vdir.api.routes import create_app
from vdir.workflows.service import process_next


def main():
    output = ROOT / "artifacts/generated" / ("browser-graph-" + uuid.uuid4().hex[:8])
    output.mkdir(parents=True)
    original_worker = evaluation.run_worker
    errors = []
    resumed_notes = []
    def execute(store):
        # Playwright's sync driver runs an event loop on this thread; isolate the async worker.
        with ThreadPoolExecutor(max_workers=1) as workers:
            return workers.submit(process_next, store).result()
    def provider(workspace, *, mode="baseline", requests=None, continuation=None, spend_root=None):
        if mode != "langgraph":
            return original_worker(workspace, mode=mode, requests=requests)
        tools = EvidenceTools(workspace)
        if tools.manifest["contract"]["metric"] == "completed_item_revenue":
            diagnostic = "SELECT product_id, COUNT(*) AS versions FROM product_versions GROUP BY product_id"
            def plan(messages):
                return completion([call("record_plan", {"objective": "Check version-join cardinality.",
                    "hypotheses": [{"id": "h1", "claim": "Multiple product versions multiply items.",
                        "test_sql": diagnostic, "expected_signal": "Products have more than one version."}],
                    "evidence_ids": [tools.trace[0]["evidence_id"]]})])
            def findings(messages):
                evidence = next(r["evidence_id"] for r in tools.trace if r["method"] == "query")
                return completion([call("record_findings", {"plan_revision": 1, "findings": [{"hypothesis_id": "h1", "assessment": "supports", "summary": "Multiple versions were observed; verify the proposed repair independently.", "evidence_ids": [evidence]}]})])
            def propose(messages):
                return completion([call("finish", {"status": "candidate", "explanation": "Use the latest product version.",
                    "candidate_sql": LATEST_SQL, "evidence_ids": [r["evidence_id"] for r in tools.trace if r["ok"]]})])
            return asyncio.run(investigate(tools, ScriptedClient([completion([call("contract", {})]), plan,
                completion([call("query", {"sql": diagnostic}), call("inspect_sql", {"sql": LATEST_SQL}, identity="inspect"), call("check_join", {"left_table": "order_items", "left_key": "product_id", "right_table": "product_versions", "right_key": "product_id"}, identity="join")]), findings, propose])))
        def clarify(messages):
            if continuation:
                resumed_notes.append(json.loads(messages[-1]["content"][0]["content"])["operator_guidance"])
                # Find the original successful contract result in the saved transcript.
                evidence = next(json.loads(block["content"])["evidence_id"]
                    for message in messages if message["role"] == "user" and isinstance(message["content"], list)
                    for block in message["content"] if block["type"] == "tool_result"
                    and "evidence_id" in json.loads(block["content"]))
            else:
                evidence = json.loads(messages[-1]["content"][0]["content"])["evidence_id"]
            return completion([call("finish", {"status": "needs_information", "explanation": "Source offsets required.",
                "evidence_ids": [evidence], "affected_ids": ["t1", "t2"], "required_fields": ["utc_offset_minutes"]})])
        steps = [clarify] if continuation else [completion([call("contract", {})]), clarify]
        return asyncio.run(investigate(EvidenceTools(workspace), ScriptedClient(steps), **(continuation or {})))
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fixture-no-network",
            "VDIR_ANTHROPIC_MODEL": "fixture-model", "VDIR_LOAD_DOTENV": "0"}), \
            patch("vdir.evaluation.evaluation.run_worker", side_effect=provider):
        app = create_app(output / "state", token="")
        with socket.socket() as reserved:
            reserved.bind(("127.0.0.1", 0))
            port = reserved.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        ready = threading.Event()
        for _ in range(100):
            if server.started:
                break
            ready.wait(0.05)
        assert server.started
        try:
            with sync_playwright() as runner:
                browser = runner.chromium.launch()
                page = browser.new_page(viewport={"width": 1440, "height": 1050})
                page.on("pageerror", lambda error: errors.append(str(error)))
                url = "http://127.0.0.1:%d" % port
                page.goto(url)
                expect(page.locator('#investigator option[value="langgraph"]')).to_be_enabled()
                page.get_by_role("button", name="New investigation", exact=True).click()
                page.select_option("#incident", "case-003")
                page.select_option("#investigator", "langgraph")
                page.get_by_role("button", name="Run investigation").click()
                expect(page.locator(".run-row")).to_have_count(1)
                assert execute(app.state.store)
                expect(page.locator(".detail-title-line .badge")).to_have_text("Awaiting guidance", timeout=20000)
                parent = app.state.store.list()[0]
                parent_version = parent["result_version"]
                expect(page.get_by_role("button", name="Approve this version")).to_have_count(0)
                note = "Continue requesting source offsets. <script>window.__injected=true</script>"
                page.get_by_label("Investigation guidance").fill(note)
                page.get_by_role("button", name="Resume investigation").click()
                expect(page.locator(".run-row")).to_have_count(2)
                child_id = app.state.store.list()[0]["id"]
                assert child_id != parent["id"]
                assert execute(app.state.store)
                expect(page.locator(".detail-title-line .badge")).to_have_text("Awaiting guidance", timeout=20000)
                child = app.state.store.get(child_id)
                assert child["result"]["response"]["model_run"]["rounds"] == 3
                assert child["result"]["grading"]["passed"]
                assert resumed_notes == [note]
                assert page.evaluate("window.__injected") is None
                assert app.state.store.get(parent["id"])["result_version"] == parent_version
                page.goto(url + "?job=" + parent["id"])
                expect(page.get_by_role("button", name="View continuation →")).to_be_visible()
                page.get_by_role("button", name="View continuation →").click()
                expect(page).to_have_url(url + "/investigations/" + child_id)
                expect(page.get_by_label("Investigation guidance")).to_be_visible()
                page.get_by_role("tab", name="Agent activity", exact=True).click()
                expect(page.get_by_role("tabpanel")).to_contain_text("No SQL precheck required")
                expect(page.locator(".workflow-timeline li")).to_have_count(len(child["result"]["response"]["agent_workflow"]["activity"]))
                expect(page.get_by_role("tabpanel")).to_contain_text("Operator guidance")
                page.screenshot(path=str(output / "desktop-paused.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.screenshot(path=str(output / "mobile-paused.png"), full_page=True)
                page.set_viewport_size({"width": 1440, "height": 1050})
                page.get_by_role("button", name="New investigation", exact=True).click()
                page.select_option("#incident", "case-001")
                page.select_option("#investigator", "langgraph")
                page.get_by_role("button", name="Run investigation").click()
                expect(page.locator(".run-row")).to_have_count(3)
                assert execute(app.state.store)
                expect(page.locator(".detail-title-line .badge")).to_have_text("Repair proposed", timeout=20000)
                proposal = app.state.store.list()[0]
                assert app.state.store.get(proposal["id"])["result"]["grading"]["passed"]
                page.get_by_role("tab", name="Agent activity", exact=True).click()
                expect(page.get_by_role("tabpanel")).to_contain_text("Public SQL precheck passed")
                page.locator(".workflow-plan summary").click()
                expect(page.locator(".workflow-plan pre")).to_have_text("SELECT product_id, COUNT(*) AS versions FROM product_versions GROUP BY product_id")
                expect(page.locator(".finding-card")).to_contain_text("Multiple versions were observed")
                page.locator(".memory-details summary").click()
                expect(page.locator(".memory-details")).to_contain_text("check_join")
                page.screenshot(path=str(output / "desktop-agent-plan.png"), full_page=True)
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.screenshot(path=str(output / "mobile-agent-plan.png"), full_page=True)
                page.get_by_role("tab", name="SQL & review", exact=True).click()
                page.get_by_label("Candidate SQL", exact=True).fill(JOIN_SQL)
                page.get_by_role("button", name="Verify candidate revision").click()
                expect(page.locator(".run-row")).to_have_count(4)
                assert execute(app.state.store)
                expect(page.locator(".detail-title-line .badge")).to_have_text("Verification failed", timeout=20000)
                expect(page.get_by_role("tab", name="Agent activity", exact=True)).to_have_count(0)
                revision = app.state.store.get(app.state.store.list()[0]["id"])
                assert "agent_workflow" not in revision["result"]["response"]
                assert not errors, errors
                browser.close()
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            assert not thread.is_alive()
    checks = ["graph selectable", "real graph paused result", "approval absent", "checkpoint continuation",
              "retained budgets", "independent verification", "immutable parent", "XSS-safe guidance",
              "continuation navigation", "mobile layout", "no page errors", "actual agent activity", "guidance stage retained",
              "planned repair workflow", "public precheck and independent grade", "rendered hypothesis SQL", "mobile plan layout", "revision removes stale agent assessment", "cited findings ledger", "bounded memory index and diagnostics"]
    (output / "result.json").write_text(json.dumps({"passed": True, "checks": checks,
        "provider": "scripted; no live model generation"}, indent=2))
    print(json.dumps({"passed": True, "output": str(output.relative_to(ROOT)), "checks": len(checks)}))


if __name__ == "__main__":
    main()
