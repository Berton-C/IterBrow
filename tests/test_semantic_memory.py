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


if __name__ == "__main__":
    unittest.main()
