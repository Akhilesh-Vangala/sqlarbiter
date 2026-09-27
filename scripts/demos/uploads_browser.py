"""Exercise real file selection, changed-input results and exports."""

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url")
    parser.add_argument("--output", default="artifacts/generated/uploads-browser")
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    project = "SQLArbiter"
    output = root / args.output
    output.mkdir(parents=True, exist_ok=True)
    server, log = None, None
    url = args.url
    if not url:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        environment = dict(
            os.environ,
            SQLARBITER_LOAD_DOTENV="0",
            ANTHROPIC_API_KEY="",
            SQLARBITER_DEMO_SECRET=secrets.token_urlsafe(64),
        )
        log = (output / "server.log").open("w")
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-access-log",
            ],
            cwd=root,
            env=environment,
            stdout=log,
            stderr=log,
        )
        for _ in range(200):
            try:
                if httpx.get(url + "/api/uploads/capabilities", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
        else:
            raise RuntimeError("Upload workspace did not become ready")
    errors, checks = [], []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            options = {"viewport": {"width": 1280, "height": 960}, "reduced_motion": "reduce"}
            if args.record:
                options.update(
                    record_video_dir=str(output / "video"),
                    record_video_size={"width": 1280, "height": 960},
                )
            context = browser.new_context(**options)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(url + "/uploads")
            expect(page.locator("#brand")).to_contain_text(project)
            page.screenshot(path=str(output / "upload-desktop.png"), full_page=True)
            checks.append("public-workspace-without-login")
            source = "event_id,amount,category,status\nCLIENT-17,12.34,Custom,completed\nCLIENT-17,12.34,Custom,completed\nCLIENT-18,3.21,Other,pending\n"
            page.locator("#file").set_input_files(
                {"name": "customer-export.csv", "mimeType": "text/csv", "buffer": source.encode()}
            )
            page.locator("#review-rules").click()
            expect(page.locator("#contract")).to_be_visible()
            page.locator("#review-definition").click()
            page.locator("#confirm-rules").check()
            page.locator("#analyze").click()
            expect(page.locator("#output")).to_be_visible(timeout=30000)
            expect(page.locator("#error")).to_be_hidden()
            expect(page.locator("#verification")).to_have_text("Independent checks passed")
            report = json.loads(page.locator("#evidence pre").last.text_content())
            assert report["live_ai"] is False
            assert report["summary"]["verified_total_cents"] == 1234
            assert report["summary"]["duplicate_deliveries"] == 1
            checks.append("new-customer-values-independently-verified")
            for kind in ("json", "csv"):
                with page.expect_download() as download_info:
                    page.locator("#download-" + kind).click()
                downloaded = download_info.value
                downloaded.save_as(output / ("checked-result." + kind))
                assert (output / ("checked-result." + kind)).stat().st_size > 20
            checks.append("real-json-and-csv-downloads")
            page.screenshot(path=str(output / "results-desktop.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            page.screenshot(path=str(output / "results-mobile.png"), full_page=True)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            checks.append("mobile-without-page-overflow")
            page.locator("#clear").click()
            page.locator("#confirm-clear").click()
            expect(page.locator("#output")).to_be_hidden()
            expect(page.locator("#contract")).to_be_hidden()
            assert not page.locator("#file").input_value()
            assert page.evaluate("localStorage.length") == 0
            assert page.evaluate("sessionStorage.length") == 0
            checks.append("clear-removes-source-results-and-contract")
            malicious = "id,ID\nx,1\n"
            page.locator("#file").set_input_files(
                {"name": "invalid.csv", "mimeType": "text/csv", "buffer": malicious.encode()}
            )
            expect(page.locator("#error")).to_contain_text("Duplicate column")
            checks.append("malformed-file-feedback-without-results")
            context.close()
            browser.close()
            assert not errors, errors
        (output / "report.json").write_text(
            json.dumps(
                {
                    "project": project,
                    "url": url,
                    "passed": True,
                    "checks": checks,
                    "page_errors": errors,
                },
                indent=2,
            )
            + "\n"
        )
        print(json.dumps({"project": project, "passed": True, "checks": checks}))
    finally:
        if server:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
        if log:
            log.close()


if __name__ == "__main__":
    main()
