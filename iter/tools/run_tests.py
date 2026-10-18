import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _files  # noqa: E402
from iterbrow_runtime.tool_results import ToolOutput  # noqa: E402

DESCRIPTION = (
    "Run the repository's tests with pytest from the repo root, using Iter's own Python. target: a path such as "
    "tests/test_x.py (or tests/test_x.py::Case::test_y), or any other text as a -k expression; empty runs tests/. "
    "fast=true skips tests/e2e. First line is RESULT: <pytest summary>; then the last 60 lines of output."
)

TIMEOUT = 880  # the loop allows run_tests 900 s
TAIL = 60
SUMMARY = re.compile(r"\b\d+ (?:passed|failed|errors?|skipped|xfailed|xpassed|deselected|warnings?)\b|no tests ran")


def _python():
    venv = _files.iter_dir() / ".venv" / "bin" / "python3"
    return str(venv) if venv.exists() else sys.executable


def run(target="", fast="true"):
    root = _files.repo_root()
    python = _python()
    check = subprocess.run([python, "-c", "import pytest"], capture_output=True, text=True)
    if check.returncode != 0:
        return _files.input_error("ERROR: pytest is not installed in iter/.venv; run scripts/setup_python_env.sh")
    target = str(target or "").strip()
    args = [python, "-m", "pytest"]
    if not target:
        args.append("tests")
    elif target.replace("\\", "/").startswith("tests/") or target == "tests":
        args.append(target)
    else:
        args += ["tests", "-k", target]
    args += ["-q", "-p", "no:cacheprovider"]
    if str(fast).strip().lower() not in ("false", "0", "no", "off"):
        args.append("--ignore=tests/e2e")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    try:
        proc = subprocess.run(args, cwd=str(root), env=env, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired as error:
        partial = (error.stdout or b"")
        partial = partial.decode("utf-8", "replace") if isinstance(partial, bytes) else partial
        tail = "\n".join(partial.splitlines()[-TAIL:])
        return ToolOutput("RESULT: timed out after %ds\n--- output ---\n%s" % (TIMEOUT, tail), False, state="failed")
    output = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr.strip() else "")
    lines = output.splitlines()
    summary = next((line.strip().strip("=").strip() for line in reversed(lines) if SUMMARY.search(line)),
                   "pytest exited %d with no summary" % proc.returncode)
    text = "RESULT: %s\n--- output ---\n%s" % (summary, "\n".join(lines[-TAIL:]))
    # 0 all passed, 1 some failed, 5 nothing collected: pytest ran, so the tool worked.
    return ToolOutput(text, proc.returncode in (0, 1, 5), exit_code=proc.returncode)
