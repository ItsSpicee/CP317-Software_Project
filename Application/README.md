# NutriSpoke

NutriSpoke estimates a daily calorie target and displays protein, carbohydrate, fat, and fiber targets. The estimates use the profile and personalization choices saved in `User Data/user_data.json` and `User Data/user_personalization_data.json`.

The reusable backend is `Application/get_targets.py`, independent of Reflex:

```python
from Application.get_targets import get_targets

targets = get_targets()  # Load the two saved user-data files.
# Or calculate from dictionaries already loaded by another backend:
targets = get_targets(user_data=profile, personalization=preferences)
```

The result contains unrounded daily `calories`, `protein`, `carbs`, `fat`, and `fiber`, plus `has_manual_target` and `goal_description`. Calories are in kcal; macros and fiber are in grams. The targets page handles display formatting. The preferences page restores saved allergy and diet selections when revisited.

The groceries page at `/groceries` calls `generate_weekly_plan`, `revise_weekly_plan`, and `record_purchase`. It loads any saved `weekly_suggestion.json` on open, shows weekly totals and items, accepts revision feedback, and can save the current suggestion as inventory.

## Basic grocery planner

`Application/grocery_planner.py` uses Google's `google-genai` SDK (`from google import genai`). Install the dependencies from `requirements.txt`, then add your API key and model name to `.env/variables.env`:

```dotenv
GEMINI_API_KEY=your-api-key
GEMINI_MODEL=gemini-3.6-flash
```

The `.env/` folder is ignored by Git. `.env.example` documents the settings for other checkouts. The planner loads `.env/variables.env` automatically on each AI request using `python-dotenv`. Existing process environment variables take precedence. Both settings must be nonempty.

```python
from Application.grocery_planner import (
    generate_weekly_plan,
    revise_weekly_plan,
    record_purchase,
)

suggestion = generate_weekly_plan()
suggestion = revise_weekly_plan("I don't like bananas. Replace them.")
record_purchase(suggestion)
```

Generation reads the existing profile and preferences, multiplies daily calories, macros, and fiber by seven, and sends those targets, allergies, and diets to Gemini. The returned dictionary is saved to `User Data/weekly_suggestion.json`. Revision sends the saved suggestion and feedback with the current targets and restrictions, then overwrites the same file on success. `record_purchase(suggestion)` saves the supplied dictionary to `User Data/weekly_grocery_inventory.json`, replacing the previous inventory snapshot. It does not merge stock or track consumption.

Each saved suggestion contains only `items`, `estimated_weekly_totals`, and `notes`. Targets, allergies, and diets are loaded from the user data files for each AI request and are not duplicated in the suggestion. Each item has `name`, `grocery_type`, `quantity_g`, `preparation`, and estimated calories, protein, carbs, fat, and fiber for the entire weekly quantity. The model assigns `grocery_type` as exactly one of `meat`, `dairy`, `produce`, or `dry_goods`; the schema and backend validation require a valid category for every item. Regenerate older saved plans that lack this field. Totals are summed in Python. All three functions return the dictionary they save. API keys and model names are read from configuration rather than passed into the functions.

This basic version checks JSON structure and numeric values; nutrition accuracy and dietary suitability depend on the AI response. It does not independently verify allergens, diet compatibility, or target adherence. Invalid responses and API failures leave the previous suggestion in place. Missing or malformed saved input raises an error rather than silently discarding restrictions.

Run `python tests/test_backend_sprint2.py` for a live smoke test of all three planner functions. It uses the key and model in `.env/variables.env`, makes two Gemini requests, checks that revision replaces a selected food, and overwrites both weekly JSON files. The final summary shows input targets and restrictions, feedback, generated and revised nutrition totals and grocery quantities, and the save results. Importing the test file does not make API requests.

## Assumptions used for targets

### Calorie estimate

- The app estimates basal metabolic rate with the Mifflin–St Jeor equation:
  - Male adjustment: `+5`
  - Female adjustment: `-161`
  - Other, missing, or unrecognized sex: `-78`
- Estimated maintenance calories equal basal metabolic rate multiplied by an activity factor:

  | Activity level | Factor |
  | --- | ---: |
  | None | 1.20 |
  | Low | 1.375 |
  | Medium | 1.55 |
  | High | 1.725 |
  | Extreme | 1.90 |

- The activity selector defaults to **Low**. If an activity value is missing or unrecognized in saved data, the calculation also uses Low.
- Missing or out-of-range weight and height use hard-coded average adult values. Male defaults are 199 lb and 68.9 in; female defaults are 171.8 lb and 63.5 in. If sex is missing or unrecognized, the app uses the mean of those values: about 84.1 kg and 168.1 cm.
- Missing or invalid age defaults to 40 years.
- Profile measurements are stored in metric units. Height is accepted from 90 to 250 cm, weight from 30 to 300 kg, and age from 13 to 120 years. Values outside those bounds are ignored by the calculation and replaced with defaults.
- If the profile cannot be read as a JSON object, the app uses the defaults above.

### Manual calorie target

- A user-entered calorie target from 0 through 10,000 is accepted, inclusive.
- A valid manual target replaces the estimated calorie target. It also takes precedence over the Weight Gain and Weight Loss calorie adjustments.
- A blank, invalid, or out-of-range manual target is ignored and the app uses the estimated target instead.
- When a manual target is used with Main Gain, the calories stay as entered while the modest protein-share adjustment still applies.

### Macro targets

Baseline macro grams are calculated from the calorie target:

- Protein aims for 1.0 g per kg of body weight, capped so protein supplies no more than 25% of target calories.
- Fat supplies 30% of target calories.
- Carbohydrates use the calories remaining after protein and fat.
- Calories per gram are treated as 4 for protein, 4 for carbohydrates, and 9 for fat. The targets are rounded to whole grams for display.

If a priority macro is selected, the app shifts up to 10% of total calories toward that macro, taking the energy proportionally from the other two macros. Maximum energy shares are 40% for protein, 60% for carbohydrates, and 35% for fat. The shift may be smaller if a cap is reached or there is not enough energy in the other macros. A blank or unrecognized priority leaves the baseline distribution unchanged.

### Current goals

- **Weight Gain:** adds 200 calories to estimated maintenance. Macro gram amounts are scaled proportionally from the maintenance distribution, preserving its macro proportions.
- **Weight Loss:** subtracts 200 calories from estimated maintenance, with a floor of zero. Macro gram amounts are scaled proportionally from the maintenance distribution, preserving its macro proportions.
- **Main Gain:** keeps calories at maintenance and shifts up to 5% of total calories toward protein, taken proportionally from carbohydrates and fat. Protein is capped at 40% of calories. The increase can be smaller if that cap is reached.
- A selected priority macro is applied to the maintenance distribution before Weight Gain or Weight Loss scales it. For Main Gain, the additional protein shift is applied after the priority adjustment.
- If a manual calorie target is present, Weight Gain and Weight Loss do not add or subtract 200 calories. Main Gain can still adjust the protein share.
- Micronutrient targets and the previous unsupported goal options are not calculated.

### Fiber target

- Fiber is a user-selected target, not calculated from calories or body measurements.
- The slider accepts 0 to 100 g, defaults to 30 g when no saved value exists, and displays the saved value on the targets page.

## Input limits

The browser fields provide numeric limits, and the server checks submitted values as well:

| Input | Accepted calculation range |
| --- | ---: |
| Height | 90–250 cm after unit conversion |
| Weight | 30–300 kg after unit conversion |
| Age | 13–120 years |
| Manual calories | 0–10,000 kcal/day |
| Fiber | 0–100 g/day |

The height and weight fields accept either metric or imperial units and are converted before the metric limits are applied.

## Important context

These are simple estimates based on fixed equations, average defaults, and user-selected settings. They do not account for individual medical conditions, pregnancy, body composition, or other factors that can affect nutrition needs. The project does not currently calculate micronutrient recommendations.
