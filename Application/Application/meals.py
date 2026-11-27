import json

import reflex as rx

from . import meal_planner as planner
from .meal_planner import (
    generate_meal_suggestions,
    select_meal,
)
from .grocery import _is_model_unavailable, nut_chip
from .ui import actions, go, page, press


def _friendly_error(exc: Exception) -> str:
    message = str(exc).strip()
    lower = message.lower()

    if _is_model_unavailable(message) or "429" in lower:
        return (
            "The meal model is temporarily unavailable. "
            "Wait a moment, then try again."
        )

    if "GEMINI_API_KEY" in message or "GEMINI_MODEL" in message:
        return message

    if "positive daily calorie" in lower:
        return (
            "Set a positive calorie target in Preferences "
            "before generating meals."
        )

    if "user_data.json" in message or "user_personalization_data.json" in message:
        return "Complete Profile and Preferences before generating meals."

    if "allergies" in message or "diet_types" in message:
        return (
            "Saved allergies or diet types look invalid. "
            "Re-save Preferences, then try again."
        )

    if "browser session" in lower:
        return "Your browser session could not be identified. Refresh the page and try again."

    if "timeout" in lower or "timed out" in lower:
        return "The meal request timed out. Please try again."

    if "401" in lower or "403" in lower:
        return (
            "The meal service rejected the API credentials. "
            "Check your Gemini API key."
        )

    if "404" in lower:
        return "The configured Gemini model could not be found. Check GEMINI_MODEL."

    if "gemini" in lower and ("json" in lower or "did not finish" in lower):
        return (
            "The meal service returned an incomplete response. "
            "Please try again."
        )

    return "Couldn’t complete the meal action. Check your inventory and try again."


def _ingredient_names(items) -> str:
    """Convert ingredient objects or strings into readable text."""
    if not isinstance(items, list) or not items:
        return "None"

    names = []

    for item in items:
        if isinstance(item, dict):
            name = item.get("name", "Ingredient")
            quantity = item.get("quantity_g")

            if quantity is not None:
                names.append(f"{name} ({quantity:g} g)")
            else:
                names.append(str(name))
        else:
            names.append(str(item))

    return "\n".join(f"• {name}" for name in names)


def _format_card(meal: dict) -> dict[str, str]:
    """Convert a saved meal into the string values used by the UI."""
    availability = meal.get("ingredient_availability", {})

    if not isinstance(availability, dict):
        availability = {}

    ingredient_details = availability.get("ingredients", [])
    if not isinstance(ingredient_details, list):
        ingredient_details = []

    available = [
        item for item in ingredient_details
        if isinstance(item, dict) and item.get("available_g", 0) > 0
    ]

    missing = [
        item for item in ingredient_details
        if isinstance(item, dict) and item.get("missing_g", 0) > 0
    ]

    made = bool(meal.get("made", False))

    if made:
        inventory_status = "Made"
    elif missing:
        inventory_status = "Missing ingredients"
    else:
        inventory_status = "All ingredients available"

    return {
        "meal_id": str(meal.get("meal_id", "")),
        "name": meal["name"],
        "description": meal["description"],
        "ingredients": _ingredient_names(meal["ingredients"]),
        "available_ingredients": _ingredient_names(available),
        "missing_ingredients": _ingredient_names(missing),
        "instructions": "\n".join(meal["instructions"]),
        "summary": f'{meal["meal_type"]} · Servings: {meal["servings"]}',
        "calories": f'{meal["calories"]:g} kcal',
        "protein": f'{meal["protein"]:g} g',
        "carbs": f'{meal["carbs"]:g} g',
        "fat": f'{meal["fat"]:g} g',
        "fiber": f'{meal["fiber"]:g} g',
        "inventory_status": inventory_status,
        "made": str(made),
    }


class MealState(rx.State):
    cards: list[dict[str, str]] = []
    saved: list[int] = []
    made: list[int] = []

    busy: bool = False
    status: str = ""
    error: str = ""
    error_unavailable: bool = False
    notes: str = ""

    _meals: list[dict] = []

    @rx.event
    def load_meals(self):
        session_id = self.rx_router_session.client_token or ""

        self.error = ""
        self.error_unavailable = False
        self.status = ""

        try:
            result = planner._read_json(planner.suggestion_path(session_id))
            planner._validate_meals(result)

        except (OSError, ValueError, json.JSONDecodeError):
            self._meals = []
            self.cards = []
            self.saved = []
            self.made = []
            self.notes = ""
            return

        self._meals = result["meals"]
        self.cards = [_format_card(meal) for meal in self._meals]
        self.notes = result.get("notes", "")

        self.saved = []
        self.made = []

        try:
            selected_data = planner._read_json(
                planner.selected_meals_path(session_id)
            )
            selected = selected_data.get("meals", [])

            if isinstance(selected, list):
                selected_ids = {
                    str(meal.get("meal_id"))
                    for meal in selected
                    if isinstance(meal, dict)
                    and meal.get("meal_id") is not None
                }

                made_ids = {
                    str(meal.get("meal_id"))
                    for meal in selected
                    if isinstance(meal, dict)
                    and meal.get("made", False)
                    and meal.get("meal_id") is not None
                }

                self.saved = [
                    index for index, meal in enumerate(self._meals)
                    if str(meal.get("meal_id", "")) in selected_ids
                ]

                self.made = [
                    index for index, meal in enumerate(self._meals)
                    if str(meal.get("meal_id", "")) in made_ids
                ]

        except (OSError, ValueError, json.JSONDecodeError):
            pass

        # Keep the cards' made labels synchronized with saved meal data.
        for index in self.made:
            if 0 <= index < len(self.cards):
                self.cards[index]["made"] = "True"
                self.cards[index]["inventory_status"] = "Made"

    @rx.event(background=True)
    async def generate(self):
        async with self:
            if self.busy:
                return

            session_id = self.rx_router_session.client_token or ""

            self.busy = True
            self.error = ""
            self.error_unavailable = False
            self.status = (
                "Generating meal suggestions. This can take up to 2 minutes."
            )

        yield

        try:
            result = await rx.run_in_thread(
                lambda: generate_meal_suggestions(
                    session_id=session_id,
                )
            )

        except Exception as exc:
            async with self:
                self.busy = False
                self.status = ""
                self.error = _friendly_error(exc)
                self.error_unavailable = (
                    _is_model_unavailable(str(exc))
                    or "429" in str(exc)
                )
            return

        async with self:
            self._meals = result["meals"]
            self.cards = [_format_card(meal) for meal in self._meals]

            self.saved = []
            self.made = []
            self.notes = result.get("notes", "")

            self.busy = False
            self.status = (
                "Meal suggestions are ready. "
                "Ingredient availability is based on your inventory."
            )

    @rx.event
    def save_meal(self, index: int):
        if (
            self.busy
            or index in self.saved
            or not 0 <= index < len(self._meals)
        ):
            return

        self.error = ""
        self.error_unavailable = False
        self.status = ""

        session_id = self.rx_router_session.client_token or ""

        try:
            selected = select_meal(
                self._meals[index],
                session_id=session_id,
            )

        except Exception as exc:
            self.error = _friendly_error(exc)
            return

        # Keep the generated meal's ID in memory so mark-made uses the
        # same ID as the saved selected-meal record.
        self._meals[index]["meal_id"] = selected["meal_id"]
        self.saved = [*self.saved, index]
        self.status = f'Saved {self._meals[index]["name"]}.'

    @rx.event(background=True)
    async def mark_meal_made(self, index: int):
        async with self:
            if (
                self.busy
                or index in self.made
                or index not in self.saved
                or not 0 <= index < len(self._meals)
            ):
                return

            meal = self._meals[index]
            meal_id = str(meal.get("meal_id", ""))

            if not meal_id:
                self.error = (
                    "This meal is missing its ID. "
                    "Regenerate your meal suggestions."
                )
                return

            session_id = self.rx_router_session.client_token or ""

            self.busy = True
            self.error = ""
            self.error_unavailable = False
            self.status = "Updating your grocery inventory..."

        yield

        try:
            await rx.run_in_thread(
                lambda: planner.mark_meal_made(
                    meal_id,
                    session_id=session_id,
                )
            )

        except Exception as exc:
            async with self:
                self.busy = False
                self.status = ""
                self.error = _friendly_error(exc)
            return

        async with self:
            self.busy = False
            self.made = [*self.made, index]

            self.cards[index]["made"] = "True"
            self.cards[index]["inventory_status"] = "Made"

            self.status = (
                f'Marked {self._meals[index]["name"]} as made. '
                "Your inventory has been updated. "
                "Regenerate meals to refresh ingredient availability."
            )


def meal_card(meal, index):
    is_saved = MealState.saved.contains(index)
    is_made = MealState.made.contains(index)

    has_missing = meal["missing_ingredients"] != "None"

    return rx.el.article(
        # Meal heading
        rx.el.div(
            rx.el.div(
                rx.icon("utensils", size=16, class_name="ns-grocery-icon"),
                rx.el.h3(meal["name"], class_name="ns-grocery-name"),
                class_name="ns-grocery-title",
            ),
            rx.el.span(meal["summary"], class_name="ns-meal-summary"),
            class_name="ns-grocery-head",
        ),

        # Description
        rx.el.p(meal["description"], class_name="ns-grocery-prep"),

        # Nutrition
        rx.el.div(
            rx.el.span(
                meal["calories"],
                class_name="ns-nut-chip ns-nut-kcal",
            ),
            nut_chip("ns-p", "P", meal["protein"]),
            nut_chip("ns-c", "C", meal["carbs"]),
            nut_chip("ns-f", "F", meal["fat"]),
            nut_chip("ns-fiber", "Fiber", meal["fiber"]),
            class_name="ns-grocery-nuts",
        ),

        rx.el.p(
            "Estimated nutrition for the full recipe",
            class_name="ns-grocery-prep",
        ),

        # Inventory availability
        rx.el.div(
            rx.el.h4("Inventory availability"),
            rx.cond(
                is_made,
                rx.el.p(
                    "This meal has been marked as made.",
                    class_name="ns-status",
                ),
                rx.cond(
                    has_missing,
                    rx.el.div(
                        rx.el.p(
                            "Available ingredients",
                            class_name="ns-meal-inventory-label",
                        ),
                        rx.el.p(
                            meal["available_ingredients"],
                            class_name="ns-meal-inventory-available",
                            style={"whiteSpace": "pre-line"},
                        ),
                        rx.el.p(
                            "Missing ingredients",
                            class_name="ns-meal-inventory-label",
                        ),
                        rx.el.p(
                            meal["missing_ingredients"],
                            class_name="ns-meal-inventory-missing",
                            style={"whiteSpace": "pre-line"},
                        ),
                    ),
                    rx.el.p(
                        "All ingredients are available in your inventory.",
                        class_name="ns-meal-inventory-available",
                    ),
                ),
            ),
            class_name="ns-meal-inventory",
        ),

        # Ingredients and instructions
        rx.el.div(
            rx.el.div(
                rx.el.h4("Ingredients"),
                rx.el.p(
                    meal["ingredients"],
                    style={"whiteSpace": "pre-line"},
                ),
            ),
            rx.el.div(
                rx.el.h4("Instructions"),
                rx.el.p(
                    meal["instructions"],
                    style={"whiteSpace": "pre-line"},
                ),
            ),
            class_name="ns-meal-details",
        ),

        # Save meal button
        press(
            rx.cond(is_saved, "Saved", "Select meal"),
            "secondary",
            type="button",
            on_click=MealState.save_meal(index),
            disabled=MealState.busy | is_saved | is_made,
        ),

        # Mark as made button
        rx.cond(
            is_saved,
            press(
                rx.cond(is_made, "Made", "Mark as Made"),
                "primary",
                type="button",
                on_click=MealState.mark_meal_made(index),
                disabled=MealState.busy | is_made,
            ),
        ),

        class_name="ns-grocery-item ns-meal-item",
    )


def meals() -> rx.Component:
    return page(
        rx.el.div(
            # Page title
            rx.el.div(
                rx.el.div(
                    rx.el.p("Meal ideas", class_name="ns-kicker"),
                    rx.el.h1("Meals", class_name="ns-title"),
                    class_name="ns-title-copy",
                ),
                rx.cond(
                    MealState.cards.length() > 0,
                    press(
                        "Regenerate",
                        "secondary",
                        type="button",
                        on_click=MealState.generate,
                        disabled=MealState.busy,
                    ),
                ),
                class_name="ns-title-row",
            ),

            rx.el.p(
                "Meal suggestions from your targets, allergies, "
                "diet, and grocery inventory. Nutrition values "
                "are AI estimates.",
                class_name="ns-lede",
            ),

            # Error messages
            rx.cond(
                MealState.error != "",
                rx.cond(
                    MealState.error_unavailable,
                    rx.el.div(
                        rx.el.div(
                            rx.icon(
                                "cloud-off",
                                size=22,
                                class_name="ns-notice-icon",
                            ),
                            rx.el.div(
                                rx.el.p(
                                    "Model temporarily unavailable",
                                    class_name="ns-notice-title",
                                ),
                                rx.el.p(
                                    MealState.error,
                                    class_name="ns-notice-body",
                                ),
                                class_name="ns-notice-copy",
                            ),
                            class_name="ns-notice-row",
                        ),
                        class_name="ns-notice ns-notice-unavailable",
                        role="alert",
                    ),
                    rx.el.p(
                        MealState.error,
                        class_name="ns-error",
                        role="alert",
                    ),
                ),
            ),

            # Status message
            rx.cond(
                MealState.status != "",
                rx.el.p(
                    MealState.status,
                    class_name="ns-status",
                    role="status",
                ),
            ),

            # Main content
            rx.el.div(
                rx.cond(
                    MealState.cards.length() > 0,
                    rx.el.div(
                        rx.el.div(
                            rx.icon(
                                "list",
                                size=15,
                                class_name="ns-section-icon",
                            ),
                            rx.el.h2(
                                "Meal suggestions",
                                class_name="ns-section-title",
                            ),
                            class_name="ns-section-head",
                        ),
                        rx.foreach(MealState.cards, meal_card),
                        class_name="ns-list-block",
                    ),
                    rx.el.div(
                        rx.el.p(
                            "No meal suggestions yet. Generate meals "
                            "after saving your Profile and Preferences.",
                            class_name="ns-lede ns-lede-tight",
                        ),
                        class_name="ns-callout",
                    ),
                ),

                rx.cond(
                    MealState.notes != "",
                    rx.el.div(
                        rx.el.p(MealState.notes),
                        class_name="ns-callout",
                    ),
                ),

                # Loading indicator
                rx.cond(
                    MealState.busy,
                    rx.el.div(
                        rx.el.span(
                            class_name="ns-spinner",
                            aria_hidden="true",
                        ),
                        rx.el.span(
                            "Working…",
                            class_name="ns-spinner-label",
                        ),
                        class_name="ns-loader",
                        role="status",
                        aria_live="polite",
                    ),
                ),

                # Navigation and generate button
                actions(
                    [go("Overview", "/overview")],
                    [
                        press(
                            "Generate meals",
                            "primary",
                            type="button",
                            on_click=MealState.generate,
                            disabled=MealState.busy,
                        )
                    ],
                ),

                class_name="ns-stack ns-grocery-body",
            ),

            class_name="ns-sheet",
        ),
        current="meals",
    )