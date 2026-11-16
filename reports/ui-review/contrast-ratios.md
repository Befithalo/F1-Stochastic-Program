# Phase 6 contrast audit

Measured with the WCAG relative-luminance contrast formula. The page background is tarmac `#1B1D23`.

## Text colors

| Text color | Ratio on tarmac | Result |
| --- | ---: | --- |
| Chalk `#F2F2F0` | 15.03:1 | Passes 4.5:1 |
| Fog `#A9AEB8` | 7.57:1 | Passes 4.5:1 |
| Better `#4ADE80` | 9.67:1 | Passes 4.5:1 |
| Worse `#FF6B6B` | 6.07:1 | Passes 4.5:1 |
| Caution `#F5C518` | 10.33:1 | Passes 4.5:1 |

On pitlane `#23262E`, chalk is 13.50:1 and fog is 6.80:1.

## Data colors

| Data color | Lowest measured ratio on tarmac | Result |
| --- | ---: | --- |
| FastF1 team colors used by cached 2023–2025 races | 3.18:1 | Passes 3:1 |
| Selected driver, 2023 Aston Martin `#358C75` | 4.14:1 | Passes 3:1 |
| Soft tire `#E8323C` | 3.97:1 | Passes 3:1 |
| Medium tire `#F5C518` | 10.33:1 | Passes 3:1 |
| Hard tire `#F2F2F0` | 15.03:1 | Passes 3:1 |
| Intermediate tire `#43B047` | 6.05:1 | Passes 3:1 |
| Wet tire `#2F7FD6` | 4.11:1 | Passes 3:1 |
| Fastest-lap purple `#A78BFA` | 6.19:1 | Passes 3:1 |

The 2023–2025 team-color minimum is Alfa Romeo's `#C92D4B` at 3.18:1. The selected-driver race trace and recommended stint outline use the original FastF1 team color. Muted race-trace lines composite to 3.29:1. The finish-probability strip's recommended color ramp has a minimum of 3.17:1 across those team colors; the neutral ramp starts at 5.19:1.

The driver chip and Recommended tag mix 40% team color into tarmac and use chalk text. Across the team colors above, that text has a minimum contrast of 5.04:1; their team-colored outlines remain at least 3.18:1.

Fan-chart fills use three team-tinted strengths. After compositing their opacity over tarmac, the lowest ratios across the 2023–2025 team colors are 3.87:1 for the 10th–90th band, 3.56:1 for the 25th–75th band, and 3.51:1 for the 40th–60th band. The chart's band labels use fog at 7.57:1.

Compound letters sit on a dark backing over the tire bars; chalk on tarmac is 15.03:1. The podium-zone and position-range markers use fog at 7.57:1, and the bad-day marker uses worse at 6.07:1.
