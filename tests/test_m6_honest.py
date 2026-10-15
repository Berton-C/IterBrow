#!/usr/bin/env python3
"""M6-D1..D3: the theater is gone, the docs match the code, the dashboard shows the Soul honestly.

Spec: docs/milestones/M6_soul_base.md section D.
"""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m6_support import pending, m6_root, require_m6, ITER_SRC, REPO  # noqa: E402

LEGACY_FILES = ["tools/soul_eval.py", "tools/_test_soul_eval_stages.py", "tools/_test_all_stages_combined.py",
                "tools/test_soul_absent.py", "tools/_test_soul_absent.py", "tools/_test_stage4_lock.py",
                "tools/soul_skill_registry.py", "tools/_soul_skill_registry.py",
                "transformations/soul_check.py", "transformations/soul_voice.py", "transformations/skill_bundles.py"]
LEGACY_STATE = ["memory/soul_state.json", "memory/soul_gate_log.json", "memory/soul_calibration.json", "memory/soul_skills.json"]
FORBIDDEN_IN_AGENTS_MD = ["4-Channel Evaluation Engine", "Aliveness Gate", "Paraconsistency HALT", "space.metta",
                          "Value Atoms (space.metta)", "Core Values (9)", "VALUE_KEYWORDS", "soul_eval(action=",
                          "soul_skill_registry", "Skill Registry:", "Compass States:", "Calibration:"]


class RemovalTests(unittest.TestCase):
    """M6-D1"""

    def test_legacy_soul_code_is_gone(self):
        for rel in LEGACY_FILES:
            self.assertFalse((ITER_SRC / rel).exists(), rel)
        self.assertTrue((ITER_SRC / "tools" / "soul_lock.py").exists(), "Soul Lock stays (it protects the courier write)")
        self.assertTrue((ITER_SRC / "transformations" / "soul_presence.py").exists())
        self.assertTrue((ITER_SRC / "tools" / "soul_reflect.py").exists())

    def test_nothing_reads_the_legacy_state_files_any_more(self):
        offenders = []
        for folder in ("tools", "transformations", "iterbrow_runtime"):
            for path in (ITER_SRC / folder).glob("*.py"):
                text = path.read_text(encoding="utf-8")
                for name in ("soul_state.json", "soul_gate_log.json", "soul_calibration.json", "soul_skills.json"):
                    if name in text and "legacy_migration" not in path.name and "soul_migration" not in path.name:
                        offenders.append("%s/%s -> %s" % (folder, path.name, name))
        self.assertEqual(offenders, [])

    def test_first_start_archives_legacy_state_once(self):
        """The AtomSpace service (where backfills run) moves the legacy files aside, idempotently."""
        r = m6_root("m6mig")
        self.addCleanup(r.close)
        memory = Path(r.root) / "memory"
        memory.mkdir(exist_ok=True)
        for rel in LEGACY_STATE:
            (Path(r.root) / rel).write_text('{"legacy": true}')
        r.start()
        for rel in LEGACY_STATE:
            self.assertFalse((Path(r.root) / rel).exists(), rel)
        archives = sorted((Path(r.root) / "backups").glob("soul-legacy-*"))
        self.assertEqual(len(archives), 1, archives)
        self.assertEqual(sorted(p.name for p in archives[0].iterdir()), sorted(Path(p).name for p in LEGACY_STATE))
        log = r.service_log.read_text()
        self.assertIn("soul migration: legacy files archived to", log)
        r.stop()
        r.start()
        self.assertEqual(len(sorted((Path(r.root) / "backups").glob("soul-legacy-*"))), 1, "second start archives nothing")
        self.assertEqual(r.service_log.read_text().count("soul migration: legacy files archived"), 1)

    def test_prompt_has_no_old_soul_blocks(self):
        """Run every transformation the loop would (alphabetical, non-underscore) on a base prompt."""
        r = m6_root("m6prompt")
        self.addCleanup(r.close)
        r.start()
        code = """
import sys, json, os, importlib.util
root = sys.argv[1]; os.chdir(root); sys.path.insert(0, root)
msgs = [{'role': 'system', 'content': 'base'}, {'role': 'user', 'content': 'hello'}]
names = sorted(n for n in os.listdir('transformations') if n.endswith('.py') and not n.startswith('_'))
for n in names:
    spec = importlib.util.spec_from_file_location(n[:-3], os.path.join('transformations', n))
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m); msgs, _ = m.transform(msgs, [])
    except Exception as e:
        print('SKIP', n, type(e).__name__, file=sys.stderr)
print(json.dumps(msgs))
"""
        proc = subprocess.run([sys.executable, "-c", code, str(r.root)], env=r.env(), capture_output=True, text=True, timeout=300)
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        text = "\n".join(m["content"] for m in json.loads(proc.stdout.strip().splitlines()[-1]) if m["role"] == "system")
        for stale in ("## Soul\n", "ALIVE", "SILENT", "Core Values", "clarity:", "stewardship:", "VALUE_KEYWORDS", "Skill Bundles"):
            self.assertNotIn(stale, text, stale)
        self.assertEqual(text.count("## Soul ("), 1, "defaults (forks+brief on) give exactly one presence block")


class AgentsMdTests(unittest.TestCase):
    """M6-D2"""

    def test_soul_section_claims_only_what_exists(self):
        text = (ITER_SRC / "AGENTS.md").read_text(encoding="utf-8")
        start = text.index("## Soul")
        end = text.find("\n## ", start + 1)
        section = text[start:end if end > 0 else None]
        for phrase in FORBIDDEN_IN_AGENTS_MD:
            self.assertNotIn(phrase, section, phrase)
        for required in ("docs/soul/SOUL_IN_THE_FOUNDRY.md", "docs/soul/SOUL_FIDELITY_AUDIT.md", "soul_settings.json",
                         "seeds/soul_kernel.metta", "soul-choice", "card", "NACE telemetry"):
            self.assertIn(required, section, required)
        self.assertLess(len(section), 6000, "AGENTS.md is injected capped at 6000 chars; the section must stay short")

    def test_bridges_and_courier_are_documented_as_nace_telemetry(self):
        text = (ITER_SRC / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("NACE telemetry", text)
        for bridge in ("attention_stewardship_bridge", "connection_depth_bridge", "time_coherence_bridge"):
            self.assertIn(bridge, text)
        # The old "9 Compass Patterns reinterpretation" header must not present the bridges as the Soul.
        self.assertNotIn("Flourishing Reinterpretation of the 9 Compass Patterns", text)


class DashboardTests(unittest.TestCase):
    """M6-D3"""

    def test_authority_counts_include_soul_choices_from_atoms(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("dash", ITER_SRC / "transformations" / "dashboard_atomspace.py")
        dash = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dash)
        atoms = {
            "state:soul_choice:c1": '(soul-choice "berton" "fork" "c1" "a" 1700000000123)',
            "state:soul_choice:c2": '(soul-choice "berton" "read" "c2" "dismiss" 1700000005000)',
            "state:kb_statement:x": "(kb (--> raven bird) (stv 1.0 0.5))",
        }
        counts = dash.authority_counts(lambda prefix: {k: v for k, v in atoms.items() if k.startswith(prefix)}, derive=lambda: [])
        self.assertEqual(counts["soul_choices"], 2)
        self.assertEqual(counts["soul_last"], {"kind": "read", "pick": "dismiss", "at": 1700000005000})
        empty = dash.authority_counts(lambda prefix: {}, derive=lambda: [])
        self.assertEqual(empty["soul_choices"], 0)
        self.assertIsNone(empty["soul_last"])

    def test_rendered_page_has_a_soul_card_and_derived_cache_keyed_by_statements(self):
        r = m6_root("m6dash")
        self.addCleanup(r.close)
        r.start()
        code = ("import sys, json, importlib.util; spec = importlib.util.spec_from_file_location('t', sys.argv[1]);"
                "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); m.transform([], [])")

        def render():
            subprocess.run([sys.executable, "-c", code, str(Path(r.root) / "transformations" / "dashboard_atomspace.py")],
                           cwd=str(r.root), env=r.env(), check=True, timeout=120)
            return (Path(r.root) / "dashboard_atomspace.html").read_text(encoding="utf-8")

        html = render()
        self.assertIn("no Soul activity yet", html)
        cache = Path(r.root) / "transformations" / ".runtime" / "dashboard_kb_cache.json"
        first = json.loads(cache.read_text())
        self.assertIn("statements_digest", first, "the derived cache is keyed by the kb statements, not the commit")
        # A NACE write (not a kb statement) must not invalidate the derived cache.
        r.call("transact", {"operations": [{"op": "upsert", "key": "state:nace_belief:cap-efficacy:shell",
                                            "atom": "(cap-efficacy shell (stv 0.9 0.8))"}], "actor": "test", "source": "test"})
        render()
        self.assertEqual(json.loads(cache.read_text())["statements_digest"], first["statements_digest"])
        self.assertEqual(json.loads(cache.read_text()).get("computed_at"), first.get("computed_at"))
        # A choice shows up in the Soul card.
        r.call("transact", {"operations": [{"op": "upsert", "key": "state:soul_choice:c1",
                                            "atom": '(soul-choice "berton" "fork" "c1" "a" 1700000000123)'}],
                            "actor": "person", "source": "sidebar"})
        html = render()
        self.assertNotIn("no Soul activity yet", html)
        data = json.loads(html.split("<!--counts:", 1)[1].split("-->", 1)[0])
        self.assertEqual(data["soul_choices"], 1)
        self.assertEqual(data["soul_last"]["pick"], "a")


if __name__ == "__main__":
    unittest.main()
