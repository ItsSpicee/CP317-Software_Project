"""Manual session inventory, independent of grocery and meal planners.

One JSON file contains all session inventories. A process lock serializes
read/modify/write operations in this single-process prototype.
"""

import json
import math
from pathlib import Path
from threading import RLock
from uuid import uuid4

INVENTORY_FILE = Path(__file__).resolve().parent.parent / "User Data" / "inventory.json"
GROCERY_TYPES = ("meat", "dairy", "produce", "dry_goods")
_LOCK = RLock()


def _session(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A browser session is required to use inventory.")
    return value.strip()


def _name(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Enter an item name.")
    return " ".join(value.split())


def _number(value) -> float:
    if isinstance(value, bool):
        raise ValueError("Enter a finite weight in grams.")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Enter a finite weight in grams.") from exc
    if not math.isfinite(number):
        raise ValueError("Enter a finite weight in grams.")
    return number


def _read() -> dict:
    try:
        data = json.loads(INVENTORY_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"sessions": {}}
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError("Saved inventory is unreadable. It has not been overwritten.") from exc
    try:
        if not isinstance(data, dict) or not isinstance(data.get("sessions"), dict):
            raise ValueError()
        for session_id, items in data["sessions"].items():
            _session(session_id)
            if not isinstance(items, list):
                raise ValueError()
            names = set()
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError()
                name = _name(item.get("name")).casefold()
                if name in names or item.get("grocery_type") not in GROCERY_TYPES:
                    raise ValueError()
                names.add(name)
                if type(item.get("quantity_g")) not in (int, float) or _number(item["quantity_g"]) < 1:
                    raise ValueError()
    except ValueError as exc:
        raise ValueError("Saved inventory has invalid data. It has not been overwritten.") from exc
    return data


def _save(data: dict) -> None:
    text = json.dumps(data, indent=4, ensure_ascii=False, allow_nan=False) + "\n"
    INVENTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = INVENTORY_FILE.with_name(f".inventory.{uuid4().hex}.tmp.json")
    try:
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(INVENTORY_FILE)
    finally:
        temporary.unlink(missing_ok=True)


def _find(items: list[dict], name: str) -> dict:
    for item in items:
        if item["name"].casefold() == name.casefold():
            return item
    raise ValueError("That item is not in this session's inventory.")


def get_inventory(*, session_id: str) -> list[dict]:
    """Load only the requested session's items; missing inventories are empty."""
    session_id = _session(session_id)
    with _LOCK:
        return _read()["sessions"].get(session_id, [])


def add(item: str, amount: float, grocery_type: str, *, session_id: str) -> list[dict]:
    """Add at least 1 g, merging names case-insensitively within a category."""
    session_id, name, amount = _session(session_id), _name(item), _number(amount)
    if amount < 1:
        raise ValueError("Add at least 1 gram.")
    if grocery_type not in GROCERY_TYPES:
        raise ValueError("Choose meat, dairy, produce, or dry_goods.")
    with _LOCK:
        data = _read()
        items = data["sessions"].setdefault(session_id, [])
        existing = next((row for row in items if row["name"].casefold() == name.casefold()), None)
        if existing is None:
            items.append({"name": name, "quantity_g": amount, "grocery_type": grocery_type})
        else:
            if existing["grocery_type"] != grocery_type:
                raise ValueError("This item already exists in another category. Use its existing category.")
            existing["quantity_g"] = _number(existing["quantity_g"] + amount)
        _save(data)
        return items


def remove(item: str, amount: float, *, session_id: str) -> list[dict]:
    """Subtract a positive weight; an exact full removal deletes the item.

    Reject over-removal and partial removals that would leave less than 1 g.
    """
    session_id, name, amount = _session(session_id), _name(item), _number(amount)
    if amount <= 0:
        raise ValueError("Enter a positive weight to remove.")
    with _LOCK:
        data = _read()
        items = data["sessions"].get(session_id, [])
        existing = _find(items, name)
        remaining = existing["quantity_g"] - amount
        if math.isclose(remaining, 0, abs_tol=1e-9):
            items.remove(existing)
        elif remaining < 1:
            raise ValueError("Remove no more than the available weight and leave at least 1 gram, or remove the full amount.")
        else:
            existing["quantity_g"] = remaining
        _save(data)
        return items


def delete(item: str, *, session_id: str) -> list[dict]:
    """Delete a complete entry using its latest saved weight."""
    session_id, name = _session(session_id), _name(item)
    with _LOCK:
        data = _read()
        items = data["sessions"].get(session_id, [])
        items.remove(_find(items, name))
        _save(data)
        return items


def modify(item: str, change: float, *, session_id: str) -> list[dict]:
    """Apply a signed gram adjustment, rejecting any result below 1 g."""
    session_id, name, change = _session(session_id), _name(item), _number(change)
    with _LOCK:
        data = _read()
        items = data["sessions"].get(session_id, [])
        existing = _find(items, name)
        quantity = _number(existing["quantity_g"] + change)
        if quantity < 1:
            raise ValueError("An adjustment must leave at least 1 gram. Use Remove to delete the full amount.")
        existing["quantity_g"] = quantity
        _save(data)
        return items
