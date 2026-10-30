import reflex as rx


def page(*children, current: str = "") -> rx.Component:
    def link(label: str, href: str, key: str) -> rx.Component:
        class_name = "ns-nav-link is-active" if current == key else "ns-nav-link"
        return rx.link(label, href=href, class_name=class_name, underline="none")

    return rx.el.div(
        rx.el.header(
            rx.link("NutriSpoke", href="/", class_name="ns-mark", underline="none"),
            rx.el.nav(
                link("Profile", "/onboarding", "profile"),
                link("Preferences", "/personalize", "preferences"),
                link("Targets", "/targets", "targets"),
                class_name="ns-nav-links",
                aria_label="Primary",
            ),
            class_name="ns-nav",
        ),
        rx.el.main(*children, class_name="ns-main"),
        rx.el.footer(
            rx.el.div(
                rx.el.p(
                    "Estimates from a fixed equation. They are not medical advice.",
                    class_name="ns-foot",
                ),
                class_name="ns-footer-inner",
            ),
            class_name="ns-footer",
        ),
        class_name="ns-page",
    )


def steps(current: int) -> rx.Component:
    pips = []
    for number in (1, 2, 3):
        class_name = "ns-pip"
        if number < current:
            class_name += " is-done"
        elif number == current:
            class_name += " is-on"
        pips.append(rx.el.span(class_name=class_name))
    return rx.el.div(
        *pips,
        class_name="ns-steps",
        role="img",
        aria_label=f"Step {current} of 3",
    )


def go(label: str, href: str, kind: str = "ghost") -> rx.Component:
    return rx.link(
        label,
        href=href,
        class_name=f"ns-btn ns-btn-{kind}",
        underline="none",
    )


def press(label: str, kind: str = "primary", **props) -> rx.Component:
    return rx.button(
        label,
        class_name=f"ns-btn ns-btn-{kind}",
        size="3",
        **props,
    )


def actions(left: list[rx.Component], right: list[rx.Component]) -> rx.Component:
    return rx.el.div(
        rx.el.div(*left, class_name="ns-actions-group"),
        rx.el.div(*right, class_name="ns-actions-group"),
        class_name="ns-actions",
    )


def field(
    label: str,
    control: rx.Component,
    hint: str = "",
    for_id: str = "",
    class_name: str = "",
    error="",
) -> rx.Component:
    label_props: dict = {"class_name": "ns-label"}
    if for_id:
        label_props["html_for"] = for_id
    children: list[rx.Component] = [
        rx.el.label(label, **label_props),
        control,
    ]
    if hint:
        children.append(rx.el.p(hint, class_name="ns-hint"))
    children.append(
        rx.cond(
            error != "",
            rx.el.p(error, class_name="ns-error", role="alert"),
            rx.fragment(),
        )
    )
    classes = "ns-field" if not class_name else f"ns-field {class_name}"
    return rx.el.div(*children, class_name=classes)


def entry(**props) -> rx.Component:
    return rx.input(
        size="3",
        variant="surface",
        width="100%",
        color_scheme="jade",
        **props,
    )


def menu(options: list[str], **props) -> rx.Component:
    return rx.select(
        options,
        size="3",
        variant="surface",
        width="100%",
        color_scheme="jade",
        **props,
    )


def energy_bar(protein, carbs, fat) -> rx.Component:
    return rx.el.div(
        rx.el.div(class_name="ns-seg ns-p", style={"width": protein}),
        rx.el.div(class_name="ns-seg ns-c", style={"width": carbs}),
        rx.el.div(class_name="ns-seg ns-f", style={"width": fat}),
        class_name="ns-bar",
        role="img",
        aria_label="Share of calories from protein, carbohydrates, and fat",
    )


def macro_line(name, value, note, swatch: str) -> rx.Component:
    return rx.el.div(
        rx.el.span(class_name=f"ns-swatch {swatch}"),
        rx.el.div(
            rx.el.span(name, class_name="ns-macro-name"),
            rx.el.span(note, class_name="ns-macro-note"),
            class_name="ns-macro-copy",
        ),
        rx.el.span(value, class_name="ns-macro-value"),
        class_name="ns-macro",
    )


def illustration() -> rx.Component:
    return rx.el.aside(
        rx.el.div(
            rx.el.p("Illustration", class_name="ns-preview-kicker"),
            rx.el.p("Not your plan", class_name="ns-preview-note"),
            class_name="ns-preview-top",
        ),
        rx.el.p("2,180", class_name="ns-preview-number"),
        rx.el.p("kcal / day", class_name="ns-unit-label"),
        energy_bar("26%", "44%", "30%"),
        rx.el.div(
            macro_line("Protein", "140 g", "26% of calories", "ns-p"),
            macro_line("Carbohydrates", "241 g", "44% of calories", "ns-c"),
            macro_line("Fat", "73 g", "30% of calories", "ns-f"),
            macro_line("Fiber", "30 g", "Selected", "ns-fiber"),
            class_name="ns-macro-list",
        ),
        class_name="ns-preview",
        aria_label="Example of a finished target card",
    )


def process(index: str, title: str, body: str) -> rx.Component:
    return rx.el.li(
        rx.el.span(index, class_name="ns-index"),
        rx.el.h2(title),
        rx.el.p(body),
    )
