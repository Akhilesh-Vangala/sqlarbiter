"""Trusted single-host spend admission. Unknown requests retain their reservation.

Integer microdollars avoid float rounding. This is estimated usage accounting, not
an invoice cap, and it cannot constrain calls made outside this application.
"""

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from decimal import Decimal
from decimal import InvalidOperation
from decimal import ROUND_CEILING
from pathlib import Path


class SpendRejected(ValueError):
    pass


def dollars(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number <= 0 or number > 10000:
            raise ValueError
        micros = number * 1000000
        if micros != micros.to_integral_value():
            raise ValueError
        return int(micros)
    except (InvalidOperation, ValueError):
        raise SpendRejected(
            "Spend limits must be positive USD amounts with at most six decimals"
        ) from None


def configuration(state_dir=None):
    project = Path(__file__).resolve().parents[4]
    state = Path(
        state_dir or os.getenv("SQLARBITER_STATE_DIR", project / "artifacts/generated/app")
    ).resolve()
    return {
        "SQLARBITER_SPEND_LEDGER": str(
            Path(os.getenv("SQLARBITER_SPEND_LEDGER", state / "spend.sqlite")).resolve()
        ),
        "SQLARBITER_PRICE_PROFILE": str(
            Path(
                os.getenv(
                    "SQLARBITER_PRICE_PROFILE",
                    project / "backend/data/pricing/claude-sonnet-5-5.json",
                )
            ).resolve()
        ),
        "SQLARBITER_RUN_BUDGET_USD": os.getenv("SQLARBITER_RUN_BUDGET_USD", "1"),
        "SQLARBITER_TOTAL_BUDGET_USD": os.getenv("SQLARBITER_TOTAL_BUDGET_USD", "5"),
    }


class SpendLedger:
    def __init__(self, path, pricing, run_limit="1", total_limit="5"):
        required = (
            "input_per_million",
            "output_per_million",
            "cache_write_per_million",
            "cache_read_per_million",
        )
        try:
            if (
                not isinstance(pricing.get("model"), str)
                or not pricing["model"]
                or not pricing.get("verified_at")
                or not pricing.get("source_url")
            ):
                raise ValueError
            self.rates = {key: Decimal(str(pricing[key])) for key in required}
            if any(not rate.is_finite() or rate < 0 for rate in self.rates.values()):
                raise ValueError
        except (KeyError, AttributeError, ValueError, InvalidOperation):
            raise SpendRejected("A complete verified model pricing profile is required") from None
        self.path = Path(path)
        self.pricing = pricing
        self.run_limit, self.total_limit = dollars(run_limit), dollars(total_limit)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        policy = json.dumps(
            {"pricing": pricing, "run_limit": self.run_limit, "total_limit": self.total_limit},
            sort_keys=True,
        )
        with self.transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS policy (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, run_id TEXT NOT NULL, model TEXT NOT NULL, reserved INTEGER NOT NULL, actual INTEGER, status TEXT NOT NULL, usage TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP)"
            )
            row = db.execute("SELECT value FROM policy WHERE id=1").fetchone()
            if row and row[0] != policy:
                raise SpendRejected(
                    "Ledger policy changed; preserve this ledger and explicitly configure a new budget ledger"
                )
            db.execute("INSERT OR IGNORE INTO policy VALUES (1,?)", (policy,))

    @classmethod
    def from_environment(cls):
        try:
            return cls(
                os.environ["SQLARBITER_SPEND_LEDGER"],
                json.loads(Path(os.environ["SQLARBITER_PRICE_PROFILE"]).read_text()),
                os.environ["SQLARBITER_RUN_BUDGET_USD"],
                os.environ["SQLARBITER_TOTAL_BUDGET_USD"],
            )
        except (KeyError, OSError, ValueError) as error:
            if isinstance(error, SpendRejected):
                raise
            raise SpendRejected(
                "Configure the trusted spend ledger and pricing profile before live calls"
            ) from None

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            db.execute("PRAGMA busy_timeout=15000")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def cost(self, usage):
        fields = {
            "input_tokens": "input_per_million",
            "output_tokens": "output_per_million",
            "cache_creation_input_tokens": "cache_write_per_million",
            "cache_read_input_tokens": "cache_read_per_million",
        }
        if not isinstance(usage, dict) or any(
            type(usage.get(key)) is not int or usage[key] < 0
            for key in ("input_tokens", "output_tokens")
        ):
            raise SpendRejected("Provider usage is incomplete; reservation retained")
        amount = Decimal(0)
        for field, rate in fields.items():
            value = usage.get(field, 0)
            if type(value) is not int or value < 0:
                raise SpendRejected("Provider usage is invalid; reservation retained")
            amount += value * self.rates[rate]
        return int(amount.to_integral_value(rounding=ROUND_CEILING))

    def reserve(self, run_id, model, input_tokens, max_output):
        if not isinstance(run_id, str) or not run_id or len(run_id) > 128:
            raise SpendRejected("A bounded execution identifier is required")
        if model != self.pricing["model"]:
            raise SpendRejected("Resolved model does not match the verified pricing profile")
        if (
            any(type(value) is not int or value < 0 for value in (input_tokens, max_output))
            or max_output == 0
        ):
            raise SpendRejected("Invalid request token allowance")
        # Reserve at the highest input/cache rate. The client sends no cache controls.
        amount = int(
            (
                input_tokens
                * max(
                    self.rates[key]
                    for key in (
                        "input_per_million",
                        "cache_write_per_million",
                        "cache_read_per_million",
                    )
                )
                + max_output * self.rates["output_per_million"]
            ).to_integral_value(rounding=ROUND_CEILING)
        )
        identity = uuid.uuid4().hex
        with self.transaction() as db:
            if db.execute(
                "SELECT 1 FROM requests WHERE status IN ('overrun','unknown') LIMIT 1"
            ).fetchone():
                raise SpendRejected("Uncertain or overrun provider usage blocks further generation")
            total = db.execute(
                "SELECT COALESCE(SUM(COALESCE(actual,reserved)),0) FROM requests"
            ).fetchone()[0]
            run = db.execute(
                "SELECT COALESCE(SUM(COALESCE(actual,reserved)),0) FROM requests WHERE run_id=?",
                (run_id,),
            ).fetchone()[0]
            if total + amount > self.total_limit or run + amount > self.run_limit:
                raise SpendRejected("API spend allowance exhausted before generation")
            db.execute(
                "INSERT INTO requests (id,run_id,model,reserved,status) VALUES (?,?,?,?,'reserved')",
                (identity, run_id, model, amount),
            )
        return identity

    def settle(self, identity, usage):
        amount = self.cost(usage)
        with self.transaction() as db:
            row = db.execute(
                "SELECT status,actual,reserved FROM requests WHERE id=?", (identity,)
            ).fetchone()
            if not row or row[0] != "reserved":
                raise SpendRejected("Spend receipt already finalized or unknown")
            # Unexpected usage is still accounted in full, then blocks further calls.
            status = "overrun" if amount > row[2] else "settled"
            db.execute(
                "UPDATE requests SET actual=?,status=?,usage=? WHERE id=?",
                (amount, status, json.dumps(usage, sort_keys=True), identity),
            )
        if status == "overrun":
            raise SpendRejected(
                "Provider usage exceeded the reservation; further generation is blocked"
            )
        return amount

    def uncertain(self, identity):
        with self.transaction() as db:
            db.execute(
                "UPDATE requests SET status='unknown' WHERE id=? AND status='reserved'", (identity,)
            )

    def summary(self):
        with self.transaction() as db:
            rows = db.execute(
                "SELECT status,COUNT(*),SUM(COALESCE(actual,reserved)) FROM requests GROUP BY status"
            ).fetchall()
        totals = {
            status: {"requests": count, "usd": amount / 1000000} for status, count, amount in rows
        }
        charged = sum(value["usd"] for value in totals.values())
        return {
            "model": self.pricing["model"],
            "pricing_verified_at": self.pricing["verified_at"],
            "run_limit_usd": self.run_limit / 1000000,
            "total_limit_usd": self.total_limit / 1000000,
            "accounted_usd": charged,
            "remaining_usd": max(0, self.total_limit / 1000000 - charged),
            "states": totals,
            "admission_blocked": bool({"overrun", "unknown"}.intersection(totals)),
            "scope": "Estimated application usage; unresolved reservations retained; not a provider invoice cap",
        }
