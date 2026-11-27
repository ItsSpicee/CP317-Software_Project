import reflex as rx

from . import meal_planner as planner
from .grocery import _is_model_unavailable, nut_chip
from .ui import field, page, press


def _friendly_error(exc: Exception) -> str:
    message = str(exc).strip()
    if isinstance(exc, ValueError):
        return message
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

    if any(field in message for field in ("allergies", "diet_types", "religious_restrictions")):
        return (
            "Saved dietary restrictions look invalid. "
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


def _format_card(meal: dict) -> dict[str, str]:
    return {
        "meal_id": meal["meal_id"],
        "name": meal["name"],
        "description": meal["description"],
        "summary": f'{meal["meal_type"]} | Servings: {meal["servings"]}',
        "ingredients": "\n".join(f'{row["name"]} ({row["quantity_g"]:g} g)' for row in meal["ingredients"]),
        "instructions": "\n".join(meal["instructions"]),
        "calories": f'{meal["calories"]:g} kcal',
        **{name: f'{meal[name]:g} g' for name in ("protein", "carbs", "fat", "fiber")},
        "made": str(bool(meal.get("made"))),
    }


class MealState(rx.State):
    meal_type: str = "Breakfast"
    cards: list[dict[str, str]] = []
    history: list[dict[str, str]] = []
    busy: bool = False
    error: str = ""
    warning: str = ""
    status: str = ""
    notes: str = ""
    _meals: list[dict] = []

    def _refresh(self):
        session_id = self.rx_router_session.client_token or ""
        self.history = [{"meal_id": row["meal_id"], "name": row["name"]}
                        for row in planner.get_made_meals(session_id)]
        if not planner.suggestion_path(session_id).exists():
            self._meals, self.cards, self.notes = [], [], ""
            return
        try:
            result = planner.load_meal_suggestion(session_id)
        except ValueError:
            # Older multi-meal suggestions do not fit the single-meal flow.
            self._meals, self.cards, self.notes = [], [], ""
            self.warning = "Generate a new meal to replace the previous suggestions."
            return
        self._meals = result["meals"]
        self.cards = [_format_card(meal) for meal in self._meals]
        self.notes = result["notes"]

    @rx.event
    def load_meals(self):
        self.error = self.warning = self.status = ""
        try:
            self._refresh()
            session_id = self.rx_router_session.client_token or ""
            if not planner.inventory.get_inventory(session_id=session_id):
                self.warning = "Your inventory is empty. Add groceries before generating a meal."
            if self._meals:
                self.meal_type = self._meals[0]["meal_type"]
        except (OSError, ValueError) as exc:
            self.error = _friendly_error(exc)

    @rx.event
    def choose_meal_type(self, value: str):
        if not self.busy and value in planner.MEAL_TYPES:
            self.meal_type = value
            self.warning = self.error = self.status = ""

    @rx.event(background=True)
    async def generate(self):
        async with self:
            if self.busy:
                return
            session_id = self.rx_router_session.client_token or ""
            meal_type = self.meal_type
            self.busy = True
            self.error = self.warning = ""
            self.status = f"Generating one {meal_type.lower()} from your inventory..."
        yield
        try:
            result = await rx.run_in_thread(lambda: planner.generate_meal_suggestions(meal_type, session_id=session_id))
        except Exception as exc:
            async with self:
                self.busy = False
                self.status = ""
                if isinstance(exc, planner.InsufficientInventoryError):
                    self.warning = str(exc)
                    self.cards = []
                    self._meals = []
                    self.notes = ""
                else:
                    self.error = _friendly_error(exc)
            return
        async with self:
            self._meals = result["meals"]
            self.cards = [_format_card(meal) for meal in self._meals]
            self.notes = result["notes"]
            self.busy = False
            self.status = "Your meal is ready. Mark it as made when you prepare it."

    @rx.event(background=True)
    async def mark_meal_made(self, meal_id: str):
        async with self:
            if self.busy:
                return
            self.busy = True
            self.error = self.warning = self.status = ""
            session_id = self.rx_router_session.client_token or ""
        yield
        try:
            await rx.run_in_thread(lambda: planner.mark_meal_made(meal_id, session_id=session_id))
            async with self:
                self._refresh()
                self.status = "Meal recorded. Ingredients deducted from inventory."
        except Exception as exc:
            async with self:
                if isinstance(exc, planner.InsufficientInventoryError):
                    self.warning = str(exc)
                else:
                    self.error = _friendly_error(exc)
        finally:
            async with self:
                self.busy = False

    @rx.event(background=True)
    async def unmark_meal_made(self, meal_id: str):
        async with self:
            if self.busy:
                return
            self.busy = True
            self.error = self.warning = self.status = ""
            session_id = self.rx_router_session.client_token or ""
        yield
        try:
            await rx.run_in_thread(lambda: planner.unmark_meal_made(meal_id, session_id=session_id))
            async with self:
                self._refresh()
                self.status = "Meal unmarked. Ingredients returned to inventory."
        except Exception as exc:
            async with self:
                self.error = _friendly_error(exc)
        finally:
            async with self:
                self.busy = False


def meal_card(meal):
    return rx.el.article(
        rx.el.div(
            rx.el.h3(meal["name"], class_name="ns-grocery-name"),
            rx.el.span(meal["summary"], class_name="ns-meal-summary"),
            class_name="ns-grocery-head",
        ),
        rx.el.p(meal["description"], class_name="ns-grocery-prep"),
        rx.el.div(
            rx.el.span(meal["calories"], class_name="ns-nut-chip ns-nut-kcal"),
            nut_chip("ns-p", "P", meal["protein"]),
            nut_chip("ns-c", "C", meal["carbs"]),
            nut_chip("ns-f", "F", meal["fat"]),
            nut_chip("ns-fiber", "Fiber", meal["fiber"]),
            class_name="ns-grocery-nuts",
        ),
        rx.el.p("Estimated nutrition for the full recipe", class_name="ns-hint"),
        rx.el.div(
            rx.el.div(rx.el.h4("Ingredients"), rx.el.p(meal["ingredients"], style={"whiteSpace": "pre-line"})),
            rx.el.div(rx.el.h4("Instructions"), rx.el.p(meal["instructions"], style={"whiteSpace": "pre-line"})),
            class_name="ns-meal-details",
        ),
        rx.cond(
            meal["made"] == "True",
            press("Unmark as Made", "secondary", on_click=MealState.unmark_meal_made(meal["meal_id"]), disabled=MealState.busy),
            press("Mark as Made", on_click=MealState.mark_meal_made(meal["meal_id"]), disabled=MealState.busy),
        ),
        class_name="ns-grocery-item ns-meal-item",
    )


def history_row(meal):
    return rx.el.li(
        rx.el.span(meal["name"]),
        press("Unmark as Made", "secondary", on_click=MealState.unmark_meal_made(meal["meal_id"]), disabled=MealState.busy),
        class_name="ns-grocery-head",
    )


def meals() -> rx.Component:
    return page(
        rx.el.div(
            rx.el.p("Cook from your inventory", class_name="ns-kicker"),
            rx.el.h1("Meals", class_name="ns-title"),
            rx.el.p("Choose a meal type and generate one recipe using only what you have. Nutrition values are AI estimates.", class_name="ns-lede"),
            field(
                "Meal type",
                rx.select(list(planner.MEAL_TYPES), value=MealState.meal_type, on_change=MealState.choose_meal_type,
                          disabled=MealState.busy, id="meal-type", aria_label="Meal type"),
                for_id="meal-type",
            ),
            press("Generate meal", on_click=MealState.generate, disabled=MealState.busy),
            rx.cond(MealState.warning != "", rx.el.p(MealState.warning, class_name="ns-notice", role="alert")),
            rx.cond(MealState.error != "", rx.el.p(MealState.error, class_name="ns-error", role="alert")),
            rx.cond(MealState.status != "", rx.el.p(MealState.status, class_name="ns-status", role="status")),
            rx.cond(MealState.busy, rx.el.div(rx.el.span(class_name="ns-spinner", aria_hidden="true"), rx.el.span("Working..."), class_name="ns-loader", role="status")),
            rx.foreach(MealState.cards, meal_card),
            rx.cond(MealState.notes != "", rx.el.p(MealState.notes, class_name="ns-callout")),
            rx.cond(
                MealState.history.length() > 0,
                rx.el.section(
                    rx.el.h2("Made today", class_name="ns-section-title"),
                    rx.el.ul(rx.foreach(MealState.history, history_row), class_name="ns-grocery-list ns-made-meals"),
                    class_name="ns-list-block",
                ),
            ),
            class_name="ns-sheet ns-stack",
        ),
        current="meals",
    )
