"""Main menu overview, future tracking sections, and developer settings."""

import reflex as rx

from . import get_targets as nutrition
from .grocery import GroceryState
from .intake import MacroIntakeState
from .meals import MealState
from .navigation import NavigationState
from .target_calculations import TargetState
from .ui import go, intake_pie_row, page, press


class OverviewState(rx.State):
    profile_summary: str = ""
    preference_summary: str = ""

    @rx.event
    def load_overview(self):
        profile = nutrition._load_json(nutrition.USER_DATA_FOLDER / "user_data.json")
        preferences = nutrition._load_json(nutrition.USER_DATA_FOLDER / "user_personalization_data.json")
        parts = []
        for field, unit in (("sex", ""), ("age", " years"), ("height", " cm"), ("weight", " kg")):
            value = profile.get(field)
            if value not in (None, ""):
                formatted = f"{value:g}" if isinstance(value, (int, float)) else str(value)
                parts.append(formatted + unit)
        parts.append(f"{profile.get('activity_level', 'Low')} activity")
        self.profile_summary = " · ".join(parts)
        self.preference_summary = str(preferences.get("current_goal", "Maintenance"))
        if preferences.get("muscle_gain"):
            self.preference_summary += " · Muscle Gain"
        for field in ("allergies", "diet_types"):
            choices = preferences.get(field, [])
            if choices:
                self.preference_summary += " · " + ", ".join(choices)


def tracking_preview() -> rx.Component:
    return rx.el.div(
        rx.image(src="/tracking-placeholder.svg", alt="Placeholder illustration of a daily tracking chart; no tracking data yet", width="100%"),
        rx.el.p("Tracking preview · coming soon", class_name="ns-hint"),
        class_name="ns-tracking-preview",
    )


def overview() -> rx.Component:
    return page(
        rx.el.p("Your daily direction", class_name="ns-kicker"),
        rx.el.h1("Overview", class_name="ns-title"),
        rx.el.p("Your profile is set. Here’s where you stand today.", class_name="ns-lede"),
        rx.el.div(
            rx.el.section(
                rx.icon("user-round", size=23),
                rx.el.h2("Your profile", class_name="ns-card-title"),
                rx.el.p(OverviewState.profile_summary, class_name="ns-overview-copy"),
                rx.el.p(OverviewState.preference_summary, class_name="ns-meta"),
                go("Edit profile", "/profile", "secondary"),
                class_name="ns-overview-card",
            ),
            rx.el.section(
                rx.el.h2("Daily targets", class_name="ns-card-title"),
                rx.el.p(TargetState.calories, class_name="ns-overview-calories"),
                rx.el.p("kcal / day", class_name="ns-unit-label"),
                rx.el.dl(*[
                    rx.el.div(rx.el.dt(label), rx.el.dd(value), class_name="ns-overview-macro")
                    for label, value in [("Protein", TargetState.protein), ("Carbohydrates", TargetState.carbs), ("Fat", TargetState.fat), ("Fiber", TargetState.fiber)]
                ], class_name="ns-overview-macros"),
                go("View targets", "/targets", "secondary"),
                class_name="ns-overview-card",
            ),
            rx.el.section(
                rx.el.h2("Selected meals vs daily targets", class_name="ns-card-title"),
                rx.el.p(MacroIntakeState.calorie_figure, class_name="ns-overview-copy"),
                intake_pie_row(MacroIntakeState, "ns-intake-grid ns-home-charts-grid"),
                rx.el.p("Totals are from saved meal selections; they are not a daily food log.", class_name="ns-hint"),
                class_name="ns-overview-card ns-overview-tracking ns-home-charts",
            ),
            rx.el.section(
                rx.el.h2("Daily tracking", class_name="ns-card-title"),
                tracking_preview(),
                rx.el.p("A place to follow your daily intake. Tracking will be added in a future update.", class_name="ns-overview-copy"),
                class_name="ns-overview-card ns-overview-tracking",
            ),
            class_name="ns-overview-grid",
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
        rx.el.p("Delete the saved profile, preferences, grocery plans, inventory, meal suggestions, and selected meals for all prototype sessions. Then start onboarding from scratch.", class_name="ns-lede"),
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
