"""Weekly grocery planner UI wired to grocery_planner.py."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import reflex as rx

from . import grocery_planner as planner
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
    items: list[GroceryItem] = []
    display_items: list[GroceryItem] = []
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
    item_count: str = "0 items"

    def _refresh_display(self) -> None:
        self.display_items = _sorted_items(self.items, self.sort_by)

    def _apply_suggestion(self, suggestion: dict) -> None:
        totals = suggestion["estimated_weekly_totals"]
        self.items = [
            _format_item(item, order_index=index)
            for index, item in enumerate(suggestion["items"])
        ]
        self._refresh_display()
        self.notes = str(suggestion.get("notes", "")).strip()
        weekly = float(totals["calories"])
        self.calories_total = f"{weekly:,.0f}"
        self.calories_daily = f"{weekly / 7:,.0f}"
        protein = float(totals["protein"])
        carbs = float(totals["carbs"])
        fat = float(totals["fat"])
        fiber = float(totals["fiber"])
        self.protein_total = f"{protein:.0f} g"
        self.protein_day = f"{protein / 7:.0f} g"
        self.carbs_total = f"{carbs:.0f} g"
        self.carbs_day = f"{carbs / 7:.0f} g"
        self.fat_total = f"{fat:.0f} g"
        self.fat_day = f"{fat / 7:.0f} g"
        self.fiber_total = f"{fiber:.0f} g"
        self.fiber_day = f"{fiber / 7:.0f} g"
        count = len(suggestion["items"])
        self.item_count = f"{count} item" if count == 1 else f"{count} items"
        self.has_plan = True

    def _clear_plan(self) -> None:
        self.has_plan = False
        self.purchased = False
        self.notes = ""
        self.items = []
        self.display_items = []
        self.sort_by = "Default order"
        self.calories_total = "0"
        self.calories_daily = "0"
        self.protein_total = "0 g"
        self.protein_day = "0 g"
        self.carbs_total = "0 g"
        self.carbs_day = "0 g"
        self.fat_total = "0 g"
        self.fat_day = "0 g"
        self.fiber_total = "0 g"
        self.fiber_day = "0 g"
        self.item_count = "0 items"

    def _session_id(self) -> str:
        return self.rx_router_session.client_token or ""

    def _clear_error(self) -> None:
        self.error = ""
        self.error_kind = ""

    def _set_error(self, kind: str, message: str) -> None:
        self.error_kind = kind
        self.error = message

    @rx.event
    def load_plan(self):
        self._clear_error()
        self.status = ""
        session_id = self._session_id()
        suggestion = _read_suggestion(planner.suggestion_path(session_id))
        if suggestion is None:
            self._clear_plan()
            return
        self._apply_suggestion(suggestion)
        self.purchased = planner.inventory_path(session_id).exists()

    @rx.event
    def set_feedback(self, value: str):
        self.feedback = value

    @rx.event
    def set_sort(self, value: str):
        self.sort_by = value if value in SORT_OPTIONS else "Default order"
        self._refresh_display()

    @rx.event(background=True)
    async def generate_plan(self):
        async with self:
            if self.busy:
                return
            session_id = self._session_id()
            self.busy = True
            self._clear_error()
            self.status = "Generating a weekly list. This can take up to 2 minutes."
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
            self.feedback = ""
            self.busy = False
            self.status = "New weekly grocery plan ready."

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
            self.feedback = ""
            self.busy = False
            self.status = "Plan revised."

    @rx.event
    def record_purchase(self):
        if self.busy:
            return
        self._clear_error()
        self.status = ""
        session_id = self._session_id()
        suggestion = _read_suggestion(planner.suggestion_path(session_id))
        if suggestion is None:
            self._set_error("error", "Generate a grocery plan first, then record a purchase.")
            return
        try:
            planner.record_purchase(suggestion, session_id)
        except Exception as exc:
            kind, message = _friendly_error(exc)
            self._set_error(kind, message)
            return
        self.purchased = True
        self.status = "Saved as this week’s grocery inventory."


def nut_chip(swatch: str, prefix: str, value) -> rx.Component:
    return rx.el.span(
        rx.el.span(class_name=f"ns-swatch {swatch}"),
        rx.el.span(prefix, class_name="ns-nut-prefix"),
        rx.el.span(value, class_name="ns-nut-value"),
        class_name="ns-nut-chip",
    )


def grocery_row(item: GroceryItem) -> rx.Component:
    return rx.el.li(
        rx.el.div(
            rx.el.div(
                rx.icon("shopping-basket", size=16, class_name="ns-grocery-icon"),
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
                "A seven-day grocery list from your targets, allergies, and diet. "
                "Nutrition values are AI estimates.",
                class_name="ns-lede",
            ),
            rx.cond(
                GroceryState.error != "",
                rx.cond(
                    GroceryState.error_kind == "unavailable",
                    rx.el.div(
                        rx.el.div(
                            rx.icon("cloud-off", size=22, class_name="ns-notice-icon"),
                            rx.el.div(
                                rx.el.p(
                                    MODEL_UNAVAILABLE_TITLE,
                                    class_name="ns-notice-title",
                                ),
                                rx.el.p(
                                    GroceryState.error,
                                    class_name="ns-notice-body",
                                ),
                                class_name="ns-notice-copy",
                            ),
                            class_name="ns-notice-row",
                        ),
                        class_name="ns-notice ns-notice-unavailable",
                        role="alert",
                    ),
                    rx.el.p(GroceryState.error, class_name="ns-error", role="alert"),
                ),
            ),
            rx.cond(
                GroceryState.status != "",
                rx.el.p(GroceryState.status, class_name="ns-status", role="status"),
            ),
            rx.cond(
                GroceryState.has_plan,
                rx.el.div(
                    rx.el.div(
                        rx.el.div(
                            calorie_stat(
                                "calendar-days",
                                GroceryState.calories_total,
                                "Per week",
                            ),
                            calorie_stat(
                                "flame",
                                GroceryState.calories_daily,
                                "Per day",
                            ),
                            class_name="ns-calorie-grid",
                        ),
                        rx.el.div(
                            rx.icon("package", size=16, class_name="ns-meta-icon"),
                            rx.el.span(GroceryState.item_count),
                            class_name="ns-meta ns-meta-row",
                        ),
                        rx.cond(
                            GroceryState.purchased,
                            rx.el.p(
                                rx.icon("check", size=14),
                                "Recorded as purchased",
                                class_name="ns-badge",
                            ),
                        ),
                        class_name="ns-grocery-summary",
                    ),
                    rx.el.div(
                        total_cell(
                            "Protein",
                            GroceryState.protein_total,
                            GroceryState.protein_day,
                            "beef",
                            "ns-p",
                        ),
                        total_cell(
                            "Carbs",
                            GroceryState.carbs_total,
                            GroceryState.carbs_day,
                            "wheat",
                            "ns-c",
                        ),
                        total_cell(
                            "Fat",
                            GroceryState.fat_total,
                            GroceryState.fat_day,
                            "droplets",
                            "ns-f",
                        ),
                        total_cell(
                            "Fiber",
                            GroceryState.fiber_total,
                            GroceryState.fiber_day,
                            "leaf",
                            "ns-fiber",
                        ),
                        class_name="ns-totals",
                    ),
                    rx.el.div(
                        rx.el.div(
                            rx.el.div(
                                rx.icon("list", size=15, class_name="ns-section-icon"),
                                rx.el.h2("Grocery list", class_name="ns-section-title"),
                                class_name="ns-section-head",
                            ),
                            rx.el.div(
                                rx.el.label(
                                    "Sort",
                                    html_for="grocery-sort",
                                    class_name="ns-sort-label",
                                ),
                                rx.select(
                                    SORT_OPTIONS,
                                    name="grocery_sort",
                                    id="grocery-sort",
                                    value=GroceryState.sort_by,
                                    on_change=GroceryState.set_sort,
                                    size="2",
                                    variant="surface",
                                    color_scheme="jade",
                                    width="13.5rem",
                                    class_name="ns-sort-select",
                                    aria_label="Sort grocery list",
                                ),
                                class_name="ns-sort-control",
                            ),
                            class_name="ns-list-toolbar",
                        ),
                        rx.el.ul(
                            rx.foreach(GroceryState.display_items, grocery_row),
                            class_name="ns-grocery-list",
                        ),
                        class_name="ns-list-block",
                    ),
                    rx.cond(
                        GroceryState.notes != "",
                        rx.el.div(
                            rx.el.p(GroceryState.notes),
                            class_name="ns-callout",
                        ),
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
                    rx.cond(
                        GroceryState.busy,
                        rx.el.div(
                            rx.el.span(class_name="ns-spinner", aria_hidden="true"),
                            rx.el.span("Working…", class_name="ns-spinner-label"),
                            class_name="ns-loader",
                            role="status",
                            aria_live="polite",
                        ),
                    ),
                    actions(
                        [
                            go("Back", "/targets"),
                            press(
                                "Record purchase",
                                "secondary",
                                type="button",
                                on_click=GroceryState.record_purchase,
                                disabled=GroceryState.busy,
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
                ),
                rx.el.div(
                    rx.el.div(
                        rx.el.p(
                            "No weekly list for these targets. Generate one after Profile and Preferences are saved. Changing either clears the previous list.",
                            class_name="ns-lede ns-lede-tight",
                        ),
                        class_name="ns-callout",
                    ),
                    rx.cond(
                        GroceryState.busy,
                        rx.el.div(
                            rx.el.span(class_name="ns-spinner", aria_hidden="true"),
                            rx.el.span("Working…", class_name="ns-spinner-label"),
                            class_name="ns-loader",
                            role="status",
                            aria_live="polite",
                        ),
                    ),
                    actions(
                        [go("Back", "/targets")],
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
                ),
            ),
            class_name="ns-sheet",
        ),
        current="groceries",
    )
