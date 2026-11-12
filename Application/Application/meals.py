import reflex as rx

from .meal_planner import generate_meal_suggestions, select_meal
from .ui import page, press


class MealState(rx.State):
    cards: list[dict[str, str]] = []
    saved: list[int] = []
    busy: bool = False
    status: str = ""
    _meals: list[dict] = []

    @rx.event(background=True)
    async def generate(self):
        async with self:
            if self.busy:
                return
            self.busy = True
            self.status = "Generating meal suggestions…"

        try:
            result = await rx.run_in_thread(generate_meal_suggestions)
        except Exception:
            async with self:
                self.busy = False
                self.status = "Couldn’t generate meals. Check your saved preferences and try again."
            return

        async with self:
            self._meals = result["meals"]
            self.cards = [
                {
                    "name": meal["name"],
                    "description": meal["description"],
                    "summary": f'{meal["meal_type"]} · Servings: {meal["servings"]}',
                    "nutrition": (
                        f'{meal["calories"]:g} kcal · {meal["protein"]:g} g protein · '
                        f'{meal["carbs"]:g} g carbs · {meal["fat"]:g} g fat · '
                        f'{meal["fiber"]:g} g fibre'
                    ),
                }
                for meal in self._meals
            ]
            self.saved = []
            self.busy = False
            self.status = "Meal suggestions are ready."

    @rx.event
    def save_meal(self, index: int):
        if self.busy or index in self.saved or not 0 <= index < len(self._meals):
            return

        try:
            select_meal(self._meals[index])
        except Exception:
            self.status = "Couldn’t save that meal. Try selecting it again."
            return

        self.saved = [*self.saved, index]
        self.status = f'Saved {self._meals[index]["name"]}.'


def meal_card(meal, index):
    is_saved = MealState.saved.contains(index)

    return rx.el.article(
        rx.el.p(meal["summary"]),
        rx.el.h2(meal["name"], style={"font_weight": "600"}),
        rx.el.p(meal["description"]),
        rx.el.p("Estimated nutrition for the full recipe"),
        rx.el.p(meal["nutrition"]),
        press(
            rx.cond(is_saved, "Saved", "Select meal"),
            type="button",
            on_click=MealState.save_meal(index),
            disabled=MealState.busy | is_saved,
        ),
        style={
            "display": "grid",
            "gap": "8px",
            "justify_items": "start",
            "margin_top": "16px",
            "padding": "24px",
            "border": "1px solid #d9d5ca",
            "border_radius": "16px",
            "max_width": "640px",
        },
    )


def meals() -> rx.Component:
    return page(
        rx.el.h1("Meal Suggestions", class_name="ns-title"),
        rx.el.p(
            "Generate meal ideas based on your nutrition targets and dietary preferences.",
            class_name="ns-lede",
        ),
        press(
            "Generate meals",
            type="button",
            on_click=MealState.generate,
            disabled=MealState.busy,
        ),
        rx.el.p(MealState.status, role="status"),
        rx.foreach(MealState.cards, meal_card),
        current="meals",
    )