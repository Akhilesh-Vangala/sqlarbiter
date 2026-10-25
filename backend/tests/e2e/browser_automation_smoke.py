"""Real workflow/cancellation UI with actual fixed investigator; no hosted model."""
import json
import os
import socket
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import uvicorn
from playwright.sync_api import sync_playwright
from playwright.sync_api import expect
from sqlarbiter.api.routes import create_app
from sqlarbiter.workflows.service import process_next

ROOT = Path(__file__).resolve().parents[3]


def main():
    output = ROOT / 'artifacts/generated' / ('browser-automation-' + uuid.uuid4().hex[:8])
    output.mkdir(parents=True)
    errors, checks = [], []
    def execute(store):
        with ThreadPoolExecutor(max_workers=1) as workers:
            return workers.submit(process_next, store).result()
    with patch.dict(os.environ, {'SQLARBITER_LOAD_DOTENV': '0', 'ANTHROPIC_API_KEY': '', 'SQLARBITER_ANTHROPIC_MODEL': ''}):
        app = create_app(output / 'state', token='')
        with socket.socket() as connection:
            connection.bind(('127.0.0.1', 0))
            port = connection.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='error'))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        for _ in range(100):
            if server.started:
                break
            threading.Event().wait(.05)
        assert server.started
        try:
            with sync_playwright() as runner:
                browser = runner.chromium.launch()
                page = browser.new_page(viewport={'width': 1440, 'height': 1050})
                page.on('pageerror', lambda error: errors.append(str(error)))
                url = 'http://127.0.0.1:%d' % port
                page.goto(url)
                expect(page.locator('#workflow-scenarios input')).to_have_count(6)
                expect(page.locator('#workflow-investigator option[value=langgraph]')).to_be_disabled()
                checks.append('unconfigured AI disabled')
                page.get_by_role('button', name='Run workflow', exact=True).click()
                expect(page.locator('#new-workflow-view')).to_be_visible()
                page.get_by_role('button', name='Cancel', exact=True).click()
                expect(page.locator('#home-view')).to_be_visible()
                checks.append('setup page cancel and return')
                page.get_by_role('button', name='Run workflow', exact=True).click()
                for item in page.locator('#workflow-scenarios input').all():
                    item.uncheck()
                page.get_by_role('button', name='Start workflow', exact=True).click()
                expect(page.locator('#new-workflow-view')).to_be_visible()
                assert not app.state.store.list_workflows()
                checks.append('empty selection does not create work')
                name = 'Revenue review <script>window.__injected=true</script>'
                page.get_by_label('Workflow name', exact=True).fill(name)
                for case in ('case-001', 'case-003', 'case-005'):
                    page.locator('#workflow-scenarios input[value="%s"]' % case).check()
                page.get_by_role('button', name='Start workflow', exact=True).click()
                expect(page.locator('.workflow-member')).to_have_count(3)
                flow_url = page.url
                flow = app.state.store.list_workflows()[0]
                assert flow['counts']['queued'] == 3
                expect(page.locator('#workflow-progress')).to_have_attribute('value', '0')
                assert page.evaluate('window.__injected') is None
                checks.extend(['atomic multi-metric creation', 'actual queued progress', 'XSS-safe workflow name'])
                for _ in range(3):
                    assert execute(app.state.store)
                expect(page.locator('#workflow-progress')).to_have_attribute('value', '3', timeout=20000)
                flow = app.state.store.get_workflow(flow['id'])
                assert flow['counts']['resolved'] == 2 and flow['counts']['attention'] == 1
                expect(page.locator('.workflow-header')).to_contain_text('needs attention')
                page.screenshot(path=str(output / 'desktop-workflow.png'), full_page=True)
                checks.extend(['independent per-metric verification', 'aggregate attention remains visible'])
                page.locator('.workflow-member').first.click()
                expect(page.locator('#detail-view')).to_be_visible()
                expect(page.locator('#back-button')).to_contain_text('workflow')
                page.locator('#back-button').click()
                expect(page).to_have_url(flow_url)
                page.reload()
                expect(page.locator('.workflow-member')).to_have_count(3)
                checks.extend(['member detail and contextual back', 'workflow deep link reload'])
                page.get_by_role('button', name='Run workflow', exact=True).click()
                page.get_by_label('Workflow name', exact=True).fill('Stopped metric review')
                for item in page.locator('#workflow-scenarios input').all():
                    item.uncheck()
                for case in ('case-001', 'case-003', 'case-005'):
                    page.locator('#workflow-scenarios input[value="%s"]' % case).check()
                page.get_by_role('button', name='Start workflow', exact=True).click()
                expect(page.locator('#workflow-detail h2')).to_have_text('Stopped metric review')
                page.get_by_role('button', name='Cancel remaining work', exact=True).click()
                page.get_by_label('Cancellation reason', exact=True).fill('<script>window.__injected=true</script>')
                page.get_by_role('button', name='Confirm cancellation', exact=True).click()
                expect(page.locator('.workflow-header')).to_contain_text('cancelled')
                expect(page.locator('#workflow-progress')).to_have_attribute('value', '3')
                stopped = next(f for f in app.state.store.list_workflows() if f['name'] == 'Stopped metric review')
                assert all(j['status'] == 'cancelled' for j in stopped['jobs'])
                assert execute(app.state.store) is False
                checks.extend(['cancel all queued members', 'cancelled work never executed'])
                page.locator('.workflow-member').first.click()
                expect(page.locator('.detail-title-line .badge')).to_have_text('Cancelled')
                assert page.get_by_role('button', name='Approve this version').count() == 0
                checks.append('cancelled run has no approval')
                page.get_by_role('button', name='Run details & audit', exact=True).click()
                expect(page.locator('#inspector-content')).to_contain_text('<script>window.__injected=true</script>')
                assert page.evaluate('window.__injected') is None
                page.keyboard.press('Escape')
                checks.append('escaped cancellation audit')
                page.get_by_role('button', name='New investigation', exact=True).click()
                page.get_by_role('button', name='Run investigation', exact=True).click()
                expect(page.get_by_role('button', name='Cancel run', exact=True)).to_be_visible()
                page.get_by_role('button', name='Cancel run', exact=True).click()
                page.get_by_role('button', name='Keep running', exact=True).click()
                expect(page.get_by_role('button', name='Cancel run', exact=True)).to_be_visible()
                page.get_by_role('button', name='Cancel run', exact=True).click()
                page.get_by_role('button', name='Confirm cancellation', exact=True).click()
                expect(page.locator('.detail-title-line .badge')).to_have_text('Cancelled')
                checks.append('single-run cancellation and dismiss')
                page.goto(flow_url)
                expect(page.locator('.workflow-member')).to_have_count(3)
                for width in (320, 390, 600, 768, 1440):
                    page.set_viewport_size({'width': width, 'height': 900})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
                    page.get_by_role('button', name='Run workflow', exact=True).click()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
                    page.get_by_label('Workflow name', exact=True).fill('Draft survives polling')
                    page.wait_for_timeout(1700)
                    expect(page.get_by_label('Workflow name', exact=True)).to_have_value('Draft survives polling')
                    if width == 390:
                        page.screenshot(path=str(output / 'mobile-workflow-dialog.png'), full_page=True)
                    page.get_by_role('button', name='Cancel', exact=True).click()
                    checks.append('workflow and setup layout %d' % width)
                checks.append('polling preserves workflow draft')
                page.goto(url + '/workflows/' + 'f' * 32)
                expect(page.locator('#workflow-detail')).to_contain_text('Workflow unavailable')
                page.get_by_role('button', name='Retry loading workflow', exact=True).click()
                expect(page.locator('#workflow-detail')).to_contain_text('Workflow unavailable')
                checks.append('unknown workflow offers retry')
                assert not errors, errors
                checks.append('no browser errors')
                browser.close()
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            assert not thread.is_alive()
    (output / 'result.json').write_text(json.dumps({'passed': True, 'checks': checks, 'provider': 'fixed investigator; no live AI'}, indent=2))
    print(json.dumps({'passed': True, 'output': str(output.relative_to(ROOT)), 'checks': len(checks)}))


if __name__ == '__main__':
    main()
