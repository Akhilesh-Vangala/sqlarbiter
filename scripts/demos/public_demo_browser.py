"""Exercise the real public app; optionally retain a continuous WebM recording."""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time

import httpx
from playwright.sync_api import sync_playwright
from playwright.sync_api import expect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url")
    parser.add_argument("--output", default="artifacts/generated/public-demo-browser")
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--publish-assets", action="store_true")
    args = parser.parse_args()
    if args.publish_assets and not args.record:
        parser.error("Publishing demo media requires --record")
    root = Path(__file__).resolve().parents[2]
    relay = (root / "backend/src/relayops").is_dir()
    package = "relayops" if relay else "vdir"
    name = "RelayOps" if relay else "VerifyOps"
    output = root / args.output
    output.mkdir(parents=True, exist_ok=True)
    assets = root / "frontend/apps/demo"
    server, log = None, None
    url = args.url
    if not url:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        url = "http://127.0.0.1:" + str(port)
        environment = dict(
            os.environ, VDIR_LOAD_DOTENV="0", RELAY_ALLOW_LIVE="0", ANTHROPIC_API_KEY=""
        )
        environment["RELAY_DEMO_SECRET" if relay else "VDIR_DEMO_SECRET"] = secrets.token_urlsafe(
            48
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
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                if httpx.get(url + "/healthz", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
        else:
            raise RuntimeError("Demo server did not become ready")
    frames, errors = [], []
    player_verified = False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            options = {"viewport": {"width": 1180, "height": 844}}
            if args.record:
                options.update(
                    record_video_dir=str(output / "raw-video"),
                    record_video_size={"width": 1180, "height": 844},
                )
            context = browser.new_context(**options)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            decoder = browser.new_page(viewport={"width": 1180, "height": 844})

            def capture(stage, selector=None):
                if selector:
                    page.locator(selector).first.scroll_into_view_if_needed()
                page.evaluate("document.activeElement?.blur()")
                page.wait_for_timeout(150)
                path = output / (str(len(frames)).zfill(2) + "-" + stage + ".png")
                pixels = page.screenshot(path=str(path))
                frames.append(
                    {
                        "stage": stage,
                        "path": path.name,
                        "sha256": hashlib.sha256(pixels).hexdigest(),
                    }
                )
                if args.record:
                    rgba = decoder.evaluate(
                        """async source => { const image=new Image();image.src='data:image/png;base64,'+source;await image.decode();const canvas=document.createElement('canvas');canvas.width=image.width;canvas.height=image.height;canvas.getContext('2d').drawImage(image,0,0);const data=canvas.getContext('2d').getImageData(0,0,image.width,image.height).data;let value='';for(let i=0;i<data.length;i+=8192)value+=String.fromCharCode(...data.subarray(i,i+8192));return btoa(value); }""",
                        base64.b64encode(pixels).decode(),
                    )
                    (output / (str(len(frames) - 1).zfill(2) + ".rgba")).write_bytes(
                        base64.b64decode(rgba)
                    )
                    page.wait_for_timeout(1000)

            page.goto(url + "/demo")
            page.get_by_role("heading", name="Start a working investigation").wait_for()
            page.get_by_label("Choose a synthetic case").select_option(
                "short-shipment" if relay else "case-002"
            )
            capture("choose-case")
            with page.expect_response(
                lambda r: r.url.endswith("/api/demo/investigate") and r.request.method == "POST",
                timeout=60000,
            ) as response:
                page.get_by_role("button", name="Investigate case").click()
            initial = response.value.json()
            assert response.value.status == 200, initial
            page.get_by_role("button", name="Download report").wait_for()
            assert initial["simulation"]["passed"] if relay else initial["grading"]["passed"]
            capture("checked-proposal")
            page.get_by_role("button", name="Source evidence", exact=True).click()
            expect(page.locator(".result-card details")).to_have_count(
                4 if relay else len([e for e in initial["evidence"] if e["ok"]])
            )
            capture("executed-evidence", ".result-card")
            if relay:
                page.get_by_role("button", name="Proposal + action", exact=True).click()
                page.get_by_role("button", name="Approve sandbox proposal").click()
                page.get_by_role("button", name="Test lost acknowledgment").wait_for()
                with page.expect_response(
                    lambda r: r.url.endswith("/api/demo/execute") and r.request.method == "POST"
                ) as response:
                    page.get_by_role("button", name="Test lost acknowledgment").click()
                uncertain = response.value.json()
                assert (
                    uncertain["stage"] == "uncertain"
                    and uncertain["receipts"][0]["status"] == "unknown"
                )
                page.get_by_role("button", name="Reconcile and complete").wait_for()
                capture("uncertain-action", ".result-card")
                with page.expect_response(
                    lambda r: r.url.endswith("/api/demo/reconcile") and r.request.method == "POST"
                ) as response:
                    page.get_by_role("button", name="Reconcile and complete").click()
                final = response.value.json()
                assert (
                    final["stage"] == "executed"
                    and final["execution"]["passed"]
                    and final["execution"]["reconciled_receipts"] == 1
                )
                assert len(final["receipts"]) == 4 and all(
                    r["status"] == "confirmed" for r in final["receipts"]
                )
                page.get_by_role("button", name="Verification", exact=True).click()
                expect(page.locator(".result-card .check-row")).to_have_count(24)
                capture("verified-effects", ".result-card")
                page.get_by_role("button", name="Proposal + action", exact=True).click()
            else:
                page.get_by_role("button", name="SQL + revision", exact=True).click()
                page.get_by_label("Candidate SQL", exact=True).fill(
                    "SELECT substr(occurred_at,1,10) AS business_date, SUM(DISTINCT amount_cents) AS revenue_cents FROM event_deliveries GROUP BY business_date"
                )
                with page.expect_response(
                    lambda r: r.url.endswith("/api/demo/verify") and r.request.method == "POST",
                    timeout=60000,
                ) as response:
                    page.get_by_role("button", name="Verify edited SQL").click()
                failed = response.value.json()
                assert not failed["grading"]["passed"] and failed["parent_id"] == initial["id"]
                expect(page.get_by_role("button", name="Accept verified finding")).to_be_disabled()
                capture("false-repair-blocked", ".result-card")
                page.goto(url + "/demo/runs/" + initial["id"])
                page.get_by_role("button", name="Verification", exact=True).click()
                expect(page.locator(".result-card .check-row")).to_have_count(
                    len(initial["grading"]["checks"])
                )
                capture("independent-regressions", ".result-card")
                page.get_by_role("button", name="Finding", exact=True).click()
                with page.expect_response(
                    lambda r: r.url.endswith("/api/demo/review") and r.request.method == "POST",
                    timeout=60000,
                ) as response:
                    page.get_by_role("button", name="Accept verified finding").click()
                final = response.value.json()
                assert final["stage"] == "approved" and final["version"] == initial["version"]
            page.locator(".review-summary").wait_for()
            capture("reviewed-result", ".result-card")
            with page.expect_download() as download:
                page.get_by_role("button", name="Download report").click()
            download.value.save_as(str(output / "downloaded-report.json"))
            exported = json.loads((output / "downloaded-report.json").read_text())
            assert (
                "token" not in exported["report"]
                and exported["report"]["version"] == final["version"]
            )
            page.reload()
            page.get_by_role("button", name="Download report").wait_for()
            expect(page.locator(".review-summary")).to_contain_text(
                "verified" if relay else "approved"
            )
            other = browser.new_context(viewport={"width": 1180, "height": 844})
            other_page = other.new_page()
            other_page.goto(url + "/demo/runs/" + final["id"])
            other_page.get_by_role("heading", name="Report unavailable in this browser.").wait_for()
            assert other_page.request.get(url + "/api/demo/runs/" + final["id"]).status == 404
            other.close()
            page.set_viewport_size({"width": 390, "height": 844})
            page.evaluate("window.scrollTo(0,0)")
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (
                "Mobile layout overflows"
            )
            page.screenshot(path=str(output / "mobile.png"), full_page=True)
            page.get_by_role("link", name="Investigation history", exact=True).click()
            page.get_by_role("heading", name="Investigation history", exact=True).wait_for()
            assert page.locator(".history-row").count() >= (1 if relay else 2)
            assert not errors, errors
            video = page.video
            context.close()
            if args.record:
                video.save_as(str(output / "continuous-walkthrough.webm"))
                assert (output / "continuous-walkthrough.webm").stat().st_size < 4000000, (
                    "Recording exceeds hosted media budget"
                )
            decoder.close()
            if args.publish_assets:
                shutil.copyfile(output / "continuous-walkthrough.webm", assets / "assets/media/walkthrough.webm")
                shutil.copyfile(output / frames[1]["path"], assets / "assets/media/poster.png")
            if (assets / "assets/media/walkthrough.webm").exists() or args.url:
                player = browser.new_page()
                player.goto(url + "/demo/recording")
                player.get_by_role("heading", name=name + " in action.").wait_for()
                player.wait_for_function(
                    "() => document.querySelector('video')?.readyState >= 1", timeout=30000
                )
                assert player.locator("video").evaluate("video=>video.duration > 0")
                player_verified = True
                player.close()
            browser.close()
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
    report = {
        "project": name,
        "url": url,
        "interactive_journey": True,
        "guided": True,
        "paid_model_calls": 0,
        "download": True,
        "reload": True,
        "cross_browser_history_hidden": True,
        "mobile_overflow": False,
        "recording_player": player_verified,
        "page_errors": errors,
        "frames": frames,
        "proof": (
            {
                "uncertain_receipt": True,
                "reconciliation": True,
                "verified_effects": True,
                "confirmed_receipts": 4,
            }
            if relay
            else {
                "independent_verification": True,
                "false_repair_rejected": True,
                "failed_acceptance_disabled": True,
                "exact_version_review": True,
            }
        ),
        "source_sha256": {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [
                root / "app.py",
                *sorted((root / "backend/src" / package).rglob("*.py")),
                *sorted((root / "agent/investigator").glob("*.py")),
                assets / "assets/scripts/app.js",
                assets / "assets/styles/style.css",
            ]
        },
    }
    if args.record:
        report["video_sha256"] = hashlib.sha256(
            (output / "continuous-walkthrough.webm").read_bytes()
        ).hexdigest()
        report["recording"] = (
            "Continuous actual browser capture; automated synthetic interactions, not customer feedback or live model inference"
        )
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {key: value for key, value in report.items() if key not in ("frames", "source_sha256")}
        )
    )


if __name__ == "__main__":
    main()
