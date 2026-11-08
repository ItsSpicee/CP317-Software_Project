"""Live grocery planner smoke test: two Gemini calls and both weekly JSON files.

Run explicitly with: python tests/test_backend_sprint2.py
Reads .env/variables.env and overwrites the saved suggestion and inventory.
"""

import json
import sys
from pathlib import Path
from textwrap import fill, shorten

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))

from Application.grocery_planner import (
    USER_DATA_FOLDER,
    _planning_context,
    generate_weekly_plan,
    record_purchase,
    revise_weekly_plan,
)


def print_summary(context, generated, revised, feedback):
    width = 78
    print("\n" + "=" * width)
    print("NUTRISPOKE - LIVE GROCERY PLANNER TEST: PASS")
    print("=" * width)
    print(f"INPUTS | {context['days']} days | One person")
    print(fill("Allergies: " + (", ".join(context["allergies"]) or "None selected"), width))
    print(fill("Diets: " + (", ".join(context["diet_types"]) or "None selected"), width))
    print(fill("Feedback: " + feedback, width))

    print("\nNUTRITION | Calories in kcal; other values in grams. Outputs are AI estimates.")
    print(f"{'Nutrient':<12}{'Daily target':>15}{'Weekly target':>16}{'Generated':>15}{'Revised':>15}")
    for name, daily in context["daily_targets"].items():
        print(
            f"{name.capitalize():<12}{daily:>15,.1f}"
            f"{context['weekly_targets'][name]:>16,.1f}"
            f"{generated['estimated_weekly_totals'][name]:>15,.1f}"
            f"{revised['estimated_weekly_totals'][name]:>15,.1f}"
        )

    before = {item["name"]: item["quantity_g"] for item in generated["items"]}
    after = {item["name"]: item["quantity_g"] for item in revised["items"]}
    print("\nGROCERY OUTPUTS | Weekly quantities; '-' means absent from that list.")
    print(f"{'Food':<44}{'Generated (g)':>16}{'Revised (g)':>16}")
    for name in dict.fromkeys([*before, *after]):
        old = f"{before[name]:,.0f}" if name in before else "-"
        new = f"{after[name]:,.0f}" if name in after else "-"
        print(f"{shorten(name, width=43, placeholder='...'):<44}{old:>16}{new:>16}")

    print(f"\nGeneration: PASS ({len(generated['items'])} items) | Revision: PASS ({len(revised['items'])} items)")
    print("Purchase recording: PASS - inventory matches the revised suggestion.")
    print("FILES | User Data/weekly_suggestion.json")
    print("        User Data/weekly_grocery_inventory.json")
    print("=" * width)


def main():
    suggestion_path = USER_DATA_FOLDER / "weekly_suggestion.json"
    inventory_path = USER_DATA_FOLDER / "weekly_grocery_inventory.json"
    context = _planning_context()

    print("1/3 Generating a weekly grocery suggestion...", flush=True)
    suggestion = generate_weekly_plan()
    assert json.loads(suggestion_path.read_text(encoding="utf-8")) == suggestion

    unwanted_food = suggestion["items"][0]["name"]
    feedback = f"I don't like {unwanted_food}. Remove it and replace it with other foods to maintain the weekly nutrition targets."
    print(f"2/3 Revising the suggestion to replace {unwanted_food}...", flush=True)
    revised = revise_weekly_plan(feedback)
    assert json.loads(suggestion_path.read_text(encoding="utf-8")) == revised
    assert all(item["name"].casefold() != unwanted_food.casefold() for item in revised["items"])

    print("3/3 Recording the revised suggestion as purchased...", flush=True)
    inventory = record_purchase(revised)
    assert json.loads(inventory_path.read_text(encoding="utf-8")) == inventory == revised

    print_summary(context, suggestion, revised, feedback)


if __name__ == "__main__":
    main()
