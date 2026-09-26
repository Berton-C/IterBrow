#!/usr/bin/env bash
# One offline command for the Build Atlas acceptance baseline.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Use the same managed runtime that the source app uses when it is available.
# The system Python on macOS does not carry Hyperon and therefore cannot run
# native-governor or real-engine acceptance tests. Keep a system fallback for
# clean source trees before setup_python_env.sh has created the environment.
PYTHON_BIN="$ROOT_DIR/iter/.venv/bin/python3"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi
export PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/iterbrow-control-pycache"

echo "[control] authoritative runtime tests"
"$PYTHON_BIN" -m unittest discover -s tests -p 'test_*.py' -v

echo "[control] historical Iter regressions"
legacy_tests=(
  tools/_test_all_stages_combined.py
  tools/_test_metta_gate_stage3.py
  tools/_test_soul_eval_stages.py
  tools/_test_stage4_lock.py
  transformations/_test_dashboard_beliefs_refresh.py
  transformations/_test_flourishing_bridges.py
  transformations/_test_flourishing_bridges_2.py
  transformations/_test_mode_signal_bridge.py
  transformations/_test_provenance_guard.py
  transformations/_test_stage5_guard.py
)
for test_path in "${legacy_tests[@]}"; do
  echo "[control] $test_path"
  (cd iter && "$PYTHON_BIN" "$test_path")
done

echo "[control] syntax and manifest"
"$PYTHON_BIN" -m compileall -q \
  iter/iterbrow_runtime \
  iter/iterbrow_runtime/app_revision_manager.py \
  iter/hotload_control.py \
  iter/iter.py \
  iter/metta_server.py \
  iter/pwq_service.py \
  iter/tools/atomspace.py \
  iter/tools/app_revision_control.py \
  iter/tools/metta.py \
  iter/tools/pwq_write.py \
  iter/tools/revision_control.py \
  iter/tools/self_improve.py \
  iter/tools/task_state.py \
  iter/tools/start_new_task.py \
  iter/channels/electron_ui.py \
  iter/tools/_petta_db.py \
  iter/tools/soul_eval.py \
  iter/tools/soul_skill_registry.py \
  iter/transformations/nace_courier.py \
  iter/transformations/pwq_board.py \
  iter/transformations/transcript.py \
  iter/transformations/tool_reliability_tracker.py
"$PYTHON_BIN" -m json.tool iter/state_manifest.json >/dev/null
"$PYTHON_BIN" -m py_compile scripts/smoke_atomspace_service.py
node --check main.js
node --check preload.js
node --check bridge/chat_bridge.js
node --check bridge/pwq_preload.js
node --check renderer/renderer.js
bash -n install.sh
bash -n scripts/setup_python_env.sh
# Runtime-generated dashboard projections may change while Iter is cycling and
# contain transcript text verbatim. Preserve them, but do not let their content
# mask whitespace errors in authored control-plane files.
git diff --check -- . \
  ':(exclude)iter/dashboard_atomspace.html' \
  ':(exclude)iter/dashboard_context.html' \
  ':(exclude)iter/dashboard_gallery.html' \
  ':(exclude)iter/dashboard_runtime.html'

echo "[control] PASS"
