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
from pathlib import Path

from playwright.sync_api import sync_playwright, expect
from vdir.cases import JOIN_SQL

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / "artifacts" / "generated" / ("browser-smoke-" + uuid.uuid4().hex[:8])
    output.mkdir(parents=True)
    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        port = connection.getsockname()[1]
    environment = os.environ.copy()
    environment["VDIR_LOAD_DOTENV"] = "0"
    for name in ("ANTHROPIC_API_KEY", "VDIR_ANTHROPIC_MODEL", "VDIR_ACCESS_TOKEN", "VDIR_PUBLIC_ORIGIN"):
        environment.pop(name, None)
    environment["PYTHONPATH"] = str(ROOT / "src")
    url = "http://127.0.0.1:%d" % port
    errors = []
    with (output / "server.log").open("w") as logs:
        process = subprocess.Popen([sys.executable, "-m", "vdir.serve", "--port", str(port),
                                    "--state-dir", str(output / "state")], cwd=str(ROOT),
                                   env=environment, stdout=logs, stderr=logs)
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
                page = browser.new_page(viewport={"width": 1440, "height": 1050}, device_scale_factor=1)
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(url)
                expect(page.locator("#incident option")).to_have_count(6)
                page.screenshot(path=str(output / "desktop-empty.png"), full_page=True)
                page.select_option("#incident", "case-001")
                page.get_by_role("button", name="Run investigation").click()
                expect(page.locator(".detail-title-line .badge")).to_have_text("Repair proposed", timeout=20000)
                original_url = page.url
                page.get_by_role("tab", name="Evidence", exact=True).click()
                expect(page.locator("details.evidence-item")).to_have_count(8)
                page.locator("details.evidence-item").last.locator("summary").click()
                expect(page.locator("details.evidence-item[open] table")).to_be_visible()
                page.get_by_role("tab", name="SQL & review", exact=True).click()
                approve = page.get_by_role("button", name="Approve this version")
                expect(approve).to_be_enabled()
                page.get_by_label("Candidate SQL", exact=True).fill(JOIN_SQL)
                expect(approve).to_be_disabled()
                page.get_by_role("button", name="Verify candidate revision").click()
                expect(page.locator(".detail-title-line .badge")).to_have_text("Verification failed", timeout=20000)
                page.get_by_role("tab", name="SQL & review", exact=True).click()
                expect(page.get_by_role("button", name="Approve this version")).to_be_disabled()
                page.goto(original_url)
                expect(page.locator(".detail-title-line .badge")).to_have_text("Repair proposed")
                page.get_by_role("tab", name="SQL & review", exact=True).click()
                page.get_by_label("Review note", exact=True).fill("Browser check: <script>window.__injected=true</script>")
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
                page.select_option("#incident", "case-003")
                page.get_by_role("button", name="Run investigation").click()
                expect(page.locator(".detail-title-line .badge")).to_have_text("Needs information", timeout=20000)
                expect(page.locator(".outcome-card")).to_contain_text("t1, t2")
                page.select_option("#incident", "case-005")
                page.get_by_role("button", name="Run investigation").click()
                expect(page.locator(".detail-title-line .badge")).to_have_text("No change", timeout=20000)
                page.reload()
                expect(page.locator(".detail-title-line .badge")).to_have_text("No change")
                page.set_viewport_size({"width": 390, "height": 844})
                page.screenshot(path=str(output / "mobile-result.png"), full_page=True)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Mobile layout overflows"
                assert not errors, errors
                browser.close()
            result = {"passed": True, "checks": ["investigation", "evidence table", "edited SQL approval blocked",
                "failed revision", "version-bound review", "XSS-safe notes", "report export",
                "clarification", "healthy no-change", "reload persistence", "mobile layout", "no page errors"]}
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
    print(json.dumps({"passed": True, "output": str(output.relative_to(ROOT)), "checks": len(result["checks"])}))


if __name__ == "__main__":
    main()
