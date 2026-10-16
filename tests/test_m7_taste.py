#!/usr/bin/env python3
"""M7-A1..A5: taste from choices — the card records what it offered, the reducer folds choices
into taste beliefs, the lens reads them back, the person can forget, two M6 gaps close.

Spec: docs/milestones/M7_soul_personality.md section A.
"""
import json
import os
import re
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m7_support import (pending, m7_root, require_m7, soul_lens, seed_choice, card_atoms, choice_atom,  # noqa: E402
                        run_transformation, write_soul_settings, stv, taste_n, museum_save, museum_get,
                        run_bridge, card, outbox_message, NODE, REPO, ITER_SRC, FEATURES)

SOUL_KEYS = ("state:soul_card:", "state:soul_card_choice:", "state:soul_taste:", "state:soul_dismiss:",
             "state:soul_taste_seen:", "state:soul_felt:")


class CardMetadataTests(unittest.TestCase):
    """M7-A1: the card tool writes soul-card / soul-card-choice atoms and validates patterns against the atoms."""

    def setUp(self):
        self.r = m7_root("m7card")
        self.addCleanup(self.r.close)
        self.r.start()

    def test_card_with_patterns_and_museum_ids_records_its_offer(self):
        write_soul_settings(self.r.root, "berton")
        out = self.r.text("card", kind="fork", title="Which way?", body="Two poles.",
                          choices=[{"id": "a", "label": "Playful", "pattern": "CreativeTranscendence", "museum_id": "comp-aaaaaaaaaaaa"},
                                   {"id": "b", "label": "On time", "pattern": "TimeCoherence"}])
        self.assertTrue(out.startswith("CARD-SENT: card-"), out)
        self.assertNotIn("unrecorded", out)
        card_id = out.split()[1]
        cards = self.r.call("read_atoms", {"prefix": "state:soul_card:"})["atoms"]
        self.assertEqual(cards["state:soul_card:%s" % card_id].split()[:4],
                         ["(soul-card", '"%s"' % card_id, '"fork"', '"berton"'])
        choices = self.r.call("read_atoms", {"prefix": "state:soul_card_choice:%s:" % card_id})["atoms"]
        self.assertEqual(choices["state:soul_card_choice:%s:a" % card_id],
                         '(soul-card-choice "%s" "a" CreativeTranscendence "comp-aaaaaaaaaaaa")' % card_id)
        self.assertEqual(choices["state:soul_card_choice:%s:b" % card_id],
                         '(soul-card-choice "%s" "b" TimeCoherence "-")' % card_id)
        # The sidebar message carries the same metadata.
        outbox = sorted((Path(self.r.root) / ".runtime" / "electron_ui" / "outbox").glob("*.json"))
        message = json.loads(outbox[-1].read_text())
        self.assertEqual(message["card"]["choices"][0]["pattern"], "CreativeTranscendence")
        self.assertEqual(message["card"]["choices"][0]["museum_id"], "comp-aaaaaaaaaaaa")

    def test_unknown_pattern_is_refused_before_anything_is_sent(self):
        before = len(list((Path(self.r.root) / ".runtime" / "electron_ui" / "outbox").glob("*.json"))) if (Path(self.r.root) / ".runtime" / "electron_ui" / "outbox").exists() else 0
        out = self.r.text("card", kind="fork", title="Which way?", body="",
                          choices=[{"id": "a", "label": "x", "pattern": "Velocity"}, {"id": "b", "label": "y"}])
        self.assertTrue(out.startswith("ERROR: unknown pattern"), out)
        after = len(list((Path(self.r.root) / ".runtime" / "electron_ui" / "outbox").glob("*.json"))) if (Path(self.r.root) / ".runtime" / "electron_ui" / "outbox").exists() else 0
        self.assertEqual(before, after)
        self.assertEqual(self.r.call("read_atoms", {"prefix": "state:soul_card:"})["atoms"], {})

    def test_pattern_names_come_from_the_atoms_not_a_python_list(self):
        source = (ITER_SRC / "tools" / "card.py").read_text(encoding="utf-8")
        self.assertNotIn("AgencyBalance", source, "the nine names live in the seed, not in card.py")
        self.assertIn("soul_lens", source)

    def test_card_without_metadata_still_records_the_offer_with_none(self):
        out = self.r.text("card", kind="read", title="Tempo?", body="", choices=["Faster", "Slower"])
        card_id = out.split()[1]
        choices = self.r.call("read_atoms", {"prefix": "state:soul_card_choice:%s:" % card_id})["atoms"]
        self.assertEqual(len(choices), 2)
        for atom in choices.values():
            self.assertIn(" none ", atom)
            self.assertTrue(atom.endswith('"-")'), atom)

    def test_service_down_card_still_goes_out_marked_unrecorded(self):
        write_soul_settings(self.r.root, "berton")
        # The tool runs in a subprocess; the runner's env override is what reaches it.
        out = self.r.text("card", env={"ITER_METTA_SOCKET": "/nonexistent/sock"},
                          kind="fork", title="Which way?", body="", choices=["a", "b"])
        self.assertTrue(out.startswith("CARD-SENT: card-"), out)
        self.assertIn("(unrecorded)", out)

    def test_views_other_than_soul_never_see_card_metadata(self):
        self.r.call("transact", {"operations": card_atoms("card-v", "fork", "berton",
                                                           [("a", "CreativeTranscendence", None), ("b", "TimeCoherence", None)]),
                                 "actor": "iter", "source": "card"})
        for view in ("current", "full", "kb"):
            out = self.r.call("query", {"code": '!(match &self (soul-card-choice "card-v" $c $p $m) $p)', "view": view}, timeout=60)["result"]
            self.assertNotIn("CreativeTranscendence", out, view)
        out = self.r.call("query", {"code": '!(match &self (soul-card-choice "card-v" $c $p $m) $p)', "view": "soul"}, timeout=60)["result"]
        self.assertIn("CreativeTranscendence", out)


@unittest.skipUnless(NODE, "needs node")
class BridgeMetadataTests(unittest.TestCase):
    """M7-A1 (bridge side): validCard keeps pattern/museum_id and drops bad values without failing the card."""

    def test_valid_card_keeps_pattern_and_museum_id_and_drops_junk(self):
        code, stdout, stderr = __import__("m7_support").node("""
const { validCard } = require(%s);
const c = validCard({ id: 'card-1', kind: 'fork', title: 't', choices: [
  { id: 'a', label: 'A', pattern: 'CreativeTranscendence', museum_id: 'comp-aaaaaaaaaaaa' },
  { id: 'b', label: 'B', pattern: { bad: true }, museum_id: 'x'.repeat(65) },
  { id: 'c', label: 'C', pattern: 'has space', museum_id: 7 } ] });
process.stdout.write(JSON.stringify(c));
""" % json.dumps(str(REPO / "bridge" / "chat_bridge.js")))
        self.assertEqual(code, 0, stderr)
        out = json.loads(stdout.strip().splitlines()[-1])
        self.assertEqual(out["choices"][0]["pattern"], "CreativeTranscendence")
        self.assertEqual(out["choices"][0]["museum_id"], "comp-aaaaaaaaaaaa")
        for index in (1, 2):
            self.assertNotIn("pattern", out["choices"][index])
            self.assertNotIn("museum_id", out["choices"][index])


class ReducerTests(unittest.TestCase):
    """M7-A2: choices become taste beliefs, once each; dismissals are counted; nothing else is touched."""

    def setUp(self):
        self.r = m7_root("m7reduce")
        self.addCleanup(self.r.close)
        self.r.start()

    def _tastes(self, person="berton"):
        return self.r.call("read_atoms", {"prefix": "state:soul_taste:%s:" % person})["atoms"]

    def _reduce(self):
        return run_transformation(self.r.root, "soul_taste.py", env_extra={"ITER_METTA_SOCKET": str(self.r.sock)})

    def test_one_pick_makes_two_beliefs_with_nal_truth(self):
        seed_choice(self.r, "berton", "fork", "card-1", "a",
                    [("a", "CreativeTranscendence", None), ("b", "TimeCoherence", None)])
        self._reduce()
        tastes = self._tastes()
        picked = tastes["state:soul_taste:berton:CreativeTranscendence:TimeCoherence"]
        other = tastes["state:soul_taste:berton:TimeCoherence:CreativeTranscendence"]
        self.assertTrue(picked.startswith('(soul-taste "berton" CreativeTranscendence TimeCoherence (stv '), picked)
        self.assertEqual(stv(picked), (1.0, 0.5))
        self.assertEqual(taste_n(picked), 1)
        self.assertEqual(stv(other), (0.0, 0.5))
        self.assertEqual(taste_n(other), 1)
        self.assertIn("state:soul_taste_seen:card-1", self.r.call("read_atoms", {"prefix": "state:soul_taste_seen:"})["atoms"])

    def test_evidence_accumulates_and_each_choice_counts_once(self):
        pair = [("a", "CreativeTranscendence", None), ("b", "TimeCoherence", None)]
        seed_choice(self.r, "berton", "fork", "card-1", "a", pair, at=1)
        seed_choice(self.r, "berton", "fork", "card-2", "a", pair, at=2)
        seed_choice(self.r, "berton", "fork", "card-3", "b", pair, at=3)
        self._reduce()
        self._reduce()  # idempotent: seen markers stop a second fold
        picked = self._tastes()["state:soul_taste:berton:CreativeTranscendence:TimeCoherence"]
        f, c = stv(picked)
        self.assertEqual(taste_n(picked), 3)
        self.assertAlmostEqual(f, 2 / 3, places=2)
        self.assertAlmostEqual(c, 0.75, places=2)
        self.assertEqual(len(self.r.call("read_atoms", {"prefix": "state:soul_taste_seen:"})["atoms"]), 3)

    def test_dismiss_counts_per_kind_and_gives_no_taste(self):
        pair = [("a", "CreativeTranscendence", None), ("b", "TimeCoherence", None)]
        seed_choice(self.r, "bright", "read", "card-1", "dismiss", pair)
        seed_choice(self.r, "bright", "read", "card-2", "dismiss", pair, at=2)
        self._reduce()
        self.assertEqual(self._tastes("bright"), {})
        dismissed = self.r.call("read_atoms", {"prefix": "state:soul_dismiss:bright:"})["atoms"]
        self.assertEqual(dismissed["state:soul_dismiss:bright:read"], '(soul-dismissed "bright" "read" 2)')

    def test_choices_without_card_metadata_are_marked_seen_and_yield_nothing(self):
        self.r.call("transact", {"operations": [{"op": "upsert", "key": "state:soul_choice:card-old",
                                                 "atom": choice_atom("berton", "fork", "card-old", "a")}],
                                 "actor": "person", "source": "sidebar"})
        self._reduce()
        self.assertEqual(self._tastes(), {})
        self.assertIn("state:soul_taste_seen:card-old", self.r.call("read_atoms", {"prefix": "state:soul_taste_seen:"})["atoms"])

    def test_reducer_is_scoped_to_the_person_on_the_choice_and_touches_nothing_else(self):
        nace_before = self.r.call("read_atoms", {"prefix": "state:nace_belief:"})["atoms"]
        kb_before = self.r.call("read_atoms", {"prefix": "state:kb_"})["atoms"]
        seed_choice(self.r, "haley", "fork", "card-h", "b", [("a", "WonderPreservation", None), ("b", "SharedUnderstanding", None)])
        self._reduce()
        self.assertEqual(self._tastes("berton"), {})
        self.assertIn("state:soul_taste:haley:SharedUnderstanding:WonderPreservation", self._tastes("haley"))
        self.assertEqual(self.r.call("read_atoms", {"prefix": "state:nace_belief:"})["atoms"], nace_before)
        self.assertEqual(self.r.call("read_atoms", {"prefix": "state:kb_"})["atoms"], kb_before)

    def test_nothing_new_costs_one_read_and_no_transaction(self):
        status_before = self.r.call("status")
        self._reduce()
        status_after = self.r.call("status")
        self.assertEqual(status_after["commit"], status_before["commit"], "an idle reduce must not commit")


class LensTests(unittest.TestCase):
    """M7-A3: the lens reads taste back; the presence block carries one learned line; reflect names the lean."""

    def setUp(self):
        self.r = m7_root("m7lens")
        self.addCleanup(self.r.close)
        self.r.start()

    def _env(self):
        """Point the lens (read at call time) at this root's service."""
        env = unittest.mock.patch.dict(os.environ, {"ITER_DIR": str(self.r.root), "ITER_METTA_SOCKET": str(self.r.sock)})
        env.start()
        self.addCleanup(env.stop)

    def _taste(self, picked, over, f, c, n, person="berton"):
        self.r.call("transact", {"operations": [{"op": "upsert", "key": "state:soul_taste:%s:%s:%s" % (person, picked, over),
                                                 "atom": '(soul-taste "%s" %s %s (stv %s %s) %d)' % (person, picked, over, f, c, n)}],
                                 "actor": "iter", "source": "soul_taste"})

    def test_taste_and_taste_line_from_atoms(self):
        self._env()
        self._taste("CreativeTranscendence", "TimeCoherence", 0.75, 0.8, 4)
        self._taste("TimeCoherence", "CreativeTranscendence", 0.25, 0.8, 4)
        self._taste("WonderPreservation", "SharedUnderstanding", 1.0, 0.5, 1)  # n=1: not yet a lean
        lens = soul_lens()
        tastes = lens.taste("berton")
        self.assertEqual(tastes[0]["picked"], "CreativeTranscendence")
        self.assertEqual((tastes[0]["f"], tastes[0]["c"], tastes[0]["n"]), (0.75, 0.8, 4))
        line = lens.taste_line("berton")
        self.assertIn("you've leaned CreativeTranscendence over TimeCoherence (3 of 4 forks)", line)
        self.assertNotIn("WonderPreservation", line)
        self.assertNotIn("TimeCoherence over", line)
        self.assertEqual(lens.taste_line("bright"), "")

    def test_dismissals_reach_the_line_only_when_they_dominate(self):
        self._env()
        self.r.call("transact", {"operations": [{"op": "upsert", "key": "state:soul_dismiss:berton:read",
                                                 "atom": '(soul-dismissed "berton" "read" 3)'}],
                                 "actor": "iter", "source": "soul_taste"})
        lens = soul_lens()
        self.assertEqual(lens.dismissals("berton"), {"read": 3})
        self.assertIn("you dismiss most read cards", lens.taste_line("berton"))
        # Four answered read cards outweigh three dismissals.
        for index in range(4):
            self.r.call("transact", {"operations": [{"op": "upsert", "key": "state:soul_choice:card-r%d" % index,
                                                     "atom": choice_atom("berton", "read", "card-r%d" % index, "a")}],
                                     "actor": "person", "source": "sidebar"})
        self.assertNotIn("dismiss", lens.taste_line("berton"))

    def test_presence_block_carries_the_learned_line_and_stays_short(self):
        self._env()
        self._taste("CreativeTranscendence", "TimeCoherence", 0.75, 0.8, 4)
        write_soul_settings(self.r.root, "berton", {"forks": True})
        msgs, _ = run_transformation(self.r.root, "soul_presence.py", env_extra={"ITER_METTA_SOCKET": str(self.r.sock)})
        content = msgs[-1]["content"]
        self.assertEqual(content.count("## Soul ("), 1)
        self.assertIn("Learned: you've leaned CreativeTranscendence over TimeCoherence (3 of 4 forks)", content)
        self.assertLess(len(content) - len("base"), 900)
        # The cap holds in the largest case: every feature on, two leans and a dismissal line.
        self._taste("WonderPreservation", "SharedUnderstanding", 1.0, 0.75, 3)
        self.r.call("transact", {"operations": [{"op": "upsert", "key": "state:soul_dismiss:berton:read",
                                                 "atom": '(soul-dismissed "berton" "read" 5)'}],
                                 "actor": "iter", "source": "soul_taste"})
        write_soul_settings(self.r.root, "berton", {f: True for f in FEATURES}, budget_per_cycle=3, frequency="chatty")
        msgs, _ = run_transformation(self.r.root, "soul_presence.py", env_extra={"ITER_METTA_SOCKET": str(self.r.sock)})
        content = msgs[-1]["content"]
        self.assertEqual(content.count("Learned:"), 1)
        self.assertIn("you dismiss most read cards", content)
        self.assertLess(len(content) - len("base"), 900, "all features on must still fit the cap")
        write_soul_settings(self.r.root, "berton", {f: False for f in ("forks", "brief", "read", "wonder", "felt", "browsing_ally", "margin")})
        msgs, _ = run_transformation(self.r.root, "soul_presence.py", env_extra={"ITER_METTA_SOCKET": str(self.r.sock)})
        self.assertEqual(msgs, [{"role": "system", "content": "base"}], "all off: no trace, learned or not")

    def test_no_learned_line_before_two_forks(self):
        self._env()
        self._taste("CreativeTranscendence", "TimeCoherence", 1.0, 0.5, 1)
        write_soul_settings(self.r.root, "berton", {"forks": True})
        msgs, _ = run_transformation(self.r.root, "soul_presence.py", env_extra={"ITER_METTA_SOCKET": str(self.r.sock)})
        self.assertNotIn("Learned:", msgs[-1]["content"])

    def test_reflect_names_the_lean_for_a_declared_pair_without_a_verdict(self):
        self._env()
        self._taste("CreativeTranscendence", "TimeCoherence", 0.75, 0.8, 4)
        write_soul_settings(self.r.root, "berton")
        out = self.r.text("soul_reflect", situation="deciding between TimeCoherence and CreativeTranscendence")
        self.assertIn("declared pair", out.lower())
        self.assertIn("Your lean so far", out)
        self.assertIn("still your call", out)
        for forbidden in ("VERDICT", "gate", "block", "halt", "must"):
            self.assertNotIn(forbidden, out, forbidden)


@unittest.skipUnless(NODE, "needs node")
class ForgetTests(unittest.TestCase):
    """M7-A4: forgetting deletes taste and dismissal beliefs for one person; seen markers stay."""

    def setUp(self):
        self.r = m7_root("m7forget")
        self.addCleanup(self.r.close)
        self.r.start()

    def test_forget_deletes_only_that_persons_beliefs(self):
        ops = []
        for person in ("berton", "bright"):
            ops.append({"op": "upsert", "key": "state:soul_taste:%s:CreativeTranscendence:TimeCoherence" % person,
                        "atom": '(soul-taste "%s" CreativeTranscendence TimeCoherence (stv 1.0 0.5) 1)' % person})
            ops.append({"op": "upsert", "key": "state:soul_dismiss:%s:read" % person, "atom": '(soul-dismissed "%s" "read" 1)' % person})
        ops.append({"op": "upsert", "key": "state:soul_taste_seen:card-1", "atom": '(soul-taste-seen "card-1")'})
        self.r.call("transact", {"operations": ops, "actor": "iter", "source": "soul_taste"})
        code, stdout, stderr = __import__("m7_support").node("""
const { forgetSoulTaste } = require(%s);
forgetSoulTaste({ socket: %s, person: 'berton' }).then((r) => process.stdout.write(JSON.stringify(r)));
""" % (json.dumps(str(REPO / "bridge" / "soul_choice.js")), json.dumps(str(self.r.sock))))
        self.assertEqual(code, 0, stderr)
        self.assertEqual(json.loads(stdout.strip().splitlines()[-1]), {"deleted": 2})
        self.assertEqual(self.r.call("read_atoms", {"prefix": "state:soul_taste:berton:"})["atoms"], {})
        self.assertEqual(self.r.call("read_atoms", {"prefix": "state:soul_dismiss:berton:"})["atoms"], {})
        self.assertEqual(len(self.r.call("read_atoms", {"prefix": "state:soul_taste:bright:"})["atoms"]), 1)
        self.assertIn("state:soul_taste_seen:card-1", self.r.call("read_atoms", {"prefix": "state:soul_taste_seen:"})["atoms"])
        # The reducer does not rebuild a forgotten taste from the old (seen) choice.
        self.r.call("transact", {"operations": card_atoms("card-1", "fork", "berton",
                                                           [("a", "CreativeTranscendence", None), ("b", "TimeCoherence", None)])
                                 + [{"op": "upsert", "key": "state:soul_choice:card-1", "atom": choice_atom("berton", "fork", "card-1", "a")}],
                                 "actor": "test", "source": "test"})
        run_transformation(self.r.root, "soul_taste.py", env_extra={"ITER_METTA_SOCKET": str(self.r.sock)})
        self.assertEqual(self.r.call("read_atoms", {"prefix": "state:soul_taste:berton:"})["atoms"], {})

    def test_panel_button_and_ipc_take_the_person_from_the_saved_settings(self):
        html = (REPO / "renderer" / "index.html").read_text(encoding="utf-8")
        main = (REPO / "main.js").read_text(encoding="utf-8")
        preload = (REPO / "preload.js").read_text(encoding="utf-8")
        self.assertIn('id="btn-soul-forget"', html)
        self.assertIn("ipcMain.handle('soul:forget'", main)
        self.assertIn("forgetSoulTaste", preload)
        handler = main[main.index("ipcMain.handle('soul:forget'"):][:800]
        self.assertIn("loadSoulSettings()", handler)
        self.assertNotIn("person)", handler.split("=>")[0], "the renderer does not pass a person")


class GapTests(unittest.TestCase):
    """M7-A5: budget reaches the prompt; the pending choice queue flushes when the service comes up."""

    def test_budget_line_in_presence_block(self):
        temp = tempfile.mkdtemp(prefix="m7budget-")
        self.addCleanup(lambda: __import__("shutil").rmtree(temp, ignore_errors=True))
        write_soul_settings(temp, "berton", {"forks": True, "felt": True}, budget_per_cycle=3)
        msgs, _ = run_transformation(temp, "soul_presence.py", env_extra={"ITER_METTA_SOCKET": "/nonexistent/sock"})
        self.assertIn("Up to 3 cards or felt notes per cycle.", msgs[-1]["content"])
        write_soul_settings(temp, "berton", {"forks": True, "felt": True}, budget_per_cycle=0)
        msgs, _ = run_transformation(temp, "soul_presence.py", env_extra={"ITER_METTA_SOCKET": "/nonexistent/sock"})
        self.assertIn("No cards or felt notes unless asked.", msgs[-1]["content"])
        # Felt off leaves no mention of felt (M7-B3), so the budget line counts cards only.
        write_soul_settings(temp, "berton", {"forks": True}, budget_per_cycle=2)
        msgs, _ = run_transformation(temp, "soul_presence.py", env_extra={"ITER_METTA_SOCKET": "/nonexistent/sock"})
        self.assertIn("Up to 2 cards per cycle.", msgs[-1]["content"])
        self.assertNotIn("felt", msgs[-1]["content"])

    @unittest.skipUnless(NODE, "needs node")
    def test_flush_exists_and_main_calls_it_on_service_ready(self):
        r = m7_root("m7flush")
        self.addCleanup(r.close)
        r.start()
        pending_file = Path(r.root) / ".runtime" / "soul_choice_pending.jsonl"
        pending_file.parent.mkdir(exist_ok=True)
        pending_file.write_text(json.dumps({"person": "berton", "kind": "fork", "cardId": "card-q", "pick": "a", "at": 1700000000000}) + "\n")
        code, stdout, stderr = __import__("m7_support").node("""
const { flushSoulChoices } = require(%s);
flushSoulChoices({ socket: %s, iterDir: %s }).then((r) => process.stdout.write(JSON.stringify(r)));
""" % (json.dumps(str(REPO / "bridge" / "soul_choice.js")), json.dumps(str(r.sock)), json.dumps(str(r.root))))
        self.assertEqual(code, 0, stderr)
        self.assertEqual(json.loads(stdout.strip().splitlines()[-1]), {"flushed": 1})
        self.assertFalse(pending_file.exists())
        self.assertIn("state:soul_choice:card-q", r.call("read_atoms", {"prefix": "state:soul_choice:"})["atoms"])
        main = (REPO / "main.js").read_text(encoding="utf-8")
        ready = main.index("[atomspace] ready")
        self.assertIn("flushSoulChoices", main[ready - 1500:ready + 1500], "flushed where the service is logged ready")


class DashboardTests(unittest.TestCase):
    """M7-A honest surfaces: taste/felt counts and the learned line from the authority."""

    def test_authority_counts_include_tastes_felt_and_learned_line(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("dash", ITER_SRC / "transformations" / "dashboard_atomspace.py")
        dash = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dash)
        atoms = {
            "state:soul_taste:berton:CreativeTranscendence:TimeCoherence": '(soul-taste "berton" CreativeTranscendence TimeCoherence (stv 0.75 0.8) 4)',
            "state:soul_taste:berton:TimeCoherence:CreativeTranscendence": '(soul-taste "berton" TimeCoherence CreativeTranscendence (stv 0.25 0.8) 4)',
            "state:soul_felt:iter-1": '(soul-felt "berton" 1700000000000)',
        }
        temp = tempfile.mkdtemp(prefix="m7dash-")
        self.addCleanup(lambda: __import__("shutil").rmtree(temp, ignore_errors=True))
        write_soul_settings(temp, "berton")
        with unittest.mock.patch.dict(os.environ, {"ITER_DIR": temp}):
            counts = dash.authority_counts(lambda prefix: {k: v for k, v in atoms.items() if k.startswith(prefix)}, derive=lambda: [])
        self.assertEqual(counts["soul_tastes"], 2)
        self.assertEqual(counts["soul_felt"], 1)
        self.assertIn("leaned CreativeTranscendence over TimeCoherence", counts["soul_learned"])
        with unittest.mock.patch.dict(os.environ, {"ITER_DIR": temp}):
            empty = dash.authority_counts(lambda prefix: {}, derive=lambda: [])
        self.assertEqual((empty["soul_tastes"], empty["soul_felt"], empty["soul_learned"]), (0, 0, None))


if __name__ == "__main__":
    unittest.main()
