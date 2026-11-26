"""Manual stock management using the central inventory JSON backend."""

import reflex as rx

from . import inventory as stock
from .ui import entry, field, go, menu, page, press

CATEGORY_LABELS = {"meat": "Meat", "dairy": "Dairy", "produce": "Produce", "dry_goods": "Dry goods"}
CATEGORY_ICONS = {"meat": "beef", "dairy": "milk", "produce": "apple", "dry_goods": "package"}


class InventoryState(rx.State):
    rows: list[dict[str, str]] = []
    summary: str = "0 items"
    error: str = ""
    status: str = ""
    selected: str = ""
    category_filter: str = "all"

    @rx.var
    def visible_rows(self) -> list[dict[str, str]]:
        if self.category_filter == "all":
            return self.rows
        label = CATEGORY_LABELS[self.category_filter]
        return [row for row in self.rows if row["category"] == label]

    @rx.var
    def category_icon(self) -> str:
        return CATEGORY_ICONS.get(self.category_filter, "package")

    @rx.var
    def visible_summary(self) -> str:
        if self.category_filter == "all":
            return self.summary
        count = len(self.visible_rows)
        total = sum(float(row["weight_g"]) for row in self.visible_rows)
        return f"{count} {'item' if count == 1 else 'items'} · {total:,.2f} g total"

    @rx.event
    def filter_category(self, category: str):
        self.category_filter = category if category in CATEGORY_LABELS else "all"
        self.selected = ""
        self.error = ""
        self.status = ""

    def _session_id(self) -> str:
        return self.rx_router_session.client_token or ""

    def _apply(self, items: list[dict]):
        self.rows = [
            {"name": item["name"], "quantity": f"{item['quantity_g']:,.6f}".rstrip("0").rstrip(".") + " g",
             "weight_g": str(item["quantity_g"]),
             "category": CATEGORY_LABELS[item["grocery_type"]],
             "icon": CATEGORY_ICONS[item["grocery_type"]]}
            for item in sorted(items, key=lambda row: row["name"].casefold())
        ]
        count = len(items)
        total = sum(item["quantity_g"] for item in items)
        self.summary = f"{count} {'item' if count == 1 else 'items'} · {total:,.2f} g total"
        if not any(item["name"] == self.selected for item in items):
            self.selected = ""

    def _failure(self, exc: Exception):
        self.status = ""
        self.error = str(exc) if isinstance(exc, ValueError) else "Could not save inventory. Try again."

    @rx.event
    def load_inventory(self):
        self.error = ""
        self.status = ""
        try:
            self._apply(stock.get_inventory(session_id=self._session_id()))
        except (ValueError, OSError) as exc:
            self.rows = []
            self.selected = ""
            self.summary = "Inventory unavailable"
            self._failure(exc)

    @rx.event
    def add_item(self, form_data: dict):
        self.error = ""
        try:
            category = form_data.get("grocery_type", "")
            category = next((key for key, label in CATEGORY_LABELS.items() if label == category), category)
            self._apply(stock.add(form_data.get("item", ""), form_data.get("amount", ""),
                                  category, session_id=self._session_id()))
            self.status = "Item added to inventory."
        except (ValueError, OSError) as exc:
            self._failure(exc)

    @rx.event
    def select_item(self, name: str):
        self.selected = name
        self.error = ""
        self.status = ""

    @rx.event
    def adjust_item(self, form_data: dict):
        self.error = ""
        try:
            self._apply(stock.modify(self.selected, form_data.get("change", ""), session_id=self._session_id()))
            self.status = "Inventory weight updated."
        except (ValueError, OSError) as exc:
            self._failure(exc)

    @rx.event
    def remove_entry(self, name: str):
        self.error = ""
        try:
            self._apply(stock.delete(name, session_id=self._session_id()))
            self.status = f"Removed {name} from inventory."
        except (ValueError, OSError) as exc:
            self._failure(exc)

    @rx.event
    def remove_amount(self, form_data: dict):
        self.error = ""
        try:
            self._apply(stock.remove(self.selected, form_data.get("amount", ""), session_id=self._session_id()))
            self.status = "Removed the specified weight from inventory."
        except (ValueError, OSError) as exc:
            self._failure(exc)


def inventory_row(item) -> rx.Component:
    return rx.el.li(
        rx.el.div(
            rx.icon(item["icon"], size=22, class_name="ns-inventory-icon"),
            rx.el.div(rx.el.h3(item["name"], class_name="ns-grocery-name"), rx.el.p(item["category"], class_name="ns-hint")),
            class_name="ns-inventory-item-name",
        ),
        rx.el.div(
            rx.el.span(item["quantity"], class_name="ns-grocery-qty"),
            rx.el.div(
                press("Adjust", "secondary", type="button", on_click=InventoryState.select_item(item["name"])),
                press("Remove", "ghost", type="button", on_click=InventoryState.remove_entry(item["name"]), aria_label="Remove " + item["name"] + " from inventory"),
                class_name="ns-inventory-row-buttons",
            ),
            class_name="ns-inventory-item-actions",
        ), class_name="ns-inventory-row",
    )


def inventory_page() -> rx.Component:
    return page(
        rx.el.div(
            rx.el.p("What you have", class_name="ns-kicker"),
            rx.el.div(
                rx.el.h1("Inventory", class_name="ns-title"),
                rx.el.div(
                    go("Overview", "/overview"),
                    press("Refresh", "secondary", type="button", on_click=InventoryState.load_inventory),
                    class_name="ns-actions-group",
                ),
                class_name="ns-title-row",
            ),
            rx.el.p("Keep track of the food you have on hand. All weights are in grams.", class_name="ns-lede"),
            rx.cond(InventoryState.error != "", rx.el.p(InventoryState.error, role="alert", class_name="ns-error")),
            rx.cond(InventoryState.status != "", rx.el.p(InventoryState.status, role="status", class_name="ns-status")),
            rx.el.div(
                rx.el.section(
                    rx.el.div(rx.icon("package-plus", size=21), rx.el.h2("Add an item", class_name="ns-card-title"), class_name="ns-inventory-heading"),
                    rx.form(
                        field("Item name", entry(name="item", id="inventory-name", placeholder="e.g. Brown rice", required=True), for_id="inventory-name"),
                        field("Weight (g)", entry(name="amount", id="inventory-amount", type="number", min=1, step="any", placeholder="500", required=True), for_id="inventory-amount"),
                        field("Category", menu(list(CATEGORY_LABELS.values()), name="grocery_type", default_value="Produce")),
                        press("Add to inventory", type="submit"),
                        on_submit=InventoryState.add_item, class_name="ns-stack",
                    ), class_name="ns-overview-card",
                ),
                rx.el.section(
                    rx.el.div(
                        *[
                            rx.el.button(
                                label,
                                type="button",
                                aria_pressed=InventoryState.category_filter == key,
                                on_click=InventoryState.filter_category(key),
                                class_name=rx.cond(
                                    InventoryState.category_filter == key,
                                    "ns-filter-button is-active",
                                    "ns-filter-button",
                                ),
                            )
                            for key, label in [("all", "All"), *CATEGORY_LABELS.items()]
                        ],
                        class_name="ns-filter-group ns-inventory-filters",
                        role="group",
                        aria_label="Filter inventory by grocery type",
                    ),
                    rx.el.div(rx.icon(InventoryState.category_icon, size=21), rx.el.h2("On hand", class_name="ns-card-title"), class_name="ns-inventory-heading"),
                    rx.el.p(InventoryState.visible_summary, class_name="ns-meta ns-inventory-summary"),
                    rx.cond(
                        InventoryState.visible_rows.length() > 0,
                        rx.el.ul(rx.foreach(InventoryState.visible_rows, inventory_row), class_name="ns-inventory-list"),
                        rx.el.div(
                            rx.icon("package-open", size=36),
                            rx.el.p(rx.cond(InventoryState.rows.length() > 0, "No items in this category.", "Your inventory is empty."), class_name="ns-overview-copy"),
                            rx.el.p(rx.cond(InventoryState.rows.length() > 0, "Choose another category or add an item.", "Add your first item to get started."), class_name="ns-hint"),
                            class_name="ns-inventory-empty",
                        ),
                    ), class_name="ns-overview-card",
                ), class_name="ns-inventory-grid",
            ),
            rx.cond(
                InventoryState.selected != "",
                rx.el.section(
                    rx.el.div(rx.icon("scale", size=21), rx.el.h2("Adjust " + InventoryState.selected, class_name="ns-card-title"), class_name="ns-inventory-heading"),
                    rx.el.div(
                        rx.form(
                            field("Change (g)", entry(name="change", id="inventory-change", type="number", step="any", placeholder="e.g. +100 or -50", required=True), "Add or subtract grams. At least 1 g must remain.", for_id="inventory-change"),
                            press("Apply change", "secondary", type="submit"),
                            on_submit=InventoryState.adjust_item, class_name="ns-stack",
                        ),
                        rx.form(
                            field("Remove weight (g)", entry(name="amount", id="inventory-remove", type="number", min=0, step="any", placeholder="Weight to remove", required=True), "Remove the full weight to delete the item.", for_id="inventory-remove"),
                            press("Remove weight", "secondary", type="submit"),
                            on_submit=InventoryState.remove_amount, class_name="ns-stack",
                        ), class_name="ns-row",
                    ), class_name="ns-overview-card ns-inventory-adjust",
                ),
            ),
        ), current="inventory",
    )
