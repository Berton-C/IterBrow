#!/usr/bin/env python3
"""M9-A1..A4: the wonder jar — keep cut ideas, offer one back rarely, fold the pick back.

Spec: docs/milestones/M9_soul_wonder_ally.md section A.
"""
import json
import os
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from m9_support import (pending, m9_root, require_m9, write_soul_settings, run_transformation, make_app_dir,  # noqa: E402
                        seed_wonder, seed_offered, seed_topic_card, seed_pick, wonders, now_ms, HOUR, ITER_SRC, NODE, REPO)


class WonderToolTests(unittest.TestCase):
    """M9-A1"""

    def setUp(self):
        self.r = m9_root("m9wonder")
        self.addCleanup(self.r.close)
        self.r.start()

    @pending("M9-A1")
    def test_add_list_take_let_go(self):
        write_soul_settings(self.r.root, "berton", {"wonder": True})
        make_app_dir(self.r.root, "crm")
        out = self.r.text("wonder", action="add", app="crm", idea="a timeline view of every conversation with a person")
        self.assertTrue(out.startswith("WONDER-KEPT: wonder-"), out)
        first = out.split()[1]
        second = self.r.text("wonder", action="add", app="crm", idea="birthday reminders that feel like a friend's nudge").split()[1]
        self.assertEqual(wonders(self.r), {first: "open", second: "open"})
        listing = self.r.text("wonder", action="list")
        self.assertTrue(listing.startswith("Wonder jar (2 open)"), listing)
        self.assertLess(listing.index(first), listing.index(second), "oldest first")
        self.assertIn("- %s crm: a timeline view of every conversation with a person" % first, listing)
        self.assertEqual(self.r.text("wonder", action="take", id=first), "WONDER-TAKEN: %s" % first)
        self.assertEqual(self.r.text("wonder", action="let_go", id=second), "WONDER-LET-GO: %s" % second)
        self.assertEqual(wonders(self.r), {first: "taken", second: "let-go"})
        self.assertEqual(self.r.text("wonder", action="list"), "Wonder jar (0 open)")
        self.assertEqual(self.r.text("wonder", action="take", id="wonder-nope"), "ERROR: no idea wonder-nope")
        self.assertEqual(self.r.text("wonder", action="shake"), "ERROR: action must be add, list, take or let_go")

    @pending("M9-A1")
    def test_ideas_are_per_person_and_per_app_and_need_a_real_app(self):
        write_soul_settings(self.r.root, "berton", {"wonder": True})
        make_app_dir(self.r.root, "crm")
        make_app_dir(self.r.root, "music")
        self.r.text("wonder", action="add", app="crm", idea="one")
        self.r.text("wonder", action="add", app="music", idea="two")
        self.assertTrue(self.r.text("wonder", action="add", app="nope", idea="x").startswith("ERROR: no app named"))
        self.assertTrue(self.r.text("wonder", action="add", app="crm", idea="y" * 201).startswith("ERROR:"))
        self.assertIn("(1 open)", self.r.text("wonder", action="list", app="music"))
        write_soul_settings(self.r.root, "bright", {"wonder": True})
        self.assertEqual(self.r.text("wonder", action="list"), "Wonder jar (0 open)", "bright sees none of berton's")

    @pending("M9-A1")
    def test_wonder_atoms_live_only_in_the_soul_view(self):
        seed_wonder(self.r, "berton", "crm", "wonder-aaaaaaaa", "an idea")
        for view in ("current", "full", "kb"):
            self.assertNotIn("wonder-aaaaaaaa", self.r.call("query", {"code": '!(match &self (soul-wonder $p $a $i $t $s $at) $i)', "view": view}, timeout=60)["result"], view)
        self.assertIn("wonder-aaaaaaaa", self.r.call("query", {"code": '!(match &self (soul-wonder $p $a $i $t $s $at) $i)', "view": "soul"}, timeout=60)["result"])


class OfferTests(unittest.TestCase):
    """M9-A2"""

    def setUp(self):
        self.r = m9_root("m9offer")
        self.addCleanup(self.r.close)
        self.r.start()

    def _block(self):
        msgs, _ = run_transformation(self.r.root, "soul_wonder.py", env_extra={"ITER_METTA_SOCKET": str(self.r.sock)})
        return msgs[-1]["content"]

    @pending("M9-A2")
    def test_first_offer_then_the_dial_cooldown(self):
        write_soul_settings(self.r.root, "berton", {"wonder": True}, frequency="occasional")
        seed_wonder(self.r, "berton", "crm", "wonder-11111111", "a timeline view", at=1)
        seed_wonder(self.r, "berton", "crm", "wonder-22222222", "friendly reminders", at=2)
        content = self._block()
        self.assertIn("## Wonder", content)
        self.assertIn("topic wonder:wonder-11111111", content, "the oldest never-offered idea goes first")
        self.assertIn("crm: a timeline view", content)
        self.assertIn("take / keep / let_go", content)
        offered = self.r.call("read_atoms", {"prefix": "state:soul_wonder_offer:berton"})["atoms"]
        self.assertIn('"wonder-11111111"', list(offered.values())[0])
        self.assertEqual(self._block(), "base", "no second offer inside the cooldown")
        # Past the cooldown (occasional = 4 h): the other idea, offered longest ago (never).
        seed_offered(self.r, "berton", "wonder-11111111", now_ms() - 5 * HOUR)
        self.assertIn("topic wonder:wonder-22222222", self._block())

    @pending("M9-A2")
    def test_dial_sets_the_wait(self):
        for frequency, hours, expected in (("whisper", 23, False), ("whisper", 25, True), ("chatty", 0.5, False), ("chatty", 1.5, True)):
            write_soul_settings(self.r.root, "berton", {"wonder": True}, frequency=frequency)
            seed_wonder(self.r, "berton", "crm", "wonder-33333333", "an idea", at=1)
            seed_offered(self.r, "berton", "wonder-33333333", now_ms() - int(hours * HOUR))
            self.assertEqual("## Wonder" in self._block(), expected, "%s after %sh" % (frequency, hours))

    @pending("M9-A2")
    def test_nothing_when_off_quiet_outstanding_or_nothing_open(self):
        seed_wonder(self.r, "berton", "crm", "wonder-44444444", "an idea", at=1)
        write_soul_settings(self.r.root, "berton", {"wonder": False})
        self.assertEqual(self._block(), "base", "feature off")
        write_soul_settings(self.r.root, "berton", {"wonder": True}, mode="quiet")
        self.assertEqual(self._block(), "base", "quiet")
        write_soul_settings(self.r.root, "berton", {"wonder": True})
        seed_topic_card(self.r, "card-w1", "wonder:wonder-44444444")  # offered, not yet answered
        self.assertEqual(self._block(), "base", "an outstanding offer card")
        seed_pick(self.r, "card-w1", "let_go")
        run_transformation(self.r.root, "soul_taste.py", env_extra={"ITER_METTA_SOCKET": str(self.r.sock)})
        self.assertEqual(wonders(self.r)["wonder-44444444"], "let-go")
        self.assertEqual(self._block(), "base", "nothing open")
        self.assertEqual(self.r.call("read_atoms", {"prefix": "state:soul_wonder_offer:"})["atoms"], {}, "no offer was recorded")

    @pending("M9-A2")
    def test_let_go_and_taken_are_never_offered(self):
        write_soul_settings(self.r.root, "berton", {"wonder": True})
        seed_wonder(self.r, "berton", "crm", "wonder-55555555", "gone", status="let-go", at=1)
        seed_wonder(self.r, "berton", "crm", "wonder-66666666", "done", status="taken", at=2)
        seed_wonder(self.r, "berton", "crm", "wonder-77777777", "still here", at=3)
        content = self._block()
        self.assertIn("topic wonder:wonder-77777777", content)
        self.assertNotIn("wonder-55555555", content)
        self.assertNotIn("wonder-66666666", content)


class FoldTests(unittest.TestCase):
    """M9-A3: picks on topic cards become soul-topic-pick; wonder picks change status."""

    def setUp(self):
        self.r = m9_root("m9fold")
        self.addCleanup(self.r.close)
        self.r.start()

    def _reduce(self):
        run_transformation(self.r.root, "soul_taste.py", env_extra={"ITER_METTA_SOCKET": str(self.r.sock)})

    @pending("M9-A3")
    def test_topic_picks_are_recorded_latest_wins_and_wonder_status_follows(self):
        seed_wonder(self.r, "berton", "crm", "wonder-88888888", "idea", at=1)
        seed_topic_card(self.r, "card-t1", "wonder:wonder-88888888")
        seed_pick(self.r, "card-t1", "keep", at=10)
        self._reduce()
        picks = self.r.call("read_atoms", {"prefix": "state:soul_topic_pick:"})["atoms"]
        self.assertEqual(picks["state:soul_topic_pick:wonder:wonder-88888888"], '(soul-topic-pick "wonder:wonder-88888888" "keep" 10)')
        self.assertEqual(wonders(self.r)["wonder-88888888"], "open")
        seed_topic_card(self.r, "card-t2", "wonder:wonder-88888888", at=20)
        seed_pick(self.r, "card-t2", "take", at=21)
        self._reduce()
        picks = self.r.call("read_atoms", {"prefix": "state:soul_topic_pick:"})["atoms"]
        self.assertEqual(picks["state:soul_topic_pick:wonder:wonder-88888888"], '(soul-topic-pick "wonder:wonder-88888888" "take" 21)')
        self.assertEqual(wonders(self.r)["wonder-88888888"], "taken")
        # Growth and ally topics are recorded the same way; dismiss counts as a pick.
        seed_topic_card(self.r, "card-g1", "growth", choices=("now", "later"))
        seed_pick(self.r, "card-g1", "dismiss", at=30)
        self._reduce()
        picks = self.r.call("read_atoms", {"prefix": "state:soul_topic_pick:"})["atoms"]
        self.assertEqual(picks["state:soul_topic_pick:growth"], '(soul-topic-pick "growth" "dismiss" 30)')
        # The rest of the reducer is untouched: a topic card without patterns makes no taste.
        self.assertEqual(self.r.call("read_atoms", {"prefix": "state:soul_taste:"})["atoms"], {})

    @pending("M9-A3")
    def test_card_tool_records_the_topic(self):
        write_soul_settings(self.r.root, "berton", {"wonder": True})
        out = self.r.text("card", kind="offer", title="One from the jar", body="A timeline view?", topic="wonder:wonder-99999999",
                          choices=[{"id": "take", "label": "Take it"}, {"id": "keep", "label": "Keep it"}, {"id": "let_go", "label": "Let it go"}])
        self.assertTrue(out.startswith("CARD-SENT: card-"), out)
        card_id = out.split()[1]
        topics = self.r.call("read_atoms", {"prefix": "state:soul_card_topic:"})["atoms"]
        self.assertEqual(topics["state:soul_card_topic:%s" % card_id], '(soul-card-topic "%s" "wonder:wonder-99999999")' % card_id)
        bad = self.r.text("card", kind="offer", title="x", body="", topic="Not A Topic!", choices=["a", "b"])
        self.assertTrue(bad.startswith("ERROR:"), bad)
        message = json.loads(sorted((Path(self.r.root) / ".runtime" / "electron_ui" / "outbox").glob("*.json"))[-1].read_text())
        self.assertEqual(message["card"]["topic"], "wonder:wonder-99999999")

    @unittest.skipUnless(NODE, "needs node")
    @pending("M9-A3")
    def test_bridge_keeps_a_valid_topic_and_drops_a_bad_one(self):
        code, stdout, stderr = __import__("m9_support").node("""
const { validCard } = require(%s);
const ok = validCard({ id: 'c1', kind: 'offer', title: 't', topic: 'ally:wonder-time', choices: [{ id: 'a', label: 'A' }] });
const bad = validCard({ id: 'c2', kind: 'offer', title: 't', topic: 'Not A Topic!', choices: [{ id: 'a', label: 'A' }] });
process.stdout.write(JSON.stringify({ ok: ok.topic, bad: bad && bad.topic === undefined && !!bad }));
""" % json.dumps(str(REPO / "bridge" / "chat_bridge.js")))
        self.assertEqual(code, 0, stderr)
        self.assertEqual(json.loads(stdout.strip().splitlines()[-1]), {"ok": "ally:wonder-time", "bad": True})


class WonderCountTests(unittest.TestCase):
    """M9-A4 and M9-C5"""

    @pending("M9-A4")
    def test_counts_open_ideas_and_ally_cards(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("dash", ITER_SRC / "transformations" / "dashboard_atomspace.py")
        dash = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dash)
        atoms = {"state:soul_wonder:w1": '(soul-wonder "berton" "crm" "w1" "a" "open" 1)',
                 "state:soul_wonder:w2": '(soul-wonder "berton" "crm" "w2" "b" "taken" 2)',
                 "state:soul_wonder:w3": '(soul-wonder "bright" "crm" "w3" "c" "open" 3)',
                 "state:soul_card_topic:c1": '(soul-card-topic "c1" "ally:wonder-time")',
                 "state:soul_card_topic:c2": '(soul-card-topic "c2" "growth")'}
        temp = tempfile.mkdtemp(prefix="m9dash-")
        self.addCleanup(lambda: __import__("shutil").rmtree(temp, ignore_errors=True))
        with unittest.mock.patch.dict(os.environ, {"ITER_DIR": temp}):
            counts = dash.authority_counts(lambda prefix: {k: v for k, v in atoms.items() if k.startswith(prefix)}, derive=lambda: [])
            empty = dash.authority_counts(lambda prefix: {}, derive=lambda: [])
        self.assertEqual(counts["soul_wonder_open"], 2)
        self.assertEqual(counts["soul_ally_cards"], 1)
        self.assertEqual((empty["soul_wonder_open"], empty["soul_ally_cards"]), (0, 0))


if __name__ == "__main__":
    unittest.main()
