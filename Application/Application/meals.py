import reflex as rx

from .ui import page, press


def meals() -> rx.Component:
    return page(
        rx.el.h1("Meal Suggestions", class_name="ns-title"),
        rx.el.p(
            "Find meal ideas based on your nutrition targets and dietary preferences.",
            class_name="ns-lede",
        ),
        press("Generate meals", type="button", disabled=True),
        rx.el.article(
            rx.el.p("Example meal · Lunch · 1 serving"),
            rx.el.h2("Lemon Chicken and Rice Bowl"),
            rx.el.p("Grilled chicken, rice, cucumber, and a lemon dressing."),
            rx.el.p(
                "Estimated nutrition per serving: 510 kcal · "
                "36 g protein · 60 g carbs · 14 g fat · 5 g fibre"
            ),
            press("Select meal", type="button", disabled=True),
            style={
                "margin_top": "24px",
                "padding": "24px",
                "border": "1px solid #d9d5ca",
                "border_radius": "16px",
                "max_width": "640px",
            },
        ),
        current="meals",
    )
