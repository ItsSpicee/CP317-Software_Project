# NutriSpoke

NutriSpoke estimates a daily calorie target and displays protein, carbohydrate, fat, and fiber targets. The estimates use the profile and personalization choices saved in `User Data/user_data.json` and `User Data/user_personalization_data.json`.

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
