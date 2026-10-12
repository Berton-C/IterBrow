#!/usr/bin/env python3
"""Semantic (fact) memory: AtomSpace authority + chroma_db search index.

Every test drives the real tools in fresh processes against the real AtomSpace
service (see semantic_memory_support.py); the bug each class guards is named in
its docstring (B1..B15, S1 from the semantic-memory audit).
"""
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from semantic_memory_support import SemanticRoot, ITER_SRC  # noqa: E402

MEMORY_TOOLS = ["remember", "chroma_query", "forget", "memory_update", "support", "contradict",
                "link_episode", "unlink_episode", "formalize_metta"]


def load_petta(test, name="petta_under_test"):
    """Import tools/_petta_db.py with its index in a private temp directory."""
    sys.path.insert(0, str(ITER_SRC))
    temp = tempfile.mkdtemp(prefix="iterbrow-petta-")
    test.addCleanup(shutil.rmtree, temp, True)
    with mock.patch.dict(os.environ, {"ITER_DIR": temp}):
        spec = importlib.util.spec_from_file_location(name, ITER_SRC / "tools" / "_petta_db.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    module.DB_DIR = str(Path(temp) / "chroma_db")
    module.DB_FILE = module.DB_DIR + "/memories.json"
    return module


def gauss_vector(seed, dimensions=1024):
    out, index = [], 0
    while len(out) < dimensions:
        digest = hashlib.sha256(("%s:%d" % (seed, index)).encode()).digest()
        out.extend((b - 127.5) / 127.5 for b in digest)
        index += 1
    return out[:dimensions]


def write_current_index(root, ids, documents, metadatas):
    """A schema-3 int8 index like the owner's (vectors from the test endpoint)."""
    from semantic_memory_support import fake_vector

    def pack(vector):
        low, high = min(vector), max(vector)
        scale = (high - low) / 255.0
        return {"q": bytes(int(round((v - low) / scale)) for v in vector).hex(), "s": scale, "o": low}
    (root / "chroma_db").mkdir(exist_ok=True)
    (root / "chroma_db" / "memories.json").write_text(json.dumps({
        "ids": ids, "documents": documents, "metadatas": metadatas,
        "embeddings": [pack(fake_vector(d)) for d in documents],
        "embedding_model": "qwen/qwen3-embedding-8b", "embedding_dimensions": 1024, "embedding_schema": 3}))


class ServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.r = SemanticRoot(self.id().rsplit(".", 1)[-1][:20])
        self.addCleanup(self.r.close)
        self.r.start()


class ToolImportPathTests(ServiceTestCase):
    """B9: hot-loaded tools must import _petta_db from their own generation, and
    B14: the memory journal belongs to ITER_DIR, not to the worker's cwd."""

    def test_every_memory_tool_imports_petta_db_from_its_own_directory(self):
        generation = self.r.root / ".runtime" / "hotload" / "generations" / "cand-1" / "tools"
        shutil.copytree(self.r.root / "tools", generation)
        for tool in MEMORY_TOOLS:
            for variant in (tool, "_" + tool):
                if not (generation / (variant + ".py")).exists():
                    continue
                kwargs = {
                    "remember": {"text": "generation probe"}, "chroma_query": {"query": "x"},
                    "forget": {"item_id": "nope"}, "memory_update": {"item_id": "nope", "text": "x"},
                    "support": {"item_id": "nope", "episode_time": "E"},
                    "contradict": {"item_id": "nope", "episode_time": "E"},
                    "link_episode": {"item_id": "nope", "linked_time": "E"},
                    "unlink_episode": {"item_id": "nope", "linked_time": "E"},
                    "formalize_metta": {"LTM_item": "nope", "formalization": "(--> a b)"},
                }[tool]
                result = self.r.tool(variant, tool_dir=generation, **kwargs)
                self.assertEqual(result.get("petta_file"), str(generation / "_petta_db.py"),
                                 "%s loaded the wrong _petta_db: %r" % (variant, result))

    def test_journal_is_written_under_iter_dir_whatever_the_cwd(self):
        elsewhere = Path(tempfile.mkdtemp(prefix="iterbrow-cwd-"))
        self.addCleanup(shutil.rmtree, elsewhere, True)
        result = self.r.text("remember", text="journal location probe", cwd=elsewhere)
        self.assertTrue(result.startswith("REMEMBER-SUCCESS"), result)
        self.assertTrue((self.r.root / "memory" / "journal.jsonl").exists())
        self.assertFalse((elsewhere / "memory" / "journal.jsonl").exists())


CONTROL_SAMPLES = {
    "ansi colour": "shell said \x1b[32mOK\x1b[0m",
    "backspace": "a\bb",
    "form feed": "page\fbreak",
    "unit separator": "a\x1fb",
    "windows line ending": "line one\r\nline two",
    "tab and newline": "col\tcol\nrow",
    "quote and backslash": 'say "hi" \\ bye',
    "unicode": "caf\u00e9 \u4e2d\u6587 \U0001f600 \u2028",
}


class MettaStringEscapingTests(unittest.TestCase):
    """B5: metta_string emitted JSON escapes (\\u001b, \\b, \\f) that Hyperon rejects."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ITER_SRC))
        from iterbrow_runtime import cognitive_events, legacy_migration
        cls.ce = cognitive_events
        cls.lm = legacy_migration

    def test_ordinary_strings_are_byte_identical_to_the_old_encoding(self):
        for value in ["plain", 'say "hi"', "back\\slash", "multi\nline\ttab\rcr", "caf\u00e9 \U0001f600",
                      "\u2028 \x7f", "{\"json\": [1, 2]}"]:
            old = json.dumps(value, ensure_ascii=False)
            self.assertEqual(self.ce.metta_string(value), old)
            self.assertEqual(self.lm._metta_string(value), old)

    def test_hyperon_parses_every_control_character_back_to_the_same_value(self):
        from hyperon import MeTTa
        engine = MeTTa()
        for code in list(range(1, 32)) + [0x7f]:
            value = "x" + chr(code) + "y"
            for encode in (self.ce.metta_string, self.lm._metta_string):
                literal = encode(value)
                atom = engine.parse_all("(probe %s)" % literal)[0]
                parsed = atom.get_children()[1].get_object().value
                self.assertEqual(parsed, value, "U+%04X via %r" % (code, literal))
                self.assertEqual(self.ce.parse_metta_string(literal), value)

    def test_nul_never_reaches_hyperon(self):
        # Hyperon aborts the whole process when it serialises a string holding
        # NUL, so it is stored as U+FFFD (the only lossy character).
        literal = self.ce.metta_string("a\x00b")
        self.assertNotIn("\x00", literal)
        self.assertEqual(self.ce.parse_metta_string(literal), "a\ufffdb")

    def test_semantic_atom_round_trips_through_the_parser(self):
        for name, document in CONTROL_SAMPLES.items():
            metadata = {"note": document, "linkedEpisodes": ["2026-01-01 00:00:00"]}
            atom = "(semantic-memory %s %s %s)" % (
                self.ce.metta_string("m1"), self.ce.metta_string(document),
                self.ce.metta_string(json.dumps(metadata, sort_keys=True, ensure_ascii=False)))
            self.assertEqual(self.ce.parse_semantic_atom("state:semantic_memory:m1", atom),
                             ("m1", document, metadata), name)


class ControlCharacterServiceTests(ServiceTestCase):
    """B5 through the real service: remember and legacy migration with control characters."""

    def test_remember_accepts_control_characters_and_commits_them_exactly(self):
        for name, text in CONTROL_SAMPLES.items():
            out = self.r.text("remember", text=text)
            self.assertTrue(out.startswith("REMEMBER-SUCCESS"), "%s: %s" % (name, out))
            item_id = out.split()[2]
            self.assertEqual(self.r.memories()[item_id][0], text, name)
        self.assertEqual(self.r.pending_files(), [])
        self.assertEqual(self.r.index_ids(), set(self.r.memories()))


class LegacyControlCharacterMigrationTests(unittest.TestCase):
    """B5: one legacy document with an ANSI escape failed the one-time migration,
    leaving the AtomSpace service without an engine (every cognitive write failed)."""

    def test_legacy_index_with_ansi_document_migrates_and_service_is_ready(self):
        r = SemanticRoot("legacy-ansi")
        self.addCleanup(r.close)
        (r.root / "chroma_db").mkdir()
        (r.root / "chroma_db" / "memories.json").write_text(json.dumps({
            "ids": ["legacy-1", "legacy-2"],
            "documents": ["normal fact", "shell said \x1b[32mOK\x1b[0m and \b\f"],
            "metadatas": [{"mem_type": "fact"}, {"mem_type": "fact"}],
            "embeddings": [[0.1] * 4, [0.2] * 4],
        }))
        status = r.start()
        self.assertEqual(status["legacy_migration"]["status"], "migrated", status)
        self.assertTrue(status.get("engine_available", status.get("ready")), status)
        self.assertEqual(r.memories()["legacy-2"][0], "shell said \x1b[32mOK\x1b[0m and \b\f")


class QuantizationTests(unittest.TestCase):
    """B12: every load->save re-quantized decoded vectors with int(), drifting them
    a little further on each of the many saves a memory sees."""

    def test_load_save_cycles_are_byte_stable(self):
        petta = load_petta(self)
        db = petta._empty()
        for k in range(12):
            db["ids"].append("m%d" % k)
            db["documents"].append("doc %d" % k)
            db["metadatas"].append({"k": k})
            db["embeddings"].append(gauss_vector(k))
        petta._save(db)
        first = Path(petta.DB_FILE).read_bytes()
        for _ in range(5):
            petta._save(petta._load())
        self.assertEqual(Path(petta.DB_FILE).read_bytes(), first)

    def test_quantization_rounds_to_the_nearest_level(self):
        petta = load_petta(self)
        vector = gauss_vector("round")
        packed = petta._quantize_embedding(vector)
        decoded = petta._dequantize_embedding(packed)
        worst = max(abs(a - b) for a, b in zip(vector, decoded))
        self.assertLessEqual(worst, packed["s"] / 2 + 1e-12)

    def test_existing_packed_file_loads_and_scores(self):
        petta = load_petta(self)
        vectors = [gauss_vector(k) for k in range(3)]
        os.makedirs(petta.DB_DIR)
        Path(petta.DB_FILE).write_text(json.dumps({
            "ids": ["a", "b", "c"], "documents": ["A", "B", "C"], "metadatas": [{}, {}, {}],
            "embeddings": [petta._quantize_embedding(v) for v in vectors],
            "embedding_model": petta.EMBEDDING_MODEL, "embedding_dimensions": 1024, "embedding_schema": 3}))
        result = petta.Collection().query(query_embeddings=[vectors[1]], n_results=1)
        self.assertEqual(result["ids"][0], ["b"])


class AtomicSaveTests(unittest.TestCase):
    """B8: _save renamed memories.json to .bak before moving the new file in; a
    concurrent pure reader that landed in that gap restored the old .bak over the
    writer's new file (or found no file at all), rolling back committed writes."""

    WRITER = r"""
import sys, json
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[1] + "/tools")
import _petta_db as p
p.DB_DIR = sys.argv[2]; p.DB_FILE = p.DB_DIR + "/memories.json"
db = p._empty()
for i in range(int(sys.argv[3])):
    db["ids"].append("m%d" % i); db["documents"].append("doc"); db["metadatas"].append({})
    db["embeddings"].append([0.25] * 8)
    p._save(db)
"""
    READER = r"""
import sys, os, time, json
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[1] + "/tools")
import _petta_db as p
p.DB_DIR = sys.argv[2]; p.DB_FILE = p.DB_DIR + "/memories.json"
missing = 0
end = time.time() + float(sys.argv[3])
while time.time() < end:
    if not os.path.exists(p.DB_FILE):
        missing += 1
    try:
        p._load()
    except Exception:
        pass
print(json.dumps({"missing": missing}))
"""

    def test_concurrent_readers_never_lose_or_roll_back_a_save(self):
        import subprocess
        work = Path(tempfile.mkdtemp(prefix="iterbrow-atomic-"))
        self.addCleanup(shutil.rmtree, work, True)
        (work / "w.py").write_text(self.WRITER)
        (work / "r.py").write_text(self.READER)
        db_dir = work / "chroma_db"
        db_dir.mkdir()
        (db_dir / "memories.json").write_text(json.dumps(
            {"ids": [], "documents": [], "metadatas": [], "embeddings": []}))
        env = dict(os.environ, ITER_DIR=str(work))
        readers = [subprocess.Popen([sys.executable, str(work / "r.py"), str(ITER_SRC), str(db_dir), "4"],
                                    stdout=subprocess.PIPE, text=True, env=env) for _ in range(3)]
        subprocess.run([sys.executable, str(work / "w.py"), str(ITER_SRC), str(db_dir), "300"],
                       check=True, env=env)
        missing = sum(json.loads(r.communicate()[0])["missing"] for r in readers)
        self.assertEqual(len(json.loads((db_dir / "memories.json").read_text())["ids"]), 300)
        self.assertEqual(missing, 0, "memories.json was absent during a save")

    def test_a_reader_never_restores_the_backup_itself(self):
        petta = load_petta(self)
        db = petta._empty()
        db["ids"].append("m1"); db["documents"].append("d"); db["metadatas"].append({})
        db["embeddings"].append([0.5] * 4)
        petta._save(db)
        petta._save(db)  # leaves a .bak
        os.remove(petta.DB_FILE)
        self.assertEqual(petta._load()["ids"], ["m1"])
        self.assertFalse(os.path.exists(petta.DB_FILE), "a read wrote the index")


NO_STRICT = {"ITER_REQUIRE_ATOMSPACE": None}


class FailClosedTests(ServiceTestCase):
    """B6: with the AtomSpace down and ITER_REQUIRE_ATOMSPACE unset (a direct
    `python iter.py` launch) memory writes were 'deferred': the tool reported
    success and the index advanced while the authority never got the write.
    S1: a refused connection (nothing was sent) was reported as uncertain."""

    def test_remember_with_authority_down_reports_failure_and_changes_nothing(self):
        self.r.stop()
        result = self.r.tool("remember", text="written while authority is down", env=NO_STRICT)
        self.assertFalse(result["ok"] and "SUCCESS" in result.get("result", ""), result)
        self.assertEqual(self.r.index_ids(), set())
        self.assertEqual(self.r.pending_files(), [], "a definite failure left a pending entry")
        # S1: nothing was sent, so the outcome is definite, not 'uncertain'.
        self.assertEqual((result.get("execution") or {}).get("state"), "not_executed", result)

    def test_metadata_write_with_authority_down_reports_failure(self):
        item_id = self.r.remember("belief to support")
        before = self.r.index()
        self.r.stop()
        out = self.r.text("support", item_id=item_id, episode_time="E1", env=NO_STRICT)
        self.assertNotIn("SUCCESS", out)
        self.assertEqual(self.r.index()["metadatas"], before["metadatas"])
        self.r.start()
        self.assertEqual(self.r.memories()[item_id][1].get("strength", 1.0), 1.0)

    def test_sent_without_reply_is_uncertain_and_keeps_its_pending_identity(self):
        result = self.r.tool("remember", text="reply lost in transit", env={"NO_REPLY_AFTER_SEND": "1"})
        self.assertFalse(result["ok"], result)
        self.assertEqual((result.get("execution") or {}).get("state"), "uncertain", result)
        self.assertEqual(len(self.r.pending_files()), 1)


class PendingIdentityTests(ServiceTestCase):
    """B1: a pending entry that outlived its commit (worker killed after the index
    save) made a later identical request reuse the old transaction id; the
    AtomSpace answered 'duplicate' and applied nothing, yet the tool reported
    success. B2: a leftover entry resurrected an old identity, mem_type and
    provenance for a different request, and survived failures it should not."""

    def _authority_has(self, item_id):
        return item_id in self.r.memories()

    def test_remember_forget_remember_after_a_crash_reaches_the_authority(self):
        text = "the user's cat is named Miso"
        # The commit lands but its reply is lost: the pending entry outlives the commit.
        lost = self.r.tool("remember", text=text, env={"NO_REPLY_AFTER_SEND": "1"})
        self.assertEqual((lost.get("execution") or {}).get("state"), "uncertain", lost)
        self.assertEqual(len(self.r.pending_files()), 1)
        item_id = next(iter(self.r.memories()))
        self.assertTrue(self.r.text("forget", item_id=item_id, force="true").startswith("FORGET-SUCCESS"))
        self.assertEqual(self.r.memories(), {})
        out = self.r.text("remember", text=text)
        self.assertTrue(out.startswith("REMEMBER-SUCCESS"), out)
        stored = out.split()[2]
        self.assertTrue(self._authority_has(stored), "reported success but the authority has nothing")
        self.assertEqual(self.r.memories()[stored][0], text)
        self.assertEqual(self.r.index_ids(), set(self.r.memories()))
        self.assertEqual(self.r.pending_files(), [])

    def test_link_unlink_link_after_a_crash_reaches_the_authority(self):
        item_id = self.r.remember("belief with episodes")
        self.r.tool("link_episode", item_id=item_id, linked_time="E1", env={"NO_REPLY_AFTER_SEND": "1"})
        self.assertEqual(len(self.r.pending_files()), 1)
        self.assertEqual(self.r.memories()[item_id][1].get("linkedEpisodes"), ["E1"])
        self.assertIn("UNLINK-SUCCESS", self.r.text("unlink_episode", item_id=item_id, linked_time="E1"))
        self.assertIsNone(self.r.memories()[item_id][1].get("linkedEpisodes"))
        self.assertIn("LINK-SUCCESS", self.r.text("link_episode", item_id=item_id, linked_time="E1"))
        self.assertEqual(self.r.memories()[item_id][1].get("linkedEpisodes"), ["E1"])
        self.assertEqual(self.r.pending_files(), [])

    def test_server_side_rejection_removes_the_pending_entry(self):
        self.r.call("quiesce")
        out = self.r.text("remember", text="Berton prefers dark mode", mem_type="todo")
        self.r.call("resume")
        self.assertNotIn("SUCCESS", out)
        self.assertEqual(self.r.pending_files(), [])

    def test_leftover_entry_is_reused_only_for_the_same_text_type_and_provenance(self):
        text = "Berton prefers dark mode"
        self.r.tool("remember", text=text, mem_type="todo", provenance_type="model_estimated",
                    env={"CRASH_BEFORE_SEND": "1"})
        self.assertEqual(len(self.r.pending_files()), 1)
        self.assertEqual(self.r.memories(), {})
        out = self.r.text("remember", text=text, mem_type="fact", provenance_type="observed")
        self.assertTrue(out.startswith("REMEMBER-SUCCESS"), out)
        metadata = self.r.memories()[out.split()[2]][1]
        self.assertEqual((metadata["mem_type"], metadata["provenance_type"]), ("fact", "observed"))
        self.assertTrue(self.r.text("forget", item_id=out.split()[2]).startswith("FORGET-REFUSED"))

    def test_matching_uncertain_entry_resumes_its_original_identity(self):
        text = "resume me exactly"
        self.r.tool("remember", text=text, mem_type="todo", env={"CRASH_BEFORE_SEND": "1"})
        pending_id = json.loads(self.r.pending_files()[0].read_text())["request"][1][0]["id"]
        out = self.r.text("remember", text=text, mem_type="todo")
        self.assertEqual(out.split()[2], pending_id)
        self.assertTrue(self._authority_has(pending_id))
        self.assertEqual(self.r.pending_files(), [])

    def test_pending_queue_is_cleared_by_reset(self):
        manifest = json.loads((ITER_SRC / "state_manifest.json").read_text())
        entry = next(e for e in manifest["entries"] if e["path"] == ".runtime/memory_pending")
        self.assertTrue(entry["reset"])


class ConcurrentWriterTests(ServiceTestCase):
    """B7: each writer loaded the index before taking any lock, so parallel
    remember processes each saved their own snapshot and the last one won
    (8 parallel remembers -> index held 1)."""

    def test_parallel_remembers_all_reach_authority_and_index(self):
        from concurrent.futures import ThreadPoolExecutor
        texts = ["parallel fact number %d" % i for i in range(8)]
        with ThreadPoolExecutor(8) as pool:
            outs = list(pool.map(lambda t: self.r.text("remember", text=t), texts))
        self.assertTrue(all(o.startswith("REMEMBER-SUCCESS") for o in outs), outs)
        self.assertEqual(len(self.r.memories()), 8)
        self.assertEqual(self.r.index_ids(), set(self.r.memories()))


def revised(s1, c1, s2, c2=0.5):
    """NAL revision exactly as tools/support.py computes it."""
    w1 = c1 / (1.0 - c1)
    w2 = c2 / (1.0 - c2)
    w = w1 + w2
    f = min(1.0, (w1 * s1 + w2 * s2) / w)
    c = min(0.99, max(w / (w + 1.0), c1, c2))
    return round(f, 6), round(c, 6)


class AuthoritativeMetadataTests(ServiceTestCase):
    """B3: metadata tools read the index, computed new metadata from it and
    upserted that into the authority. After any commit whose index save failed
    (or a concurrent writer), the next metadata write erased committed evidence."""

    def _stv(self, item_id):
        metadata = self.r.memories()[item_id][1]
        return metadata.get("strength", 1.0), metadata.get("confidence", 0.5)

    def test_metadata_writes_build_on_the_authority_not_a_stale_index(self):
        item_id = self.r.remember("belief under evidence")
        expected = (1.0, 0.5)
        for episode in ("E1", "E2", "E3"):
            self.r.tool("support", item_id=item_id, episode_time=episode, env={"FAIL_SAVE": "1"})
            expected = revised(expected[0], expected[1], 1.0)
        self.assertEqual(self._stv(item_id), expected, "the index-save failures lost commits")
        out = self.r.text("contradict", item_id=item_id, episode_time="E4")
        self.assertIn("CONTRADICT-SUCCESS", out)
        expected = revised(expected[0], expected[1], 0.0)
        metadata = self.r.memories()[item_id][1]
        self.assertEqual(self._stv(item_id), expected)
        self.assertEqual(metadata["linkedEpisodes"], ["E1", "E2", "E3", "E4"])
        self.assertEqual(self.r.pending_files(), [])

    def test_parallel_supports_count_every_episode_once(self):
        from concurrent.futures import ThreadPoolExecutor
        item_id = self.r.remember("target belief for support")
        episodes = ["2026-10-0%d 10:00:00" % i for i in range(1, 7)]
        with ThreadPoolExecutor(6) as pool:
            outs = list(pool.map(lambda e: self.r.text("support", item_id=item_id, episode_time=e), episodes))
        self.assertTrue(all("SUPPORT-SUCCESS" in o for o in outs), outs)
        expected = (1.0, 0.5)
        for _ in episodes:
            expected = revised(expected[0], expected[1], 1.0)
        metadata = self.r.memories()[item_id][1]
        self.assertEqual(sorted(metadata["linkedEpisodes"]), episodes)
        self.assertEqual((metadata["strength"], metadata["confidence"]), expected)
        index_meta = self.r.index()["metadatas"][self.r.index()["ids"].index(item_id)]
        self.assertEqual(index_meta, metadata)


class EvidenceCountingTests(ServiceTestCase):
    """B10: linkedEpisodes doubled as 'evidence already counted', but link/unlink
    edit it without touching truth values: support -> unlink -> support counted an
    episode twice; link -> support refused real evidence."""

    def test_unlink_then_support_does_not_count_twice(self):
        item_id = self.r.remember("belief A")
        self.assertIn("SUPPORT-SUCCESS", self.r.text("support", item_id=item_id, episode_time="E1"))
        once = self.r.memories()[item_id][1]["confidence"]
        self.assertIn("UNLINK-SUCCESS", self.r.text("unlink_episode", item_id=item_id, linked_time="E1"))
        self.assertNotIn("SUCCESS", self.r.text("support", item_id=item_id, episode_time="E1"))
        self.assertEqual(self.r.memories()[item_id][1]["confidence"], once)

    def test_link_then_support_counts_the_evidence(self):
        item_id = self.r.remember("belief B")
        self.assertIn("LINK-SUCCESS", self.r.text("link_episode", item_id=item_id, linked_time="E9"))
        self.assertEqual(self.r.memories()[item_id][1].get("confidence", 0.5), 0.5)
        self.assertIn("SUPPORT-SUCCESS", self.r.text("support", item_id=item_id, episode_time="E9"))
        metadata = self.r.memories()[item_id][1]
        self.assertEqual(metadata["confidence"], revised(1.0, 0.5, 1.0)[1])
        self.assertEqual(metadata["linkedEpisodes"], ["E9"])
        # an episode contributes evidence once, whichever direction
        self.assertNotIn("SUCCESS", self.r.text("contradict", item_id=item_id, episode_time="E9"))

    def test_link_and_unlink_never_change_truth_or_counted_evidence(self):
        item_id = self.r.remember("belief C")
        self.r.text("support", item_id=item_id, episode_time="E1")
        before = self.r.memories()[item_id][1]
        self.r.text("link_episode", item_id=item_id, linked_time="E2")
        self.r.text("unlink_episode", item_id=item_id, linked_time="E2")
        self.r.text("unlink_episode", item_id=item_id, linked_time="E1")
        after = self.r.memories()[item_id][1]
        self.assertEqual((after["strength"], after["confidence"]), (before["strength"], before["confidence"]))
        self.assertEqual(after.get("evidenceEpisodes"), before.get("evidenceEpisodes"))


class LegacyEvidenceMigrationTests(unittest.TestCase):
    """B10 on the owner's existing memories (no evidenceEpisodes field): linked
    episodes of a revised memory count as already counted; links of a memory still
    at the default (1.0, 0.5) were never counted."""

    def test_existing_memories_are_read_with_the_documented_rule(self):
        r = SemanticRoot("legacy-evidence")
        self.addCleanup(r.close)
        write_current_index(
            r.root, ["revised", "linked-only"], ["a revised belief", "a merely linked belief"],
            [{"mem_type": "belief", "linkedEpisodes": ["E1"], "strength": 1.0, "confidence": 0.666667},
             {"mem_type": "belief", "linkedEpisodes": ["E3"]}])
        r.start()
        atoms_before = r.atoms()
        self.assertNotIn("SUCCESS", r.text("support", item_id="revised", episode_time="E1"))
        self.assertEqual(r.atoms(), atoms_before, "a refused write changed bytes")
        self.assertIn("SUPPORT-SUCCESS", r.text("support", item_id="revised", episode_time="E2"))
        self.assertEqual(r.memories()["revised"][1]["evidenceEpisodes"], {"E1": "+", "E2": "+"})
        self.assertIn("SUPPORT-SUCCESS", r.text("support", item_id="linked-only", episode_time="E3"))
        self.assertEqual(r.memories()["linked-only"][1]["confidence"], revised(1.0, 0.5, 1.0)[1])


class IndexReconcileTests(ServiceTestCase):
    """B3 (index half): nothing ever rebuilt chroma_db from the authority, so a
    commit whose index save failed stayed unsearchable forever, orphans stayed
    searchable, and drifted metadata was shown (and, before, written back)."""

    def _inject(self, mutate):
        path = self.r.root / "chroma_db" / "memories.json"
        index = json.loads(path.read_text())
        mutate(index)
        path.write_text(json.dumps(index))

    def test_committed_memory_missing_from_the_index_becomes_searchable(self):
        self.r.remember("anchor belief")
        self.r.tool("remember", text="committed but never indexed", env={"FAIL_SAVE": "1"})
        self.assertEqual(len(self.r.memories()), 2)
        self.assertEqual(len(self.r.index_ids()), 1)
        out = self.r.text("chroma_query", query="committed but never indexed", k=1)
        self.assertIn("Content: committed but never indexed", out)
        self.assertEqual(self.r.index_ids(), set(self.r.memories()))

    def test_orphans_are_removed_and_drifted_metadata_follows_the_authority(self):
        keep = self.r.remember("a real memory")
        self.r.text("support", item_id=keep, episode_time="E1")

        def drift(index):
            index["ids"].append("orphan-1")
            index["documents"].append("a memory the authority never had")
            index["metadatas"].append({"mem_type": "fact"})
            index["embeddings"].append(index["embeddings"][0])
            index["metadatas"][index["ids"].index(keep)] = {"mem_type": "todo"}
        self._inject(drift)
        out = self.r.text("chroma_query", query="a memory the authority never had", k=5)
        self.assertNotIn("orphan-1", out)
        self.assertEqual(self.r.index_ids(), {keep})
        index = self.r.index()
        self.assertEqual(index["metadatas"][index["ids"].index(keep)], self.r.memories()[keep][1])

    def test_without_embeddings_removals_still_apply_and_the_gap_is_reported(self):
        self.r.remember("anchor belief")
        self.r.tool("remember", text="waiting for an embedding", env={"FAIL_SAVE": "1"})
        self._inject(lambda index: (index["ids"].append("orphan-2"), index["documents"].append("x"),
                                    index["metadatas"].append({}), index["embeddings"].append(index["embeddings"][0])))
        self.r.embeddings.fail = True
        out = self.r.text("chroma_query", query="anything")
        self.assertIn("1 memory is not yet searchable", out)
        self.assertNotIn("orphan-2", self.r.index_ids())
        self.r.embeddings.fail = False
        index = self.r.index()
        index["authority_index"]["retry_after"] = 0  # skip the retry back-off in the test
        (self.r.root / "chroma_db" / "memories.json").write_text(json.dumps(index))
        out = self.r.text("chroma_query", query="waiting for an embedding", k=1)
        self.assertIn("Content: waiting for an embedding", out)
        self.assertNotIn("not yet searchable", out)

    def test_deleted_index_is_rebuilt_from_the_authority(self):
        self.r.remember("Berton lives in Buenos Aires")
        shutil.rmtree(self.r.root / "chroma_db")
        out = self.r.text("chroma_query", query="Berton lives in Buenos Aires", k=1)
        self.assertIn("Content: Berton lives in Buenos Aires", out)
        self.assertTrue(self.r.text("remember", text="Berton lives in Buenos Aires").startswith("REMEMBER-DUPLICATE"))

    def test_an_aligned_index_is_not_re_embedded(self):
        self.r.remember("steady memory")
        self.r.text("chroma_query", query="steady")
        before = self.r.embeddings.requests
        self.r.text("chroma_query", query="steady")
        self.assertEqual(self.r.embeddings.requests - before, 1, "only the query itself is embedded")


class LegacyIndexTests(unittest.TestCase):
    """B13: a legacy (hash-vector) index made every memory tool tell the agent to
    delete chroma_db; doing so left nothing to rebuild the index from, chroma_query
    found nothing, and remember of a known fact minted a duplicate."""

    def test_legacy_index_is_rebuilt_from_the_authority_without_duplicates(self):
        r = SemanticRoot("legacy-index")
        self.addCleanup(r.close)
        (r.root / "chroma_db").mkdir()
        (r.root / "chroma_db" / "memories.json").write_text(json.dumps({
            "ids": ["legacy-0", "legacy-1"],
            "documents": ["Berton lives in Buenos Aires", "Berton likes mate"],
            "metadatas": [{"mem_type": "fact"}, {"mem_type": "fact"}],
            "embeddings": [[0.1] * 16, [0.2] * 16],
            "embedding_model": "hash", "embedding_dimensions": 16, "embedding_schema": 1}))
        r.start()
        out = r.text("chroma_query", query="Berton lives in Buenos Aires", k=1)
        self.assertNotIn("Remove", out)
        self.assertIn("Content: Berton lives in Buenos Aires", out)
        self.assertTrue(r.text("remember", text="Berton lives in Buenos Aires").startswith("REMEMBER-DUPLICATE"))
        self.assertEqual(len(r.memories()), 2)
        self.assertEqual(r.index_ids(), {"legacy-0", "legacy-1"})


class DuplicateDetectionTests(ServiceTestCase):
    """B11: duplicate detection anchored a regex on the raw stored text (so
    surrounding whitespace defeated it) and consulted only the index."""

    def test_whitespace_variants_are_duplicates(self):
        cases = [("  padded fact", "padded fact"), ("fact with newline\n", "fact with newline"),
                 ("line one\nline two", "line one   line two"), ("a.b*c (x) [y] $5 ^ | \\ + ?", " a.b*c (x) [y] $5 ^ | \\ + ?")]
        for stored, again in cases:
            self.r.remember(stored)
            out = self.r.text("remember", text=again)
            self.assertTrue(out.startswith("REMEMBER-DUPLICATE"), "%r vs %r: %s" % (stored, again, out))
        self.assertEqual(len(self.r.memories()), len(cases))

    def test_authority_documents_are_checked_not_only_the_index(self):
        self.r.remember("anchor")
        self.r.tool("remember", text="known only to the authority", env={"FAIL_SAVE": "1"})
        self.r.embeddings.fail = True
        out = self.r.text("remember", text="known only to the authority")
        self.assertTrue(out.startswith("REMEMBER-DUPLICATE"), out)
        self.assertEqual(len(self.r.memories()), 2)


class SpaceMettaTests(ServiceTestCase):
    """B15: atom_space_update merged formalizations from chroma_query output into
    space.metta and never removed any, so forgotten memories' formalizations stayed."""

    TRANSFORM = r"""
import sys, json, importlib.util
spec = importlib.util.spec_from_file_location("asu", sys.argv[1])
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
module.transform(json.loads(sys.argv[2]), [])
"""

    def _transform(self, messages):
        import subprocess
        subprocess.run([sys.executable, "-c", self.TRANSFORM,
                        str(self.r.root / "transformations" / "atom_space_update.py"), json.dumps(messages)],
                       cwd=str(self.r.root), env=self.r.env(), check=True)
        path = self.r.root / "transformations" / ".runtime" / "space.metta"
        return path.read_text() if path.exists() else ""

    def test_space_metta_follows_current_formalizations(self):
        raven = self.r.remember("ravens are birds", mem_type="todo")
        swan = self.r.remember("swans are white", mem_type="todo")
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=raven, formalization="(--> raven bird)"))
        self.assertIn("SUCCESS", self.r.text("formalize_metta", LTM_item=swan, formalization="(--> swan ([] white))"))
        query = self.r.text("chroma_query", query="ravens are birds")
        space = self._transform([{"role": "tool", "content": query}])
        self.assertIn("((--> raven bird) (stv 1.0 0.5))", space)
        self.assertIn("((--> swan ([] white)) (stv 1.0 0.5))", space)
        self.assertTrue(self.r.text("forget", item_id=raven).startswith("FORGET-SUCCESS"))
        space = self._transform([{"role": "user", "content": "hi"}])
        self.assertNotIn("raven", space)
        self.assertIn("((--> swan ([] white)) (stv 1.0 0.5))", space)


if __name__ == "__main__":
    unittest.main()
