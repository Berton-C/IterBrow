"""
Static (no-subprocess) metadata extraction for tools/ and transformations/ files.

Mirrors iter.py's dynamic_worker() behavior for the "__tool_metadata__" and
"__description__" pseudo-functions -- WITHOUT executing the target file.
Reads the file's source text and parses its AST instead of importing/running it.

NOT wired into iter.py's live load_tools() / load_transformation_descriptions()
yet. This module exists purely to be verified -- see tools/eval.py's
"metadata_parity" test -- before any live call site changes. Nothing in
iter.py's main loop imports or calls anything in this file today.

Design notes (see StaticParseError contract):
  - Any file this module can't confidently parse raises StaticParseError.
    The caller is expected to fall back to the real subprocess-based
    invoke_dynamic(path, "__tool_metadata__" / "__description__") for that
    one file -- i.e. today's exact existing behavior -- rather than guess.
  - Parameter extraction order mirrors inspect.signature()'s parameter order
    exactly: positional-only, positional-or-keyword, *args, keyword-only,
    **kwargs. Two real files in this codebase (tools/self_improve.py,
    tools/_self_improve.py) use **kwargs, so this order is not theoretical.
  - Description truncation mirrors iter.py's MAX_TOOL_DESCRIPTION_CHARS
    constant and its " [DESCRIPTION TRUNCATED]" marker exactly, for the
    "__tool_metadata__" path only -- "__description__" (used for
    transformations) is never truncated, matching dynamic_worker()'s two
    separate branches today.
"""
import ast

# Kept in sync with iter.py's constant of the same name. If iter.py's value
# ever changes, this one must be updated too -- the parity test will catch
# a drift immediately since it diffs against the real subprocess output.
MAX_TOOL_DESCRIPTION_CHARS = 500
TRUNCATION_MARKER = " [DESCRIPTION TRUNCATED]"


class StaticParseError(Exception):
    """Raised when a file can't be statically parsed with full confidence.
    Callers must treat this as a signal to fall back to the real
    subprocess-based invoke_dynamic() path for that one file, not as a
    tool-is-broken error."""


def _load_tree(path):
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise StaticParseError(f"could not read {path}: {error}") from error
    try:
        return ast.parse(source)
    except SyntaxError as error:
        raise StaticParseError(f"syntax error in {path}: {error}") from error


def _extract_description(tree, path):
    description = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "DESCRIPTION"
            for target in node.targets
        ):
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, TypeError) as error:
                raise StaticParseError(
                    f"DESCRIPTION in {path} is not a static string literal "
                    f"(f-string, variable, or expression): {error}"
                ) from error
            description = value
    if not isinstance(description, str):
        raise StaticParseError(f"no top-level DESCRIPTION string literal found in {path}")
    return description


def _extract_function_parameters(tree, path, func_name):
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            args = node.args
            names = []
            names += [a.arg for a in args.posonlyargs]
            names += [a.arg for a in args.args]
            if args.vararg is not None:
                names.append(args.vararg.arg)
            names += [a.arg for a in args.kwonlyargs]
            if args.kwarg is not None:
                names.append(args.kwarg.arg)
            return names
    raise StaticParseError(f"no top-level def {func_name}(...) found in {path}")


def static_tool_metadata(path):
    """Mirrors dynamic_worker()'s "__tool_metadata__" branch exactly,
    including MAX_TOOL_DESCRIPTION_CHARS truncation + marker.
    Returns {"description": str, "parameters": [str, ...]} -- same shape
    load_tools() already expects from invoke_dynamic()."""
    tree = _load_tree(path)
    description = _extract_description(tree, path)
    parameters = _extract_function_parameters(tree, path, "run")
    if len(description) > MAX_TOOL_DESCRIPTION_CHARS:
        description = description[:MAX_TOOL_DESCRIPTION_CHARS] + TRUNCATION_MARKER
    return {"description": description, "parameters": parameters}


def static_description(path):
    """Mirrors dynamic_worker()'s "__description__" branch exactly (no
    truncation -- that branch never truncates today)."""
    tree = _load_tree(path)
    return _extract_description(tree, path)


# --------------------------------------------------------------------
# mtime-keyed cache -- iter.py's main loop runs as one long-lived process
# (see iter.py's "while True:" loop), so a plain module-level dict here
# persists across cycles for free: an unchanged file is re-parsed exactly
# once, then served from cache until its mtime changes. Errors are never
# cached -- a broken file is cheap to re-check and we want a fix on disk
# picked up on the very next cycle, not stuck behind a stale cached error.
_tool_metadata_cache = {}   # key -> (mtime, {"description":..., "parameters":...})
_description_cache = {}    # key -> (mtime, str)


def get_static_tool_metadata_cached(path):
    key = str(path.resolve())
    mtime = path.stat().st_mtime
    cached = _tool_metadata_cache.get(key)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    result = static_tool_metadata(path)  # raises StaticParseError on failure -- not cached
    _tool_metadata_cache[key] = (mtime, result)
    return result


def get_static_description_cached(path):
    key = str(path.resolve())
    mtime = path.stat().st_mtime
    cached = _description_cache.get(key)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    result = static_description(path)  # raises StaticParseError on failure -- not cached
    _description_cache[key] = (mtime, result)
    return result


# --------------------------------------------------------------------
# Shadow mode -- compute the static result alongside the real subprocess
# result every cycle, diff, and log loudly on mismatch. NEVER raises and
# NEVER changes what the caller actually uses -- the real invoke_dynamic()
# result stays authoritative. This exists purely to accumulate real-world
# proof, across your own live usage, before the static path is ever wired
# in as the thing load_tools()/load_transformation_descriptions() actually
# use (that is a separate, later, explicitly-approved step).
SHADOW_LOG_PATH_STR = "transformations/.runtime/metadata_shadow.log"


def shadow_check_tool_metadata(path, real_metadata):
    """Compare the cached static tool-metadata result for `path` against
    `real_metadata` (the dict already returned by invoke_dynamic(path,
    "__tool_metadata__") in load_tools()). Logs to SHADOW_LOG_PATH_STR on
    any mismatch or parse failure; silent on agreement. Best-effort only --
    swallows every exception so a bug here can never affect live tool
    loading."""
    try:
        static_metadata = get_static_tool_metadata_cached(path)
    except StaticParseError as error:
        _log_shadow_issue(path, "__tool_metadata__", f"static parser could not parse a file the real path handles fine: {error}")
        return
    except Exception as error:
        _log_shadow_issue(path, "__tool_metadata__", f"shadow check itself failed: {type(error).__name__}: {error}")
        return
    if static_metadata != real_metadata:
        _log_shadow_issue(path, "__tool_metadata__", f"MISMATCH -- static={static_metadata!r} real={real_metadata!r}")


def shadow_check_description(path, real_description):
    """Same as shadow_check_tool_metadata but for the "__description__"
    path used by load_transformation_descriptions()."""
    try:
        static_value = get_static_description_cached(path)
    except StaticParseError as error:
        _log_shadow_issue(path, "__description__", f"static parser could not parse a file the real path handles fine: {error}")
        return
    except Exception as error:
        _log_shadow_issue(path, "__description__", f"shadow check itself failed: {type(error).__name__}: {error}")
        return
    if static_value != real_description:
        _log_shadow_issue(path, "__description__", f"MISMATCH -- static={static_value!r} real={real_description!r}")


# --------------------------------------------------------------------
# Promotion (live) path -- "verify on first sight". Unlike shadow mode above
# (which always ran the real subprocess and only observed), this is the
# actual gate load_tools()/load_transformation_descriptions() call to decide
# whether the real subprocess is needed AT ALL for a given file this cycle.
#
# Contract:
#   - get_trusted_tool_metadata(path)/get_trusted_description(path) return
#     the cached static result ONLY if this exact (path, mtime) has already
#     been verified equal to a real subprocess result in some prior cycle.
#     Otherwise they return None -- meaning "do the real subprocess call,
#     same as today, then call the matching record_*_verified() below."
#   - record_tool_metadata_verified(path, real_metadata)/
#     record_description_verified(path, real_description) are called right
#     after a real subprocess result comes back. They compute the static
#     result and compare: on a match, this exact (path, mtime) becomes
#     trusted, so the NEXT cycle can skip the subprocess for it. On a
#     mismatch or parse failure, nothing is marked trusted -- the file keeps
#     paying the real subprocess cost every cycle until it's fixed on disk,
#     and the discrepancy is logged loudly so it's visible.
#   - A file's trust is keyed to its exact mtime. Any edit changes the mtime,
#     which immediately un-trusts it -- the very next cycle re-verifies the
#     new content via a real subprocess call before ever trusting it again.
#   - Never raises. Any internal failure here just means "don't trust it",
#     which safely falls back to today's exact existing behavior for that
#     one file.
_trusted_tool_mtimes = {}          # key -> mtime already verified == real result
_trusted_description_mtimes = {}   # key -> mtime already verified == real result


def get_trusted_tool_metadata(path):
    try:
        key = str(path.resolve())
        mtime = path.stat().st_mtime
    except OSError:
        return None
    if _trusted_tool_mtimes.get(key) != mtime:
        return None
    cached = _tool_metadata_cache.get(key)
    if cached is None or cached[0] != mtime:
        return None
    return cached[1]


def record_tool_metadata_verified(path, real_metadata):
    try:
        static_metadata = get_static_tool_metadata_cached(path)
    except StaticParseError as error:
        _log_shadow_issue(path, "__tool_metadata__",
                           f"NOT PROMOTED -- static parser could not parse a file the real path handles fine: {error}")
        return
    except Exception as error:
        _log_shadow_issue(path, "__tool_metadata__",
                           f"NOT PROMOTED -- verify check itself failed: {type(error).__name__}: {error}")
        return
    try:
        key = str(path.resolve())
        mtime = path.stat().st_mtime
    except OSError:
        return
    if static_metadata == real_metadata:
        _trusted_tool_mtimes[key] = mtime
    else:
        _log_shadow_issue(path, "__tool_metadata__",
                           f"NOT PROMOTED -- MISMATCH static={static_metadata!r} real={real_metadata!r}")


def get_trusted_description(path):
    try:
        key = str(path.resolve())
        mtime = path.stat().st_mtime
    except OSError:
        return None
    if _trusted_description_mtimes.get(key) != mtime:
        return None
    cached = _description_cache.get(key)
    if cached is None or cached[0] != mtime:
        return None
    return cached[1]


def record_description_verified(path, real_description):
    try:
        static_value = get_static_description_cached(path)
    except StaticParseError as error:
        _log_shadow_issue(path, "__description__",
                           f"NOT PROMOTED -- static parser could not parse a file the real path handles fine: {error}")
        return
    except Exception as error:
        _log_shadow_issue(path, "__description__",
                           f"NOT PROMOTED -- verify check itself failed: {type(error).__name__}: {error}")
        return
    try:
        key = str(path.resolve())
        mtime = path.stat().st_mtime
    except OSError:
        return
    if static_value == real_description:
        _trusted_description_mtimes[key] = mtime
    else:
        _log_shadow_issue(path, "__description__",
                           f"NOT PROMOTED -- MISMATCH static={static_value!r} real={real_description!r}")


def _log_shadow_issue(path, kind, detail):
    import json as _json
    import time as _time
    from pathlib import Path as _Path
    try:
        log_path = _Path(SHADOW_LOG_PATH_STR)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as f:
            f.write(_json.dumps({"ts": _time.time(), "file": str(path), "kind": kind, "detail": detail}, ensure_ascii=False) + "\n")
    except Exception:
        pass  # logging itself must never raise -- worst case we lose one log line
