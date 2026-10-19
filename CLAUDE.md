# IterBrow — how we build here

IterBrow is an Electron browser (`main.js`, `bridge/`, `renderer/`) hosting Iter, a Python agent (`iter/`).
Berton owns it (github.com/Berton-C/IterBrow). His Mac is the source of truth; family installs (Bright,
Haley) pull from origin. This file is the standing brief for any session that changes the code. A
milestone's own design lives in its spec, `docs/milestones/Mxx_*.md`.

## Rules that do not change between milestones

- **Nothing gates or vetoes Iter.** Only the person's own locks (🔒 tabs) and switches refuse anything. A
  transformation may add a note to the system prompt; it never removes a tool, refuses a `send`, or blocks
  a call. The MeTTa gate's default is `advisory`; `enforce` is opt-in by env only.
- **Refusals are not failures.** A lock or a tool's own scope rule returns a `ToolOutput` with
  `success=None` (`state="refused"`); bad input is `state="invalid_input"`. Neither moves a belief.
- **Don't change NACE's tracker or courier, or episodic memory** (`iter/transformations/
  tool_reliability_tracker.py`, `nace_courier.py`; `tests/test_m12_untie.py` pins them).
- **The Soul is values and paraconsistent pairs, not rules.** Pattern text enters Python only through
  the lens (`iterbrow_runtime/soul_lens.py`); never hard-code the nine patterns in Python.
- **A feature that is off leaves no trace**: no files, no menu items, no prompt text.
- **Never commit `iter/.venv`**, `.runtime/` state, or anything under `.gitignore`.
- **Pushes are Berton's.** Commit; never push. No git tool for Iter: copies of IterBrow must not push.
- Token/context limits are settled (45k ceiling); don't re-tune them.
- Honest surfaces: a tool whose action could not happen as asked says so in its first line.

## Building a milestone

Specs are written to be implemented section by section. Each comes with `@pending("Mxx-yy")` tests
(`tests/test_mxx_*.py`, maybe `tests/e2e/test_mxx_*.py`) and a support module `tests/mxx_support.py`.
**The tests are the acceptance criteria; the spec explains them.**

1. Read the whole spec first: Why, Decisions, Test seams, Vocabulary, every section's Build notes, and
   "Not in this milestone". Then read the support module and the section's tests, then the code they
   touch (the Build notes name it).
2. For each section, in order: implement it, remove that section's `@pending` decorators, run
   `scripts/check_section.sh Mxx-Y` until it passes with 0 markers left, then commit.
3. After the last section run `scripts/test_all.sh` (unit ≈ 7 min, e2e ≈ 30 min) and fix what it finds.
4. Finish with the spec's Status line and an **Implementation notes** block at the top: what deviated and
   why, numbers the spec asks you to record, and anything Berton must do on the Mac.

If a test looks wrong rather than the code, read the spec line it cites first. If it is still wrong, fix
the test, and say so in the commit message and the implementation notes. Never bend the code to a wrong
test, and never delete a test to make a section pass.

Prefer the smallest change that meets the spec. Match the style around you: existing helpers
(`iter/tools/_files.py`, `_browser_bridge.py`, `iterbrow_runtime/tool_results.py`), output formats other
tools already use, and the comment style that cites the milestone item (`# M14-B1: …`).

## Commits

- One commit per section: `Mxx-Y: <what it gives the person>` (for example, `M14-B: snapshots and
  rollback`). The body lists the items and any deviation.
- Author: `git -c user.name="Berton" -c user.email="laxness.02idol@icloud.com" commit …`, plus the session's
  attribution lines. Iter's own work is committed as `-c user.name=Iter -c user.email=iter@iterbrow.local`.

## Where things are

- `iter/iter.py`: the loop. Tools are `iter/tools/*.py` (`DESCRIPTION` + `run`), loaded each cycle.
  Underscore files are helpers. `MAX_TOOLS` and `PROTECTED_TOOL_NAMES` are here, and
  `tests/test_tool_cap.py` guards them.
- `iter/transformations/*.py`: `transform(messages, tools)`, run every cycle, in name order.
  `dynamic_tool_budget.PROTECTED_TOOLS` is the never-hide list; new build or verify tools join it and
  `PROTECTED_TOOL_NAMES`.
- `iter/AGENTS.md`: Iter's own guide. Only the first 6,000 chars reach the prompt
  (`agents_md_inject.py`). Its Tool Inventory table and README's tables are generated from each tool's
  `DESCRIPTION`.
- `bridge/browser_bridge_server.js` (`buildMethods`, exported for tests), `bridge/tab_manager.js`,
  `bridge/page_scripts.js` (pure page expressions).
- Testing without Electron:
  - page scripts run in Playwright Chromium;
  - bridge methods run in node over a fake tab manager (`m13_support.bridge_call`);
  - tools run in a throwaway ITER_DIR (`m12_support.run_tool`), with a fake bridge socket where they need
    one (`m13_support.fake_bridge`);
  - the e2e harness (`tests/e2e/harness.py`) runs the real loop with a scripted fake model.
- Python: `iter/.venv/bin/python3` (`scripts/setup_python_env.sh`; dev deps in
  `scripts/requirements-dev.txt`).

## Delivering to Berton's Mac

When the session is linked to the Mac (the repo is `$HOME/mnt/IterBrow` through the device bridge;
`/Users/bcb/Documents/ClarityOmega/IterBrow` on disk), send commits as a git bundle:

```
git bundle create /mnt/user-data/outputs/<name>.bundle <mac-head>..main
# device_commit_files → /Users/bcb/Documents/ClarityOmega/IterBrow/.runtime-transfer/<name>.bundle
cd "$HOME/mnt/IterBrow" && rm -f .git/index.lock && git fetch -q .runtime-transfer/<name>.bundle main:refs/bundles/x \
  && git merge -q --ff-only refs/bundles/x && git update-ref -d refs/bundles/x && rm -rf .runtime-transfer
```

Before you build, bring the cloud clone up to the Mac's head the same way in reverse, so Iter's own
commits on the Mac are never lost. Berton pushes (`git push origin main`). Family installs run
`git pull --ff-only origin main && ./install.sh repair`.
