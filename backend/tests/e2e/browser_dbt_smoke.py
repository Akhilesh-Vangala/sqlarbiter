"""Actual queued dbt builds through Chromium, no provider credentials or paid calls."""

import json
import os
import re
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright
from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[3]


def main():
    output = ROOT / "artifacts/generated" / ("browser-dbt-" + uuid.uuid4().hex[:8])
    output.mkdir()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = "http://127.0.0.1:" + str(port)
    environment = {
        **os.environ,
        "SQLARBITER_LOAD_DOTENV": "0",
        "PYTHONPATH": str(ROOT / "backend" / "src"),
    }
    for name in (
        "ANTHROPIC_API_KEY",
        "SQLARBITER_ANTHROPIC_MODEL",
        "SQLARBITER_ACCESS_TOKEN",
        "SQLARBITER_PUBLIC_ORIGIN",
    ):
        environment.pop(name, None)
    errors, checks = [], []
    with (output / "server.log").open("w") as logs:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "sqlarbiter.cli.serve",
                "--port",
                str(port),
                "--state-dir",
                str(output / "state"),
            ],
            cwd=ROOT,
            env=environment,
            stdout=logs,
            stderr=logs,
        )
        try:
            with httpx.Client(base_url=base, timeout=5) as client:
                for _ in range(100):
                    try:
                        if client.get("/healthz").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.1)
                else:
                    raise AssertionError("Server did not start")
                with sync_playwright() as runner:
                    browser = runner.chromium.launch()
                    page = browser.new_page(viewport={"width": 1440, "height": 1000})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(base + "/dbt")
                    expect(page.locator("#dbt-view")).to_be_visible()
                    expect(page.locator(".dbt-project-card")).to_have_count(1)
                    page.get_by_role("button", name="Investigate project", exact=True).click()
                    expect(page).to_have_url(base + "/dbt/new")
                    expect(
                        page.locator("#dbt-investigator option[value=langgraph]")
                    ).to_be_disabled()
                    page.reload()
                    expect(page.get_by_label("Project", exact=True)).to_have_value(
                        "payment-revenue"
                    )
                    checks.extend(
                        [
                            "project catalog",
                            "setup deep link reload",
                            "hosted methods disabled without key",
                        ]
                    )
                    page.get_by_role(
                        "button", name="Start project investigation", exact=True
                    ).click()
                    expect(page).to_have_url(
                        re.compile(re.escape(base) + r"/dbt/runs/[a-f0-9]{32}$")
                    )
                    identity = page.url.rsplit("/", 1)[1]
                    expect(page.locator("#dbt-progress-status")).to_contain_text(
                        "reporting incident", timeout=20000
                    )
                    expect(page.locator("#dbt-model-checks tbody tr")).to_have_count(
                        20, timeout=120000
                    )
                    expect(page.locator("#dbt-patch-diff")).to_contain_text(
                        "models/int_payment_events.sql"
                    )
                    expect(
                        page.get_by_role("button", name="Approve verified patch", exact=True)
                    ).to_be_enabled()
                    page.screenshot(path=str(output / "desktop-dbt-run.png"), full_page=True)
                    job = client.get("/api/jobs/" + identity).json()
                    assert job["status"] == "completed" and job["result"]["grading"]["passed"]
                    assert len(job["result"]["dbt"]["verification"]) == 5
                    assert (
                        len([event for event in job["events"] if event["name"] == "dbt_progress"])
                        >= 10
                    )
                    checks.extend(
                        [
                            "actual queued dbt build",
                            "actual progress events",
                            "five fixture twenty model checks",
                            "verified patch visible",
                        ]
                    )
                    page.reload()
                    expect(page.locator("#dbt-model-checks tbody tr")).to_have_count(20)
                    with page.expect_download() as download:
                        page.get_by_role(
                            "button", name="Download verified patch", exact=True
                        ).click()
                    saved = output / "repair.patch"
                    download.value.save_as(saved)
                    assert saved.read_text() == job["result"]["patch"]
                    checks.extend(["completed deep link reload", "exact verified patch download"])
                    false_fix = "SELECT MIN(event_id) AS event_id, customer_id, occurred_at, status, amount_cents FROM stg_payment_deliveries GROUP BY customer_id, occurred_at, status, amount_cents"
                    page.get_by_label("dbt candidate SQL", exact=True).fill(false_fix)
                    expect(
                        page.get_by_role("button", name="Approve verified patch", exact=True)
                    ).to_be_disabled()
                    page.get_by_role("button", name="Verify SQL revision", exact=True).click()
                    expect(page).not_to_have_url(base + "/dbt/runs/" + identity)
                    revision_id = page.url.rsplit("/", 1)[1]
                    expect(page.locator("#dbt-detail")).to_contain_text(
                        "Verification did not pass", timeout=120000
                    )
                    expect(
                        page.get_by_role("button", name="Approve verified patch", exact=True)
                    ).to_be_disabled()
                    expect(
                        page.get_by_role("button", name="Download verified patch", exact=True)
                    ).to_be_disabled()
                    assert client.get("/api/dbt/runs/" + revision_id + "/patch").status_code == 409
                    page.get_by_role(
                        "link", name="Open original investigation", exact=False
                    ).click()
                    expect(page.locator("#dbt-model-checks tbody tr")).to_have_count(20)
                    original = client.get("/api/jobs/" + identity).json()
                    assert original["result_version"] == job["result_version"]
                    checks.extend(
                        [
                            "editing blocks approval",
                            "revision is independent job",
                            "false fix rejected by real verification",
                            "failed patch download blocked",
                            "original result preserved",
                        ]
                    )
                    page.get_by_label("dbt review note", exact=True).fill(
                        "Browser integration review; synthetic test only"
                    )
                    page.get_by_role("button", name="Approve verified patch", exact=True).click()
                    expect(page.locator("#dbt-review-status")).to_contain_text("approved")
                    page.reload()
                    expect(page.locator("#dbt-review-status")).to_contain_text("approved")
                    approved = client.get("/api/jobs/" + identity).json()
                    assert approved["review"]["version"] == job["result_version"]
                    checks.extend(["exact version review", "immutable review survives reload"])
                    page.get_by_role("button", name="Back to dbt projects", exact=False).click()
                    expect(page).to_have_url(base + "/dbt")
                    expect(page.locator("#dbt-run-list .home-run")).to_have_count(2)
                    page.goto(base + "/runs")
                    page.get_by_role("button", name="Payment revenue", exact=False).first.click()
                    expect(page).to_have_url(
                        re.compile(re.escape(base) + r"/dbt/runs/[a-f0-9]{32}$")
                    )
                    checks.extend(
                        [
                            "contextual back to project history",
                            "global history opens correct project page",
                        ]
                    )
                    for width in (320, 390, 768, 1440):
                        page.set_viewport_size({"width": width, "height": 1000})
                        for route in ("/dbt", "/dbt/new", "/dbt/runs/" + identity):
                            page.goto(base + route)
                            if route.endswith(identity):
                                expect(page.locator("#dbt-model-checks tbody tr")).to_have_count(20)
                            assert page.evaluate(
                                "document.documentElement.scrollWidth <= innerWidth"
                            ), (width, route)
                            bad = page.evaluate(
                                """() => [...document.querySelectorAll('body *')].filter(e=>e.getClientRects().length).flatMap(e=>['color','backgroundColor','borderTopColor'].map(p=>getComputedStyle(e)[p])).filter(c=>{const v=c.match(/[\\d.]+/g);return v&&v.length>=3&&(v[0]!==v[1]||v[1]!==v[2]);})"""
                            )
                            assert not bad, (width, route, bad[:3])
                        checks.append("responsive project routes " + str(width))
                    page.set_viewport_size({"width": 390, "height": 1000})
                    page.screenshot(path=str(output / "mobile-dbt-run.png"), full_page=True)
                    page.goto(base + "/dbt/new")
                    page.get_by_role(
                        "button", name="Start project investigation", exact=True
                    ).click()
                    expect(
                        page.get_by_role("button", name="Cancel project run", exact=True)
                    ).to_be_visible()
                    cancelled_id = page.url.rsplit("/", 1)[1]
                    page.get_by_role("button", name="Cancel project run", exact=True).click()
                    page.get_by_role("button", name="Confirm cancellation", exact=True).click()
                    expect(page.locator("#dbt-detail .detail-title-line .badge")).to_have_text(
                        "Cancelled", timeout=15000
                    )
                    cancelled = client.get("/api/jobs/" + cancelled_id).json()
                    assert cancelled["result"] is None
                    checks.append("queued or running cancellation publishes no result")
                    assert not errors, errors
                    checks.append("no browser runtime errors")
                    browser.close()
        finally:
            process.terminate()
            process.wait(timeout=15)
    (output / "result.json").write_text(
        json.dumps(
            {
                "passed": True,
                "checks": checks,
                "provider": "none; actual local dbt execution",
                "live_model_generation": False,
            },
            indent=2,
        )
    )
    print(
        json.dumps({"passed": True, "checks": len(checks), "output": str(output.relative_to(ROOT))})
    )


if __name__ == "__main__":
    main()
