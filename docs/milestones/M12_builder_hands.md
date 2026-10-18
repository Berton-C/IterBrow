# Milestone 12 — The builder's hands: Iter can act, edit, and run tests

Status: **scoped 2026-10-18**. Base: M6–M11. Tests: `tests/test_m12_*.py`, `tests/e2e/test_m12_loop.py`;
helpers in `tests/m12_support.py`. `tests/semantic_tool_runner.py` now reports a `ToolOutput`'s execution state on success too
(the A3 tests read it). Every test starts `@pending("M12-xx")`; remove the decorator as each
passes. `M12_IMPLEMENTED` is keyed on `iter/tools/read_file.py` (B1, the first file this milestone creates).

## Why (the audit, 2026-10-18)

Berton asked what blocks Iter from being an excellent coder and app builder. Three sources: Iter's own
learned beliefs on his Mac (`nace_beliefs.metta`), the code paths, and what we watched Iter do this week.
Findings, each verified in code:

1. **Iter's hands are tied by its own gate.** `iter/capability_lifecycle.metta:86-90` hard-quarantines
   `browser_click`, `browser_type`, `browser_cdp` (plus `lm_studio_chat`, `museum_vote`) on data from
   2026-09-14 — the week `browser_cdp` had a `TypeError` bug in its own wrapper (fixed in 1acd044) — and
   `METTA_GATE_MODE` defaults to `enforce` (`main.js:603`, `_metta_gate.py:168`), so every call to them
   has been vetoed before it ran. Vetoed calls are never scored (`iter.py:886-887`,
   `tool_reliability_tracker.py:304-306`), so a quarantined tool can never earn its way back. Iter has
   not been able to click or type in a page it built since September. This contradicts the standing
   principle that nothing gates or vetoes Iter except the person's own locks and switches.
2. **No file tools.** There is no read, write, edit, list or grep tool. Code is written through `shell`
   heredocs, the `python` tool's `open()`, or `self_improve apply`, which compiles every target as
   Python and silently reverts an `.html`/`.js`/`.css` write (`self_improve.py:242-253, 481-497`).
   `reprogramming.txt:29` tells the model to use "editing tools" that do not exist. `shell` has no
   `cwd` or timeout argument, and its `python3` is the system one, not the venv (`main.js:581-606`).
3. **Reading code costs too much.** A tool result shows at most 1,800 characters, then 2,000-character
   pages through `read_tool_result` (`tool_results.py:380, 522`), with 10 tool calls per turn.
4. **Iter cannot run the repo's tests.** `eval` runs eight self-checks, not `tests/`; nothing names
   `test_all.sh`; the 180 s tool timeout is shorter than the fast suite; pytest is not in
   `scripts/requirements.txt`; `python -m pytest tests` from `iter/` finds nothing (we watched this:
   "`tests` isn't a package", "Playwright is not installed in this environment").
5. **The reliability metric is wrong in both directions.** A lock refusal counts as a tool failure
   (`_browser_bridge.py:39-40`), while a click that hit nothing counts as a success.
6. **The model never sees how to build an app.** Only the first 6,000 of 63,547 bytes of AGENTS.md are
   injected (`agents_md_inject.py:13`), and that slice contains no app-building guidance; the tool table
   omits `python`, `self_improve`, `app_revision_control`, `read_tool_result`. `apps.py` tells Iter to
   open apps with `browser_new_tab`, which has no app preload. Two app-id regexes disagree
   (`local_apps.py:14` allows `_`, `foundry_projects.py:22` does not).
7. **Verification primitives are weak** (click resolves only `document.querySelector`, no
   scroll-into-view, no wait-for, no post-action state, human-opened tabs steal the agent's target,
   `newTab` returns before load). These are real and concrete, and they are **M13**, not this
   milestone: hands first, then eyes.

This milestone gives Iter working hands: an unblocked, honestly scored tool set; real file tools; a
shell with a working directory and a timeout; a test runner; and guidance that reaches the prompt.

Principles unchanged. Nothing new gates or vetoes Iter: this milestone *removes* a veto (A). The
person's locks still refuse; a refusal is reported as a refusal, never counted as a failure. The
file tools work inside the repository only and never through a symlink. Honest surfaces: a tool that
cannot do what was asked says so in its first line.

## Decisions for Berton (recorded here once made)

- **D1 — gate mode.** A1 makes `advisory` the default. `enforce` stays available by env for anyone who
  wants vetoes. Recommended: yes; the enforce default is why Iter's hands have been tied.
- **D2 — write scope.** B1 lets Iter read and write anywhere inside the repository (the browser's
  own `main.js` and `bridge/` included, which Iter already edits through `shell` today), refusing only
  `.git`, `node_modules`, `iter/.venv` and anything outside. Recommended: yes; a narrower default
  (`iter/` only) is one constant if Berton prefers it.

## Vocabulary

- *Repo root*: the directory holding `main.js`; `ITER_DIR` is its `iter/` (in a packaged install with no
  `main.js` beside it, the repo root is `ITER_DIR` itself). Tool paths are relative to `ITER_DIR` unless
  absolute; `..` is allowed as long as the resolved real path stays inside the repo root.
- *Refused*: a tool result whose execution state is `refused` (a person's lock, a tool's own scope
  rule). `ToolOutput(text, None, state="refused")` — `success=None` is what the reliability tracker
  already skips, so a refusal moves no belief.

---

## A. Untie the hands

**M12-A1 — Gate default.** `METTA_GATE_MODE` defaults to `advisory` in both places (`main.js` env block
and `_metta_gate.py` `run`, and its MODES docstring). `enforce` keeps working when set. The gate's text
for a quarantined capability in advisory mode stays an `[NACE advisory: …]` prefix on a call that runs.

**M12-A2 — Quarantine lifted.** The five `(cap-lifecycle … quarantined)` lines leave
`iter/capability_lifecycle.metta`; the comment block above them is kept and gains two lines saying
when and why they were lifted (data from the broken-wrapper week; the gate no longer vetoes). No
replacement declarations: the lifecycle derives from live confidence as for every other tool.

**M12-A3 — Refusals are not failures.** `iter/tools/_browser_bridge.py` `call()` returns, instead of
raising, when the bridge's error says the tab is locked (`locked by the user`), so every browser tool
that goes through it yields `ToolOutput(<the bridge's message>, None, state="refused")`. Same for the
`not-allowed` / scope refusals the file tools below emit. The tracker is unchanged: it already skips
`success=None`. `browser_navigate` reports a bridge load error as a failure (today it reports success
text over the error).

**M12-A4 — No hidden hands.** `dynamic_tool_budget.PROTECTED_TOOLS` gains the build-and-verify set:
`browser_click`, `browser_type`, `browser_scroll`, `browser_eval`, `browser_read_text`,
`browser_navigate`, `browser_new_tab`, `browser_close_tab`, `read_file`, `write_file`, `edit_file`,
`list_files`, `grep_files`, `run_tests`. Hiding stays for everything else.

## B. Hands

All five file tools share `iter/tools/_files.py`: `repo_root()`, `resolve(path, *, write=False)` →
absolute path or raises `FileScopeError` (message starts `REFUSED:`) when the real path leaves the
repo root, passes through a symlink that leaves it, or (writes only) is under `.git/`, `node_modules/`
or `iter/.venv/`. Text is UTF-8; a write over 2 MB is refused; a read of a non-UTF-8 file says so.

**M12-B1 — `read_file(path, offset="1", limit="200")`.** Returns `path (lines a–b of N)` on the first
line, then numbered lines `   12| text` (right-aligned 5-wide number, `|`, one space). `limit` ≤ 400;
a page is never more than 24,000 characters (lines beyond that are cut and the header says `…cut at
line k`). A missing file → `ERROR: no file at <path>`. A directory → `ERROR: <path> is a directory;
use list_files`.

**M12-B2 — `write_file(path, content)`.** Creates parent directories, writes atomically (temp +
rename), keeps the file's mode if it existed. Returns `WROTE <path> (<n> bytes, <m> lines)`, or
`WROTE <path> (unchanged)` when the content is identical.

**M12-B3 — `edit_file(path, old, new)`.** `old` must occur exactly once; `EDIT-FAILED: old text occurs
<k> times in <path>` (k = 0 or ≥ 2) changes nothing. Success: `EDITED <path> (+<a> −<b> lines)` where
a/b are the line counts of new/old, followed by the edited region with 2 lines of context, numbered
as `read_file` prints them. `new` may be empty (deletion).

**M12-B4 — `list_files(path=".", glob="*", limit="200")`.** Relative paths (to `ITER_DIR`), one per
line, files as `path  <size>` and directories as `path/`, sorted, skipping `.git`, `node_modules`,
`.venv`, `__pycache__`; `glob` is a pathlib pattern (`**/*.py` allowed); more than `limit` →
`… and <k> more`.

**M12-B5 — `grep_files(pattern, path=".", glob="*", limit="100")`.** Python regex, case-sensitive
unless the pattern starts with `(?i)`; `path:line: text` per match, binary and skipped directories
excluded, at most `limit` matches then `… and more`; `NO MATCHES` when none.

**M12-B6 — `shell(cmd, cwd="", timeout="")`.** `cwd` resolves like a file path (must be inside the
repo root; default `ITER_DIR`); `timeout` seconds, default 120, max 170 (the loop's outer bound is
180). Output keeps today's `SUCCESS, RETURN: ` / `FAILED (exit N), RETURN: ` prefix, then stdout, then
a `--- stderr ---` line and stderr when stderr is non-empty. A timeout returns `FAILED (timeout after
<t>s), RETURN: ` with whatever was captured; the process group is killed. The memory-guard `BLOCKED`
path is unchanged. The directory of the Python running Iter (`ITER_DIR/.venv/bin` when the venv exists, else
`os.path.dirname(sys.executable)`) is put first on `PATH` for the child, so `python3` is Iter's own.

**M12-B7 — `run_tests(target="", fast="true")`.** Runs from the repo root with Iter's Python (`ITER_DIR/.venv/bin/python3` when it exists, else `sys.executable`):
`python3 -m pytest <target or tests> -q -p no:cacheprovider --ignore=tests/e2e` (fast) — with
`fast="false"`, the e2e directory is included. `target` may be a path or a `-k` expression (anything
not starting with `tests/` or `tests\` is passed as `-k`). Returns the last 60 lines of output, the
summary line first (`RESULT: 12 passed, 1 skipped in 4.2s`), then `--- output ---`. `iter.py`'s timeout
table gives `run_tests` 900 s. When pytest is missing: `ERROR: pytest is not installed in iter/.venv;
run scripts/setup_python_env.sh` (and `scripts/requirements-dev.txt`, new, lists `pytest`;
`setup_python_env.sh` installs it when present). Playwright stays a system-python concern (the
harness's choice); tests that need it skip, and the summary shows the skips.

**M12-B8 — `self_improve apply` on a non-Python target** returns `{"error": "self_improve edits Python
components only (tools/, transformations/, channels/); use write_file or edit_file for <path>"}`
without touching the file. (Today it writes, "validates" as Python, and reverts.)

## C. Guidance that reaches the prompt

**M12-C1 — AGENTS.md "Building and changing code".** A section of at most 1,800 characters placed
directly after the title block of `iter/AGENTS.md` (so it lands inside the injected 6,000), covering:
the five file tools and when to use `edit_file` over `write_file`; `shell` with `cwd`/`timeout`;
`run_tests` and reading its first line; where apps live (plain app `iter/<id>/index.html`, Foundry
project `iter/apps/<id>/app.json` + `src/`), and that a plain app opened from the Apps menu runs with
the app preload while a tab opened by URL does not; verify in the page with `browser_eval`, never from
a screenshot alone (already in the file; keep one line). The tool table gains rows for `read_file`,
`write_file`, `edit_file`, `list_files`, `grep_files`, `run_tests`, `python`, `self_improve`,
`read_tool_result`. `reprogramming.txt:29` names the real tools.

**M12-C2 — One app-id rule.** `local_apps.py` uses the same id regex as `foundry_projects.py`
(`^[a-z][a-z0-9-]{0,62}$`); `main.js` `plainAppDir` mirrors it. `tools/apps.py` says how to open an app
honestly: from the Apps menu (or `browser_navigate` to the file URL, which runs it without the app
preload — M13 adds `browser_open_app`).

**M12-C3 — README rows corrected**: `self_improve` and `revision_control` rows say activation runs in
the ordinary loop without a PWQ card (what the code does), and the tool catalog gains the new tools.

## D. End-to-end

**M12-D1** — through the real loop (fake model, no Electron): `write_file` a plain app
(`buildertest/index.html`) → `read_file` shows the numbered page → `edit_file` changes one line →
`grep_files` finds the new text → `write_file` a tiny pytest file under `tests/` of the run root and
`run_tests` on it reports `RESULT: 1 passed` → `browser_click` (no bridge in the harness) comes back as
a real bridge error, **not** `Tool execution blocked by reasoning substrate`. The experience shows
the file tools' results verbatim (each under the 4,500-character wire limit).

## E. Done means

`scripts/test_all.sh` (full, including e2e) green with every `@pending` removed; `node -e` syntax check;
the reliability tracker and courier unchanged (`git diff --stat` shows neither); `iter/.venv` untouched.
AGENTS.md's tool table matches `ls iter/tools` for every tool this milestone adds. The implementation
notes at the top of this file record any deviation.

## Next (M13 — the builder's eyes)

Verification primitives from the audit: `browser_wait_for(selector|text|url, timeout)`; click/type
that scroll into view, check visibility and focus, and return post-action state (`url`, `title`,
active element, matched element's text/value); clear "invalid CSS selector" errors; optional `tab_id`
on click/type/scroll/eval; `newTab` waits for load; human-opened tabs and session restore never steal
the agent's target; `browser_tabs` shows `locked`, `app`, `attached`; `browser_open_app(app_id)`
(the bridge's `openApp`) and `app_probe` (the bridge's `inspectApp`) as tools; `browser_cdp` attach
error explained when DevTools is open. Then the beliefs recover on their own: with A1–A3 every call is
scored, and NAL revision moves `f` within a handful of successes.
