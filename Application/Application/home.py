"""Main menu overview, future tracking sections, and developer settings."""

import json

import reflex as rx

from . import get_targets as nutrition
from . import grocery_planner
from . import inventory as stock
from . import meal_planner
from .grocery import GroceryState, _read_suggestion
from .intake import MacroIntakeState
from .meals import MealState
from .navigation import NavigationState
from .ui import go, intake_pie_row, page, press

INVENTORY_LABELS = (
    ("meat", "Meat"),
    ("dairy", "Dairy"),
    ("produce", "Produce"),
    ("dry_goods", "Dry goods"),
)


def _clip(text: str, limit: int = 140) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


class OverviewState(rx.State):
    welcome: str = "Welcome"
    intent_line: str = ""
    chips: list[str] = []
    has_chips: bool = False
    has_grocery: bool = False
    grocery_summary: str = ""
    grocery_note: str = ""
    has_meals: bool = False
    meal_names: list[str] = []
    has_inventory: bool = False
    inventory_summary: str = ""

    @rx.event
    def load_overview(self):
        profile = nutrition._load_json(nutrition.USER_DATA_FOLDER / "user_data.json")
        name = " ".join(str(profile.get("name") or "").split())
        self.welcome = f"Welcome, {name}" if name else "Welcome"
        preferences = nutrition._load_json(nutrition.USER_DATA_FOLDER / "user_personalization_data.json")
        targets = nutrition.get_targets()
        goal = str(preferences.get("current_goal") or "Maintenance").strip() or "Maintenance"
        line = f"{goal} · {float(targets['calories']):,.0f} kcal"
        if preferences.get("muscle_gain"):
            line += " · Muscle gain"
        self.intent_line = line
        chips: list[str] = []
        for field in ("allergies", "diet_types"):
            choices = preferences.get(field, [])
            if isinstance(choices, list):
                chips.extend(str(choice).strip() for choice in choices if str(choice).strip())
        self.chips = chips
        self.has_chips = bool(chips)

        session_id = self.rx_router_session.client_token or ""
        suggestion = _read_suggestion(grocery_planner.suggestion_path(session_id))
        if suggestion is None:
            self.has_grocery = False
            self.grocery_summary = ""
            self.grocery_note = ""
        else:
            count = len(suggestion["items"])
            pantry = len(suggestion.get("inventory_used", []))
            weekly = float(suggestion["estimated_weekly_totals"]["calories"])
            noun = "item" if count == 1 else "items"
            summary = f"{count} {noun} to buy"
            if pantry:
                summary += f" · {pantry} from your inventory"
            self.has_grocery = True
            self.grocery_summary = f"{summary} · {weekly:,.0f} kcal this week"
            self.grocery_note = _clip(str(suggestion.get("notes", "")))

        names: list[str] = []
        try:
            saved = meal_planner._read_json(meal_planner.selected_meals_path(session_id))
            meals = saved.get("meals", [])
            if isinstance(meals, list):
                names = [
                    str(meal.get("name", "")).strip()
                    for meal in meals
                    if isinstance(meal, dict) and str(meal.get("name", "")).strip()
                ]
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            names = []
        self.meal_names = names
        self.has_meals = bool(names)

        counts = {key: 0 for key, _label in INVENTORY_LABELS}
        try:
            items = stock.get_inventory(session_id=session_id) if session_id else []
        except ValueError:
            items = []
        for item in items:
            kind = item.get("grocery_type")
            if kind in counts:
                counts[kind] += 1
        self.has_inventory = sum(counts.values()) > 0
        self.inventory_summary = " · ".join(
            f"{label} {counts[key]}" for key, label in INVENTORY_LABELS if counts[key]
        )


def tracking_preview() -> rx.Component:
    return rx.el.div(
        rx.image(src="/tracking-placeholder.svg", alt="Placeholder illustration of a daily tracking chart; no tracking data yet", width="100%"),
        rx.el.p("Tracking preview · coming soon", class_name="ns-hint"),
        class_name="ns-tracking-preview",
    )


def overview() -> rx.Component:
    return page(
        rx.el.p("Today", class_name="ns-kicker"),
        rx.el.h1(OverviewState.welcome, class_name="ns-title"),
        rx.el.p(OverviewState.intent_line, class_name="ns-lede"),
        rx.cond(
            OverviewState.has_chips,
            rx.el.ul(
                rx.foreach(
                    OverviewState.chips,
                    lambda chip: rx.el.li(chip, class_name="ns-overview-chip"),
                ),
                class_name="ns-overview-chips",
            ),
        ),
        go("Edit profile", "/profile", "ghost"),
        rx.el.section(
            rx.el.p(MacroIntakeState.calorie_left, class_name="ns-overview-calories"),
            rx.el.p("From meals you have selected", class_name="ns-unit-label"),
            intake_pie_row(MacroIntakeState, "ns-intake-grid ns-home-charts-grid"),
            rx.el.p("Totals are from saved meal selections; they are not a daily food log.", class_name="ns-hint"),
            class_name="ns-overview-card ns-overview-hero ns-home-charts",
        ),
        rx.el.div(
            rx.el.section(
                rx.el.h2("This week’s groceries", class_name="ns-card-title"),
                rx.cond(
                    OverviewState.has_grocery,
                    rx.fragment(
                        rx.el.p(OverviewState.grocery_summary, class_name="ns-overview-copy"),
                        rx.cond(
                            OverviewState.grocery_note != "",
                            rx.el.p(OverviewState.grocery_note, class_name="ns-hint"),
                        ),
                    ),
                    rx.el.p("Build this week’s grocery list.", class_name="ns-overview-copy"),
                ),
                go("Open groceries", "/groceries", "secondary"),
                class_name="ns-overview-card",
            ),
            rx.el.section(
                rx.el.h2("Today’s meals", class_name="ns-card-title"),
                rx.cond(
                    OverviewState.has_meals,
                    rx.el.ul(
                        rx.foreach(
                            OverviewState.meal_names,
                            lambda name: rx.el.li(name),
                        ),
                        class_name="ns-overview-meals",
                    ),
                    rx.el.p("Pick today’s meals.", class_name="ns-overview-copy"),
                ),
                go("Open meals", "/meals", "secondary"),
                class_name="ns-overview-card",
            ),
            rx.el.section(
                rx.el.h2("In the kitchen", class_name="ns-card-title"),
                rx.cond(
                    OverviewState.has_inventory,
                    rx.el.p(OverviewState.inventory_summary, class_name="ns-overview-copy"),
                    rx.el.p("Add what you already have.", class_name="ns-overview-copy"),
                ),
                go("Open inventory", "/inventory", "secondary"),
                class_name="ns-overview-card",
            ),
            class_name="ns-overview-actions",
        ), current="overview",
    )


def placeholder(title: str, current: str, description: str) -> rx.Component:
    return page(rx.el.div(
        rx.el.p("Coming soon", class_name="ns-kicker"),
        rx.el.h1(title, class_name="ns-title"),
        rx.el.p(description, class_name="ns-lede"),
        tracking_preview(),
        class_name="ns-sheet",
    ), current=current)


def settings() -> rx.Component:
    busy = GroceryState.busy | MealState.busy
    return page(rx.el.div(
        rx.el.p("Prototype controls", class_name="ns-kicker"),
        rx.el.h1("Settings", class_name="ns-title"),
        rx.el.h2("Reset profile", class_name="ns-card-title"),
        rx.el.p("Delete the saved profile, preferences, grocery plans, inventory, meal suggestions, and selected meals for all prototype sessions. Then return to the intro page to start fresh.", class_name="ns-lede"),
        rx.cond(busy, rx.el.p("Wait for grocery or meal generation to finish before resetting.", class_name="ns-hint")),
        rx.cond(
            NavigationState.reset_confirmation,
            rx.el.div(
                rx.el.p("Delete all saved data? This cannot be undone.", class_name="ns-overview-copy"),
                rx.el.div(
                    press("Cancel", "secondary", on_click=NavigationState.cancel_reset),
                    press("Delete data and restart", on_click=NavigationState.reset_profile, disabled=busy),
                    class_name="ns-actions-group",
                ), class_name="ns-callout", role="alert",
            ),
            press("Reset profile", "secondary", on_click=NavigationState.ask_reset, disabled=busy),
        ),
        rx.cond(NavigationState.reset_error != "", rx.el.p(NavigationState.reset_error, class_name="ns-error", role="alert")),
        class_name="ns-sheet",
    ), current="settings")
