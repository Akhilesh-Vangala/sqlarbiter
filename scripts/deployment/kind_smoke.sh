#!/usr/bin/env bash
set -euo pipefail

cluster_name="${VDIR_KIND_CLUSTER:-verifyops-ci}"
token="kind-only-access-token-0000000000000000"
cleanup() {
  if [[ -n "${forward_pid:-}" ]]; then kill "${forward_pid}" 2>/dev/null || true; fi
  kind delete cluster --name "${cluster_name}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

kind create cluster --name "${cluster_name}" --wait 120s
docker build -f backend/docker/Dockerfile --target runtime -t verifyops:kind .
kind load docker-image verifyops:kind --name "${cluster_name}"
kubectl apply -k infrastructure/kubernetes/overlays/kind
kubectl -n verifyops wait --for=condition=complete job/verifyops-migrate --timeout=180s
kubectl -n verifyops rollout status deployment/verifyops-api --timeout=180s
kubectl -n verifyops rollout status deployment/verifyops-worker --timeout=180s
kubectl -n verifyops port-forward service/verifyops-api 18080:80 > /tmp/verifyops-kind-forward.log 2>&1 &
forward_pid=$!

for _ in $(seq 1 40); do
  if curl --fail --silent --show-error -H 'Host: localhost' http://127.0.0.1:18080/healthz >/dev/null; then break; fi
  sleep 0.5
done
curl --fail --silent --show-error -H 'Host: localhost' http://127.0.0.1:18080/healthz | grep -q '"status":"ok"'

response=$(curl --fail --silent --show-error \
  -H 'Host: localhost' \
  -H "Authorization: Bearer ${token}" \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: kind-smoke-001' \
  -d '{"case_id":"case-001","investigator":"baseline","engine":"duckdb"}' \
  http://127.0.0.1:18080/api/jobs)
job_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"${response}")

for _ in $(seq 1 80); do
  job=$(curl --fail --silent --show-error -H 'Host: localhost' \
    -H "Authorization: Bearer ${token}" \
    "http://127.0.0.1:18080/api/jobs/${job_id}")
  status=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])' <<<"${job}")
  if [[ "${status}" == "completed" ]]; then
    python3 -c 'import json,sys; value=json.load(sys.stdin); assert value["result"]["grading"]["passed"]' <<<"${job}"
    break
  fi
  if [[ "${status}" =~ ^(failed|interrupted|cancelled)$ ]]; then
    echo "Kubernetes smoke job ended in ${status}" >&2
    exit 1
  fi
  sleep 0.5
done
[[ "${status}" == "completed" ]]
kubectl -n verifyops get pods
