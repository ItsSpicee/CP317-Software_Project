"""Session inventory shared by the Inventory, Groceries, and Meals pages.

One JSON file contains all session inventories. A process lock serializes
read/modify/write operations in this single-process prototype.

Every saved item keeps at least 1 g, so each operation checks its result
before saving. A failed check leaves the file untouched.
"""

import json
import math
from pathlib import Path
from threading import RLock
from uuid import uuid4

INVENTORY_FILE = Path(__file__).resolve().parent.parent / "User Data" / "inventory.json"
GROCERY_TYPES = ("meat", "dairy", "produce", "dry_goods")
TYPE_LABELS = {"meat": "Meat", "dairy": "Dairy", "produce": "Produce", "dry_goods": "Dry goods"}
MAX_NAME_LENGTH = 80
MAX_QUANTITY_G = 100_000
_LOCK = RLock()


def _session(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A browser session is required to use inventory.")
    return value.strip()


def _name(value: str, *, check_length: bool = True) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Enter an item name.")
    name = " ".join(value.split())
    if check_length and len(name) > MAX_NAME_LENGTH:
        raise ValueError(f"Use {MAX_NAME_LENGTH} characters or fewer for the item name.")
    return name


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


def _quantity(value: float) -> float:
    """Round away float drift and enforce the per-item ceiling."""
    quantity = round(_number(value), 3)
    if quantity > MAX_QUANTITY_G:
        raise ValueError(f"An item can hold at most {MAX_QUANTITY_G:,} g.")
    return quantity


def _category(value: str) -> str:
    if value not in GROCERY_TYPES:
        raise ValueError("Choose meat, dairy, produce, or dry_goods.")
    return value


def _grams(value: float) -> str:
    return f"{value:,.2f}".rstrip("0").rstrip(".") + " g"


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
                name = _name(item.get("name"), check_length=False).casefold()
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


def _lookup(items: list[dict], name: str) -> dict | None:
    key = name.casefold()
    return next((item for item in items if item["name"].casefold() == key), None)


def _find(items: list[dict], name: str) -> dict:
    item = _lookup(items, name)
    if item is None:
        raise ValueError(f"{name} is not in your inventory.")
    return item


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
    grocery_type = _category(grocery_type)
    with _LOCK:
        data = _read()
        items = data["sessions"].setdefault(session_id, [])
        existing = _lookup(items, name)
        if existing is None:
            items.append({"name": name, "quantity_g": _quantity(amount), "grocery_type": grocery_type})
        else:
            if existing["grocery_type"] != grocery_type:
                label = TYPE_LABELS[existing["grocery_type"]]
                raise ValueError(f"{existing['name']} is already listed under {label}. Use that category.")
            existing["quantity_g"] = _quantity(existing["quantity_g"] + amount)
        _save(data)
        return items


def add_many(groceries: list[dict], *, session_id: str) -> list[dict]:
    """Add a purchased grocery list in one save.

    Each entry needs name, quantity_g, and grocery_type. Names already in the
    inventory are topped up and keep their existing category. Amounts under
    1 g are rounded up to 1 g, since an item must hold at least 1 g.
    Nothing is saved unless every entry is valid.
    """
    session_id = _session(session_id)
    if not isinstance(groceries, list) or not groceries:
        raise ValueError("There are no groceries to add.")

    incoming: dict[str, dict] = {}
    for grocery in groceries:
        if not isinstance(grocery, dict):
            raise ValueError("Each grocery must be an object.")
        name = _name(grocery.get("name"))
        amount = _number(grocery.get("quantity_g"))
        if amount <= 0:
            raise ValueError(f"{name} needs a positive weight.")
        grocery_type = _category(grocery.get("grocery_type"))
        key = name.casefold()
        if key in incoming:
            incoming[key]["quantity_g"] += amount
        else:
            incoming[key] = {"name": name, "quantity_g": amount, "grocery_type": grocery_type}

    with _LOCK:
        data = _read()
        items = data["sessions"].setdefault(session_id, [])
        updates = []
        for entry in incoming.values():
            existing = _lookup(items, entry["name"])
            current = existing["quantity_g"] if existing else 0
            updates.append((existing, entry, _quantity(current + max(entry["quantity_g"], 1))))
        # Every total passed its check, so apply them all.
        for existing, entry, quantity in updates:
            if existing is None:
                items.append({"name": entry["name"], "quantity_g": quantity, "grocery_type": entry["grocery_type"]})
            else:
                existing["quantity_g"] = quantity
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
        if math.isclose(remaining, 0, abs_tol=1e-6):
            items.remove(existing)
        elif remaining < 0:
            raise ValueError(f"Only {_grams(existing['quantity_g'])} of {existing['name']} is available.")
        elif remaining < 1:
            raise ValueError("At least 1 gram must remain. Remove the full amount to delete the item.")
        else:
            existing["quantity_g"] = _quantity(remaining)
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
    if change == 0:
        raise ValueError("Enter a change other than 0.")
    with _LOCK:
        data = _read()
        items = data["sessions"].get(session_id, [])
        existing = _find(items, name)
        quantity = _number(existing["quantity_g"] + change)
        if quantity < 1:
            raise ValueError("An adjustment must leave at least 1 gram. Use Remove to delete the full amount.")
        existing["quantity_g"] = _quantity(quantity)
        _save(data)
        return items


def consume_many(ingredients: list[dict], *, session_id: str) -> list[dict]:
    """Atomically consume multiple ingredients from inventory.

    Each ingredient is either used up completely or leaves at least 1 g.
    """
    session_id = _session(session_id)
    if not isinstance(ingredients, list) or not ingredients:
        raise ValueError("A meal must contain ingredients.")

    required: dict[str, float] = {}
    for ingredient in ingredients:
        if not isinstance(ingredient, dict):
            raise ValueError("Invalid meal ingredient.")
        name = _name(ingredient.get("name"), check_length=False)
        amount = _number(ingredient.get("quantity_g"))
        if amount <= 0:
            raise ValueError("Ingredient quantities must be positive.")
        key = name.casefold()
        required[key] = required.get(key, 0) + amount

    with _LOCK:
        data = _read()
        items = data["sessions"].get(session_id, [])

        # Validate every ingredient before changing anything.
        plan = []
        for key, amount in required.items():
            existing = _lookup(items, key)
            if existing is None:
                raise ValueError(f"{key.title()} is not in your inventory.")
            remaining = existing["quantity_g"] - amount
            if remaining < -1e-6:
                raise ValueError(f"Not enough {existing['name']} in inventory.")
            if 1e-6 < remaining < 1:
                raise ValueError(
                    f"Using this recipe would leave less than 1 g of {existing['name']}. "
                    "Adjust the inventory amount or recipe."
                )
            plan.append((existing, remaining))

        for existing, remaining in plan:
            if remaining <= 1e-6:
                items.remove(existing)
            else:
                existing["quantity_g"] = _quantity(remaining)

        _save(data)
        return items