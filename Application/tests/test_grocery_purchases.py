"""Dated grocery purchase history and duplicate-purchase protection."""

import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Application import grocery_planner as planner
from Application import inventory


class GroceryPurchaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for target, field, value in (
            (planner, "USER_DATA_FOLDER", self.root),
            (inventory, "INVENTORY_FILE", self.root / "inventory.json"),
        ):
            patcher = patch.object(target, field, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.plan = {
            "plan_id": "first-plan",
            "items": [{
                "name": "Rice", "grocery_type": "dry_goods",
                "quantity_g": 100, "preparation": "Cook in water.",
                "calories": 350, "protein": 7, "carbs": 80,
                "fat": 1, "fiber": 2,
            }],
            "notes": "",
        }

    def test_same_instant_purchases_create_separate_dated_files(self):
        fixed = datetime(2026, 11, 26, 14, 30, 12, tzinfo=timezone.utc)
        with patch.object(planner, "datetime") as clock:
            clock.now.return_value.astimezone.return_value = fixed
            planner.record_purchase(self.plan, "session-a")
            second = {**self.plan, "plan_id": "second-plan"}
            planner.record_purchase(second, "session-a")
        records = list(planner.purchase_folder("session-a").glob("*.json"))
        self.assertEqual(len(records), 2)
        for path in records:
            self.assertTrue(path.name.startswith("grocery_purchase_2026-11-26_143012_"))
            saved = planner._read_json(path)
            self.assertEqual(saved["purchased_at"], fixed.isoformat())
            self.assertEqual(saved["items"], self.plan["items"])
        self.assertEqual(inventory.get_inventory(session_id="session-a")[0]["quantity_g"], 200)
        self.assertFalse(planner.inventory_path("session-a").exists())
        # An earlier purchase remains protected after a newer purchase.
        with self.assertRaisesRegex(ValueError, "already"):
            planner.record_purchase(self.plan, "session-a")
        self.assertEqual(inventory.get_inventory(session_id="session-a")[0]["quantity_g"], 200)
        self.assertFalse(planner.is_purchased(self.plan, "session-b"))

    def test_legacy_purchase_still_prevents_duplicate(self):
        planner._save_json(planner.inventory_path("session-a"), self.plan)
        with self.assertRaisesRegex(ValueError, "already"):
            planner.record_purchase(self.plan, "session-a")
        self.assertEqual(inventory.get_inventory(session_id="session-a"), [])

    def test_preferences_invalidation_preserves_purchase_history(self):
        planner.record_purchase(self.plan, "session-a")
        planner._save_json(planner.suggestion_path("session-a"), self.plan)
        planner.invalidate_weekly_plan()
        self.assertFalse(planner.suggestion_path("session-a").exists())
        self.assertTrue(planner.is_purchased(self.plan, "session-a"))
        self.assertEqual(len(list(planner.purchase_folder("session-a").glob("*.json"))), 1)

    def test_failed_purchase_record_restores_stock_and_retry_adds_once(self):
        inventory.add("Rice", 40, "dry_goods", session_id="session-a")
        inventory.add("Milk", 70, "dairy", session_id="session-b")
        before = inventory._read()
        with patch.object(planner, "_save_json", side_effect=OSError("Purchase write failed")):
            with self.assertRaisesRegex(OSError, "Purchase write failed"):
                planner.record_purchase(self.plan, "session-a")
        self.assertEqual(inventory._read(), before)
        self.assertFalse(planner.is_purchased(self.plan, "session-a"))
        self.assertEqual(list(planner.purchase_folder("session-a").glob("*.json")), [])
        planner.record_purchase(self.plan, "session-a")
        self.assertEqual(inventory.get_inventory(session_id="session-a")[0]["quantity_g"], 140)
        self.assertTrue(planner.is_purchased(self.plan, "session-a"))
        with self.assertRaisesRegex(ValueError, "already"):
            planner.record_purchase(self.plan, "session-a")
        self.assertEqual(inventory.get_inventory(session_id="session-a")[0]["quantity_g"], 140)

    def test_failed_purchase_with_empty_inventory_leaves_no_items(self):
        with patch.object(planner, "_save_json", side_effect=OSError("Purchase write failed")):
            with self.assertRaises(OSError):
                planner.record_purchase(self.plan, "session-a")
        self.assertEqual(inventory.get_inventory(session_id="session-a"), [])
        self.assertFalse(planner.is_purchased(self.plan, "session-a"))


if __name__ == "__main__":
    unittest.main()
