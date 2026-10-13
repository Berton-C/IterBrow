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
import unittest.mock
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


    def write_timed(self, rows):
        recap = self.dir / "memory" / "recap"
        recap.mkdir(parents=True, exist_ok=True)
        for number, start, end in rows:
            episode = {"e": number, "s": "summary %d" % number}
            if start:
                episode["start_time"] = start
            if end:
                episode["end_time"] = end
            (recap / ("episode_%04d.json" % number)).write_text(json.dumps(episode))

    def test_r2_tiers_and_recap_order_episodes_by_time_not_number(self):
        # E3 was written late about an earlier period: it is not "most recent".
        self.write_timed([(1, "2026-10-01 09:00:00", "2026-10-01 10:00:00"),
                          (2, "2026-10-03 09:00:00", "2026-10-03 10:00:00"),
                          (3, "2026-09-20 09:00:00", "2026-09-20 10:00:00")])
        load("tools/rebuild_tiers.py").rebuild()
        lines = self.tier("tier3").splitlines()
        self.assertEqual([line.split(":")[0] for line in lines], ["E3", "E1", "E2"])
        content = load("transformations/recap.py").transform([system()], [])[0][0]["content"]
        self.assertLess(content.index("### E3"), content.index("### E1"))
        self.assertLess(content.index("### E1"), content.index("### E2"))

    def test_r2_start_time_and_untimed_episodes_keep_a_sensible_place(self):
        # E2 has only start_time; E4 (untimed) stays after the episode before it by number.
        self.write_timed([(1, None, "2026-10-01 10:00:00"),
                          (2, "2026-09-25 09:00:00", None),
                          (3, None, "2026-10-05 10:00:00"),
                          (4, None, None)])
        load("tools/rebuild_tiers.py").rebuild()
        order = [line.split(":")[0] for line in self.tier("tier3").splitlines()]
        self.assertEqual(order, ["E2", "E1", "E3", "E4"])


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


    def test_first_rebuild_keeps_the_old_life_and_era_summaries_in_the_prompt(self):
        # Review 3 H1: episodes 1-25 are gone; the hand-written tier4/tier5 were the
        # only summaries of them and of the life so far.  Archiving them on the
        # first rebuild dropped them from every later prompt.
        tiers = self.dir / "memory/tiers"
        tiers.mkdir(parents=True)
        (tiers / "tier3.txt").write_text("E70: hand tier3 line", encoding="utf-8")
        (tiers / "tier4.txt").write_text("E1-5: LEGACY ERA early IterBrow setup; E11-25: NodeQuest", encoding="utf-8")
        (tiers / "tier5.txt").write_text("LIFE: Iter has helped Berton since August.", encoding="utf-8")
        self.write_episodes(range(26, 75))
        tiered = load("transformations/tiered_memory.py")
        content = tiered.transform([system()], [])[0][0]["content"]
        self.assertIn("LIFE: Iter has helped Berton since August.", content)
        self.assertIn("E1-5: LEGACY ERA early IterBrow setup", content)
        self.assertIn("E74", content)
        self.assertLess(content.index("LEGACY ERA"), content.index("## Life Summary"),
                        "the legacy summary comes ahead of the regenerated tiers")
        legacy = (tiers / "legacy_summary.txt").read_text(encoding="utf-8")
        self.assertNotIn("hand tier3 line", legacy)
        # Later rebuilds keep it (written once, never regenerated) and keep injecting it.
        self.write_episodes([75], text=lambda i: "NEWER EPISODE")
        content = tiered.transform([system()], [])[0][0]["content"]
        self.assertIn("NEWER EPISODE", content)
        self.assertIn("LIFE: Iter has helped Berton since August.", content)
        self.assertEqual((tiers / "legacy_summary.txt").read_text(encoding="utf-8"), legacy)

    def test_legacy_summary_is_bounded_and_not_agent_writable(self):
        tiers = self.dir / "memory/tiers"
        tiers.mkdir(parents=True)
        (tiers / "tier5.txt").write_text("LIFE " + "x" * 20000, encoding="utf-8")
        self.write_episodes(range(1, 3))
        content = load("transformations/tiered_memory.py").transform([system()], [])[0][0]["content"]
        self.assertIn("LIFE xxx", content)
        self.assertLess(len(content), 9000)
        guard = load("tools/_memory_guard.py")
        with self.assertRaises(PermissionError):
            guard.check_open(str(tiers / "legacy_summary.txt"), "w")


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
TRANSCRIPT_TAIL = "transformations/transcript_tail.py"


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
        old = 1759190400  # 2026-09-30: the episodes predate all of this history
        for i in range(26, 75):
            os.utime(recap_dir / ("episode_%04d.json" % i), (old, old))
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

    def test_record_episode_reports_success_when_only_the_tier_rebuild_fails(self):
        # Review 3 LOW-a: the episode is stored and the cursor advanced; a failed
        # rebuild_tiers must not make the agent think it has to record it again.
        log_history(25)
        load("transformations/recap.py").transform([system()], [])
        broken = type(sys)("rebuild_tiers")

        def fail(actor=None):
            raise OSError(28, "No space left on device (test)")
        broken.rebuild = fail
        with unittest.mock.patch.dict(sys.modules, {"rebuild_tiers": broken}):
            result = load("tools/record_episode.py").run("Answered 25 questions.")
        self.assertIn("SUCCESS", str(result))
        self.assertIn("tiers will be rebuilt", str(result))
        self.assertIs(result.execution_outcome["success"], True)
        self.assertTrue((self.dir / "memory/recap/episode_0001.json").exists())
        self.assertEqual((self.dir / "memory/recap/.recap_state").read_text(), "25")


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


def history_record(i, base="2026-09-01 00:00:00"):
    import datetime
    when = datetime.datetime.strptime(base, "%Y-%m-%d %H:%M:%S") + datetime.timedelta(seconds=i)
    return '("%s" "TOOL_RESULT: record %d")\n' % (when.strftime("%Y-%m-%d %H:%M:%S"), i)


def stamp_of(i, base="2026-09-01 00:00:00"):
    return history_record(i, base)[2:21]


class RecapCursorMigrationTests(EpisodicCase):
    """Review 3 B2: the owner's .recap_state (181) predates the logical-history
    cursor and episodes 26-74 carry no "lines", so the agent was asked to
    re-summarize everything from record 182 in 200-record spans (hundreds of
    requests on real data), and those new episodes would rank as newest."""

    def owner_shape(self, archived=3000, tail=1500):
        recap = self.dir / "memory" / "recap"
        self.write_episodes(range(26, 75), text=lambda i: "Episode %d: worked on thing %d" % (i, i))
        (recap / ".recap_state").write_text("181")
        (recap / ".recap_needed").write_text("New lines: 999 (old flag text)\n")
        archive = self.dir / "memory" / "archive" / "history.metta"
        archive.mkdir(parents=True)
        (archive / "1758000000000000000-rotation-aaaa.txt").write_text(
            "".join(history_record(i) for i in range(archived)))
        (self.dir / "history.metta").write_text("".join(history_record(i) for i in range(archived, archived + tail)))
        return recap

    def set_mtime(self, path, stamp):
        import datetime
        when = datetime.datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").timestamp()
        os.utime(path, (when, when))

    def test_cursor_is_inferred_from_the_newest_episode_file_time(self):
        recap = self.owner_shape()
        for i in range(26, 75):  # episodes written as history went by; the newest covers record 4199
            self.set_mtime(recap / ("episode_%04d.json" % i), stamp_of(4199 - (74 - i) * 10))
        content = load("transformations/recap.py").transform([system()], [])[0][0]["content"]
        # logical position of record 4199 is 4200
        self.assertEqual((recap / ".recap_state").read_text(), "4200")
        self.assertIn("History records 4201-4400 ", content)
        self.assertIn("episode_0075.json", content)
        self.assertNotIn("not summarized", content)

    def test_episode_end_time_wins_over_file_time_and_is_persisted_once(self):
        recap = self.owner_shape()
        (recap / "episode_0074.json").write_text(json.dumps({"e": 74, "s": "last", "end_time": stamp_of(3999)}))
        load("transformations/recap.py").transform([system()], [])
        self.assertEqual((recap / ".recap_state").read_text(), "4000")
        # One-time: the episode file changing later does not move the cursor again.
        (recap / "episode_0074.json").write_text(json.dumps({"e": 74, "s": "last", "end_time": stamp_of(4400)}))
        load("transformations/recap.py").transform([system()], [])
        self.assertEqual((recap / ".recap_state").read_text(), "4000")

    def test_mem_type_t_field_is_not_mistaken_for_a_time(self):
        recap = self.owner_shape()
        (recap / "episode_0074.json").write_text(json.dumps({"e": 74, "s": "last", "t": "fact",
                                                             "time": stamp_of(4299)}))
        load("transformations/recap.py").transform([system()], [])
        self.assertEqual((recap / ".recap_state").read_text(), "4300")

    def test_span_times_tolerate_out_of_order_records(self):
        # Review 3 LOW-c: history.metta records carry event-time stamps, so a
        # span's first record is not necessarily its earliest.
        from iterbrow_runtime import recap_state
        Path("history.metta").write_text("".join(history_record(i) for i in (5, 2, 9, 7, 1, 8)))
        self.assertEqual(recap_state.span_times(1, 4), (stamp_of(2), stamp_of(9)))
        self.assertEqual(recap_state.span_times(2, 6), (stamp_of(1), stamp_of(9)))
        self.assertEqual(recap_state.span_for_times(stamp_of(2), stamp_of(7)), (1, 4))
        self.assertEqual(recap_state.span_for_times(stamp_of(1), stamp_of(1)), (5, 5))


    def test_backlog_is_capped_to_the_most_recent_spans_and_said_once(self):
        recap = self.owner_shape()
        for i in range(26, 75):  # episodes much older than the history
            self.set_mtime(recap / ("episode_%04d.json" % i), "2026-08-01 00:00:00")
        recap_t = load("transformations/recap.py")
        content = recap_t.transform([system()], [])[0][0]["content"]
        # 4500 records pending, more than 3 spans of 200: skip to the newest 600.
        self.assertEqual((recap / ".recap_state").read_text(), "3900")
        self.assertIn("History records 3901-4100 ", content)
        self.assertIn("records 182-3900", content)
        self.assertIn("not summarized", content)
        self.assertIn("search_transcript", content)
        again = recap_t.transform([system()], [])[0][0]["content"]
        self.assertIn("records 182-3900", again, "the pending request keeps its note")
        load("tools/record_episode.py").run("first span")
        content = recap_t.transform([system()], [])[0][0]["content"]
        self.assertIn("History records 4101-4300 ", content)
        self.assertNotIn("not summarized", content)


class RecapBacklogTests(EpisodicCase):
    """R1: the backlog cap was meant as a one-time catch-up at cursor migration,
    but it fired whenever Iter was busy and permanently skipped history. In
    normal running nothing is skipped; a large backlog gets a coarser span."""

    def busy(self, covered=100, total=1600, base="2026-10-01 00:00:00", step=20):
        import datetime
        recap = self.dir / "memory" / "recap"
        recap.mkdir(parents=True, exist_ok=True)
        start = datetime.datetime.strptime(base, "%Y-%m-%d %H:%M:%S")
        lines = []
        for i in range(total):
            when = (start + datetime.timedelta(seconds=step * i)).strftime("%Y-%m-%d %H:%M:%S")
            lines.append('("%s" "TOOL_RESULT: record %d")\n' % (when, i))
        (self.dir / "history.metta").write_text("".join(lines))
        (recap / "episode_0001.json").write_text(json.dumps({"e": 1, "s": "first", "lines": [1, covered]}))
        (recap / ".recap_state").write_text(str(covered))
        return recap

    def test_busy_backlog_of_1500_records_is_never_skipped(self):
        recap = self.busy()
        recap_t = load("transformations/recap.py")
        content = recap_t.transform([system()], [])[0][0]["content"]
        self.assertEqual((recap / ".recap_state").read_text(), "100", "history was skipped during normal running")
        request = json.loads((recap / ".recap_request.json").read_text())
        self.assertEqual(request["start"], 101)
        self.assertNotIn("skipped", request)
        self.assertNotIn("not summarized into episodes", content)
        self.assertIn("History records 101-", content)

    def test_busy_backlog_asks_for_a_coarser_episode_and_a_filtered_read(self):
        recap = self.busy()
        content = load("transformations/recap.py").transform([system()], [])[0][0]["content"]
        request = json.loads((recap / ".recap_request.json").read_text())
        span = request["end"] - request["start"] + 1
        self.assertGreater(span, 200)
        self.assertLessEqual(span, 1000)
        self.assertIn("conversation_only=true", content)
        self.assertIn('end_time="%s"' % request["end_time"], content)
        load("tools/record_episode.py").run("coarse busy-day episode")
        load("transformations/recap.py").transform([system()], [])
        following = json.loads((recap / ".recap_request.json").read_text())
        self.assertEqual(following["start"], request["end"] + 1)

    def test_coarse_span_stops_at_one_calendar_day(self):
        # 3000 records (coarse limit 1000), one every 2 minutes: 720 per day.
        recap = self.busy(covered=0, total=3000, base="2026-10-01 00:00:00", step=120)
        (recap / "episode_0001.json").write_text(json.dumps({"e": 1, "s": "none", "lines": [0, 0]}))
        load("transformations/recap.py").transform([system()], [])
        request = json.loads((recap / ".recap_request.json").read_text())
        self.assertEqual(request["start"], 1)
        self.assertTrue(request["start_time"].startswith("2026-10-01"))
        self.assertTrue(request["end_time"].startswith("2026-10-01"), request)
        self.assertEqual(request["end"], 720)

    def test_small_backlog_keeps_the_normal_span(self):
        recap = self.busy(covered=100, total=500)
        load("transformations/recap.py").transform([system()], [])
        request = json.loads((recap / ".recap_request.json").read_text())
        self.assertEqual((request["start"], request["end"]), (101, 300))

    def test_episodes_conversation_only_filters_tool_chatter(self):
        records = [
            ("2026-10-01 10:00:00", "HUMAN_MESSAGE: [electron_ui] please plan the trip"),
            ("2026-10-01 10:00:01", "TOOL_CALL: websearch {\"q\": \"trains\"}"),
            ("2026-10-01 10:00:02", "TOOL_RESULT: Step 2026-10-01 10:00:02: 40 results"),
            ("2026-10-01 10:00:03", "ASSISTANT: thinking about trains"),
            ("2026-10-01 10:00:04", "TOOL_CALL: send {\"content\": \"Here is the plan\"}"),
            ("2026-10-01 10:00:05", "TOOL_RESULT: Step 2026-10-01 10:00:05: SUCCESS"),
            ("2026-10-01 11:30:00", "HUMAN_MESSAGE: [electron_ui] later question"),
        ]
        (self.dir / "history.metta").write_text("".join(
            '("%s" %s)\n' % (ts, json.dumps(text)) for ts, text in records))
        episodes = load("tools/episodes.py")
        out = str(episodes.run("2026-10-01 10:00:00", end_time="2026-10-01 10:00:05", conversation_only=True))
        self.assertIn("please plan the trip", out)
        self.assertIn("thinking about trains", out)
        self.assertIn("Here is the plan", out)
        self.assertNotIn("TOOL_RESULT", out)
        self.assertNotIn("websearch", out)
        self.assertNotIn("later question", out)
        full = str(episodes.run("2026-10-01 10:00:00", k=10))
        self.assertIn("TOOL_RESULT", full)
        window = str(episodes.run("2026-10-01 10:00:02", k=1, conversation_only="true"))
        self.assertNotIn("TOOL_RESULT", window)
        self.assertNotIn("websearch", window)
        self.assertIn("thinking about trains", window)


# ---------------------------------------------------------------- BUG-15
class TranscriptLagTests(EpisodicCase):
    def _order(self):
        """iter.py runs public transformations in sorted file-name order."""
        names = sorted(p.name for p in (ITER / "transformations").glob("*.py") if not p.name.startswith("_"))
        reader = next(n for n in names
                      if "transcript (historical conversation" in (ITER / "transformations" / n).read_text(encoding="utf-8"))
        return names, reader

    def test_bug15_transcript_is_written_before_its_tail_is_read(self):
        names, reader = self._order()
        self.assertLess(names.index("transcript.py"), names.index(reader))

    def test_bug15_current_user_message_is_in_the_same_cycle_transcript_tail(self):
        names, reader = self._order()
        messages = [system(), user("2026-10-01 09:00:00", "FIRST-MESSAGE")]
        for name in [n for n in names if n in ("transcript.py", reader)]:
            messages, _ = load("transformations/" + name).transform(roundtrip(messages), [])
        content = messages[0]["content"]
        self.assertIn("transcript (historical conversation", content)
        self.assertIn("FIRST-MESSAGE", content.split("transcript (historical conversation")[-1])


if __name__ == "__main__":
    unittest.main()
