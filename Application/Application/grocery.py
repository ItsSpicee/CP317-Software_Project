"""Weekly grocery planner UI wired to grocery_planner.py."""

from __future__ import annotations

import json
from dataclasses import dataclass

import reflex as rx

from . import grocery_planner as planner
from .ui import actions, field, go, page, press


@dataclass
class GroceryItem:
    name: str = ""
    quantity_label: str = ""
    preparation: str = ""
    nutrients_label: str = ""


def _format_item(item: dict) -> GroceryItem:
    return GroceryItem(
        name=str(item["name"]),
        quantity_label=f"{float(item['quantity_g']):,.0f} g",
        preparation=str(item["preparation"]),
        nutrients_label=(
            f"{float(item['calories']):,.0f} kcal · "
            f"P {float(item['protein']):.0f} g · "
            f"C {float(item['carbs']):.0f} g · "
            f"F {float(item['fat']):.0f} g · "
            f"Fiber {float(item['fiber']):.0f} g"
        ),
    )


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


def _friendly_error(exc: Exception) -> str:
    message = str(exc).strip() or "Something went wrong while planning groceries."
    if "GEMINI_API_KEY" in message or "GEMINI_MODEL" in message:
        return message
    if "positive daily calorie" in message.lower():
        return "Set a positive calorie target on Preferences before planning groceries."
    if "user_data.json" in message or "user_personalization_data.json" in message:
        return "Complete Profile and Preferences before planning groceries."
    if "allergies" in message or "diet_types" in message:
        return "Saved allergies or diet types look invalid. Re-save Preferences, then try again."
    if "Provide nonempty feedback" in message:
        return "Enter feedback describing what to change."
    if "weekly_suggestion.json" in message:
        return "Generate a grocery plan first, then revise it."
    if "timeout" in message.lower() or "timed out" in message.lower():
        return "The grocery request took longer than 2 minutes. Try again."
    return message


class GroceryState(rx.State):
    has_plan: bool = False
    busy: bool = False
    purchased: bool = False
    error: str = ""
    status: str = ""
    notes: str = ""
    feedback: str = ""
    items: list[GroceryItem] = []
    calories_total: str = "0"
    protein_total: str = "0 g"
    carbs_total: str = "0 g"
    fat_total: str = "0 g"
    fiber_total: str = "0 g"
    item_count: str = "0 items"

    def _apply_suggestion(self, suggestion: dict) -> None:
        totals = suggestion["estimated_weekly_totals"]
        self.items = [_format_item(item) for item in suggestion["items"]]
        self.notes = str(suggestion.get("notes", "")).strip()
        self.calories_total = f"{float(totals['calories']):,.0f}"
        self.protein_total = f"{float(totals['protein']):.0f} g"
        self.carbs_total = f"{float(totals['carbs']):.0f} g"
        self.fat_total = f"{float(totals['fat']):.0f} g"
        self.fiber_total = f"{float(totals['fiber']):.0f} g"
        count = len(suggestion["items"])
        self.item_count = f"{count} item" if count == 1 else f"{count} items"
        self.has_plan = True

    def _clear_plan(self) -> None:
        self.has_plan = False
        self.purchased = False
        self.notes = ""
        self.items = []
        self.calories_total = "0"
        self.protein_total = "0 g"
        self.carbs_total = "0 g"
        self.fat_total = "0 g"
        self.fiber_total = "0 g"
        self.item_count = "0 items"

    def _session_id(self) -> str:
        return self.rx_router_session.client_token or ""

    @rx.event
    def load_plan(self):
        self.error = ""
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

    @rx.event(background=True)
    async def generate_plan(self):
        async with self:
            if self.busy:
                return
            session_id = self._session_id()
            self.busy = True
            self.error = ""
            self.status = "Generating a weekly list. This can take up to 2 minutes."
        yield

        try:
            suggestion = await rx.run_in_thread(
                lambda: planner.generate_weekly_plan(session_id)
            )
        except Exception as exc:
            async with self:
                self.busy = False
                self.status = ""
                self.error = _friendly_error(exc)
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
                self.error = "Enter feedback describing what to change."
                return
            if not self.has_plan:
                self.error = "Generate a grocery plan first, then revise it."
                return
            session_id = self._session_id()
            self.busy = True
            self.error = ""
            self.status = "Revising the list from your feedback…"
        yield

        try:
            suggestion = await rx.run_in_thread(
                lambda: planner.revise_weekly_plan(feedback, session_id)
            )
        except Exception as exc:
            async with self:
                self.busy = False
                self.status = ""
                self.error = _friendly_error(exc)
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
        self.error = ""
        self.status = ""
        session_id = self._session_id()
        suggestion = _read_suggestion(planner.suggestion_path(session_id))
        if suggestion is None:
            self.error = "Generate a grocery plan first, then record a purchase."
            return
        try:
            planner.record_purchase(suggestion, session_id)
        except Exception as exc:
            self.error = _friendly_error(exc)
            return
        self.purchased = True
        self.status = "Saved as this week’s grocery inventory."


def grocery_row(item: GroceryItem) -> rx.Component:
    return rx.el.li(
        rx.el.div(
            rx.el.span(item.name, class_name="ns-grocery-name"),
            rx.el.span(item.quantity_label, class_name="ns-grocery-qty"),
            class_name="ns-grocery-head",
        ),
        rx.el.p(item.preparation, class_name="ns-grocery-prep"),
        rx.el.p(item.nutrients_label, class_name="ns-grocery-nuts"),
        class_name="ns-grocery-item",
    )


def total_cell(label: str, value) -> rx.Component:
    return rx.el.div(
        rx.el.span(label, class_name="ns-total-label"),
        rx.el.span(value, class_name="ns-total-value"),
        class_name="ns-total",
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
                rx.el.p(GroceryState.error, class_name="ns-error", role="alert"),
            ),
            rx.cond(
                GroceryState.status != "",
                rx.el.p(GroceryState.status, class_name="ns-status", role="status"),
            ),
            rx.cond(
                GroceryState.has_plan,
                rx.el.div(
                    rx.el.div(
                        rx.el.p(GroceryState.calories_total, class_name="ns-calorie"),
                        rx.el.p("kcal / week estimated", class_name="ns-unit-label"),
                        rx.el.p(GroceryState.item_count, class_name="ns-meta"),
                        rx.cond(
                            GroceryState.purchased,
                            rx.el.p("Recorded as purchased", class_name="ns-badge"),
                        ),
                        class_name="ns-grocery-summary",
                    ),
                    rx.el.div(
                        total_cell("Protein", GroceryState.protein_total),
                        total_cell("Carbs", GroceryState.carbs_total),
                        total_cell("Fat", GroceryState.fat_total),
                        total_cell("Fiber", GroceryState.fiber_total),
                        class_name="ns-totals",
                    ),
                    rx.el.ul(
                        rx.foreach(GroceryState.items, grocery_row),
                        class_name="ns-grocery-list",
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
