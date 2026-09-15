"""Manual verification for dashboard_beliefs_refresh.py -- 2026-09-14.
Run directly: python3 transformations/_test_dashboard_beliefs_refresh.py
from the iter/ directory. Builds a temp cwd shaped like the real iter/ root
(.runtime/pages/beliefs_layer.html + chroma_db/memories.json) so the
module's relative paths resolve exactly like they do for real.
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile

REPO_ITER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE_PATH = os.path.join(REPO_ITER, "transformations", "dashboard_beliefs_refresh.py")

FIXTURE_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>t</title></head><body>
<div class="sub">Founder Toolkit v2 &middot; seeded 2026-09-14 &middot; f/c refreshed 14:17</div>
<div class="card"><h3>H1 &middot; Path-fragility is a recurring bug class</h3>
<div class="meter">f=1.00 c=0.67<div class="bar"><div style="width:100%"></div></div></div></div>
<div class="card"><h3>H2 &middot; NAL-weighted reliability improves tool selection</h3>
<div class="meter">f=1.00 c=0.67<div class="bar"><div style="width:100%"></div></div></div></div>
<div class="card"><h3>H3 &middot; Short proactive updates prevent send-discipline fires</h3>
<div class="meter">f=0.00 c=0.00<div class="bar"><div style="width:0%"></div></div></div></div>
<div class="card"><h3>H4 &middot; websearch: weak for repo discovery</h3>
<div class="meter">f=0.00 c=0.00<div class="bar"><div style="width:0%"></div></div></div></div>
<div class="card"><h3>H5 &middot; The substrate earns leverage by compounding</h3>
<div class="meter">f=0.00 c=0.00<div class="bar"><div style="width:0%"></div></div></div></div>
</body></html>
"""

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS" if cond else "FAIL") + " - " + name + ((" :: " + detail) if detail and not cond else ""))


def load_module_at(tmpdir):
    spec = importlib.util.spec_from_file_location("dashboard_beliefs_refresh", MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ITER_ROOT = tmpdir
    mod.DB_PATH = os.path.join(tmpdir, "chroma_db", "memories.json")
    mod.PAGE_PATH = os.path.join(tmpdir, ".runtime", "pages", "beliefs_layer.html")
    return mod


def write_fixtures(tmpdir, metadatas):
    os.makedirs(os.path.join(tmpdir, ".runtime", "pages"), exist_ok=True)
    os.makedirs(os.path.join(tmpdir, "chroma_db"), exist_ok=True)
    with open(os.path.join(tmpdir, ".runtime", "pages", "beliefs_layer.html"), "w") as f:
        f.write(FIXTURE_HTML)
    ids = ["505c1ac3xxx", "d7615651xxx", "05fbf5bdxxx", "0a901d47xxx", "dc7ca12fxxx"]
    with open(os.path.join(tmpdir, "chroma_db", "memories.json"), "w") as f:
        json.dump({"ids": ids, "metadatas": metadatas}, f)


def main():
    # Test 1: real evidence exists for H1-H4, none yet for H5 -- meters
    # for H3/H4 should move off the stale 0.00/0.00 they shipped with.
    tmpdir = tempfile.mkdtemp()
    try:
        write_fixtures(tmpdir, [
            {"strength": 1.0, "confidence": 0.666667},
            {"strength": 1.0, "confidence": 0.666667},
            {"strength": 1.0, "confidence": 0.666667},
            {"strength": 1.0, "confidence": 0.666667},
            {},
        ])
        mod = load_module_at(tmpdir)
        summary = mod.refresh()
        check("first refresh reports a change", summary.startswith("refreshed"), summary)
        html = open(mod.PAGE_PATH).read()
        check("H3 meter now shows real evidence (was stale 0.00/0.00)",
              html.count("f=1.00 c=0.67") == 4, "expected 4 occurrences (H1,H2,H3,H4)")
        check("H5 meter still honestly 0.00/0.00 (no strength/confidence recorded)",
              "f=0.00 c=0.00" in html)
        check("timestamp line updated off the stale 14:17 snapshot",
              "f/c refreshed 14:17" not in html)

        # Test 2: idempotency -- re-running with no belief changes must be a no-op.
        summary2 = mod.refresh()
        check("second refresh with no belief change is a no-op", summary2.startswith("no-op"), summary2)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Test 3: missing chroma_db/memories.json must fail open, never raise.
    tmpdir = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(tmpdir, ".runtime", "pages"), exist_ok=True)
        with open(os.path.join(tmpdir, ".runtime", "pages", "beliefs_layer.html"), "w") as f:
            f.write(FIXTURE_HTML)
        mod = load_module_at(tmpdir)
        summary3 = mod.refresh()
        check("missing memories.json fails open with no-op", summary3.startswith("no-op"), summary3)
        messages, tools = mod.transform([{"role": "system", "content": "x"}], [])
        check("transform() never raises even without a db file", True)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    failed = [name for name, ok, _ in results if not ok]
    print("\n" + str(len(results) - len(failed)) + "/" + str(len(results)) + " checks passed")
    if failed:
        print("FAILED: " + ", ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
