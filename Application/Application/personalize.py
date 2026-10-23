import reflex as rx

def personalize() -> rx.Component:
    return rx.container(
        rx.text("time to personalize")
    )