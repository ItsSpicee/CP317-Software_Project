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
                link("Groceries", "/groceries", "groceries"),
                link("Meals", "/meals", "meals"),
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
    children.append(
        rx.cond(
            error != "",
            rx.fragment(),
            rx.cond(
                hint == "",
                rx.fragment(),
                rx.el.p(hint, class_name="ns-hint"),
            ),
        )
    )
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


def illustration(state) -> rx.Component:
    """Live daily targets card from the user's profile (not a hardcoded sample)."""
    return rx.el.aside(
        rx.el.div(
            rx.el.p("Your targets", class_name="ns-preview-kicker"),
            rx.el.p("Today", class_name="ns-preview-note"),
            class_name="ns-preview-top",
        ),
        rx.el.p(state.calories, class_name="ns-preview-number"),
        rx.el.p("kcal / day", class_name="ns-unit-label"),
        energy_bar(state.protein_width, state.carbs_width, state.fat_width),
        rx.el.div(
            macro_line("Protein", state.protein, state.protein_note, "ns-p"),
            macro_line("Carbohydrates", state.carbs, state.carbs_note, "ns-c"),
            macro_line("Fat", state.fat, state.fat_note, "ns-f"),
            macro_line("Fiber", state.fiber, "Selected", "ns-fiber"),
            class_name="ns-macro-list",
        ),
        class_name="ns-preview",
        aria_label="Your daily calorie and macro targets",
    )


def macro_donut() -> rx.Component:
    """Example calorie-share donut: protein 26%, carbs 44%, fat 30%.

    Segment geometry (dasharray / offset / draw) lives in CSS so motions stay
    consistent and Reflex emotion styles do not fight the chart.
    """
    return rx.el.div(
        rx.el.svg(
            rx.el.circle(cx="50", cy="50", r="36", class_name="ns-donut-track"),
            rx.el.circle(cx="50", cy="50", r="36", class_name="ns-donut-seg ns-donut-p"),
            rx.el.circle(cx="50", cy="50", r="36", class_name="ns-donut-seg ns-donut-c"),
            rx.el.circle(cx="50", cy="50", r="36", class_name="ns-donut-seg ns-donut-f"),
            view_box="0 0 100 100",
            class_name="ns-donut-svg",
            role="img",
            aria_label="Example calorie share: protein 26 percent, carbohydrates 44 percent, fat 30 percent",
        ),
        rx.el.div(
            rx.el.span("kcal", class_name="ns-donut-unit"),
            rx.el.span("share", class_name="ns-donut-label"),
            class_name="ns-donut-center",
            aria_hidden="true",
        ),
        class_name="ns-donut",
    )


def macro_legend_item(name: str, value: str, swatch: str) -> rx.Component:
    return rx.el.li(
        rx.el.span(class_name=f"ns-swatch {swatch}"),
        rx.el.span(name, class_name="ns-pie-name"),
        rx.el.span(value, class_name="ns-pie-value"),
        class_name="ns-pie-item",
    )


def home_splash() -> rx.Component:
    return rx.el.section(
        rx.el.div(
            rx.el.p("NutriSpoke", class_name="ns-kicker ns-splash-brand"),
            rx.el.h1("Macros you can see.", class_name="ns-display"),
            rx.el.p(
                "Protein, carbohydrates, and fat as a share of the day — estimated from a short profile.",
                class_name="ns-lede",
            ),
            rx.el.div(
                go("Get Started", "/onboarding", "primary"),
                class_name="ns-hero-actions",
            ),
            class_name="ns-splash-copy",
        ),
        rx.el.div(
            macro_donut(),
            rx.el.div(
                rx.el.ul(
                    macro_legend_item("Protein", "26%", "ns-p"),
                    macro_legend_item("Carbs", "44%", "ns-c"),
                    macro_legend_item("Fat", "30%", "ns-f"),
                    class_name="ns-pie-legend",
                ),
                rx.el.p(
                    rx.el.span(class_name="ns-swatch ns-fiber"),
                    "Fiber ",
                    rx.el.strong("30\u00a0g"),
                    " · selected target, not a calorie share",
                    class_name="ns-pie-fiber",
                ),
                class_name="ns-pie-side",
            ),
            class_name="ns-splash-visual",
        ),
        class_name="ns-splash",
        aria_label="NutriSpoke macro overview",
    )


def intake_ring(
    label: str,
    swatch: str,
    progress,
    figure,
    left,
) -> rx.Component:
    """Apple Health–style circular progress ring for one macro."""
    return rx.el.article(
        rx.el.div(
            rx.el.svg(
                rx.el.circle(cx="50", cy="50", r="36", class_name="ns-ring-track"),
                rx.el.circle(
                    cx="50",
                    cy="50",
                    r="36",
                    class_name=f"ns-ring-fill {swatch}",
                    style={"--ring-p": progress},
                ),
                view_box="0 0 100 100",
                class_name="ns-ring-svg",
                role="img",
                aria_label=label + " intake versus goal",
            ),
            class_name="ns-ring",
        ),
        rx.el.p(label, class_name="ns-ring-name"),
        rx.el.p(figure, class_name="ns-ring-figure"),
        rx.el.p(left, class_name="ns-ring-left"),
        class_name="ns-ring-card",
    )


def intake_pie(
    label: str,
    swatch: str,
    progress,
    figure,
    left,
) -> rx.Component:
    """Flat dashboard-style donut for one macro (intake vs goal)."""
    return rx.el.article(
        rx.el.div(
            rx.el.svg(
                rx.el.circle(cx="50", cy="50", r="36", class_name="ns-flat-track"),
                rx.el.circle(
                    cx="50",
                    cy="50",
                    r="36",
                    class_name=f"ns-flat-fill {swatch}",
                    style={"--ring-p": progress},
                ),
                rx.el.g(
                    # Arrowhead only, sitting on the ring and pointing clockwise.
                    rx.el.polygon(
                        points="80.2,45.5 91.8,45.5 86,58",
                        class_name=f"ns-flat-tip-head {swatch}",
                    ),
                    class_name="ns-flat-tip",
                    style={"--ring-p": progress},
                ),
                view_box="0 0 100 100",
                class_name="ns-flat-svg",
                role="img",
                aria_label=label + " intake versus goal chart",
            ),
            rx.el.div(
                rx.el.span(figure, class_name="ns-flat-center-figure"),
                class_name="ns-flat-center",
                aria_hidden="true",
            ),
            class_name="ns-flat",
            style={"--ring-p": progress},
        ),
        rx.el.p(label, class_name="ns-flat-name"),
        rx.el.p(left, class_name="ns-flat-left"),
        class_name="ns-flat-card",
    )


def intake_pie_row(state, class_name: str = "ns-intake-grid") -> rx.Component:
    """Four dashboard pies: protein, carbs, fat, fiber."""
    return rx.el.div(
        intake_pie(
            "Protein",
            "ns-p",
            state.protein_progress,
            state.protein_figure,
            state.protein_left,
        ),
        intake_pie(
            "Carbs",
            "ns-c",
            state.carbs_progress,
            state.carbs_figure,
            state.carbs_left,
        ),
        intake_pie(
            "Fat",
            "ns-f",
            state.fat_progress,
            state.fat_figure,
            state.fat_left,
        ),
        intake_pie(
            "Fiber",
            "ns-fiber",
            state.fiber_progress,
            state.fiber_figure,
            state.fiber_left,
        ),
        class_name=class_name,
    )


def intake_vs_goal(state) -> rx.Component:
    """Bottom home section: dashboard pies for intake vs daily goals."""
    return rx.el.section(
        rx.el.div(
            rx.el.p("Today", class_name="ns-kicker"),
            rx.el.h2("Intake vs goal", class_name="ns-intake-title"),
            rx.el.p(
                "Daily targets from your profile; intake from meals you have selected.",
                class_name="ns-lede ns-lede-tight",
            ),
            class_name="ns-intake-intro",
        ),
        intake_pie_row(state),
        class_name="ns-intake ns-intake-bottom",
        aria_label="Macro intake versus daily goals",
    )


def protein_track(
    label: str,
    intake,
    goal,
    left,
    width,
    hint: str,
) -> rx.Component:
    return rx.el.article(
        rx.el.p(label, class_name="ns-protein-label"),
        rx.el.div(
            rx.el.span(intake, class_name="ns-protein-intake"),
            rx.el.span("of ", goal, class_name="ns-protein-goal"),
            class_name="ns-protein-figures",
        ),
        rx.el.div(
            rx.el.div(
                class_name="ns-protein-fill",
                style={"width": width},
            ),
            class_name="ns-protein-bar",
            role="img",
            aria_label=label + " protein progress",
        ),
        rx.el.p(
            rx.el.span("Left ", class_name="ns-protein-left-label"),
            rx.el.span(left, class_name="ns-protein-left-value"),
            class_name="ns-protein-left",
        ),
        rx.el.p(hint, class_name="ns-protein-hint"),
        class_name="ns-protein-card",
    )


def protein_progress(state) -> rx.Component:
    """Today and week protein bars from targets + selected meals."""
    return rx.el.section(
        rx.el.div(
            rx.el.p("Protein", class_name="ns-kicker"),
            rx.el.h2("Intake vs goal", class_name="ns-protein-title"),
            rx.el.p(
                "From your daily target and meals you have selected.",
                class_name="ns-lede ns-lede-tight",
            ),
            class_name="ns-protein-intro",
        ),
        rx.el.div(
            protein_track(
                "Today",
                state.daily_intake,
                state.daily_goal,
                state.daily_left,
                state.daily_width,
                "Daily protein target from your profile.",
            ),
            protein_track(
                "This week",
                state.weekly_intake,
                state.weekly_goal,
                state.weekly_left,
                state.weekly_width,
                "Weekly goal is seven times your daily target.",
            ),
            class_name="ns-protein-grid",
        ),
        class_name="ns-protein",
        aria_label="Protein progress for today and this week",
    )


def process(index: str, title: str, body: str) -> rx.Component:
    return rx.el.li(
        rx.el.span(index, class_name="ns-index"),
        rx.el.h2(title),
        rx.el.p(body),
    )
