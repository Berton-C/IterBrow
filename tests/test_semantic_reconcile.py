#!/usr/bin/env python3
"""Index -> authority reconcile on the owner's existing data.

B1 (review 3): reconcile deleted index-only memories ("orphans").  The old code
reported success for writes that never reached the AtomSpace (deferred commits,
direct index writes), so an orphan is a memory the agent believes it stored.
Reconcile must adopt it into the authority, keep a one-time backup of the index
it found, log index versions that differ from the authority instead of silently
discarding them, and tell the agent what it did.
"""
import hashlib
import json
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from semantic_memory_support import SemanticRoot, fake_vector  # noqa: E402
from test_semantic_memory import write_current_index  # noqa: E402


def pack(vector):
    low, high = min(vector), max(vector)
    scale = (high - low) / 255.0
    return {"q": bytes(int(round((v - low) / scale)) for v in vector).hex(), "s": scale, "o": low}


OWNER_IDS = ["m-0", "m-1", "m-2", "m-3"]
OWNER_DOCS = ["Berton prefers concise answers", "Berton lives in Buenos Aires",
              "IterBrow uses Electron", "Tab locking is per tab"]
OWNER_METAS = [{"mem_type": "fact", "provenance_type": "observed", "strength": 1.0, "confidence": 0.5},
               {"mem_type": "fact", "provenance_type": "observed", "strength": 0.9, "confidence": 0.8,
                "linkedEpisodes": ["26", "27"]},
               {"mem_type": "preference", "provenance_type": "observed", "linkedEpisodes": ["30"]},
               {"mem_type": "fact", "provenance_type": "observed"}]
ORPHAN_DOC = "Owner's son is building a video game (stored while the AtomSpace deferred)"
ORPHAN_META = {"mem_type": "fact", "provenance_type": "observed", "time": "2026-09-01 10:00:00"}
PENDING_DOC = "Berton is travelling to India in November"
PENDING_META = {"mem_type": "fact", "provenance_type": "observed", "time": "2026-09-02 11:00:00"}


class OrphanAdoptionTests(unittest.TestCase):
    """B1: owner-shaped index after the legacy migration, drifted by old-code writes."""

    def setUp(self):
        r = self.r = SemanticRoot("orphans")
        self.addCleanup(r.close)
        write_current_index(r.root, list(OWNER_IDS), list(OWNER_DOCS), [dict(m) for m in OWNER_METAS])
        r.start()  # legacy migration: authority == index
        r.stop()
        path = r.root / "chroma_db" / "memories.json"
        db = json.loads(path.read_text())
        # An old-code write that only reached the index.
        db["ids"].append("orphan-real")
        db["documents"].append(ORPHAN_DOC)
        db["metadatas"].append(dict(ORPHAN_META))
        db["embeddings"].append(pack(fake_vector(ORPHAN_DOC)))
        # An old-code metadata edit that only reached the index.
        db["metadatas"][1] = dict(OWNER_METAS[1], strength=0.95, confidence=0.9)
        path.write_text(json.dumps(db))
        self.original_index = path.read_bytes()
        self.orphan_vector = db["embeddings"][-1]
        # Old-code pending entries: one for the orphan, one for a write that
        # reached neither side.
        pending = r.root / ".runtime" / "memory_pending"
        pending.mkdir(parents=True, exist_ok=True)
        for item_id, doc, meta in (("orphan-real", ORPHAN_DOC, ORPHAN_META),
                                   ("pending-only", PENDING_DOC, PENDING_META)):
            canonical = json.dumps(["remembered", [{"id": item_id, "document": doc, "metadata": meta}], []],
                                   sort_keys=True, ensure_ascii=False)
            (pending / (hashlib.sha256(canonical.encode()).hexdigest() + ".json")).write_text(
                json.dumps({"operation_id": uuid.uuid4().hex, "request": json.loads(canonical)}))
        r.start()

    def test_orphans_are_adopted_not_deleted(self):
        r = self.r
        out = r.text("chroma_query", query="son video game", k=10)
        memories = r.memories()
        self.assertIn("orphan-real", memories, "an index-only memory was deleted")
        document, metadata = memories["orphan-real"]
        self.assertEqual(document, ORPHAN_DOC)
        self.assertTrue(metadata.get("reconciled_from_index"))
        self.assertEqual({k: v for k, v in metadata.items() if k != "reconciled_from_index"}, ORPHAN_META)
        self.assertIn("orphan-real", r.index_ids())
        self.assertIn("ID: orphan-real", out)
        index = r.index()
        self.assertEqual(index["embeddings"][index["ids"].index("orphan-real")], self.orphan_vector,
                         "an adopted orphan was re-embedded")

    def test_pending_writes_that_reached_neither_side_are_committed(self):
        r = self.r
        r.text("chroma_query", query="India", k=1)
        by_doc = {doc: (item_id, meta) for item_id, (doc, meta) in r.memories().items()}
        self.assertIn(PENDING_DOC, by_doc)
        self.assertEqual(by_doc[PENDING_DOC][0], "pending-only")
        self.assertEqual(r.index_ids(), set(r.memories()))
        self.assertEqual(r.pending_files(), [])

    def test_first_reconcile_keeps_a_backup_and_never_overwrites_it(self):
        r = self.r
        r.text("chroma_query", query="anything")
        backups = sorted((r.root / "chroma_db").glob("memories.pre-reconcile-*.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), self.original_index)
        r.text("remember", text="a later memory")
        r.text("chroma_query", query="anything")
        self.assertEqual(sorted((r.root / "chroma_db").glob("memories.pre-reconcile-*.json")), backups)
        self.assertEqual(backups[0].read_bytes(), self.original_index)

    def test_differing_index_versions_are_logged_not_discarded(self):
        r = self.r
        r.text("chroma_query", query="anything")
        index = r.index()
        self.assertEqual(index["metadatas"][index["ids"].index("m-1")], r.memories()["m-1"][1],
                         "the authority stays the truth for the index")
        log = r.root / "chroma_db" / "reconcile_conflicts.jsonl"
        entries = [json.loads(line) for line in log.read_text().splitlines()]
        self.assertEqual([e["id"] for e in entries], ["m-1"])
        self.assertEqual(entries[0]["index_metadata"]["confidence"], 0.9)
        self.assertEqual(entries[0]["authority_metadata"]["confidence"], 0.8)

    def test_tools_surface_what_reconcile_did_once(self):
        r = self.r
        out = r.text("chroma_query", query="anything")
        notice = [line for line in out.splitlines() if "reconcile" in line.lower()]
        self.assertEqual(len(notice), 1, out)
        self.assertIn("adopted 2", notice[0])
        self.assertIn("reconcile_conflicts.jsonl", notice[0])
        again = r.text("chroma_query", query="anything")
        self.assertNotIn("reconcile", again.lower())

    def test_remember_surfaces_the_notice_too(self):
        out = self.r.text("remember", text="a brand new memory")
        self.assertTrue(out.startswith("REMEMBER-SUCCESS"), out)
        self.assertIn("adopted 2", out)


class ForgottenOrphanTests(unittest.TestCase):
    """Adoption must not resurrect a memory whose forget committed but whose
    index save failed."""

    def test_a_forgotten_memory_left_in_the_index_stays_forgotten(self):
        r = SemanticRoot("forgotten")
        self.addCleanup(r.close)
        r.start()
        keep = r.remember("keep me")
        gone = r.remember("forget me", mem_type="todo")
        r.tool("forget", item_id=gone, env={"FAIL_SAVE": "1"})
        self.assertNotIn(gone, r.memories())
        self.assertIn(gone, r.index_ids())
        r.text("chroma_query", query="forget me")
        self.assertEqual(set(r.memories()), {keep})
        self.assertEqual(r.index_ids(), {keep})


if __name__ == "__main__":
    unittest.main()
