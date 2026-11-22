import json
import math

import reflex as rx
from rxconfig import config
from . import meal_planner as planner
from .get_targets import USER_DATA_FOLDER, get_targets
from .grocery import GroceryState, grocery
from .meals import MealState, meals
from .onboarding import ButtonEvent, onboarding
from .personalize import PersonalizationState, personalize
from .target_calculations import TargetState, targets
from .ui import (
    go,
    home_splash,
    intake_pie_row,
    page,
    process,
)

MACRO_KEYS = ("protein", "carbs", "fat", "fiber", "calories")


class State(rx.State):
    """The app state."""


def _ring_progress(intake: float, goal: float) -> str:
    """0–1 fill ratio for SVG rings; caps visually at 100%."""
    if goal <= 0:
        return "0"
    return f"{min(1.0, intake / goal):.4f}"


def _selected_macro_intake(session_id: str) -> dict[str, float]:
    """Sum macro grams and calories from session selected meals; missing → 0."""
    totals = {key: 0.0 for key in MACRO_KEYS}
    try:
        path = planner.selected_meals_path(session_id or None)
        if not path.exists():
            return totals
        data = planner._read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return totals

    meals = data.get("meals", [])
    if not isinstance(meals, list):
        return totals

    for meal in meals:
        if not isinstance(meal, dict):
            continue
        for key in MACRO_KEYS:
            try:
                amount = float(meal.get(key, 0))
            except (TypeError, ValueError):
                continue
            if math.isfinite(amount) and amount > 0:
                totals[key] += amount
    return totals


def _has_saved_profile() -> bool:
    """True when the user has saved at least one profile field."""
    try:
        with open(USER_DATA_FOLDER / "user_data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    for key in ("sex", "height", "weight", "age"):
        value = data.get(key, "")
        if value not in (None, ""):
            return True
    activity = str(data.get("activity_level", "")).strip()
    return bool(activity and activity != "Low")


class MacroIntakeState(rx.State):
    """Home intake-vs-goal rings and pies from get_targets + selected_meals.json."""

    has_profile: bool = False
    calories: str = "0"
    calorie_goal: str = "0"
    calorie_figure: str = "0 / 0 kcal"
    calorie_left: str = "0 kcal left"
    protein_progress: str = "0"
    protein_figure: str = "0 / 0 g"
    protein_left: str = "0 g left"
    carbs_progress: str = "0"
    carbs_figure: str = "0 / 0 g"
    carbs_left: str = "0 g left"
    fat_progress: str = "0"
    fat_figure: str = "0 / 0 g"
    fat_left: str = "0 g left"
    fiber_progress: str = "0"
    fiber_figure: str = "0 / 0 g"
    fiber_left: str = "0 g left"

    @rx.event
    def load_intake(self):
        self.has_profile = _has_saved_profile()
        if not self.has_profile:
            return

        values = get_targets()
        intake = _selected_macro_intake(self.rx_router_session.client_token or "")

        calorie_goal = max(0.0, float(values["calories"]))
        protein_goal = max(0.0, float(values["protein"]))
        carbs_goal = max(0.0, float(values["carbs"]))
        fat_goal = max(0.0, float(values["fat"]))
        fiber_goal = max(0.0, float(values["fiber"]))

        self.calories = f"{calorie_goal:,.0f}"
        self.calorie_goal = f"{calorie_goal:,.0f}"
        self.calorie_figure = f'{intake["calories"]:,.0f} / {calorie_goal:,.0f} kcal eaten'
        self.calorie_left = f'{max(0.0, calorie_goal - intake["calories"]):,.0f} kcal left'

        self.protein_progress = _ring_progress(intake["protein"], protein_goal)
        self.protein_figure = f'{intake["protein"]:.0f} / {protein_goal:.0f} g'
        self.protein_left = f'{max(0.0, protein_goal - intake["protein"]):.0f} g left'

        self.carbs_progress = _ring_progress(intake["carbs"], carbs_goal)
        self.carbs_figure = f'{intake["carbs"]:.0f} / {carbs_goal:.0f} g'
        self.carbs_left = f'{max(0.0, carbs_goal - intake["carbs"]):.0f} g left'

        self.fat_progress = _ring_progress(intake["fat"], fat_goal)
        self.fat_figure = f'{intake["fat"]:.0f} / {fat_goal:.0f} g'
        self.fat_left = f'{max(0.0, fat_goal - intake["fat"]):.0f} g left'

        self.fiber_progress = _ring_progress(intake["fiber"], fiber_goal)
        self.fiber_figure = f'{intake["fiber"]:.0f} / {fiber_goal:.0f} g'
        self.fiber_left = f'{max(0.0, fiber_goal - intake["fiber"]):.0f} g left'


def home_link(icon: str, label: str, href: str, note: str) -> rx.Component:
    return rx.link(
        rx.icon(icon, size=22, class_name="ns-home-icon"),
        rx.el.span(
            rx.el.span(label, class_name="ns-home-label"),
            rx.el.span(note, class_name="ns-home-note"),
            class_name="ns-home-text",
        ),
        href=href,
        class_name="ns-home-item",
        underline="none",
    )


def index() -> rx.Component:
    return page(
        home_splash(),
        rx.el.section(
            rx.el.aside(
                rx.el.p("Menu", class_name="ns-kicker"),
                rx.el.nav(
                    home_link(
                        "smile",
                        "Profile",
                        "/onboarding",
                        "Sex, age, size, and activity.",
                    ),
                    home_link(
                        "calendar-days",
                        "Daily tracking",
                        "/targets",
                        "Today's calories and macros.",
                    ),
                    home_link(
                        "chart-column",
                        "Progress",
                        "/targets#macros",
                        "How the day splits across macros.",
                    ),
                    home_link(
                        "apple",
                        "Grocery",
                        "/groceries",
                        "A seven-day list from your targets.",
                    ),
                    home_link(
                        "soup",
                        "Meals",
                        "/meals",
                        "Ideas that follow your diet.",
                    ),
                    class_name="ns-home-links",
                    aria_label="Menu",
                ),
                class_name="ns-home-menu",
            ),
            rx.el.div(
                rx.el.div(
                    rx.el.div("N", class_name="ns-home-mark", aria_hidden="true"),
                    rx.el.p("Daily nutrition", class_name="ns-kicker"),
                    rx.el.h1(
                        "Your daily targets, estimated.",
                        class_name="ns-display",
                    ),
                    rx.el.p(
                        "A short profile sets maintenance calories. A calorie goal and the Muscle Gain toggle can adjust them. You leave with protein, carbohydrates, fat, and fiber — then a weekly grocery plan.",
                        class_name="ns-lede",
                    ),
                    rx.el.div(
                        rx.cond(
                            MacroIntakeState.has_profile,
                            go("Edit profile", "/onboarding", "secondary"),
                            go("Get Started", "/onboarding", "primary"),
                        ),
                        class_name="ns-hero-actions",
                    ),
                    class_name="ns-home-copy",
                ),
                rx.cond(
                    MacroIntakeState.has_profile,
                    rx.el.div(
                        rx.el.p("Intake vs goal", class_name="ns-home-charts-title"),
                        rx.el.div(
                            rx.el.p(
                                MacroIntakeState.calories,
                                class_name="ns-home-cal-number",
                            ),
                            rx.el.div(
                                rx.el.p("kcal / day", class_name="ns-home-cal-unit"),
                                rx.el.p(
                                    MacroIntakeState.calorie_figure,
                                    class_name="ns-home-cal-figure",
                                ),
                                rx.el.p(
                                    MacroIntakeState.calorie_left,
                                    class_name="ns-home-cal-left",
                                ),
                                class_name="ns-home-cal-meta",
                            ),
                            class_name="ns-home-calories",
                            aria_label="Calorie intake versus daily goal",
                        ),
                        intake_pie_row(
                            MacroIntakeState,
                            "ns-intake-grid ns-home-charts-grid",
                        ),
                        class_name="ns-home-charts",
                        aria_label="Macro intake versus goals",
                    ),
                    rx.fragment(),
                ),
                class_name="ns-home-stage",
            ),
            class_name="ns-home",
        ),
        rx.el.ol(
            process("01", "Profile", "Sex, age, height, weight, and activity."),
            process(
                "02",
                "Preferences",
                "Calorie goal, Muscle Gain, fiber, allergies, and diet.",
            ),
            process("03", "Targets", "Calories and grams for the day."),
            process(
                "04",
                "Groceries",
                "A seven-day list from your targets, then revise or record a purchase.",
            ),
            class_name="ns-process",
        ),
    )


app = rx.App(
    html_lang="en",
    stylesheets=[
        "https://fonts.googleapis.com/css2?family=Instrument+Sans:ital,wght@0,400;0,500;0,600;1,400&family=Instrument+Serif:ital@0;1&display=swap",
        "/styles.css",
    ],
    head_components=[
        rx.script(src="/scroll-charts.js"),
    ],
)
app.add_page(
    index,
    title="NutriSpoke",
    description="Estimated daily calorie and macro targets.",
    on_load=MacroIntakeState.load_intake,
)
app.add_page(
    onboarding,
    route="/onboarding",
    title="Profile · NutriSpoke",
    on_load=ButtonEvent.load_saved_profile,
)
app.add_page(
    personalize,
    route="/personalize",
    title="Preferences · NutriSpoke",
    on_load=PersonalizationState.load_saved_preferences,
)
app.add_page(targets, route="/targets", title="Targets · NutriSpoke", on_load=TargetState.load_targets)
app.add_page(
    grocery,
    route="/groceries",
    title="Groceries · NutriSpoke",
    on_load=GroceryState.load_plan,
)
app.add_page(meals, route="/meals", title="Meal Suggestions · NutriSpoke", on_load=MealState.load_meals)
