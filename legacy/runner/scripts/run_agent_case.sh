#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 CASE_ID CASE_KIND" >&2
  exit 2
fi

CASE_ID="$1"
CASE_KIND="$2"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CASE_DIR="${ROOT}/cases/${CASE_KIND}"
RUNTIME_CASE="/root/.openclaw/workspace/tool-modeling/${CASE_ID}"
AGENT_RUN="${CASE_DIR}/agent_run"
TIMEOUT=3600

if [[ ! -f /host-openclaw/openclaw.json ]]; then
  echo "missing /host-openclaw/openclaw.json; mount the host OpenClaw directory read-only" >&2
  exit 2
fi
rm -rf /root/.openclaw
python3 "${ROOT}/scripts/sync_openclaw_config.py" \
  /host-openclaw /root/.openclaw
rm -rf "${RUNTIME_CASE}"
mkdir -p \
  /root/.openclaw/skills \
  /root/.openclaw/workspace/tool-modeling \
  "${RUNTIME_CASE}/input" \
  "${RUNTIME_CASE}/output" \
  "${AGENT_RUN}"
find "${CASE_DIR}/output" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
find "${AGENT_RUN}" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
cp -a "${CASE_DIR}/input/." "${RUNTIME_CASE}/input/"
cp "${CASE_DIR}/task.prompt" "${AGENT_RUN}/task.prompt"
rm -rf "/root/.openclaw/skills/${CASE_KIND}"
ln -s "${ROOT}/vendor/skills/${CASE_KIND}" "/root/.openclaw/skills/${CASE_KIND}"

openclaw config validate >"${AGENT_RUN}/openclaw_config_validate.log" 2>&1
OPENCLAW_VERSION="$(openclaw --version 2>/dev/null)"
OPENCLAW_VERSION="${OPENCLAW_VERSION%%$'\n'*}"

openclaw models status --check --probe \
  --probe-provider deepseek --agent main \
  >"${AGENT_RUN}/models_check.stdout.log" \
  2>"${AGENT_RUN}/models_check.stderr.log"

PROMPT="$(<"${CASE_DIR}/task.prompt")"
START_EPOCH="$(date +%s.%N)"
set +e
(
  cd "${RUNTIME_CASE}"
  openclaw agent \
    --local \
    --agent main \
    --session-key "agent:main:${CASE_ID}" \
    --timeout "${TIMEOUT}" \
    --message "${PROMPT}" \
    --json
) >"${AGENT_RUN}/openclaw_agent.stdout.json" \
  2>"${AGENT_RUN}/openclaw_agent.stderr.log"
AGENT_EXIT_CODE=$?
set -e
END_EPOCH="$(date +%s.%N)"
printf '%s\n' "${AGENT_EXIT_CODE}" >"${AGENT_RUN}/openclaw_agent.exit_code"

python3 - "${CASE_ID}" "${START_EPOCH}" "${END_EPOCH}" \
  "${AGENT_RUN}/task_window.json" <<'PY'
import json
import pathlib
import sys

case_id, start, end, target = sys.argv[1:]
start_value = float(start)
end_value = float(end)
pathlib.Path(target).write_text(
    json.dumps(
        {
            "case_id": case_id,
            "start_epoch": start_value,
            "end_epoch": end_value,
            "duration_seconds": round(end_value - start_value, 3),
            "source": "openclaw_runner",
        },
        indent=2,
    )
    + "\n"
)
PY

python3 "${ROOT}/scripts/capture_openclaw_session.py" \
  "${CASE_ID}" \
  "${AGENT_RUN}/openclaw_agent.stdout.json" \
  "${AGENT_RUN}/openclaw_session.jsonl"
python3 "${ROOT}/scripts/export_openclaw_atif.py" \
  "${AGENT_RUN}/openclaw_session.jsonl" \
  "${AGENT_RUN}/trajectory.json" \
  --agent-version "${OPENCLAW_VERSION}"
python3 "${ROOT}/scripts/extract_key_operations.py" \
  "${AGENT_RUN}/trajectory.json" \
  "${AGENT_RUN}/key_operations.json" \
  --case-id "${CASE_ID}" \
  --case-kind "${CASE_KIND}"
cp -a "${RUNTIME_CASE}/output/." "${CASE_DIR}/output/"

HOST_UID="${HOST_UID:-1000}"
HOST_GID="${HOST_GID:-1000}"
chown -R "${HOST_UID}:${HOST_GID}" "${CASE_DIR}/output" "${AGENT_RUN}" || true

if [[ "${AGENT_EXIT_CODE}" -ne 0 ]]; then
  echo "OpenClaw agent failed with exit code ${AGENT_EXIT_CODE}" >&2
  exit "${AGENT_EXIT_CODE}"
fi
python3 "${ROOT}/scripts/check_agent_output.py" \
  "${CASE_KIND}" "${CASE_DIR}/output"
