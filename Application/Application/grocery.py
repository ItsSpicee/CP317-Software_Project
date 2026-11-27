"""Weekly grocery planner UI wired to grocery_planner.py.

Plans count what is already in the session inventory, so the page shows
two lists: what to buy and what comes from your inventory.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import reflex as rx

from . import grocery_planner as planner
from . import inventory as stock
from .ui import actions, field, go, page, press

SORT_OPTIONS = [
    "Default order",
    "Name A–Z",
    "Name Z–A",
    "Calories low → high",
    "Calories high → low",
    "Quantity low → high",
    "Quantity high → low",
    "Protein high → low",
]


@dataclass
class GroceryItem:
    name: str = ""
    grocery_type: str = ""
    quantity_label: str = ""
    preparation: str = ""
    calories_label: str = ""
    protein_label: str = ""
    carbs_label: str = ""
    fat_label: str = ""
    fiber_label: str = ""
    quantity_g: float = 0.0
    calories: float = 0.0
    protein: float = 0.0
    order_index: int = 0


def _format_item(item: dict, order_index: int = 0) -> GroceryItem:
    quantity_g = float(item["quantity_g"])
    calories = float(item["calories"])
    protein = float(item["protein"])
    carbs = float(item["carbs"])
    fat = float(item["fat"])
    fiber = float(item["fiber"])
    return GroceryItem(
        name=str(item["name"]),
        grocery_type=str(item["grocery_type"]),
        quantity_label=f"{quantity_g:,.0f} g",
        preparation=str(item["preparation"]),
        calories_label=f"{calories:,.0f} kcal",
        protein_label=f"{protein:.0f} g",
        carbs_label=f"{carbs:.0f} g",
        fat_label=f"{fat:.0f} g",
        fiber_label=f"{fiber:.0f} g",
        quantity_g=quantity_g,
        calories=calories,
        protein=protein,
        order_index=order_index,
    )


def _sorted_items(items: list[GroceryItem], sort_by: str) -> list[GroceryItem]:
    rows = list(items)
    if sort_by == "Name A–Z":
        return sorted(rows, key=lambda row: (row.name.lower(), row.order_index))
    if sort_by == "Name Z–A":
        return sorted(
            rows, key=lambda row: (row.name.lower(), row.order_index), reverse=True
        )
    if sort_by == "Calories low → high":
        return sorted(rows, key=lambda row: (row.calories, row.order_index))
    if sort_by == "Calories high → low":
        return sorted(rows, key=lambda row: (-row.calories, row.order_index))
    if sort_by == "Quantity low → high":
        return sorted(rows, key=lambda row: (row.quantity_g, row.order_index))
    if sort_by == "Quantity high → low":
        return sorted(rows, key=lambda row: (-row.quantity_g, row.order_index))
    if sort_by == "Protein high → low":
        return sorted(rows, key=lambda row: (-row.protein, row.order_index))
    return sorted(rows, key=lambda row: row.order_index)


def _read_suggestion(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        planner._validate_suggestion(value)
    except ValueError:
        return None
    if "estimated_weekly_totals" not in value or not isinstance(
        value["estimated_weekly_totals"], dict
    ):
        return None
    return value


def _count(number: int, singular: str, plural: str) -> str:
    return f"{number} {singular if number == 1 else plural}"


MODEL_UNAVAILABLE_TITLE = "Model temporarily unavailable"
MODEL_UNAVAILABLE_BODY = (
    "The grocery model is under high demand right now. "
    "This usually clears quickly — wait a moment, then try again."
)


def _is_model_unavailable(message: str) -> bool:
    lower = message.lower()
    return any(
        token in lower
        for token in (
            "503",
            "unavailable",
            "high demand",
            "resource_exhausted",
            "overloaded",
            "try again later",
        )
    )


def _friendly_error(exc: Exception) -> tuple[str, str]:
    """Return (kind, message). kind is 'unavailable' or 'error'."""
    message = str(exc).strip() or "Something went wrong while planning groceries."
    if _is_model_unavailable(message):
        return "unavailable", MODEL_UNAVAILABLE_BODY
    if "GEMINI_API_KEY" in message or "GEMINI_MODEL" in message:
        return "error", message
    if "positive daily calorie" in message.lower():
        return "error", "Set a positive calorie target on Preferences before planning groceries."
    if "user_data.json" in message or "user_personalization_data.json" in message:
        return "error", "Complete Profile and Preferences before planning groceries."
    if "allergies" in message or "diet_types" in message:
        return (
            "error",
            "Saved allergies or diet types look invalid. Re-save Preferences, then try again.",
        )
    if "Provide nonempty feedback" in message:
        return "error", "Enter feedback describing what to change."
    if "weekly_suggestion.json" in message:
        return "error", "Generate a grocery plan first, then revise it."
    if "at least one grocery or inventory item" in message:
        return "error", "The model returned an empty plan. Try again."
    if "Gemini" in message:
        return "error", "The grocery model returned an incomplete response. Try again."
    if "timeout" in message.lower() or "timed out" in message.lower():
        return "error", "The grocery request took longer than 2 minutes. Try again."
    return "error", message


class GroceryState(rx.State):
    has_plan: bool = False
    busy: bool = False
    purchased: bool = False
    error: str = ""
    error_kind: str = ""
    status: str = ""
    notes: str = ""
    feedback: str = ""
    sort_by: str = "Default order"
    selected_types: list[str] = []
    items: list[GroceryItem] = []
    display_items: list[GroceryItem] = []
    pantry_items: list[GroceryItem] = []
    display_pantry: list[GroceryItem] = []
    has_pantry: bool = False
    nothing_to_buy: bool = False
    inventory_stale: bool = False
    inventory_count: int = 0
    split_line: str = ""
    calories_total: str = "0"
    calories_daily: str = "0"
    protein_total: str = "0 g"
    protein_day: str = "0 g"
    carbs_total: str = "0 g"
    carbs_day: str = "0 g"
    fat_total: str = "0 g"
    fat_day: str = "0 g"
    fiber_total: str = "0 g"
    fiber_day: str = "0 g"
    item_count: str = "0 to buy"

    @rx.var
    def inventory_hint(self) -> str:
        if self.inventory_count == 0:
            return "Your inventory is empty, so the list will cover the whole week."
        return (
            f"The list will count the {_count(self.inventory_count, 'item', 'items')} "
            "in your inventory and only suggest what you still need."
        )

    def _refresh_display(self) -> None:
        def keep(item: GroceryItem) -> bool:
            return not self.selected_types or item.grocery_type in self.selected_types

        self.display_items = _sorted_items([i for i in self.items if keep(i)], self.sort_by)
        self.display_pantry = _sorted_items([i for i in self.pantry_items if keep(i)], self.sort_by)

    def _apply_suggestion(self, suggestion: dict) -> None:
        to_buy = suggestion["items"]
        used = suggestion.get("inventory_used", [])
        self.items = [_format_item(item, order_index=index) for index, item in enumerate(to_buy)]
        self.pantry_items = [_format_item(item, order_index=index) for index, item in enumerate(used)]
        self._refresh_display()
        self.has_pantry = bool(used)
        self.nothing_to_buy = not to_buy
        self.notes = str(suggestion.get("notes", "")).strip()

        totals = suggestion["estimated_weekly_totals"]
        weekly = float(totals["calories"])
        self.calories_total = f"{weekly:,.0f}"
        self.calories_daily = f"{weekly / 7:,.0f}"
        for name in ("protein", "carbs", "fat", "fiber"):
            grams = float(totals[name])
            setattr(self, f"{name}_total", f"{grams:.0f} g")
            setattr(self, f"{name}_day", f"{grams / 7:.0f} g")

        count = _count(len(to_buy), "item", "items") + " to buy"
        if used:
            count += f" · {len(used)} from your inventory"
        self.item_count = count

        if used:
            buy_kcal = sum(float(item["calories"]) for item in to_buy)
            have_kcal = sum(float(item["calories"]) for item in used)
            self.split_line = f"{have_kcal:,.0f} kcal from your inventory · {buy_kcal:,.0f} kcal to buy"
        else:
            self.split_line = ""
        self.has_plan = True

    def _clear_plan(self) -> None:
        self.has_plan = False
        self.purchased = False
        self.inventory_stale = False
        self.notes = ""
        self.items = []
        self.display_items = []
        self.pantry_items = []
        self.display_pantry = []
        self.has_pantry = False
        self.nothing_to_buy = False
        self.split_line = ""
        self.sort_by = "Default order"
        self.selected_types = []
        self.calories_total = "0"
        self.calories_daily = "0"
        for name in ("protein", "carbs", "fat", "fiber"):
            setattr(self, f"{name}_total", "0 g")
            setattr(self, f"{name}_day", "0 g")
        self.item_count = "0 to buy"

    def _session_id(self) -> str:
        return self.rx_router_session.client_token or ""

    def _sync_inventory(self, session_id: str, suggestion: dict | None = None) -> None:
        """Count inventory and flag plans made from different stock."""
        try:
            rows = stock.get_inventory(session_id=session_id) if session_id else []
        except ValueError as exc:
            self.inventory_count = 0
            self.inventory_stale = False
            self._set_error("error", str(exc))
            return
        self.inventory_count = len(rows)
        self.inventory_stale = (
            suggestion is not None
            and not self.purchased
            and not planner.plan_matches_inventory(suggestion, rows)
        )

    def _clear_error(self) -> None:
        self.error = ""
        self.error_kind = ""

    def _set_error(self, kind: str, message: str) -> None:
        self.error_kind = kind
        self.error = message

    def _ready_status(self, suggestion: dict, prefix: str) -> str:
        used = len(suggestion.get("inventory_used", []))
        if not suggestion["items"]:
            return f"{prefix} Your inventory covers the week, so there is nothing to buy."
        if used:
            return f"{prefix} It counts {_count(used, 'item', 'items')} from your inventory."
        return prefix

    @rx.event
    def load_plan(self):
        self._clear_error()
        self.status = ""
        session_id = self._session_id()
        suggestion = _read_suggestion(planner.suggestion_path(session_id))
        if suggestion is None:
            self._clear_plan()
            self._sync_inventory(session_id)
            return
        self._apply_suggestion(suggestion)
        self.purchased = planner.is_purchased(suggestion, session_id)
        self._sync_inventory(session_id, suggestion)

    @rx.event
    def set_feedback(self, value: str):
        self.feedback = value

    @rx.event
    def set_sort(self, value: str):
        self.sort_by = value if value in SORT_OPTIONS else "Default order"
        self._refresh_display()

    @rx.event
    def toggle_type(self, grocery_type: str):
        if grocery_type not in planner.GROCERY_TYPES:
            return
        if grocery_type in self.selected_types:
            self.selected_types = [value for value in self.selected_types if value != grocery_type]
        else:
            self.selected_types = [*self.selected_types, grocery_type]
        self._refresh_display()

    @rx.event
    def reset_types(self):
        self.selected_types = []
        self._refresh_display()

    @rx.event(background=True)
    async def generate_plan(self):
        async with self:
            if self.busy:
                return
            session_id = self._session_id()
            self.busy = True
            self._clear_error()
            self.status = "Checking your inventory and building this week’s list. This can take up to 2 minutes."
        yield

        try:
            suggestion = await rx.run_in_thread(
                lambda: planner.generate_weekly_plan(session_id)
            )
        except Exception as exc:
            kind, message = _friendly_error(exc)
            async with self:
                self.busy = False
                self.status = ""
                self._set_error(kind, message)
            return

        async with self:
            self._apply_suggestion(suggestion)
            self.purchased = False
            self._sync_inventory(session_id, suggestion)
            self.feedback = ""
            self.busy = False
            self.status = self._ready_status(suggestion, "New weekly grocery plan ready.")

    @rx.event(background=True)
    async def revise_plan(self):
        async with self:
            if self.busy:
                return
            feedback = self.feedback.strip()
            if not feedback:
                self._set_error("error", "Enter feedback describing what to change.")
                return
            if not self.has_plan:
                self._set_error("error", "Generate a grocery plan first, then revise it.")
                return
            session_id = self._session_id()
            self.busy = True
            self._clear_error()
            self.status = "Revising the list from your feedback…"
        yield

        try:
            suggestion = await rx.run_in_thread(
                lambda: planner.revise_weekly_plan(feedback, session_id)
            )
        except Exception as exc:
            kind, message = _friendly_error(exc)
            async with self:
                self.busy = False
                self.status = ""
                self._set_error(kind, message)
            return

        async with self:
            self._apply_suggestion(suggestion)
            self.purchased = False
            self._sync_inventory(session_id, suggestion)
            self.feedback = ""
            self.busy = False
            self.status = self._ready_status(suggestion, "Plan revised.")

    @rx.event
    def record_purchase(self):
        if self.busy or self.purchased:
            return
        self._clear_error()
        self.status = ""
        session_id = self._session_id()
        suggestion = _read_suggestion(planner.suggestion_path(session_id))
        if suggestion is None:
            self._set_error("error", "Generate a grocery plan first, then record a purchase.")
            return
        try:
            rows = planner.record_purchase(suggestion, session_id)
        except Exception as exc:
            kind, message = _friendly_error(exc)
            self._set_error(kind, message)
            return
        self.purchased = True
        self.inventory_stale = False
        self.inventory_count = len(rows)
        added = _count(len(suggestion["items"]), "item", "items")
        self.status = f"Added {added} to your inventory. You can use them on the Meals page."


def nut_chip(swatch: str, prefix: str, value) -> rx.Component:
    return rx.el.span(
        rx.el.span(class_name=f"ns-swatch {swatch}"),
        rx.el.span(prefix, class_name="ns-nut-prefix"),
        rx.el.span(value, class_name="ns-nut-value"),
        class_name="ns-nut-chip",
    )


def type_filter(label: str, grocery_type: str) -> rx.Component:
    selected = GroceryState.selected_types.contains(grocery_type)
    return rx.el.button(
        label,
        type="button",
        on_click=GroceryState.toggle_type(grocery_type),
        aria_pressed=selected,
        class_name=rx.cond(selected, "ns-filter-button is-active", "ns-filter-button"),
    )


def _row(item: GroceryItem, icon: str) -> rx.Component:
    return rx.el.li(
        rx.el.div(
            rx.el.div(
                rx.icon(icon, size=16, class_name="ns-grocery-icon"),
                rx.el.span(item.name, class_name="ns-grocery-name"),
                class_name="ns-grocery-title",
            ),
            rx.el.span(item.quantity_label, class_name="ns-grocery-qty"),
            class_name="ns-grocery-head",
        ),
        rx.el.p(item.preparation, class_name="ns-grocery-prep"),
        rx.el.div(
            rx.el.span(item.calories_label, class_name="ns-nut-chip ns-nut-kcal"),
            nut_chip("ns-p", "P", item.protein_label),
            nut_chip("ns-c", "C", item.carbs_label),
            nut_chip("ns-f", "F", item.fat_label),
            nut_chip("ns-fiber", "Fiber", item.fiber_label),
            class_name="ns-grocery-nuts",
        ),
        class_name="ns-grocery-item",
    )


def grocery_row(item: GroceryItem) -> rx.Component:
    return _row(item, "shopping-basket")


def pantry_row(item: GroceryItem) -> rx.Component:
    return _row(item, "package")


def section_head(icon: str, title: str) -> rx.Component:
    return rx.el.div(
        rx.icon(icon, size=15, class_name="ns-section-icon"),
        rx.el.h2(title, class_name="ns-section-title"),
        class_name="ns-section-head",
    )


def calorie_stat(icon: str, value, label: str) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.icon(icon, size=18, class_name="ns-calorie-icon"),
            rx.el.span(label, class_name="ns-calorie-label"),
            class_name="ns-calorie-head",
        ),
        rx.el.p(value, class_name="ns-calorie"),
        rx.el.p("kcal estimated", class_name="ns-unit-label"),
        class_name="ns-calorie-stat",
    )


def total_cell(label: str, value, day_value, icon: str, swatch: str) -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.span(class_name=f"ns-swatch {swatch}"),
            rx.icon(icon, size=15, class_name=f"ns-total-icon {swatch}"),
            rx.el.span(label, class_name="ns-total-label"),
            class_name="ns-total-head",
        ),
        rx.el.span(value, class_name=f"ns-total-value {swatch}"),
        rx.el.span(day_value, " / day", class_name="ns-total-day"),
        class_name=f"ns-total {swatch}-tone",
    )


def loader() -> rx.Component:
    return rx.cond(
        GroceryState.busy,
        rx.el.div(
            rx.el.span(class_name="ns-spinner", aria_hidden="true"),
            rx.el.span("Working…", class_name="ns-spinner-label"),
            class_name="ns-loader",
            role="status",
            aria_live="polite",
        ),
    )


def error_banner() -> rx.Component:
    return rx.cond(
        GroceryState.error != "",
        rx.cond(
            GroceryState.error_kind == "unavailable",
            rx.el.div(
                rx.el.div(
                    rx.icon("cloud-off", size=22, class_name="ns-notice-icon"),
                    rx.el.div(
                        rx.el.p(MODEL_UNAVAILABLE_TITLE, class_name="ns-notice-title"),
                        rx.el.p(GroceryState.error, class_name="ns-notice-body"),
                        class_name="ns-notice-copy",
                    ),
                    class_name="ns-notice-row",
                ),
                class_name="ns-notice ns-notice-unavailable",
                role="alert",
            ),
            rx.el.p(GroceryState.error, class_name="ns-error", role="alert"),
        ),
    )


def stale_notice() -> rx.Component:
    return rx.cond(
        GroceryState.inventory_stale,
        rx.el.div(
            rx.el.div(
                rx.icon("refresh-cw", size=22, class_name="ns-notice-icon"),
                rx.el.div(
                    rx.el.p("Your inventory changed", class_name="ns-notice-title"),
                    rx.el.p(
                        "This list was planned around different stock. "
                        "Reload to plan around what you have now.",
                        class_name="ns-notice-body",
                    ),
                    class_name="ns-notice-copy",
                ),
                class_name="ns-notice-row",
            ),
            class_name="ns-notice",
            role="status",
        ),
    )


def plan_view() -> rx.Component:
    return rx.el.div(
        stale_notice(),
        rx.el.div(
            rx.el.div(
                calorie_stat("calendar-days", GroceryState.calories_total, "Per week"),
                calorie_stat("flame", GroceryState.calories_daily, "Per day"),
                class_name="ns-calorie-grid",
            ),
            rx.el.div(
                rx.icon("package", size=16, class_name="ns-meta-icon"),
                rx.el.span(GroceryState.item_count),
                class_name="ns-meta ns-meta-row",
            ),
            rx.cond(
                GroceryState.split_line != "",
                rx.el.p(GroceryState.split_line, class_name="ns-hint"),
            ),
            rx.cond(
                GroceryState.purchased,
                rx.el.p(rx.icon("check", size=14), "Added to inventory", class_name="ns-badge"),
            ),
            class_name="ns-grocery-summary",
        ),
        rx.el.div(
            total_cell("Protein", GroceryState.protein_total, GroceryState.protein_day, "beef", "ns-p"),
            total_cell("Carbs", GroceryState.carbs_total, GroceryState.carbs_day, "wheat", "ns-c"),
            total_cell("Fat", GroceryState.fat_total, GroceryState.fat_day, "droplets", "ns-f"),
            total_cell("Fiber", GroceryState.fiber_total, GroceryState.fiber_day, "leaf", "ns-fiber"),
            class_name="ns-totals",
        ),
        rx.el.p("Totals include food from your inventory and food to buy.", class_name="ns-hint"),
        rx.el.div(
            rx.el.div(
                section_head("shopping-basket", "To buy"),
                rx.el.div(
                    type_filter("Meat", "meat"),
                    type_filter("Dairy", "dairy"),
                    type_filter("Produce", "produce"),
                    type_filter("Pantry", "dry_goods"),
                    rx.el.button(
                        "Reset",
                        type="button",
                        on_click=GroceryState.reset_types,
                        disabled=GroceryState.selected_types.length() == 0,
                        class_name="ns-filter-reset",
                        aria_label="Show all grocery types",
                    ),
                    role="group",
                    aria_label="Filter grocery list by type",
                    class_name="ns-filter-group",
                ),
                rx.el.div(
                    rx.el.label("Sort", html_for="grocery-sort", class_name="ns-sort-label"),
                    rx.select(
                        SORT_OPTIONS,
                        name="grocery_sort",
                        id="grocery-sort",
                        value=GroceryState.sort_by,
                        on_change=GroceryState.set_sort,
                        size="2",
                        variant="surface",
                        color_scheme="jade",
                        width="11rem",
                        class_name="ns-sort-select",
                        aria_label="Sort grocery list",
                    ),
                    class_name="ns-sort-control",
                ),
                class_name="ns-list-toolbar",
            ),
            rx.cond(
                GroceryState.nothing_to_buy,
                rx.el.p(
                    "Your inventory covers this plan. Nothing to buy this week.",
                    class_name="ns-overview-copy",
                ),
                rx.fragment(
                    rx.el.ul(
                        rx.foreach(GroceryState.display_items, grocery_row),
                        class_name="ns-grocery-list",
                    ),
                    rx.cond(
                        GroceryState.display_items.length() == 0,
                        rx.el.p("No items to buy match the selected types.", class_name="ns-grocery-prep"),
                    ),
                ),
            ),
            class_name="ns-list-block",
        ),
        rx.cond(
            GroceryState.has_pantry,
            rx.el.div(
                section_head("package", "From your inventory"),
                rx.el.p("Food you already have that this plan counts toward your targets.", class_name="ns-hint"),
                rx.el.ul(
                    rx.foreach(GroceryState.display_pantry, pantry_row),
                    class_name="ns-grocery-list",
                ),
                rx.cond(
                    GroceryState.display_pantry.length() == 0,
                    rx.el.p("No inventory items match the selected types.", class_name="ns-grocery-prep"),
                ),
                class_name="ns-list-block",
            ),
        ),
        rx.cond(
            GroceryState.notes != "",
            rx.el.div(rx.el.p(GroceryState.notes), class_name="ns-callout"),
        ),
        field(
            "Revise with feedback",
            rx.text_area(
                placeholder="Example: Replace bananas and add more leafy greens.",
                value=GroceryState.feedback,
                on_change=GroceryState.set_feedback,
                disabled=GroceryState.busy,
                rows="3",
                width="100%",
                class_name="ns-textarea",
                aria_label="Feedback for revising the grocery plan",
            ),
            "The current list is revised and saved when this succeeds.",
        ),
        loader(),
        rx.el.p("Record purchase adds the To buy list to your inventory.", class_name="ns-hint"),
        actions(
            [
                go("Overview", "/overview"),
                press(
                    rx.cond(GroceryState.purchased, "In inventory", "Record purchase"),
                    "secondary",
                    type="button",
                    on_click=GroceryState.record_purchase,
                    disabled=GroceryState.busy | GroceryState.purchased | GroceryState.nothing_to_buy,
                ),
            ],
            [
                press(
                    "Revise plan",
                    "secondary",
                    type="button",
                    on_click=GroceryState.revise_plan,
                    disabled=GroceryState.busy,
                ),
                press(
                    "Reload",
                    "primary",
                    type="button",
                    on_click=GroceryState.generate_plan,
                    disabled=GroceryState.busy,
                ),
            ],
        ),
        class_name="ns-stack ns-grocery-body",
    )


def empty_view() -> rx.Component:
    return rx.el.div(
        rx.el.div(
            rx.el.p(
                "No weekly list for these targets. Generate one after Profile and Preferences are saved. Changing either clears the previous list.",
                class_name="ns-lede ns-lede-tight",
            ),
            rx.el.p(GroceryState.inventory_hint, class_name="ns-hint"),
            class_name="ns-callout",
        ),
        loader(),
        actions(
            [go("Overview", "/overview"), go("Open inventory", "/inventory")],
            [
                press(
                    "Generate weekly plan",
                    "primary",
                    type="button",
                    on_click=GroceryState.generate_plan,
                    disabled=GroceryState.busy,
                ),
            ],
        ),
        class_name="ns-stack ns-grocery-body",
    )


def grocery() -> rx.Component:
    return page(
        rx.el.div(
            rx.el.div(
                rx.el.div(
                    rx.el.p("Weekly plan", class_name="ns-kicker"),
                    rx.el.h1("Groceries", class_name="ns-title"),
                    class_name="ns-title-copy",
                ),
                press(
                    "Reload",
                    "secondary",
                    type="button",
                    on_click=GroceryState.generate_plan,
                    disabled=GroceryState.busy,
                ),
                class_name="ns-title-row",
            ),
            rx.el.p(
                "A seven-day grocery list from your targets, allergies, and diet that counts "
                "what is already in your inventory. Nutrition values are AI estimates.",
                class_name="ns-lede",
            ),
            error_banner(),
            rx.cond(
                GroceryState.status != "",
                rx.el.p(GroceryState.status, class_name="ns-status", role="status"),
            ),
            rx.cond(GroceryState.has_plan, plan_view(), empty_view()),
            class_name="ns-sheet",
        ),
        current="groceries",
    )