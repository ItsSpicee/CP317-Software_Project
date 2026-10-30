import reflex as rx
import json
import math
from pathlib import Path

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
    allergies: list[str] = []
    diet_types: list[str] = []
    fiber: float = 30.0
    muscle_gain: bool = False
    calories_error: str = ""
    goal_error: str = ""

    @rx.event
    def load_saved_fiber(self):
        try:
            with open(USER_DATA_FOLDER / "user_personalization_data.json", "r", encoding="utf-8") as f:
                saved_data = json.load(f)
            value = float(saved_data.get("fiber", 30)) if isinstance(saved_data, dict) else 30.0
            self.fiber = min(max(value, 0.0), 100.0)
            if isinstance(saved_data, dict):
                stored_muscle_gain = saved_data.get("muscle_gain")
                if isinstance(stored_muscle_gain, bool):
                    self.muscle_gain = stored_muscle_gain
                else:
                    legacy_goal = str(saved_data.get("current_goal", "")).strip().lower()
                    legacy_macro = str(saved_data.get("priority_macro", "")).strip().lower()
                    self.muscle_gain = legacy_goal == "main gain" or legacy_macro == "protein"
            else:
                self.muscle_gain = False
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            self.fiber = 30.0
            self.muscle_gain = False

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

    @rx.var
    def fiber_label(self) -> str:
        return f"{float(self.fiber):.0f}"

    @rx.event
    def cancel(self):
        return rx.redirect("/")

    @rx.event
    def submit(self, form_data):
        self.calories_error = ""
        self.goal_error = ""

        raw_calories = form_data.get("calories", "")
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

        current_goal = form_data.get("current_goal", "Maintenance") or "Maintenance"
        if current_goal and current_goal not in GOALS:
            self.goal_error = "Choose one of the listed options."

        if any((self.calories_error, self.goal_error)):
            return

        form_data["calories"] = calories
        form_data["current_goal"] = current_goal
        form_data["muscle_gain"] = bool(self.muscle_gain)
        self.fiber = min(max(float(self.fiber), 0.0), 100.0)
        form_data["allergies"] = list(self.allergies)
        form_data["diet_types"] = list(self.diet_types)
        form_data["fiber"] = self.fiber

        with open(USER_DATA_FOLDER / "user_personalization_data.json", "w", encoding="utf-8") as f:
            json.dump(form_data, f, indent=4)

        return rx.redirect("/targets")


def allergy_checkbox(allergy: str) -> rx.Component:
    return rx.box(
        rx.checkbox(
            allergy,
            size="2",
            color_scheme="jade",
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
            on_change=lambda checked: PersonalizationState.toggle_diet(diet, checked),
        ),
        class_name="ns-choice",
    )


def personalize() -> rx.Component:
    return page(
        rx.el.div(
            steps(2),
            rx.el.p("Step 2", class_name="ns-kicker"),
            rx.el.h1("Preferences", class_name="ns-title"),
            rx.el.p(
                "Optional. Skip this if you only want the estimate from your profile.",
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
                            default_value="Maintenance",
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
                    actions(
                        [
                            go("Back", "/onboarding"),
                            press(
                                "Cancel",
                                "ghost",
                                type="button",
                                on_click=PersonalizationState.cancel,
                            ),
                        ],
                        [
                            press("Skip", "secondary", type="submit"),
                            press("Submit", "primary", type="submit"),
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
    )
