"""Distinct page journeys, URL sections, current public metric data and mobile layouts."""
import json
import os
import socket
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import uvicorn
from playwright.sync_api import sync_playwright, expect
from vdir.api import create_app
from vdir.service import process_next

ROOT = Path(__file__).resolve().parents[2]

def main():
    output = ROOT / 'artifacts/generated' / ('browser-pages-' + uuid.uuid4().hex[:8])
    output.mkdir(parents=True)
    checks, errors = [], []
    def execute(store):
        with ThreadPoolExecutor(max_workers=1) as workers:
            return workers.submit(process_next, store).result()
    with patch.dict(os.environ, {'ANTHROPIC_API_KEY': '', 'VDIR_ANTHROPIC_MODEL': '', 'VDIR_LOAD_DOTENV': '0'}):
        app = create_app(output / 'state', token='', operator='page-test-operator')
        with socket.socket() as reserve:
            reserve.bind(('127.0.0.1', 0)); port = reserve.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='error'))
        thread = threading.Thread(target=server.run, daemon=True); thread.start()
        for _ in range(100):
            if server.started: break
            threading.Event().wait(.05)
        assert server.started
        try:
            with sync_playwright() as runner:
                browser = runner.chromium.launch()
                page = browser.new_page(viewport={'width': 1440, 'height': 1000})
                page.on('pageerror', lambda error: errors.append(str(error)))
                base = 'http://127.0.0.1:%d' % port
                page.goto(base + '/metrics')
                expect(page.locator('.metric-card')).to_have_count(6)
                expect(page.locator('.sidebar a[aria-current=page]')).to_have_attribute('href', '/metrics')
                page.get_by_label('Search metrics').fill('no-such-metric')
                expect(page.get_by_role('heading', name='No matching metrics')).to_be_visible()
                page.get_by_label('Search metrics').fill('completed_item_revenue')
                expect(page.locator('.metric-card')).to_have_count(2)
                page.locator('.metric-card').first.click()
                expect(page).to_have_url(base + '/metrics/case-001')
                expect(page.locator('#metric-content')).to_contain_text('Reporting contract')
                expect(page.locator('.schema-table')).to_have_count(3)
                page.locator('.schema-table').first.locator('summary').click()
                expect(page.locator('.schema-table[open] pre')).to_contain_text('order_id')
                page.screenshot(path=str(output / 'desktop-metric-definition.png'), full_page=True)
                checks.extend(['catalog search and actual metrics', 'metric detail current contract and schema', 'metric route and active navigation'])
                page.get_by_role('button', name='Investigate this metric', exact=True).click()
                expect(page).to_have_url(base + '/investigations/new?metric=case-001')
                expect(page.locator('#incident')).to_have_value('case-001')
                expect(page.locator('#new-investigation-view')).to_be_visible()
                expect(page.locator('#workspace-stats')).not_to_be_visible()
                page.reload()
                expect(page.locator('#incident')).to_have_value('case-001')
                page.get_by_role('button', name='Cancel', exact=True).click()
                expect(page).to_have_url(base + '/metrics/case-001')
                checks.extend(['creation is full page', 'preselected metric survives reload', 'cancel returns to source page'])
                page.get_by_role('button', name='Investigate this metric', exact=True).click()
                page.screenshot(path=str(output / 'desktop-investigation-setup.png'), full_page=True)
                page.get_by_role('button', name='Run investigation', exact=True).click()
                expect(page.get_by_role('button', name='Cancel run', exact=True)).to_be_visible()
                job = app.state.store.list()[0]
                assert execute(app.state.store)
                expect(page.locator('.detail-title-line .badge')).to_have_text('Repair proposed', timeout=20000)
                path = '/investigations/' + job['id']
                page.get_by_role('tab', name='Evidence', exact=True).click()
                expect(page).to_have_url(base + path + '/evidence')
                page.reload()
                expect(page.get_by_role('tab', name='Evidence', exact=True)).to_have_attribute('aria-selected', 'true')
                expect(page.locator('#detail .evidence-item')).to_have_count(8)
                page.get_by_role('tab', name='SQL & review', exact=True).click()
                expect(page).to_have_url(base + path + '/sql')
                page.go_back()
                expect(page.get_by_role('tab', name='Evidence', exact=True)).to_have_attribute('aria-selected', 'true')
                page.go_forward()
                expect(page.get_by_role('tab', name='SQL & review', exact=True)).to_have_attribute('aria-selected', 'true')
                page.reload()
                expect(page.get_by_label('Candidate SQL', exact=True)).to_be_visible()
                page.goto(base + path + '/definition')
                expect(page.get_by_role('tab', name='Metric definition', exact=True)).to_have_attribute('aria-selected', 'true')
                page.goto(base + path + '/activity')
                expect(page.get_by_role('tab', name='Summary', exact=True)).to_have_attribute('aria-selected', 'true')
                expect(page).to_have_url(base + path)
                checks.extend(['setup submits actual investigation', 'evidence URL reload', 'SQL URL reload and browser history', 'definition direct link', 'unavailable activity falls back explicitly'])
                page.goto(base + '/settings')
                expect(page.locator('#settings-configuration')).to_contain_text('page-test-operator')
                expect(page.locator('#settings-configuration')).to_contain_text('Not configured')
                expect(page.locator('#settings-configuration')).to_contain_text('Shared AI allowance')
                expect(page.locator('#settings-configuration')).to_contain_text('$5.00')
                expect(page.locator('#settings-access')).to_contain_text('Local loopback access')
                page.screenshot(path=str(output / 'desktop-settings.png'), full_page=True)
                checks.append('settings shows actual configuration without secrets')
                page.get_by_role('button', name='Run workflow', exact=True).click()
                expect(page).to_have_url(base + '/workflows/new')
                expect(page.locator('#new-workflow-view')).to_be_visible()
                for item in page.locator('#workflow-scenarios input').all(): item.uncheck()
                for case in ('case-001', 'case-005'): page.locator('#workflow-scenarios input[value="%s"]' % case).check()
                page.get_by_label('Workflow name', exact=True).fill('Page journey metric review')
                page.get_by_role('button', name='Start workflow', exact=True).click()
                expect(page.locator('.workflow-member')).to_have_count(2)
                workflow = app.state.store.list_workflows()[0]
                expect(page.locator('#workflow-list-panel')).not_to_be_visible()
                assert execute(app.state.store) and execute(app.state.store)
                expect(page.locator('#workflow-progress')).to_have_attribute('value', '2', timeout=20000)
                page.locator('#back-button').click()
                expect(page).to_have_url(base + '/workflows')
                expect(page.locator('.workflow-card')).to_have_count(1)
                expect(page.locator('#workflow-detail')).not_to_be_visible()
                page.locator('.workflow-card').click()
                expect(page).to_have_url(base + '/workflows/' + workflow['id'])
                page.reload()
                expect(page.locator('.workflow-member')).to_have_count(2)
                checks.extend(['workflow setup page executes', 'workflow collection and detail separate', 'workflow deep link reload'])
                for width in (320, 390, 600, 768, 1440):
                    page.set_viewport_size({'width': width, 'height': 900})
                    for route, view in (('/metrics', 'metrics'), ('/metrics/case-001', 'metric'), ('/settings', 'settings'), ('/investigations/new', 'new-investigation'), ('/workflows/new', 'new-workflow'), ('/workflows/' + workflow['id'], 'workflows')):
                        page.goto(base + route)
                        expect(page.locator('#' + view + '-view')).to_be_visible()
                        expect(page.locator('#incident option')).to_have_count(6)
                        if view == 'metric': expect(page.locator('.schema-table')).to_have_count(3)
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (width, route)
                        bad = page.evaluate("""() => [...document.querySelectorAll('body *')].filter(e => e.getClientRects().length).flatMap(e => ['color','backgroundColor','borderTopColor'].map(p => getComputedStyle(e)[p])).filter(c => {const v=c.match(/[\\d.]+/g);return v&&v.length>=3&&(v[0]!==v[1]||v[1]!==v[2]);})""")
                        assert not bad, (width, route, bad[:3])
                        if width == 390 and view in ('metric', 'new-investigation', 'new-workflow'):
                            page.screenshot(path=str(output / ('mobile-' + view + '.png')), full_page=True)
                    checks.append('distinct pages layout and neutral palette %d' % width)
                page.goto(base + '/metrics/case-999')
                expect(page.get_by_role('heading', name='Metric unavailable')).to_be_visible()
                page.get_by_role('button', name='Retry loading metric').click()
                expect(page.get_by_role('heading', name='Metric unavailable')).to_be_visible()
                checks.append('missing metric error and retry')
                assert not errors, errors
                checks.append('no browser exceptions')
                browser.close()
        finally:
            server.should_exit = True; thread.join(timeout=10); assert not thread.is_alive()
    (output / 'result.json').write_text(json.dumps({'passed': True, 'checks': checks, 'live_model_generation': False}, indent=2))
    print(json.dumps({'passed': True, 'output': str(output.relative_to(ROOT)), 'checks': len(checks)}))

if __name__ == '__main__': main()
