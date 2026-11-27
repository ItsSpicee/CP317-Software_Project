import reflex as rx
import json
import math
from pathlib import Path

from .grocery_planner import invalidate_weekly_plan
from .navigation import NavigationState
from .dietary_restrictions import RELIGIOUS_RESTRICTIONS
from .ui import actions, entry, field, go, menu, page, press, steps


PARENT_DIR = Path(__file__).resolve().parent.parent
USER_DATA_FOLDER = PARENT_DIR / "User Data"

DIETS = ["Vegetarian", "Vegan", "Keto", "Gluten Free", "Carnivore", "Animal Based"]
GOALS = ["Maintenance", "Weight Gain", "Weight Loss"]

FOOD_ALLERGIES = [
    "Eggs",
    "Milk",
    "Mustard",
    "Peanuts",
    "Crustaceans",
    "Fish",
    "Sesame seeds",
    "Soy",
    "Sulphites",
    "Tree nuts"
]

class PersonalizationState(rx.State):
    editing: bool = False
    allergies: list[str] = []
    diet_types: list[str] = []
    religious_restrictions: list[str] = []
    fiber: float = 30.0
    muscle_gain: bool = False
    calories: str = ""
    current_goal: str = "Maintenance"
    calories_error: str = ""
    goal_error: str = ""

    @rx.event
    def load_setup(self):
        self.editing = False
        self.load_saved_preferences()

    @rx.event
    def load_editor(self):
        self.editing = True
        self.load_saved_preferences()

    @rx.event
    def load_saved_preferences(self):
        try:
            with open(USER_DATA_FOLDER / "user_personalization_data.json", "r", encoding="utf-8") as f:
                saved_data = json.load(f)
        except (OSError, json.JSONDecodeError):
            saved_data = {}
        if not isinstance(saved_data, dict):
            saved_data = {}

        try:
            value = float(saved_data.get("fiber", 30))
        except (TypeError, ValueError):
            value = 30.0
        self.fiber = min(max(value, 0.0), 100.0) if math.isfinite(value) else 30.0
        stored_muscle_gain = saved_data.get("muscle_gain")
        self.muscle_gain = stored_muscle_gain if isinstance(stored_muscle_gain, bool) else False

        raw_calories = saved_data.get("calories", "")
        if raw_calories in (None, ""):
            self.calories = ""
        else:
            try:
                calories = float(raw_calories)
                self.calories = (
                    str(int(calories))
                    if math.isfinite(calories) and calories.is_integer()
                    else ""
                )
            except (TypeError, ValueError):
                self.calories = ""

        goal = str(saved_data.get("current_goal", "Maintenance") or "Maintenance")
        self.current_goal = goal if goal in GOALS else "Maintenance"

        allergies = saved_data.get("allergies", [])
        diets = saved_data.get("diet_types", [])
        self.allergies = (
            [option for option in FOOD_ALLERGIES if option in allergies]
            if isinstance(allergies, list) else []
        )
        self.diet_types = (
            [option for option in DIETS if option in diets]
            if isinstance(diets, list) else []
        )
        restrictions = saved_data.get("religious_restrictions", [])
        self.religious_restrictions = (
            [option for option in RELIGIOUS_RESTRICTIONS if option in restrictions]
            if isinstance(restrictions, list) else []
        )
        self.calories_error = ""
        self.goal_error = ""

    @rx.event
    def set_calories(self, value: str):
        self.calories = value

    @rx.event
    def set_current_goal(self, value: str):
        self.current_goal = value

    @rx.event
    def set_muscle_gain(self, checked: bool):
        self.muscle_gain = checked

    @rx.event
    def toggle_allergy(self, allergy: str, checked: bool):
        if checked and allergy not in self.allergies:
            self.allergies.append(allergy)
        elif not checked and allergy in self.allergies:
            self.allergies.remove(allergy)

    @rx.event
    def toggle_diet(self, diet: str, checked: bool):
        if checked and diet not in self.diet_types:
            self.diet_types.append(diet)
        elif not checked and diet in self.diet_types:
            self.diet_types.remove(diet)

    @rx.event
    def set_fiber(self, value: list[int | float]):
        self.fiber = value[0]

    @rx.event
    def toggle_religious_restriction(self, restriction: str, checked: bool):
        if restriction not in RELIGIOUS_RESTRICTIONS:
            return
        if checked and restriction not in self.religious_restrictions:
            self.religious_restrictions.append(restriction)
        elif not checked and restriction in self.religious_restrictions:
            self.religious_restrictions.remove(restriction)

    @rx.var
    def fiber_label(self) -> str:
        return f"{float(self.fiber):.0f}"

    @rx.event
    def cancel(self):
        return rx.redirect("/overview" if self.editing else "/onboarding")

    @rx.event
    def submit(self, form_data):
        self.calories_error = ""
        self.goal_error = ""

        raw_calories = form_data.get("calories", self.calories)
        calories = ""
        if raw_calories not in (None, ""):
            try:
                calories = float(raw_calories)
                if (
                    not math.isfinite(calories)
                    or not 0 <= calories <= 10_000
                    or not calories.is_integer()
                ):
                    self.calories_error = "Enter a whole number from 0 to 10,000, or leave it blank."
            except (TypeError, ValueError):
                self.calories_error = "Enter a valid calorie target, or leave it blank."

        current_goal = (
            form_data.get("current_goal", self.current_goal) or self.current_goal or "Maintenance"
        )
        if current_goal and current_goal not in GOALS:
            self.goal_error = "Choose one of the listed options."

        if any((self.calories_error, self.goal_error)):
            return

        self.fiber = min(max(float(self.fiber), 0.0), 100.0)
        payload = {
            "calories": calories,
            "current_goal": current_goal,
            "muscle_gain": bool(self.muscle_gain),
            "allergies": list(self.allergies),
            "diet_types": list(self.diet_types),
            "religious_restrictions": list(getattr(self, "religious_restrictions", [])),
            "fiber": self.fiber,
        }

        preferences_path = USER_DATA_FOLDER / "user_personalization_data.json"
        try:
            previous = json.loads(preferences_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = None
        USER_DATA_FOLDER.mkdir(parents=True, exist_ok=True)
        with open(preferences_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4)
        if previous != payload:
            invalidate_weekly_plan()

        self.calories = "" if calories in ("", None) else str(int(calories))
        self.current_goal = current_goal

        return rx.redirect("/overview") if self.editing else NavigationState.preferences_saved


def allergy_checkbox(allergy: str) -> rx.Component:
    return rx.box(
        rx.checkbox(
            allergy,
            size="2",
            color_scheme="jade",
            checked=PersonalizationState.allergies.contains(allergy),
            on_change=lambda checked: PersonalizationState.toggle_allergy(allergy, checked),
        ),
        class_name="ns-choice",
    )


def diet_checkbox(diet: str) -> rx.Component:
    return rx.box(
        rx.checkbox(
            diet,
            size="2",
            color_scheme="jade",
            checked=PersonalizationState.diet_types.contains(diet),
            on_change=lambda checked: PersonalizationState.toggle_diet(diet, checked),
        ),
        class_name="ns-choice",
    )


def religious_checkbox(restriction: str) -> rx.Component:
    return rx.box(
        rx.checkbox(
            restriction,
            size="2",
            color_scheme="jade",
            checked=PersonalizationState.religious_restrictions.contains(restriction),
            on_change=lambda checked: PersonalizationState.toggle_religious_restriction(restriction, checked),
        ),
        class_name="ns-choice",
    )


def personalize(edit: bool = False) -> rx.Component:
    return page(
        rx.el.div(
            *([] if edit else [steps(2), rx.el.p("Step 2", class_name="ns-kicker")]),
            rx.el.h1("Preferences", class_name="ns-title"),
            rx.el.p(
                "Update your preferences. Saving recalculates your daily targets."
                if edit else "Optional. Skip this if you only want the estimate from your profile.",
                class_name="ns-lede",
            ),
            rx.form(
                rx.el.div(
                    rx.el.div(
                        field(
                            "Calorie target",
                            entry(
                                name="calories",
                                id="calories",
                                type="number",
                                min=0,
                                max=10_000,
                                step=1,
                                placeholder="Optional",
                                value=PersonalizationState.calories,
                                on_change=PersonalizationState.set_calories,
                                aria_invalid=PersonalizationState.calories_error != "",
                            ),
                            "0–10,000. A number here replaces the estimate.",
                            for_id="calories",
                            error=PersonalizationState.calories_error,
                        ),
                        field(
                            "Muscle Gain",
                            rx.switch(
                                id="muscle_gain",
                                checked=PersonalizationState.muscle_gain,
                                on_change=PersonalizationState.set_muscle_gain,
                            ),
                            "Modestly increases protein while keeping your calorie goal.",
                            for_id="muscle_gain",
                        ),
                        class_name="ns-row",
                    ),
                    rx.el.div(
                        rx.el.div(
                            rx.el.label("Fiber", class_name="ns-label", html_for="fiber"),
                            rx.el.span(
                                PersonalizationState.fiber_label,
                                " g",
                                class_name="ns-fiber-value",
                            ),
                            class_name="ns-fiber-head",
                        ),
                        rx.slider(
                            id="fiber",
                            name="fiber",
                            value=[PersonalizationState.fiber],
                            min=0,
                            max=100,
                            step=1,
                            color_scheme="jade",
                            on_change=PersonalizationState.set_fiber,
                            aria_label="Fiber target in grams",
                        ),
                        rx.el.p(
                            "0–100 g. You choose this. It is not estimated.",
                            class_name="ns-hint",
                        ),
                        class_name="ns-field",
                    ),
                    field(
                        "Goal",
                        menu(
                            GOALS,
                            name="current_goal",
                            id="current_goal",
                            value=PersonalizationState.current_goal,
                            on_change=PersonalizationState.set_current_goal,
                            aria_invalid=PersonalizationState.goal_error != "",
                        ),
                        for_id="current_goal",
                        error=PersonalizationState.goal_error,
                    ),
                    rx.el.ul(
                        rx.el.li("Weight Gain adds 200 kcal to maintenance."),
                        rx.el.li("Weight Loss subtracts 200 kcal."),
                        class_name="ns-notes",
                    ),
                    rx.el.div(
                        rx.el.h2("Allergies", class_name="ns-label"),
                        rx.el.div(
                            *[allergy_checkbox(allergy) for allergy in FOOD_ALLERGIES],
                            class_name="ns-choices",
                        ),
                        class_name="ns-group",
                    ),
                    rx.el.div(
                        rx.el.h2("Diet types", class_name="ns-label"),
                        rx.el.div(
                            *[diet_checkbox(diet) for diet in DIETS],
                            class_name="ns-choices",
                        ),
                        class_name="ns-group",
                    ),
                    rx.el.div(
                        rx.el.h2("Religious Restrictions", class_name="ns-label"),
                        rx.el.p(
                            "Choose the food practices you follow. Check product labels and certification where required.",
                            class_name="ns-hint",
                        ),
                        rx.el.div(
                            *[religious_checkbox(option) for option in RELIGIOUS_RESTRICTIONS],
                            class_name="ns-choices",
                        ),
                        class_name="ns-group",
                    ),
                    actions(
                        [go("Cancel", "/overview")],
                        [press("Save changes", "primary", type="submit")],
                    ) if edit else actions(
                        [go("Back", "/onboarding")],
                        [
                            press("Skip", "secondary", type="submit"),
                            press("View targets", "primary", type="submit"),
                        ],
                    ),
                    class_name="ns-stack",
                ),
                on_submit=PersonalizationState.submit,
                no_validate=True,
            ),
            class_name="ns-sheet",
        ),
        current="preferences",
        setup=not edit,
    )
