"""Real-browser workflow on a private ephemeral server, without model credentials."""

import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from urllib.parse import urlparse
from pathlib import Path

from playwright.sync_api import sync_playwright
from playwright.sync_api import expect
from sqlarbiter.domain.cases import JOIN_SQL

ROOT = Path(__file__).resolve().parents[3]


def main():
    output = ROOT / "artifacts" / "generated" / ("browser-smoke-" + uuid.uuid4().hex[:8])
    output.mkdir(parents=True)
    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        port = connection.getsockname()[1]
    environment = os.environ.copy()
    environment["SQLARBITER_LOAD_DOTENV"] = "0"
    for name in (
        "ANTHROPIC_API_KEY",
        "SQLARBITER_ANTHROPIC_MODEL",
        "SQLARBITER_ACCESS_TOKEN",
        "SQLARBITER_PUBLIC_ORIGIN",
    ):
        environment.pop(name, None)
    environment["PYTHONPATH"] = str(ROOT / "backend" / "src")
    url = "http://127.0.0.1:%d" % port
    errors = []
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
            cwd=str(ROOT),
            env=environment,
            stdout=logs,
            stderr=logs,
        )
        try:
            for _ in range(100):
                try:
                    urllib.request.urlopen(url + "/healthz", timeout=1).close()
                    break
                except OSError:
                    time.sleep(0.1)
            else:
                raise AssertionError("Smoke server did not start")
            with sync_playwright() as runner:
                browser = runner.chromium.launch()
                page = browser.new_page(
                    viewport={"width": 1440, "height": 1050}, device_scale_factor=1
                )
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(url)
                expect(page.locator("#incident option")).to_have_count(6)
                expect(page.locator("#home-view")).to_be_visible()
                expect(page.locator(".scenario-card")).to_have_count(6)
                expect(page.locator("#investigations-view")).not_to_be_visible()
                page.screenshot(path=str(output / "desktop-empty.png"), full_page=True)
                page.get_by_role("button", name="New investigation", exact=True).click()
                expect(page.locator("#new-investigation-view")).to_be_visible()
                page.get_by_role("button", name="Cancel", exact=True).click()
                expect(page.locator("#home-view")).to_be_visible()
                page.get_by_role("button", name="New investigation", exact=True).click()
                page.screenshot(path=str(output / "desktop-new-run.png"), full_page=True)
                page.select_option("#incident", "case-001")
                page.get_by_role("button", name="Run investigation").click()
                expect(page.locator(".detail-title-line .badge")).to_have_text(
                    "Repair proposed", timeout=20000
                )
                expect(page.locator("#new-investigation-view")).not_to_be_visible()
                original_url = page.url
                assert urlparse(original_url).path.startswith("/investigations/")
                expect(page.locator("#detail-view")).to_be_visible()
                expect(page.locator("#home-view")).not_to_be_visible()
                page.get_by_role("button", name="Open evidence explorer", exact=True).click()
                expect(page.get_by_role("dialog", name="Evidence explorer")).to_be_visible()
                expect(page.locator("#inspector-content details.evidence-item")).to_have_count(8)
                page.screenshot(path=str(output / "desktop-evidence-drawer.png"), full_page=True)
                page.keyboard.press("Escape")
                expect(
                    page.get_by_role("button", name="Open evidence explorer", exact=True)
                ).to_be_focused()
                page.get_by_role("button", name="Run details & audit", exact=True).click()
                expect(page.locator("#inspector-content")).to_contain_text("completed")
                page.get_by_role("button", name="Close detail panel", exact=True).click()
                page.get_by_role("button", name="Back to home", exact=False).click()
                expect(page.locator("#home-view")).to_be_visible()
                expect(page.locator(".home-run")).to_have_count(1)
                expect(page.locator("#completed-count")).to_have_text("1")
                page.screenshot(path=str(output / "desktop-home.png"), full_page=True)
                page.locator(".home-run").click()
                expect(page).to_have_url(original_url)
                page.go_back()
                expect(page.locator("#home-view")).to_be_visible()
                page.go_forward()
                expect(page.locator("#detail-view")).to_be_visible()
                page.get_by_role("tab", name="Evidence", exact=True).click()
                expect(page.locator("#detail details.evidence-item")).to_have_count(8)
                page.locator("#detail details.evidence-item").last.locator("summary").click()
                expect(page.locator("#detail details.evidence-item[open] table")).to_be_visible()
                page.get_by_role("tab", name="SQL & review", exact=True).click()
                expect(page.locator(".sql-comparison .sql-block")).to_be_visible()
                expect(page.get_by_label("Candidate SQL")).to_be_visible()
                page.screenshot(path=str(output / "desktop-sql-comparison.png"), full_page=True)
                approve = page.get_by_role("button", name="Approve this version")
                expect(approve).to_be_enabled()
                page.get_by_label("Candidate SQL", exact=True).fill(JOIN_SQL)
                expect(approve).to_be_disabled()
                page.wait_for_timeout(1800)
                expect(page.get_by_label("Candidate SQL")).to_have_value(JOIN_SQL)
                expect(page.get_by_label("Candidate SQL")).to_be_focused()
                page.get_by_role("button", name="Verify candidate revision").click()
                expect(page.locator(".detail-title-line .badge")).to_have_text(
                    "Verification failed", timeout=20000
                )
                page.get_by_role("tab", name="SQL & review", exact=True).click()
                expect(page.get_by_role("button", name="Approve this version")).to_be_disabled()
                page.goto(original_url)
                expect(page.locator(".detail-title-line .badge")).to_have_text("Repair proposed")
                page.get_by_role("tab", name="SQL & review", exact=True).click()
                page.get_by_label("Review note", exact=True).fill(
                    "Browser check: <script>window.__injected=true</script>"
                )
                page.get_by_role("button", name="Approve this version").click()
                expect(page.locator(".reviewed")).to_contain_text("Review approved")
                assert page.evaluate("window.__injected") is None, "Review content executed as code"
                page.get_by_role("tab", name="Summary", exact=True).click()
                with page.expect_download() as download:
                    page.get_by_role("button", name="Export report").click()
                download.value.save_as(str(output / "downloaded-report.json"))
                report = json.loads((output / "downloaded-report.json").read_text())
                assert report["review"]["action"] == "approved"
                page.screenshot(path=str(output / "desktop-result.png"), full_page=True)
                page.get_by_role("button", name="New investigation", exact=True).click()
                page.select_option("#incident", "case-003")
                page.select_option("#engine", "sqlite")
                page.get_by_role("button", name="Run investigation").click()
                expect(page.locator(".detail-title-line .badge")).to_have_text(
                    "Needs information", timeout=20000
                )
                expect(page.locator(".outcome-card")).to_contain_text("t1, t2")
                expect(page.locator(".detail-meta")).to_contain_text("SQLite")
                report_request = page.evaluate(
                    "async () => (await (await fetch('/api/jobs/' + location.pathname.split('/').at(-1))).json()).request"
                )
                assert report_request["engine"] == "sqlite"
                page.get_by_role("button", name="New investigation", exact=True).click()
                page.select_option("#incident", "case-005")
                page.select_option("#engine", "duckdb")
                page.get_by_role("button", name="Run investigation").click()
                expect(page.locator(".detail-title-line .badge")).to_have_text(
                    "No change", timeout=20000
                )
                page.reload()
                expect(page.locator(".detail-title-line .badge")).to_have_text("No change")
                page.get_by_role("navigation", name="Workspace navigation").get_by_role(
                    "link", name="Investigations", exact=True
                ).click()
                expect(page.locator("#investigations-view")).to_be_visible()
                page.get_by_label("Filter investigation status").select_option("failed")
                expect(page.locator(".run-row")).to_have_count(1)
                expect(page.locator(".run-row")).to_contain_text("Verification failed")
                page.get_by_label("Search investigations").fill("no-such-incident")
                expect(page.locator(".empty-history")).to_have_text("No runs match these filters.")
                page.get_by_label("Filter investigation status").select_option("all")
                page.get_by_label("Search investigations").fill("")
                expect(page.locator(".run-row")).to_have_count(4)
                page.get_by_role("navigation", name="Workspace navigation").get_by_role(
                    "link", name="Run history", exact=True
                ).click()
                expect(page.locator("#runs-view")).to_be_visible()
                expect(page.locator("#investigations-view")).not_to_be_visible()
                expect(page.locator(".runs-table tbody tr")).to_have_count(4)
                original_id = urlparse(original_url).path.rsplit("/", 1)[1]
                page.get_by_label("Search run history").fill(original_id[:8])
                expect(page.locator(".runs-table tbody tr")).to_have_count(1)
                page.screenshot(path=str(output / "desktop-history.png"), full_page=True)
                page.reload()
                expect(page.locator("#runs-view")).to_be_visible()
                page.get_by_label("Search run history").fill(original_id[:8])
                page.locator(".run-link").click()
                expect(page.locator("#detail-view")).to_be_visible()
                expect(page).to_have_url(original_url)
                expect(
                    page.get_by_role("button", name="Back to run history", exact=False)
                ).to_be_visible()
                page.get_by_role("button", name="Search workspace", exact=True).click()
                page.get_by_label("Find an investigation or page").fill("no-such-run")
                expect(page.locator("#command-results")).to_contain_text(
                    "No matching pages or recent runs."
                )
                page.get_by_label("Find an investigation or page").fill(original_id[:8])
                expect(page.locator(".command-result")).to_have_count(1)
                page.keyboard.press("Tab")
                page.keyboard.press("Enter")
                expect(page.locator("#command-dialog")).not_to_be_visible()
                expect(page).to_have_url(original_url)
                page.get_by_role("tab", name="Summary", exact=True).focus()
                page.keyboard.press("End")
                expect(
                    page.get_by_role("tab", name="Metric definition", exact=True)
                ).to_be_focused()
                expect(page.get_by_role("tabpanel")).to_contain_text(
                    "AUTHORITATIVE METRIC CONTRACT"
                )
                page.keyboard.press("Home")
                expect(page.get_by_role("tab", name="Summary", exact=True)).to_be_focused()
                page.set_viewport_size({"width": 390, "height": 844})
                page.screenshot(path=str(output / "mobile-result.png"), full_page=True)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                    "Mobile layout overflows"
                )
                page.get_by_role("button", name="Run details & audit", exact=True).click()
                expect(page.locator("#inspector-dialog")).to_be_visible()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                    "Mobile drawer overflows"
                )
                page.screenshot(path=str(output / "mobile-audit-drawer.png"), full_page=True)
                page.keyboard.press("Escape")
                page.get_by_role("navigation", name="Workspace navigation").get_by_role(
                    "link", name="Run history", exact=True
                ).click()
                expect(page.locator("#runs-view")).to_be_visible()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                    "Mobile history overflows"
                )
                page.get_by_role("button", name="New investigation", exact=True).click()
                expect(page.locator("#new-investigation-view")).to_be_visible()
                page.screenshot(path=str(output / "mobile-new-run.png"), full_page=True)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                    "Mobile dialog overflows"
                )
                page.get_by_role("button", name="Cancel", exact=True).click()
                for width in (320, 768, 1024, 1440):
                    page.set_viewport_size({"width": width, "height": 900})
                    page.get_by_role("link", name="Home", exact=True).click()
                    expect(page.locator("#home-view")).to_be_visible()
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                        f"Home overflows at {width}"
                    )
                    bad_colors = page.evaluate(
                        """() => [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().width && e.getBoundingClientRect().height).flatMap(e => ['color','backgroundColor','borderTopColor'].map(p => getComputedStyle(e)[p])).filter(c => { const v = c.match(/[\\d.]+/g); return v && v.length >= 3 && (v[0] !== v[1] || v[1] !== v[2]); })"""
                    )
                    assert not bad_colors, bad_colors[:5]
                page.goto(url + "/investigations/" + "0" * 32)
                expect(
                    page.get_by_role("heading", name="Unable to load investigation")
                ).to_be_visible()
                page.get_by_role("button", name="Back to investigations", exact=False).click()
                expect(page.locator("#investigations-view")).to_be_visible()
                assert not errors, errors
                browser.close()
            result = {
                "passed": True,
                "checks": [
                    "investigation",
                    "evidence table",
                    "edited SQL approval blocked",
                    "failed revision",
                    "version-bound review",
                    "XSS-safe notes",
                    "report export",
                    "clarification",
                    "healthy no-change",
                    "reload persistence",
                    "mobile layout",
                    "no page errors",
                    "setup page cancel and return",
                    "current/candidate SQL comparison",
                    "draft preserved across polling",
                    "selected analytical engine submitted",
                    "queue filter and empty state",
                    "searchable history navigation and reload",
                    "keyboard tabs",
                    "mobile history and investigation setup page",
                    "home scenarios and actual totals",
                    "dedicated investigation route and reload",
                    "contextual back navigation",
                    "browser back and forward",
                    "evidence drawer and restored focus",
                    "run audit drawer",
                    "keyboard workspace search and empty state",
                    "mobile drawer",
                    "home responsiveness and neutral palette",
                    "missing run error and recovery",
                ],
            }
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            logs.flush()
            text = (output / "server.log").read_text()
            match = re.search(r"Queue worker started \[(\d+)\]", text)
            assert match, "Launcher did not report a worker"
            worker_pid = int(match.group(1))
            for _ in range(30):
                try:
                    os.kill(worker_pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.1)
            else:
                os.kill(worker_pid, 15)
                raise AssertionError("Launcher shutdown left its queue worker alive")
    result["checks"].append("launcher shutdown reaps worker")
    (output / "result.json").write_text(json.dumps(result, indent=2))
    print(
        json.dumps(
            {
                "passed": True,
                "output": str(output.relative_to(ROOT)),
                "checks": len(result["checks"]),
            }
        )
    )


if __name__ == "__main__":
    main()
