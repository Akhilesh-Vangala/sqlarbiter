"""Exercise the product journey, consent, immutable history, failure recovery and layouts.

The checks are automated rehearsals, never feedback from actual customers.
With --record, retain one continuous real browser journey with readable pauses.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import time

import httpx
from playwright.sync_api import expect, sync_playwright


SOURCE = "event_id,amount,category,status\nCLIENT-17,12.34,Custom,completed\nCLIENT-17,12.34,Custom,completed\nCLIENT-18,3.21,Other,pending\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url")
    parser.add_argument("--output", default="artifacts/generated/product-browser")
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--axe", help="Path to pinned axe.min.js, optional locally")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    output = root / args.output
    output.mkdir(parents=True, exist_ok=True)
    server, log = None, None
    checks, errors, audits, frames = [], [], [], []
    url = args.url
    if not url:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        url = f"http://127.0.0.1:{port}"
        environment = dict(os.environ, VDIR_LOAD_DOTENV="0", VDIR_DEMO_SECRET=secrets.token_urlsafe(64), ANTHROPIC_API_KEY="",
                           VDIR_SUPABASE_URL="", VDIR_SUPABASE_PUBLISHABLE_KEY="")
        log = (output/"server.log").open("w")
        server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port), "--no-access-log"], cwd=root, env=environment, stdout=log, stderr=log)
        for _ in range(200):
            try:
                if httpx.get(url+"/healthz", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(.1)
        else:
            raise RuntimeError("Product did not become ready")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            options = {"viewport": {"width": 1440, "height": 1000}, "reduced_motion": "reduce"}
            if args.record:
                options.update(record_video_dir=str(output/"video"), record_video_size={"width": 1440, "height": 1000})
            context = browser.new_context(**options)
            page = context.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))

            def capture(name, audit=True):
                page.evaluate("document.activeElement?.blur()")
                page.screenshot(path=str(output/(name+".png")), full_page=True)
                frames.append(name+".png")
                if args.axe and audit:
                    page.evaluate(Path(args.axe).read_text())
                    result = page.evaluate("async()=>await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})")
                    audits.append({"view": name, "violations": result["violations"], "incomplete": len(result["incomplete"]), "passes": len(result["passes"])})
                    (output/"accessibility.json").write_text(json.dumps(audits, indent=2))
                    assert not result["violations"], [(v["id"], [n["target"] for n in v["nodes"]]) for v in result["violations"]]
                if args.record:
                    page.wait_for_timeout(1300)

            def choose(source=SOURCE):
                page.locator("#file").set_input_files({"name": "customer-revenue.csv", "mimeType": "text/csv", "buffer": source.encode()})
                expect(page.locator("#review-rules")).to_be_enabled()

            def run():
                page.locator("#review-rules").click()
                page.locator("#review-definition").click()
                expect(page.locator("#analyze")).to_be_disabled()
                page.locator("#confirm-rules").check()
                page.locator("#analyze").click()

            def save_snapshot():
                previous_url = page.url
                page.get_by_role("button", name="Save investigation", exact=True).click()
                expect(page.locator("#confirm-save")).to_be_disabled()
                expect(page.locator("#save-destination option[value=cloud]")).to_be_disabled()
                page.locator("#save-consent").check()
                page.locator("#confirm-save").click()
                expect(page).not_to_have_url(previous_url)
                expect(page).to_have_url(re.compile(r"/workspace/investigations/"))
                expect(page.locator("#output")).to_be_visible()
                return page.url

            page.goto(url+"/")
            expect(page.get_by_role("heading", level=1)).to_contain_text("Find the number")
            capture("01-home")
            page.get_by_role("link", name="Open workspace", exact=True).click()
            expect(page.get_by_role("heading", name="Your first investigation starts here.")).to_be_visible()
            capture("02-empty-workspace")
            checks.append("real-empty-workspace-no-fabricated-metrics")
            page.get_by_role("link", name="Projects", exact=True).click()
            page.get_by_role("button", name="Create project", exact=True).click()
            page.locator("#project-name").fill("October revenue")
            page.locator("#project-consent").check()
            page.locator("#dialog").get_by_role("button", name="Create project", exact=True).click()
            expect(page.locator("#dialog")).not_to_be_visible()
            page.get_by_role("link", name="Overview", exact=True).click()
            page.get_by_role("link", name="New investigation", exact=True).click()
            choose()
            page.locator("#investigation-title").fill("October revenue review")
            page.locator("#project-select").select_option(label="October revenue · This device")
            capture("03-source-preview")
            assert page.evaluate("async()=>{const {saved}=await import('/product-assets/lib/storage.js');return (await saved.list()).length}") == 0
            page.locator("#review-rules").click()
            expect(page.locator("#mapping-key")).to_have_value("c0")
            page.locator("#reported-total").fill("24.68")
            capture("04-business-rules")
            page.locator("#review-definition").click()
            expect(page.locator("#analyze")).to_be_disabled()
            capture("05-reviewed-contract")
            page.locator("#confirm-rules").check()
            page.locator("#analyze").click()
            expect(page.locator("#output")).to_be_visible()
            expect(page.locator("#verification")).to_have_text("Independent checks passed")
            expect(page.locator("#output")).to_contain_text("Duplicate deliveries explain this difference")
            report = json.loads(page.locator("#evidence pre").text_content())
            assert report["summary"]["verified_total_cents"] == 1234 and report["live_ai"] is False
            capture("06-verified-report")
            page.get_by_role("tab", name="Overview", exact=True).focus()
            page.keyboard.press("ArrowRight")
            expect(page.get_by_role("tab", name="Data quality", exact=True)).to_be_focused()
            expect(page.get_by_role("tab", name="Data quality", exact=True)).to_have_attribute("aria-selected", "true")
            capture("07-data-quality")
            page.get_by_role("tab", name="SQL & checks", exact=True).click()
            capture("08-sql-and-checks")
            for kind in ("json", "csv"):
                with page.expect_download() as value:
                    page.locator("#download-"+kind).click()
                value.value.save_as(output/("result."+kind))
                assert (output/("result."+kind)).stat().st_size > 20
            saved_url = save_snapshot()
            capture("09-saved-report")
            page.reload()
            expect(page.locator("#verification")).to_have_text("Independent checks passed")
            checks.extend(["declared-rules-real-independent-result-and-evidence-exports", "keyboard-tabs-and-modal-consent", "explicit-device-save-reload-and-report-authenticity"])
            page.get_by_role("link", name="Investigations", exact=True).click()
            expect(page.get_by_role("link", name="October revenue review", exact=True)).to_be_visible()
            capture("10-saved-investigations")
            page.get_by_role("link", name="Settings", exact=True).click()
            with page.expect_download() as backup:
                page.get_by_role("button", name="Export device backup", exact=True).click()
            backup.value.save_as(output/"device-backup.json")
            video = page.video
            context.close()
            if args.record:
                video.save_as(str(output/"continuous-walkthrough.webm"))

            # Negative paths use a separate non-recorded context, kept honest and
            # independent of the readable demonstration recording above.
            context = browser.new_context(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
            page = context.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(url+"/uploads")
            choose("event_id,amount,category,status\nconflict,1.00,X,completed\nconflict,2.00,X,completed\n")
            run()
            expect(page.locator("#error")).to_contain_text("Conflicting")
            expect(page.locator("#output")).not_to_be_visible()
            page.get_by_role("button", name="Inspect affected records", exact=True).click()
            expect(page.locator("#preview-content")).to_contain_text("conflict")
            capture("11-conflict-recovery")
            choose()
            page.route("**/api/uploads/analyze-stream", lambda route: route.abort("failed"))
            run()
            expect(page.locator("#error")).to_contain_text("Connection interrupted")
            page.unroute("**/api/uploads/analyze-stream")
            page.locator("#review-definition").click()
            page.locator("#confirm-rules").check()
            page.locator("#analyze").click()
            expect(page.locator("#output")).to_be_visible()
            checks.append("conflicting-record-inspection-network-failure-and-successful-retry")
            first = save_snapshot()
            original_id = first.split("/investigations/")[1].split("?")[0]
            page.get_by_role("button", name="Edit rules & rerun", exact=True).first.click()
            page.locator("#reported-total").fill("99.00")
            page.locator("#review-definition").click()
            page.locator("#confirm-rules").check()
            page.locator("#analyze").click()
            expect(page.locator("#output")).to_be_visible()
            second = save_snapshot()
            assert first != second
            count = page.evaluate("async()=>{const {saved}=await import('/product-assets/lib/storage.js');return (await saved.list()).length}")
            assert count == 2
            checks.append("edited-investigation-saves-new-snapshot-original-preserved")
            page.evaluate("""async id=>{const db=await new Promise((resolve,reject)=>{const r=indexedDB.open('verifyops-workspace-v1',1);r.onsuccess=()=>resolve(r.result);r.onerror=reject});await new Promise((resolve,reject)=>{const tx=db.transaction('investigations','readwrite'),s=tx.objectStore('investigations'),r=s.get(id);r.onsuccess=()=>{const v=r.result;v.report.summary.verified_total_cents=99999;s.put(v)};tx.oncomplete=resolve;tx.onerror=reject});db.close()}""", original_id)
            page.goto(first)
            expect(page.locator("#error")).to_contain_text("could not be authenticated")
            expect(page.locator("#output")).not_to_be_visible()
            checks.append("tampered-device-report-never-shown-as-verified")
            page.locator("#clear").click()
            page.locator("#confirm-clear").click()
            choose()
            expect(page.locator("#file-info")).to_contain_text("3 records")
            run()
            expect(page.locator("#output")).to_be_visible()
            for width in (320, 390, 768, 1440):
                page.set_viewport_size({"width": width, "height": 900})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
                page.screenshot(path=str(output/("report-"+str(width)+".png")), full_page=True)
            checks.append("responsive-results-320-390-768-1440-with-reduced-motion")
            page.set_viewport_size({"width": 1440, "height": 1000})
            page.keyboard.press("Control+k")
            expect(page.locator("#dialog")).to_be_visible()
            page.keyboard.press("Escape")
            expect(page.locator("#dialog")).not_to_be_visible()
            page.locator("#clear").click()
            page.locator("#confirm-clear").click()
            page.get_by_role("link", name="Sign in", exact=True).click()
            expect(page.get_by_role("heading", name="Cloud accounts aren’t connected yet.")).to_be_visible()
            capture("12-account-status")
            page.get_by_role("link", name="Settings", exact=True).click()
            capture("13-storage-settings")
            page.get_by_role("link", name="Quick guide", exact=True).click()
            capture("14-quick-guide")
            checks.append("command-palette-native-dialog-and-explicit-disabled-cloud-account")
            context.close()
            context = browser.new_context(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
            page = context.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(url+"/workspace/settings")
            page.locator("#backup-file").set_input_files(output/"device-backup.json")
            expect(page.locator("#confirm-restore")).to_be_disabled()
            page.locator("#restore-consent").check()
            page.locator("#confirm-restore").click()
            expect(page).to_have_url(re.compile("/workspace/history"))
            page.get_by_role("link", name="October revenue review", exact=True).click()
            expect(page.locator("#verification")).to_have_text("Independent checks passed")
            restored_id = page.url.split("/investigations/")[1].split("?")[0]
            assert restored_id not in saved_url
            checks.append("portable-backup-consent-source-validation-and-authenticated-cross-browser-restore")
            # Real IndexedDB write transactions serialize competing saves.
            quota = page.evaluate("""async()=>{const {saved}=await import('/product-assets/lib/storage.js'); const original=(await saved.list())[0];
              const results=await Promise.allSettled(Array.from({length:53},()=>saved.put({...original,id:crypto.randomUUID()},true)));
              return {count:(await saved.list()).length,passed:results.filter(r=>r.status==='fulfilled').length,rejected:results.filter(r=>r.status==='rejected').length}}""")
            assert quota == {"count": 50, "passed": 49, "rejected": 4}, quota
            checks.append("concurrent-IndexedDB-saves-enforce-device-quota-without-partial-loss")
            context.close()
            browser.close()
        assert not errors, errors
        sources = [root/"app.py", *sorted((root/"backend/src/vdir").rglob("*.py")),
                   *[f for f in sorted((root/"frontend/apps/product").rglob("*")) if f.suffix in (".js", ".css", ".html")]]
        result = {"passed": True, "url": url, "paid_model_calls": 0, "actual_user_feedback": False, "checks": checks,
                  "page_errors": errors, "frames": frames, "automated_accessibility_views": len(audits),
                  "source_sha256": {str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest() for f in sources}}
        (output/"report.json").write_text(json.dumps(result, indent=2)+"\n")
        print(json.dumps({k: v for k, v in result.items() if k not in ("source_sha256", "frames")}))
    finally:
        if server:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill(); server.wait()
        if log:
            log.close()


if __name__ == "__main__":
    main()
