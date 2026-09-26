"""
Eval/Regression framework - inspired by OpenUI's eval/ directory.

Runs self-tests against Iter's own tools and transformations to catch regressions.
Stores results in memory/regression_tests.json.

Usage: run(test_name="all") to run all tests, or run(test_name="websearch") for one.

Ported from the browser build: all subtests are now synchronous (this native
iter.py never awaits tool run() functions), and the metta/shell/screenshot
subtests point at this build's native equivalents. The MeTTa subtest requires
the journaled Hyperon AtomSpace service to be ready; it fails clearly if the
service or engine dependency is unavailable.
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


def _test_metadata_parity():
    """Diff the new static (no-subprocess) metadata parser against the real
    subprocess-based --invoke path for every real tool and transformation
    file. This is the gate that must pass before load_tools() or
    load_transformation_descriptions() are ever switched to use the static
    path live -- see tools/_metadata_static.py's module docstring.

    Deliberately shells out to "python iter.py --invoke ..." per file
    (exactly how iter.py's own invoke_dynamic() does it) rather than
    importing iter.py as a module -- importing it directly would fall
    through past the "--invoke" early-exit branch and into iter.py's live
    while True: main loop, hanging this test forever instead of comparing
    metadata."""
    import json
    import os
    import subprocess
    import sys
    import tempfile
    from pathlib import Path
    from tools._metadata_static import static_tool_metadata, static_description, StaticParseError

    # Component code lives in an immutable generation; the host entry point
    # does not. Check this generation, using the canonical host's invoke path.
    component_root = Path(__file__).resolve().parent.parent
    iter_py = Path(os.environ.get("ITER_DIR") or os.getcwd()) / "iter.py"
    if not iter_py.is_file():
        return {"test": "metadata_parity", "pass": False,
                "error": "Canonical runtime entry point is missing: " + str(iter_py)}

    def real_invoke(path, function):
        result_fd, result_file = tempfile.mkstemp(prefix="iter-parity-result-", suffix=".json")
        payload_fd, payload_file = tempfile.mkstemp(prefix="iter-parity-payload-", suffix=".json")
        os.close(result_fd)
        os.close(payload_fd)
        try:
            Path(payload_file).write_text(json.dumps({"args": [], "kwargs": {}}))
            process = subprocess.run(
                [sys.executable, str(iter_py), "--invoke", str(path.resolve()), function, result_file, payload_file],
                timeout=15, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            if process.returncode:
                return {"ok": False, "error": "invoke exited with code " + str(process.returncode)}
            return json.loads(Path(result_file).read_text())
        except Exception as e:
            return {"ok": False, "error": f"invoke subprocess failed: {e}"}
        finally:
            os.unlink(result_file)
            os.unlink(payload_file)

    mismatches = []
    invocation_errors = []
    fallbacks = []
    checked = 0
    compared = 0
    tool_paths = [p for p in sorted((component_root / "tools").glob("*.py")) if not p.name.startswith("_")]
    for path in tool_paths:
        checked += 1
        real = real_invoke(path, "__tool_metadata__")
        if not real.get("ok"):
            invocation_errors.append({"file": str(path), "error": real.get("error", "no valid result")})
            continue
        try:
            static = static_tool_metadata(path)
        except StaticParseError as e:
            # Dynamic descriptions are supported by the loader's real-invoke
            # fallback; a deliberate static-parser rejection is not a defect.
            fallbacks.append({"file": str(path), "reason": str(e)})
            continue
        compared += 1
        if static["description"] != real["result"]["description"]:
            mismatches.append({"file": str(path), "field": "description", "static": static["description"][:120], "real": real["result"]["description"][:120]})
        if static["parameters"] != real["result"]["parameters"]:
            mismatches.append({"file": str(path), "field": "parameters", "static": static["parameters"], "real": real["result"]["parameters"]})
        if static["required"] != real["result"]["required"]:
            mismatches.append({"file": str(path), "field": "required", "static": static["required"], "real": real["result"]["required"]})

    transform_paths = [p for p in sorted((component_root / "transformations").glob("*.py")) if not p.name.startswith("_")]
    for path in transform_paths:
        checked += 1
        real = real_invoke(path, "__description__")
        if not real.get("ok"):
            invocation_errors.append({"file": str(path), "error": real.get("error", "no valid result")})
            continue
        try:
            static = static_description(path)
        except StaticParseError as e:
            fallbacks.append({"file": str(path), "reason": str(e)})
            continue
        compared += 1
        if static != real["result"]:
            mismatches.append({"file": str(path), "field": "description", "static": static[:120], "real": real["result"][:120]})

    return {"test": "metadata_parity", "pass": checked > 0 and not mismatches and not invocation_errors,
            "checked_files": checked, "compared_files": compared,
            "mismatches": mismatches, "invocation_errors": invocation_errors,
            "dynamic_fallbacks": fallbacks}


def _test_metadata_static_fixtures():
    """Exercise synthetic edge cases that don't exist in any real file today
    (f-string DESCRIPTION, *args/**kwargs/keyword-only params, half-written
    syntax) to prove the static parser's fallback behavior is correct, not
    just untested. Fixture files live in tools/ prefixed with _fixture_ or
    _metadata_static_test_probe so they're excluded from the live tool list
    by iter.py's leading-underscore filter, same as any other internal file."""
    from pathlib import Path
    from tools._metadata_static import static_tool_metadata, StaticParseError

    checks = []
    tools_dir = Path(__file__).resolve().parent
    fixtures = ["_metadata_static_test_probe.py", "_fixture_metadata_static_varargs_kwargs.py",
                "_fixture_metadata_static_broken_syntax.py", "_fixture_metadata_static_long_description.py"]
    missing = [name for name in fixtures if not (tools_dir / name).is_file()]
    if missing:
        return {"test": "metadata_static_fixtures", "pass": False, "missing_fixtures": missing}

    # f-string DESCRIPTION must raise StaticParseError (not silently succeed
    # with a wrong/partial value).
    try:
        static_tool_metadata(tools_dir / "_metadata_static_test_probe.py")
        checks.append({"case": "fstring_description", "pass": False, "detail": "expected StaticParseError, got a result instead"})
    except StaticParseError:
        checks.append({"case": "fstring_description", "pass": True})
    except Exception as e:
        checks.append({"case": "fstring_description", "pass": False, "detail": f"wrong exception type: {type(e).__name__}: {e}"})

    # Variadic arguments cannot be represented as named JSON properties;
    # keyword-only parameters remain exposed and defaults remain optional.
    try:
        result = static_tool_metadata(tools_dir / "_fixture_metadata_static_varargs_kwargs.py")
        expected = ["a", "c"]
        expected_required = ["a"]
        checks.append({
            "case": "varargs_kwargs",
            "pass": result["parameters"] == expected and result["required"] == expected_required,
            "got": result,
            "expected": {"parameters": expected, "required": expected_required},
        })
    except Exception as e:
        checks.append({"case": "varargs_kwargs", "pass": False, "detail": f"{type(e).__name__}: {e}"})

    # Broken/half-written syntax must raise StaticParseError, not crash the
    # whole load_tools() loop.
    try:
        static_tool_metadata(tools_dir / "_fixture_metadata_static_broken_syntax.py")
        checks.append({"case": "broken_syntax", "pass": False, "detail": "expected StaticParseError, got a result instead"})
    except StaticParseError:
        checks.append({"case": "broken_syntax", "pass": True})
    except Exception as e:
        checks.append({"case": "broken_syntax", "pass": False, "detail": f"wrong exception type: {type(e).__name__}: {e}"})

    # Long DESCRIPTION must be truncated with the exact same marker text
    # iter.py's dynamic_worker() uses.
    try:
        result = static_tool_metadata(tools_dir / "_fixture_metadata_static_long_description.py")
        ok = len(result["description"]) <= 500 + len(" [DESCRIPTION TRUNCATED]") and result["description"].endswith(" [DESCRIPTION TRUNCATED]")
        checks.append({"case": "long_description_truncation", "pass": ok, "got_len": len(result["description"]), "got_tail": result["description"][-40:]})
    except Exception as e:
        checks.append({"case": "long_description_truncation", "pass": False, "detail": f"{type(e).__name__}: {e}"})

    return {"test": "metadata_static_fixtures", "pass": all(c["pass"] for c in checks), "checks": checks}


DESCRIPTION = "Run regression tests on Iter's tools and transformations. Args: test_name (str, default 'all'). Returns per-check pass/fail and duration. The suite can take up to 180s; partial progress is saved in memory/regression_tests.json. This tests runtime tools, not completion of an app build."


def run(test_name="all"):
    import time
    from pathlib import Path
    from iterbrow_runtime.atomspace_store import _atomic_json

    tests = {
        "websearch": _test_websearch,
        "metta": _test_metta,
        "shell": _test_shell,
        "screenshot": _test_screenshot,
        "chroma_query": _test_chroma,
        "preview": _test_preview,
        "metadata_parity": _test_metadata_parity,
        "metadata_static_fixtures": _test_metadata_static_fixtures,
    }
    if test_name != "all" and test_name not in tests:
        return json.dumps({"error": "unknown test: " + test_name})
    names = [test_name] if test_name != "all" else [
        "screenshot", "chroma_query", "preview", "websearch", "metta", "shell",
        "metadata_parity", "metadata_static_fixtures"]
    out = {"ts": time.time(), "t": [], "complete": False, "pass": False, "running": None}

    def save_progress():
        try:
            _atomic_json(Path("memory/regression_tests.json"), out)
        except OSError as error:
            out["report_error"] = str(error)

    for name in names:
        out["running"] = name
        save_progress()
        started = time.monotonic()
        try:
            result = tests[name]()
        except Exception as error:
            result = {"test": name, "pass": False, "error": type(error).__name__ + ": " + str(error)}
        result["seconds"] = round(time.monotonic() - started, 3)
        out["t"].append(result)
        save_progress()
    out.update(complete=True, running=None, **{"pass": all(test.get("pass") is True for test in out["t"])})
    save_progress()
    return json.dumps(out)
