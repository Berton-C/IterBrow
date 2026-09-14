"""
Eval/Regression framework - inspired by OpenUI's eval/ directory.

Runs self-tests against Iter's own tools and transformations to catch regressions.
Stores results in memory/regression_tests.json.

Usage: run(test_name="all") to run all tests, or run(test_name="websearch") for one.

Ported from the browser build: all subtests are now synchronous (this native
iter.py never awaits tool run() functions), and the metta/shell/screenshot
subtests point at this build's native equivalents. The metta subtest requires
SWI-Prolog 9.3+ and `pymetta[engine]` to be installed (see README.md) — if
those aren't set up on this machine yet, that subtest fails with a clear
import error rather than silently passing.
"""

import json


def _test_websearch():
    """Test websearch returns results."""
    try:
        from tools.websearch import run as ws_run
        result = ws_run("hello world", 3)
        data = json.loads(result)
        return {"test": "websearch", "pass": len(data) > 0, "results": len(data)}
    except Exception as e:
        return {"test": "websearch", "pass": False, "error": str(e)}


def _test_metta():
    """Test MeTTa evaluation works."""
    try:
        from tools.metta import run as metta_run
        result = metta_run("(+ 1 2)")
        return {"test": "metta", "pass": "3" in str(result), "result": str(result)[:80]}
    except Exception as e:
        return {"test": "metta", "pass": False, "error": str(e)}


def _test_shell():
    """Test shell access works."""
    try:
        from tools.shell import run as shell_run
        result = shell_run("echo iter_test_ok")
        return {"test": "shell", "pass": "iter_test_ok" in str(result), "result": str(result)[:80]}
    except Exception as e:
        return {"test": "shell", "pass": False, "error": str(e)}


def _test_screenshot():
    """Test screenshot capture works (requires the Iter Browser bridge to be attached to a tab)."""
    try:
        from tools.browser_screenshot import run as ss_run
        result = ss_run()
        return {"test": "screenshot", "pass": result is not None and "SCREENSHOT" in str(result)}
    except Exception as e:
        return {"test": "screenshot", "pass": False, "error": str(e)}


def _test_chroma():
    """Test chroma_db query works."""
    try:
        from tools.chroma_query import run as cq_run
        result = cq_run("test query", "1")
        return {"test": "chroma_query", "pass": result is not None, "result": str(result)[:80]}
    except Exception as e:
        return {"test": "chroma_query", "pass": False, "error": str(e)}


def _test_preview():
    """Test preview tool renders HTML."""
    try:
        from tools.preview import run as prev_run
        result = prev_run("<h1>Test Render</h1><p>Hello from eval</p>", 400, 200)
        marker = "__ITER_BROWSER_SCREENSHOT__ "
        idx = result.find(marker)
        json_part = result[:idx] if idx != -1 else result
        data = json.loads(json_part)
        return {"test": "preview", "pass": data.get("has_content", False), "result": data}
    except Exception as e:
        return {"test": "preview", "pass": False, "error": str(e)}


DESCRIPTION = "Run regression tests on Iter's tools and transformations. Args: test_name (str, default 'all'). Returns JSON with pass/fail results."


def run(test_name="all"):
    tests = {
        "websearch": _test_websearch,
        "metta": _test_metta,
        "shell": _test_shell,
        "screenshot": _test_screenshot,
        "chroma_query": _test_chroma,
        "preview": _test_preview,
    }
    if test_name != "all":
        if test_name not in tests:
            return json.dumps({"error": "unknown test: " + test_name})
        results = [tests[test_name]()]
    else:
        results = []
        for name in ["screenshot", "chroma_query", "preview", "websearch", "metta", "shell"]:
            results.append(tests[name]())
    out = {"ts": __import__("time").time(), "t": results}
    try:
        with open("memory/regression_tests.json", "w") as f:
            f.write(json.dumps(out))
    except Exception:
        pass
    return json.dumps(out)
