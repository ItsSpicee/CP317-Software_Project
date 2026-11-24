"""Inventory persistence, weight limits, isolation, and UI event integration."""

import json
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Application import inventory as stock
from Application.inventory_page import InventoryState


class InventoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "inventory.json"
        patcher = patch.object(stock, "INVENTORY_FILE", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def add(self, name="Rice", amount=100, category="dry_goods", session="a"):
        return stock.add(name, amount, category, session_id=session)

    def test_missing_inventory_is_empty_and_requires_session(self):
        self.assertEqual(stock.get_inventory(session_id="a"), [])
        with self.assertRaises(ValueError):
            stock.get_inventory(session_id="")

    def test_add_persists_in_one_file_and_merges_case_insensitively(self):
        self.add("  Brown   rice ", 200)
        result = self.add("brown rice", 50)
        self.assertEqual(result, [{"name": "Brown rice", "quantity_g": 250, "grocery_type": "dry_goods"}])
        self.assertEqual(json.loads(self.path.read_text())["sessions"]["a"], result)
        self.assertEqual(stock.get_inventory(session_id="a"), result)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_sessions_are_independent_in_the_central_file(self):
        self.add(amount=200, session="a")
        self.add(amount=80, session="b")
        stock.modify("rice", -50, session_id="a")
        self.assertEqual(stock.get_inventory(session_id="a")[0]["quantity_g"], 150)
        self.assertEqual(stock.get_inventory(session_id="b")[0]["quantity_g"], 80)
        self.assertEqual(set(json.loads(self.path.read_text())["sessions"]), {"a", "b"})

    def test_signed_modification_accepts_one_gram_but_rejects_less(self):
        self.add(amount=10)
        stock.modify("Rice", 5, session_id="a")
        self.assertEqual(stock.modify("Rice", -14, session_id="a")[0]["quantity_g"], 1)
        original = self.path.read_bytes()
        for change in (-.1, -1, -100):
            with self.subTest(change=change), self.assertRaises(ValueError):
                stock.modify("Rice", change, session_id="a")
        self.assertEqual(self.path.read_bytes(), original)

    def test_partial_and_full_removal(self):
        self.add(amount=10.5)
        self.assertEqual(stock.remove("Rice", .5, session_id="a")[0]["quantity_g"], 10)
        self.assertEqual(stock.remove("Rice", 9, session_id="a")[0]["quantity_g"], 1)
        self.assertEqual(stock.remove("Rice", 1, session_id="a"), [])
        self.assertEqual(stock.get_inventory(session_id="a"), [])

    def test_invalid_removal_does_not_change_saved_inventory(self):
        self.add(amount=10)
        original = self.path.read_bytes()
        for amount in (0, -1, 9.5, 11, float("nan"), True):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                stock.remove("Rice", amount, session_id="a")
        self.assertEqual(self.path.read_bytes(), original)

    def test_invalid_additions_do_not_create_a_file(self):
        for amount in (0, .5, -2, True, float("inf"), float("nan"), "bad"):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                self.add(amount=amount)
        for name, category in ((" ", "meat"), ("Rice", "unknown")):
            with self.subTest(name=name, category=category), self.assertRaises(ValueError):
                self.add(name=name, category=category)
        self.assertFalse(self.path.exists())

    def test_category_conflicts_are_rejected_without_changing_stock(self):
        self.add()
        with self.assertRaises(ValueError):
            self.add(category="produce")
        self.assertEqual(stock.get_inventory(session_id="a")[0]["quantity_g"], 100)

    def test_unknown_item_and_invalid_change_are_rejected(self):
        self.add()
        for method, amount in ((stock.modify, 1), (stock.remove, 1)):
            with self.assertRaises(ValueError):
                method("missing", amount, session_id="a")
        for change in (True, float("inf"), "bad"):
            with self.assertRaises(ValueError):
                stock.modify("Rice", change, session_id="a")

    def test_malformed_inventory_is_not_silently_overwritten(self):
        for text in ("{broken", "[]", '{"sessions": []}', '{"sessions": {"a": [{}]}}'):
            self.path.write_text(text, encoding="utf-8")
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.add()
            self.assertEqual(self.path.read_text(), text)

    def test_atomic_save_failure_preserves_previous_file(self):
        self.add()
        original = self.path.read_bytes()
        with patch.object(Path, "replace", side_effect=OSError("write failed")):
            with self.assertRaises(OSError):
                stock.modify("Rice", 1, session_id="a")
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_overflow_is_rejected_without_changing_saved_data(self):
        self.add(amount=1e308)
        original = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.add(amount=1e308)
        self.assertEqual(self.path.read_bytes(), original)

    def test_concurrent_updates_do_not_lose_other_session_data(self):
        def increment(index):
            self.add(amount=1, session=str(index % 2))
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(increment, range(40)))
        for session in ("0", "1"):
            self.assertEqual(stock.get_inventory(session_id=session)[0]["quantity_g"], 20)

    def test_profile_changes_do_not_clear_manual_inventory(self):
        from Application import grocery_planner
        self.add()
        original = self.path.read_bytes()
        with patch.object(grocery_planner, "USER_DATA_FOLDER", self.path.parent):
            grocery_planner.invalidate_weekly_plan()
        self.assertEqual(self.path.read_bytes(), original)

    def test_ui_events_update_the_same_json_and_report_errors(self):
        state = SimpleNamespace(error="", status="", rows=[], summary="", selected="", _session_id=lambda: "a")
        state._apply = lambda items: InventoryState._apply(state, items)
        state._failure = lambda exc: InventoryState._failure(state, exc)
        InventoryState.add_item.fn(state, {"item": "Rice", "amount": "100", "grocery_type": "Dry goods"})
        self.assertEqual(state.rows[0]["quantity"], "100 g")
        self.assertEqual(state.error, "")
        InventoryState.select_item.fn(state, "Rice")
        InventoryState.adjust_item.fn(state, {"change": "-20"})
        self.assertEqual(stock.get_inventory(session_id="a")[0]["quantity_g"], 80)
        InventoryState.adjust_item.fn(state, {"change": "-80"})
        self.assertIn("at least 1 gram", state.error)
        InventoryState.remove_amount.fn(state, {"amount": "80"})
        self.assertEqual(state.rows, [])
        self.assertEqual(state.selected, "")
        InventoryState.load_inventory.fn(state)
        self.assertEqual(state.error, "")
        self.add(session="b")
        InventoryState.add_item.fn(state, {"item": "Rice", "amount": "100", "grocery_type": "Dry goods"})
        InventoryState.select_item.fn(state, "Rice")
        InventoryState.remove_entry.fn(state, "Rice")
        self.assertEqual(stock.get_inventory(session_id="a"), [])
        self.assertEqual(state.selected, "")
        self.assertEqual(len(stock.get_inventory(session_id="b")), 1)


if __name__ == "__main__":
    unittest.main()
