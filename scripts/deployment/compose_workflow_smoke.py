"""Authenticated grouped workflow and cancellation against separate Compose worker."""
import json
import os
import time
import urllib.request
import uuid

base = 'http://127.0.0.1:8000'

def request(path, payload=None, key=None):
    headers = {'Authorization': 'Bearer ' + os.environ['VDIR_ACCESS_TOKEN'], 'Content-Type': 'application/json'}
    if key:
        headers['Idempotency-Key'] = key
    data = json.dumps(payload).encode() if payload is not None else None
    with urllib.request.urlopen(urllib.request.Request(base + path, data=data, headers=headers), timeout=10) as response:
        return json.load(response)

assert request('/healthz')['status'] == 'ok'
existing = request('/api/jobs')
assert all(j['status'] not in ('queued', 'running', 'cancelling') for j in existing), 'Wait for idle Compose'
key = uuid.uuid4().hex
payload = {'name': 'Compose verified metric review', 'case_ids': ['case-001', 'case-003', 'case-005'], 'investigator': 'baseline', 'engine': 'duckdb'}
flow = request('/api/workflows', payload, key)
assert request('/api/workflows', payload, key)['id'] == flow['id']
for _ in range(200):
    flow = request('/api/workflows/' + flow['id'])
    if not flow['counts']['queued'] + flow['counts']['running']:
        break
    time.sleep(.2)
assert flow['counts']['resolved'] == 2 and flow['counts']['attention'] == 1 and flow['counts']['terminal'] == 3, flow['counts']
versions = {j['id']: j['result_version'] for j in flow['jobs']}
assert all(request('/api/jobs/' + j['id'] + '/report')['result_version'] == j['result_version'] for j in flow['jobs'])
assert all(request('/api/jobs/' + j['id'])['review'] is None for j in flow['jobs'])
request('/api/workflows/' + flow['id'] + '/cancel', {'reason': 'Completed members remain immutable'})
assert {j['id']: j['result_version'] for j in request('/api/workflows/' + flow['id'])['jobs']} == versions
cancelled = request('/api/workflows', {'name': 'Compose stopped workflow', 'case_ids': [c['id'] for c in request('/api/incidents')]}, uuid.uuid4().hex)
reply = request('/api/workflows/' + cancelled['id'] + '/cancel', {'reason': 'Separate worker cancellation smoke check'})
targets = [j['id'] for j in reply['jobs'] if j['status'] in ('cancelling', 'cancelled')]
assert targets, 'At least one member must observe cancellation'
for _ in range(100):
    cancelled = request('/api/workflows/' + cancelled['id'])
    if not cancelled['counts']['queued'] + cancelled['counts']['running']:
        break
    time.sleep(.2)
for identity in targets:
    job = request('/api/jobs/' + identity)
    assert job['status'] == 'cancelled' and job['result'] is None and job['result_version'] is None
assert cancelled['counts']['terminal'] == 6
for previous in existing:
    current = request('/api/jobs/' + previous['id'])
    assert (current['status'], current['result_version']) == (previous['status'], previous['result_version'])
print(json.dumps({'passed': True, 'workflow_id': flow['id'], 'counts': flow['counts'], 'cancelled_targets': len(targets), 'cancelled_counts': cancelled['counts'], 'existing_history_preserved': len(existing), 'checks': ['idempotent workflow', 'separate worker execution', 'independent outcomes', 'reports and no automatic approval', 'completed results immutable', 'cancellation acknowledged without publication', 'existing history preserved'], 'live_model_generation': False}, indent=2))
