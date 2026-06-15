"""Hardening tests: error paths, edge cases, and bad input handling."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memorybank.core import MemoryBank, MemoryBankError, Memory, TOOL_NAME, TOOL_VERSION
from memorybank.cli import main


class CoreHardeningTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "bank.jsonl")

    # --- MemoryBank.add edge cases ---

    def test_add_zero_importance_raises(self):
        b = MemoryBank(self.path)
        with self.assertRaises(MemoryBankError) as cm:
            b.add("test", importance=0)
        self.assertIn("positive", str(cm.exception))

    def test_add_negative_importance_raises(self):
        b = MemoryBank(self.path)
        with self.assertRaises(MemoryBankError) as cm:
            b.add("test", importance=-5.0)
        self.assertIn("positive", str(cm.exception))

    def test_add_whitespace_only_text_raises(self):
        b = MemoryBank(self.path)
        with self.assertRaises(MemoryBankError):
            b.add("   \t\n  ")

    def test_add_empty_tags_list_ok(self):
        b = MemoryBank(self.path)
        m = b.add("some memory", tags=[])
        self.assertEqual(m.tags, [])

    def test_add_deduplicates_tags(self):
        b = MemoryBank(self.path)
        m = b.add("some memory", tags=["a", "b", "a"])
        self.assertEqual(m.tags, ["a", "b"])

    def test_halflife_days_zero_raises(self):
        with self.assertRaises(MemoryBankError) as cm:
            MemoryBank(self.path, halflife_days=0)
        self.assertIn("halflife_days", str(cm.exception))

    def test_halflife_days_negative_raises(self):
        with self.assertRaises(MemoryBankError):
            MemoryBank(self.path, halflife_days=-1.0)

    # --- search edge cases ---

    def test_search_empty_bank_returns_empty_list(self):
        b = MemoryBank(self.path)
        results = b.search("anything")
        self.assertEqual(results, [])

    def test_search_empty_query_returns_results_by_recency(self):
        b = MemoryBank(self.path)
        b.add("memory one")
        b.add("memory two")
        # An empty query has no relevance signal; results are ordered by
        # recency + importance — should still return without error.
        results = b.search("", limit=5, touch=False)
        self.assertIsInstance(results, list)

    def test_search_zero_limit_raises(self):
        b = MemoryBank(self.path)
        b.add("test")
        with self.assertRaises(MemoryBankError) as cm:
            b.search("test", limit=0)
        self.assertIn("limit", str(cm.exception))

    def test_search_negative_limit_raises(self):
        b = MemoryBank(self.path)
        b.add("test")
        with self.assertRaises(MemoryBankError):
            b.search("test", limit=-1)

    def test_search_tag_filter_no_match_returns_empty(self):
        b = MemoryBank(self.path)
        b.add("memory with tag", tags=["infra"])
        results = b.search("memory", tag="nonexistent", touch=False)
        self.assertEqual(results, [])

    def test_search_limit_larger_than_bank_returns_all(self):
        b = MemoryBank(self.path)
        b.add("one")
        b.add("two")
        results = b.search("one two", limit=100, touch=False)
        self.assertEqual(len(results), 2)

    # --- corrupt JSONL file ---

    def test_load_corrupt_jsonl_raises_memorybankerror(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("not valid json\n")
        with self.assertRaises(MemoryBankError) as cm:
            MemoryBank(self.path)
        self.assertIn("corrupt memory", str(cm.exception))

    def test_load_missing_text_field_raises_memorybankerror(self):
        record = {"id": "abc123", "importance": 1.0, "tags": []}
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        with self.assertRaises(MemoryBankError) as cm:
            MemoryBank(self.path)
        self.assertIn("corrupt memory", str(cm.exception))

    def test_load_invalid_importance_raises_memorybankerror(self):
        record = {"text": "hello", "importance": "not-a-number", "tags": []}
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        with self.assertRaises(MemoryBankError) as cm:
            MemoryBank(self.path)
        self.assertIn("corrupt memory", str(cm.exception))

    def test_load_skips_blank_lines(self):
        b = MemoryBank(self.path)
        b.add("valid memory")
        # Manually insert blank lines into the file.
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write("\n\n")
        b2 = MemoryBank(self.path)
        self.assertEqual(len(b2.all()), 1)

    # --- all() edge case ---

    def test_all_empty_bank(self):
        b = MemoryBank(self.path)
        self.assertEqual(b.all(), [])

    # --- Memory.from_dict validation ---

    def test_from_dict_empty_text_raises(self):
        with self.assertRaises((ValueError, KeyError)):
            Memory.from_dict({"text": "   ", "importance": 1.0})

    def test_from_dict_tags_not_list_raises(self):
        with self.assertRaises((ValueError, TypeError)):
            Memory.from_dict({"text": "hello", "tags": "not-a-list", "importance": 1.0})

    # --- TOOL_NAME / TOOL_VERSION available from core ---

    def test_core_exports_tool_identity(self):
        self.assertEqual(TOOL_NAME, "memorybank")
        self.assertTrue(TOOL_VERSION)


class CliHardeningTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "bank.jsonl")

    def test_remember_negative_importance_returns_nonzero(self):
        rc = main(["--path", self.path, "remember", "test", "--importance", "-1.0"])
        self.assertNotEqual(rc, 0)

    def test_remember_zero_importance_returns_nonzero(self):
        rc = main(["--path", self.path, "remember", "test", "--importance", "0"])
        self.assertNotEqual(rc, 0)

    def test_recall_zero_limit_returns_nonzero(self):
        rc = main(["--path", self.path, "recall", "test", "--limit", "0"])
        self.assertNotEqual(rc, 0)

    def test_recall_negative_limit_returns_nonzero(self):
        rc = main(["--path", self.path, "recall", "test", "--limit", "-3"])
        self.assertNotEqual(rc, 0)

    def test_corrupt_bank_returns_nonzero(self):
        corrupt_path = os.path.join(self.dir, "corrupt_only.jsonl")
        with open(corrupt_path, "w", encoding="utf-8") as fh:
            fh.write("totally not json\n")
        rc = main(["--path", corrupt_path, "list"])
        self.assertNotEqual(rc, 0)

    def test_forget_unknown_id_returns_1(self):
        rc = main(["--path", self.path, "forget", "doesnotexist"])
        self.assertEqual(rc, 1)

    def test_list_empty_bank_returns_zero(self):
        rc = main(["--path", self.path, "list"])
        self.assertEqual(rc, 0)

    def test_stats_empty_bank_returns_zero(self):
        rc = main(["--path", self.path, "stats"])
        self.assertEqual(rc, 0)

    def test_recall_no_touch_does_not_update_access(self):
        isolated = os.path.join(self.dir, "no_touch.jsonl")
        main(["--path", isolated, "remember", "recallable"])
        main(["--path", isolated, "recall", "recallable", "--no-touch"])
        b = MemoryBank(isolated)
        self.assertEqual(b.all()[0].access_count, 0)

    def test_bank_path_in_nested_dir_is_created(self):
        nested = os.path.join(self.dir, "a", "b", "c", "bank.jsonl")
        rc = main(["--path", nested, "remember", "nested dir test"])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(nested))


if __name__ == "__main__":
    unittest.main()
