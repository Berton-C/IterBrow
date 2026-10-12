#!/usr/bin/env python3
"""Regression tests for the episodic memory pipeline (recap -> episodes -> tiers).

Each test runs the real component code from this repository against a fresh
temporary ITER_DIR (the components use cwd-relative paths, exactly as iter.py's
dynamic worker runs them).  Test names carry the audit bug ID they guard.
"""
import importlib.util
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ITER = ROOT / "iter"
for _path in (ITER / "tools", ITER):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

_COUNTER = itertools.count()


def load(relative):
    """Load a component by path, as iter.py --invoke does (fresh module each time)."""
    path = ITER / relative
    spec = importlib.util.spec_from_file_location(
        "_episodic_test_%d_%s" % (next(_COUNTER), path.stem), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def roundtrip(messages):
    """iter.py hands transformations a JSON copy of the request."""
    return json.loads(json.dumps(messages))


def system(text="prompt.txt:\nYou are Iter."):
    return {"role": "system", "content": text}


def user(ts, text, channel="electron_ui"):
    return {"role": "user", "content": "Step %s: [%s] %s" % (ts, channel, text)}


def send_exchange(call_id, ts, text):
    return [{"role": "assistant", "content": "", "tool_calls": [{
                "id": call_id, "type": "function",
                "function": {"name": "send", "arguments": json.dumps({"channel": "electron_ui", "content": text})}}]},
            {"role": "tool", "tool_call_id": call_id, "content": "Step %s: SUCCESS" % ts,
             "_iter_execution": {"success": True}}]


def tool_exchange(call_id, name, ts, result="ok", arguments="{}"):
    return [{"role": "assistant", "content": "", "tool_calls": [{
                "id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}]},
            {"role": "tool", "tool_call_id": call_id, "content": "Step %s: %s" % (ts, result)}]


class EpisodicCase(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        self._iter_dir = os.environ.get("ITER_DIR")
        self.dir = Path(tempfile.mkdtemp(prefix="ib-episodic-"))
        (self.dir / "memory").mkdir()
        os.chdir(self.dir)
        os.environ["ITER_DIR"] = str(self.dir)

    def tearDown(self):
        os.chdir(self._cwd)
        if self._iter_dir is None:
            os.environ.pop("ITER_DIR", None)
        else:
            os.environ["ITER_DIR"] = self._iter_dir
        shutil.rmtree(self.dir, ignore_errors=True)

    def write_episodes(self, numbers, name="episode_%04d.json", text=lambda i: "ep %d" % i):
        recap = self.dir / "memory" / "recap"
        recap.mkdir(parents=True, exist_ok=True)
        for i in numbers:
            (recap / (name % i)).write_text(json.dumps({"e": i, "s": text(i)}, ensure_ascii=False), encoding="utf-8")

    def tier(self, name):
        path = self.dir / "memory" / "tiers" / (name + ".txt")
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def tiers(self):
        return {name: self.tier(name) for name in ("tier3", "tier4", "tier5")}


# ---------------------------------------------------------------- BUG-4
class EpisodeOrderTests(EpisodicCase):
    def test_bug4_rebuild_orders_episodes_numerically_not_lexicographically(self):
        self.write_episodes(range(1, 13), name="episode_%d.json")
        load("tools/rebuild_tiers.py").rebuild()
        self.assertEqual(self.tier("tier5"), "12 episodes recorded, E1 to E12.")
        self.assertTrue(self.tier("tier3").splitlines()[-1].startswith("E12"), self.tier("tier3"))

    def test_bug4_recap_block_lists_episodes_in_numeric_order(self):
        self.write_episodes([9, 10, 11], name="episode_%d.json")
        messages, _ = load("transformations/recap.py").transform([system()], [])
        content = messages[0]["content"]
        self.assertLess(content.index("### E9"), content.index("### E10"))
        self.assertLess(content.index("### E10"), content.index("### E11"))

    def test_bug4_order_uses_e_field_and_tolerates_gaps(self):
        # Owner's live data: episodes 1-25 are missing.
        self.write_episodes(range(26, 75))
        load("tools/rebuild_tiers.py").rebuild()
        self.assertEqual(self.tier("tier5"), "49 episodes recorded, E26 to E74.")


# ---------------------------------------------------------------- BUG-2 / BUG-3
UNICODE = lambda i: "Sesión %d: añadí pestañas — corrección de diseño ✓ página %d ñññ" % (i, i)


class SingleTierWriterTests(EpisodicCase):
    def test_bug2_rebuild_then_auto_consolidation_changes_nothing(self):
        self.write_episodes(range(1, 61), text=UNICODE)
        load("tools/rebuild_tiers.py").rebuild()
        before = self.tiers()
        load("transformations/auto_consolidation.py").transform([system()], [])
        self.assertEqual(before, self.tiers())

    def test_bug2_rebuild_is_idempotent(self):
        self.write_episodes(range(1, 61), text=UNICODE)
        rebuild_tiers = load("tools/rebuild_tiers.py")
        rebuild_tiers.rebuild()
        first = self.tiers()
        mtimes = {n: (self.dir / "memory/tiers" / (n + ".txt")).stat().st_mtime_ns for n in first}
        result = rebuild_tiers.rebuild()
        self.assertEqual(first, self.tiers())
        self.assertEqual(mtimes, {n: (self.dir / "memory/tiers" / (n + ".txt")).stat().st_mtime_ns for n in first})
        self.assertEqual(result["changed"], [])

    def test_bug2_rollup_flag_cleared_by_rebuild_stays_cleared(self):
        # Multi-byte text: rebuild limits are characters; the checks used bytes.
        self.write_episodes(range(1, 400), text=lambda i: "día ñ%d" % i)
        load("tools/rebuild_tiers.py").rebuild()
        for _cycle in range(3):
            load("transformations/auto_consolidation.py").transform([system()], [])
            load("transformations/tiered_memory.py").transform([system()], [])
            self.assertFalse((self.dir / "memory/tiers/.rollup_needed").exists())

    def test_bug2_tiered_memory_rebuilds_when_episodes_are_newer(self):
        self.write_episodes(range(1, 4))
        load("tools/rebuild_tiers.py").rebuild()
        self.write_episodes([4], text=lambda i: "NEWEST-EPISODE-FOUR")
        messages, _ = load("transformations/tiered_memory.py").transform([system()], [])
        self.assertIn("E4: NEWEST-EPISODE-FOUR", messages[0]["content"])
        self.assertEqual(self.tier("tier5"), "4 episodes recorded, E1 to E4.")

    def test_bug2_auto_consolidation_never_writes_tiers_with_its_own_algorithm(self):
        # An over-limit tier is regenerated by rebuild_tiers, not half-moved into tier4.
        self.write_episodes(range(1, 11), text=lambda i: ("Ép%d " % i) + "ñ" * 150)
        load("tools/rebuild_tiers.py").rebuild()
        load("transformations/auto_consolidation.py").transform([system()], [])
        self.assertIn("E10:", self.tier("tier3"))
        self.assertEqual(self.tier("tier4"), "")

    def test_bug2_legacy_tier_text_is_archived_before_first_rebuild(self):
        # Owner's tiers were written before rebuild_tiers existed: keep a copy.
        tiers = self.dir / "memory/tiers"
        tiers.mkdir(parents=True)
        (tiers / "tier3.txt").write_text("OWNER LEGACY TIER3 TEXT", encoding="utf-8")
        self.write_episodes(range(26, 75))
        load("transformations/tiered_memory.py").transform([system()], [])
        archived = "".join(p.read_text(encoding="utf-8") for p in (self.dir / "memory/archive/tier3.txt").glob("*.txt"))
        self.assertIn("OWNER LEGACY TIER3 TEXT", archived)
        self.assertIn("E74", self.tier("tier3"))


class CapsKeepNewestTests(EpisodicCase):
    def test_bug3_tier4_cap_keeps_newest_eras(self):
        self.write_episodes(range(1, 201), text=lambda i: "Worked on feature number %d of the browser and verified the result" % i)
        load("tools/rebuild_tiers.py").rebuild()
        self.assertIn("E186-190", self.tier("tier4"))
        self.assertNotIn("E1-5:", self.tier("tier4"))
        self.assertIn("200 episodes recorded, E1 to E200.", self.tier("tier5"))
        self.assertIn("folded", self.tier("tier5"))
        self.assertLessEqual(len(self.tier("tier4")), 1500)

    def test_bug3_tier3_cap_drops_oldest_lines(self):
        self.write_episodes(range(1, 11), text=lambda i: "episode %d " % i + "x" * 100)
        rebuild_tiers = load("tools/rebuild_tiers.py")
        rebuild_tiers.TIER3_LIMIT = 400
        rebuild_tiers.rebuild()
        lines = self.tier("tier3").splitlines()
        self.assertTrue(lines[-1].startswith("E10:"), lines)
        self.assertFalse(any(line.startswith("E1:") for line in lines), lines)

    def test_bug3_recap_block_injects_only_newest_episodes(self):
        self.write_episodes(range(1, 41))
        recap = load("transformations/recap.py")
        content = recap.transform([system()], [])[0][0]["content"]
        self.assertIn("### E40", content)
        self.assertNotIn("### E1\n", content)
        self.assertEqual(content.count("### E"), recap.RECAP_INJECT_EPISODES)

    def test_bug3_tiered_memory_budget_keeps_newest_tier3_lines(self):
        self.write_episodes(range(1, 11), text=lambda i: "episode %d " % i + "y" * 150)
        load("tools/rebuild_tiers.py").rebuild()
        tiered = load("transformations/tiered_memory.py")
        tiered.DEFAULT_BUDGET = 700
        content = tiered.transform([system()], [])[0][0]["content"]
        self.assertIn("E10:", content)


# ---------------------------------------------------------------- BUG-5
TRANSCRIPT_TAIL = "transformations/append_last_transcript_lines.py"


class ContextBudgetSectionTests(EpisodicCase):
    def _episodic_prompt(self, base):
        self.write_episodes(range(1, 41), text=lambda i: "Episode %d: shipped feature %d" % (i, i))
        load("tools/rebuild_tiers.py").rebuild()
        messages = [system(base), user("2026-10-01 10:00:00", "hi")]
        messages, _ = load("transformations/recap.py").transform(messages, [])
        messages[0]["content"] += "\n\n## Iter Soul (Active)\nSOUL-BODY\n\n## Skill Bundles\nSKILL-BODY"
        messages, _ = load("transformations/tiered_memory.py").transform(messages, [])
        messages[0]["content"] += "\n\n## Stall Detection\nSTALL-BODY"
        return messages

    def test_bug5_recap_dedup_removes_only_the_recap(self):
        messages = self._episodic_prompt("prompt.txt:\nYou are Iter.")
        self.assertIn("## Episode Recap", messages[0]["content"])
        messages, _ = load("transformations/zz_context_budget.py").transform(messages, [])
        content = messages[0]["content"]
        self.assertNotIn("## Episode Recap", content)   # deduplicated against the pyramid
        for body in ("SOUL-BODY", "SKILL-BODY", "STALL-BODY", "## Tiered Memory Pyramid", "E40:"):
            self.assertIn(body, content)

    def test_bug5_memory_note_quoting_a_heading_cannot_hijack_a_section(self):
        base = ("prompt.txt:\nYou are Iter.\n./memory/:\nnotes.txt:\nThe block titled '## Episode Recap' "
                "repeats the pyramid.\nIMPORTANT-MEMORY-NOTE stays.")
        messages = self._episodic_prompt(base)
        messages, _ = load("transformations/zz_context_budget.py").transform(messages, [])
        self.assertIn("IMPORTANT-MEMORY-NOTE stays.", messages[0]["content"])

    def test_bug5_transcript_tail_is_recognised_as_its_own_section(self):
        Path("transcript.txt").write_text("[2026-10-01 10:00:00][user] Step 2026-10-01 10:00:00: [electron_ui] TAIL-LINE\n", encoding="utf-8")
        messages = [system(), user("2026-10-01 10:00:00", "TAIL-LINE")]
        messages, _ = load(TRANSCRIPT_TAIL).transform(messages, [])
        messages[0]["content"] += "\n\n## Iter Soul (Active)\nSOUL-BODY"
        load("transformations/zz_context_budget.py").transform(messages, [])
        log = Path(".context_budget_log.txt").read_text(encoding="utf-8")
        self.assertRegex(log, r"Transcript\s+LOW")
        transcript_size = int(re.search(r"Transcript\s+LOW\s+(\d+) chars", log).group(1))
        self.assertLess(transcript_size, 200)   # the Soul block after it is not part of the transcript


# ---------------------------------------------------------------- BUG-1
def log_history(count, start=0, minute="10:00"):
    """Log `count` user messages through the real history transformation."""
    history = load("transformations/history.py")
    messages = [user("2026-10-01 %s:%02d" % (minute, c), "q%d" % c) for c in range(start, start + count)]
    history.transform(roundtrip([system()] + messages), [])
    return messages


class RecapPipelineTests(EpisodicCase):
    def test_bug1_recap_request_reaches_the_system_prompt(self):
        log_history(25)
        content = load("transformations/recap.py").transform([system()], [])[0][0]["content"]
        self.assertIn("## Recap Request", content)
        self.assertIn("History records 1-25 (2026-10-01 10:00:00 to 2026-10-01 10:00:24)", content)
        self.assertIn('episodes(time_string="2026-10-01 10:00:00"', content)
        self.assertIn("record_episode(", content)
        self.assertIn("episode_0001.json", content)

    def test_bug1_record_episode_advances_cursor_and_clears_request(self):
        log_history(25)
        recap = load("transformations/recap.py")
        recap.transform([system()], [])
        result = load("tools/record_episode.py").run("Answered 25 questions. RECORDED-SUMMARY")
        self.assertIn("SUCCESS", result)
        episode = json.loads((self.dir / "memory/recap/episode_0001.json").read_text(encoding="utf-8"))
        self.assertEqual(episode["lines"], [1, 25])
        self.assertEqual((episode["start_time"], episode["end_time"]), ("2026-10-01 10:00:00", "2026-10-01 10:00:24"))
        content = recap.transform([system()], [])[0][0]["content"]
        self.assertNotIn("## Recap Request", content)
        self.assertEqual((self.dir / "memory/recap/.recap_state").read_text(), "25")
        self.assertFalse((self.dir / "memory/recap/.recap_needed").exists())
        self.assertIn("E1: Answered 25 questions. RECORDED-SUMMARY", self.tier("tier3"))

    def test_bug1_cursor_advances_when_requested_episode_appears_by_other_means(self):
        log_history(25)
        recap = load("transformations/recap.py")
        recap.transform([system()], [])
        self.assertTrue((self.dir / "memory/recap/.recap_needed").exists())
        self.write_episodes([1], text=lambda i: "hand-written episode")
        content = recap.transform([system()], [])[0][0]["content"]
        self.assertEqual((self.dir / "memory/recap/.recap_state").read_text(), "25")
        self.assertNotIn("## Recap Request", content)
        self.assertFalse((self.dir / "memory/recap/.recap_needed").exists())

    def test_bug1_owner_cursor_and_episode_gaps_stay_compatible(self):
        self.write_episodes(range(26, 75))
        recap_dir = self.dir / "memory/recap"
        (recap_dir / ".recap_state").write_text("181")
        (recap_dir / ".recap_needed").write_text("New lines: 40 (lines 182-221 of 221 total)\nlegacy text\n")
        log_history(60, minute="10:00")
        log_history(50, start=0, minute="10:01")
        log_history(80, start=0, minute="10:02")   # 190 records: below threshold
        recap = load("transformations/recap.py")
        content = recap.transform([system()], [])[0][0]["content"]
        self.assertNotIn("## Recap Request", content)
        self.assertEqual((recap_dir / ".recap_state").read_text(), "181")
        log_history(30, start=0, minute="10:03")   # 220 records
        content = recap.transform([system()], [])[0][0]["content"]
        self.assertIn("History records 182-220", content)
        self.assertIn("episode_0075.json", content)
        for i in range(26, 75):                     # existing episodes never rewritten
            self.assertEqual(json.loads((recap_dir / ("episode_%04d.json" % i)).read_text()), {"e": i, "s": "ep %d" % i})

    def test_bug1_large_backlog_is_requested_span_by_span(self):
        log_history(50, minute="09:00"); log_history(50, minute="09:01"); log_history(50, minute="09:02")
        log_history(50, minute="09:03"); log_history(50, minute="09:04")
        recap = load("transformations/recap.py")
        content = recap.transform([system()], [])[0][0]["content"]
        self.assertIn("History records 1-200 ", content)
        self.assertIn("50 more unsummarized records", content)
        load("tools/record_episode.py").run("first span")
        content = recap.transform([system()], [])[0][0]["content"]
        self.assertIn("History records 201-250 ", content)
        self.assertIn("episode_0002.json", content)


if __name__ == "__main__":
    unittest.main()
