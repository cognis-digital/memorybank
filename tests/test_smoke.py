"""Smoke tests for MEMORYBANK — stdlib only, no network."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memorybank import MemoryBank, MemoryBankError, TOOL_NAME, TOOL_VERSION  # noqa: E402
from memorybank.cli import main  # noqa: E402


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "bank.jsonl")

    def test_add_persist_reload(self):
        b = MemoryBank(self.path)
        m = b.add("User likes dark mode", tags=["prefs"], importance=3)
        self.assertTrue(os.path.exists(self.path))
        # Reload from disk into a fresh instance.
        b2 = MemoryBank(self.path)
        self.assertEqual(len(b2.all()), 1)
        self.assertEqual(b2.all()[0].id, m.id)
        self.assertEqual(b2.all()[0].tags, ["prefs"])

    def test_empty_text_rejected(self):
        b = MemoryBank(self.path)
        with self.assertRaises(MemoryBankError):
            b.add("   ")

    def test_search_ranks_relevant_first(self):
        b = MemoryBank(self.path)
        b.add("The capital of France is Paris")
        b.add("Docker compose runs six services", tags=["infra"])
        b.add("User prefers dark mode in the UI", tags=["prefs"], importance=5)
        res = b.search("what are the user's UI preferences", limit=2)
        self.assertTrue(res)
        self.assertIn("dark mode", res[0]["text"])
        self.assertGreater(res[0]["score"], res[1]["score"])

    def test_tag_filter(self):
        b = MemoryBank(self.path)
        b.add("infra fact", tags=["infra"])
        b.add("prefs fact", tags=["prefs"])
        res = b.search("fact", tag="infra")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["tags"], ["infra"])

    def test_touch_increments_access(self):
        b = MemoryBank(self.path)
        b.add("recallable memory")
        b.search("recallable", touch=True)
        reloaded = MemoryBank(self.path)
        self.assertEqual(reloaded.all()[0].access_count, 1)

    def test_forget_missing_raises(self):
        b = MemoryBank(self.path)
        with self.assertRaises(MemoryBankError):
            b.forget("nope")

    def test_stats(self):
        b = MemoryBank(self.path)
        b.add("a", tags=["x"])
        b.add("b", tags=["x", "y"])
        s = b.stats()
        self.assertEqual(s["count"], 2)
        self.assertEqual(s["tags"]["x"], 2)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "bank.jsonl")

    def test_remember_then_recall(self):
        rc = main(["--path", self.path, "remember", "dark mode preferred", "--tag", "prefs"])
        self.assertEqual(rc, 0)
        rc = main(["--path", self.path, "recall", "mode", "--format", "json"])
        self.assertEqual(rc, 0)

    def test_recall_table_format(self):
        main(["--path", self.path, "remember", "hello world"])
        rc = main(["--path", self.path, "recall", "hello", "--format", "table"])
        self.assertEqual(rc, 0)

    def test_forget_unknown_returns_nonzero(self):
        rc = main(["--path", self.path, "forget", "deadbeef"])
        self.assertEqual(rc, 1)

    def test_metadata(self):
        self.assertEqual(TOOL_NAME, "memorybank")
        self.assertTrue(TOOL_VERSION)


if __name__ == "__main__":
    unittest.main()
