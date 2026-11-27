"""Main menu overview, future tracking sections, and developer settings."""

import json
import math

import reflex as rx

from . import get_targets as nutrition
from . import grocery_planner
from . import inventory as stock
from . import meal_planner
from .grocery import GroceryState, _read_suggestion
from .intake import MacroIntakeState
from .meals import MealState
from .navigation import NavigationState
from .target_calculations import _get_target_values
from .ui import go, intake_pie_row, page, press

INVENTORY_LABELS = (
    ("meat", "Meat"),
    ("dairy", "Dairy"),
    ("produce", "Produce"),
    ("dry_goods", "Dry goods"),
)


def _meal_summary(meal: dict) -> dict[str, str]:
    energy = {}
    for macro, factor in (("protein", 4), ("carbs", 4), ("fat", 9)):
        try:
            value = float(meal.get(macro, 0))
        except (TypeError, ValueError):
            value = 0
        energy[macro] = max(0, value) * factor if math.isfinite(value) else 0
    dominant = max(energy, key=energy.get) if any(energy.values()) else "unknown"
    return {"name": str(meal["name"]).strip(), "macro": dominant}


class OverviewState(rx.State):
    welcome: str = "Welcome"
    intent_line: str = ""
    chips: list[str] = []
    has_chips: bool = False
    has_grocery: bool = False
    grocery_summary: str = ""
    grocery_counts: dict[str, int] = {key: 0 for key, _label in INVENTORY_LABELS}
    has_meals: bool = False
    meal_names: list[str] = []
    meal_rows: list[dict[str, str]] = []
    has_inventory: bool = False
    inventory_summary: str = ""
    inventory_counts: dict[str, int] = {key: 0 for key, _label in INVENTORY_LABELS}

    @rx.event
    def load_overview(self):
        profile = nutrition._load_json(nutrition.USER_DATA_FOLDER / "user_data.json")
        name = " ".join(str(profile.get("name") or "").split())
        self.welcome = f"Welcome, {name}" if name else "Welcome"
        preferences = nutrition._load_json(nutrition.USER_DATA_FOLDER / "user_personalization_data.json")
        targets = _get_target_values()
        self.intent_line = f"{targets['detail_line']} · {float(targets['calories']):,.0f} kcal"
        chips: list[str] = []
        for field in ("allergies", "diet_types", "religious_restrictions"):
            choices = preferences.get(field, [])
            if isinstance(choices, list):
                chips.extend(str(choice).strip() for choice in choices if str(choice).strip())
        self.chips = chips
        self.has_chips = bool(chips)

        session_id = self.rx_router_session.client_token or ""
        suggestion = _read_suggestion(grocery_planner.suggestion_path(session_id))
        self.grocery_counts = {key: 0 for key, _label in INVENTORY_LABELS}
        if suggestion is None or grocery_planner.is_purchased(suggestion, session_id):
            self.has_grocery = False
            self.grocery_summary = ""
        else:
            count = len(suggestion["items"])
            weekly = float(suggestion["estimated_weekly_totals"]["calories"])
            noun = "item" if count == 1 else "items"
            summary = f"{count} {noun} to buy"
            self.has_grocery = True
            self.grocery_summary = f"{summary} · {weekly:,.0f} kcal this week"
            for item in suggestion["items"]:
                self.grocery_counts[item["grocery_type"]] += 1

        names: list[str] = []
        rows: list[dict[str, str]] = []
        try:
            saved = {"meals": meal_planner.get_made_meals(session_id)}
            meals = saved.get("meals", [])
            if isinstance(meals, list):
                names = [
                    str(meal.get("name", "")).strip()
                    for meal in meals
                    if isinstance(meal, dict) and str(meal.get("name", "")).strip()
                ]
                rows = [_meal_summary(meal) for meal in meals
                        if isinstance(meal, dict) and str(meal.get("name", "")).strip()]
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            names = []
        self.meal_names = names
        self.meal_rows = rows
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
        total = sum(counts.values())
        self.has_inventory = total > 0
        self.inventory_counts = counts
        noun = "item" if total == 1 else "items"
        self.inventory_summary = f"{total} {noun} in your kitchen"


def category_tiles(counts, label: str) -> rx.Component:
    return rx.el.ul(
        *[
            rx.el.li(
                rx.icon(icon, size=17),
                rx.el.span(name),
                rx.el.strong(counts[key]),
                class_name=f"ns-grocery-category ns-category-{key}",
            )
            for key, name, icon in (
                ("meat", "Meat", "beef"),
                ("dairy", "Dairy", "milk"),
                ("produce", "Produce", "carrot"),
                ("dry_goods", "Dry goods", "wheat"),
            )
        ],
        class_name="ns-grocery-categories",
        aria_label=label,
    )


def overview_meal_row(meal):
    return rx.el.li(
        rx.match(
            meal["macro"],
            ("protein", rx.icon("beef", size=18, class_name="ns-p", title="Dominant macro: protein")),
            ("carbs", rx.icon("wheat", size=18, class_name="ns-c", title="Dominant macro: carbs")),
            ("fat", rx.icon("droplets", size=18, class_name="ns-f", title="Dominant macro: fat")),
            rx.icon("utensils", size=18, title="Nutrition unavailable"),
        ),
        rx.el.span(meal["name"]),
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
            rx.el.p("From meals made today", class_name="ns-unit-label"),
            intake_pie_row(MacroIntakeState, "ns-intake-grid ns-home-charts-grid"),
            rx.el.p("Totals are for full recipes marked as made today; portions eaten are not tracked.", class_name="ns-hint"),
            class_name="ns-overview-card ns-overview-hero ns-home-charts",
        ),
        rx.el.div(
            rx.el.section(
                rx.el.h2("This week’s groceries", class_name="ns-card-title"),
                rx.cond(
                    OverviewState.has_grocery,
                    rx.fragment(
                        rx.el.p(OverviewState.grocery_summary, class_name="ns-overview-copy"),
                        category_tiles(OverviewState.grocery_counts, "Items to buy by category"),
                    ),
                    rx.el.p("Build this week’s grocery list.", class_name="ns-overview-copy"),
                ),
                go("Open groceries", "/groceries", "secondary"),
                class_name="ns-overview-card",
            ),
            rx.el.section(
                rx.el.h2("Meals made today", class_name="ns-card-title"),
                rx.cond(
                    OverviewState.has_meals,
                    rx.el.ul(
                        rx.foreach(
                            OverviewState.meal_rows,
                            overview_meal_row,
                        ),
                        class_name="ns-overview-meals",
                        tab_index=0,
                        aria_label="Meals made today, with dominant macro icons",
                    ),
                    rx.el.p("Generate a meal from your inventory.", class_name="ns-overview-copy"),
                ),
                go("Open meals", "/meals", "secondary"),
                class_name="ns-overview-card ns-overview-meal-card",
            ),
            rx.el.section(
                rx.el.h2("In the kitchen", class_name="ns-card-title"),
                rx.cond(
                    OverviewState.has_inventory,
                    rx.fragment(
                        rx.el.p(OverviewState.inventory_summary, class_name="ns-overview-copy"),
                        category_tiles(OverviewState.inventory_counts, "Inventory items by category"),
                    ),
                    rx.el.p("Add what you already have.", class_name="ns-overview-copy"),
                ),
                go("Open inventory", "/inventory", "secondary"),
                class_name="ns-overview-card",
            ),
            class_name="ns-overview-actions",
        ),
        rx.el.section(
            rx.el.h2("Progress", class_name="ns-card-title"),
            tracking_preview(),
            class_name="ns-overview-card ns-overview-progress",
        ),
        current="overview",
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
