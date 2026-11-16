# Phase 6 mockup comparison

Compared the attached mockup with the live Bahrain 2023 replay after lap 15 at 1440 px and 390 px. Both live captures render all four charts; the document width equals the viewport at both sizes.

## Differences from the mockup

1. **Controls:** the live page uses Streamlit's native selectors and slider, so the slider includes its `0.50`, `0.00`, and `1.00` readouts. The mockup uses hand-drawn controls with only the risk labels. On phone, both layouts use two control columns.
2. **Team green:** the mockup uses the illustrative Aston Martin green `#229971`; the live page uses FastF1's 2023 Aston Martin color `#358C75`, as required for team colors.
3. **Decision reasons:** the live page shows the three current model estimates as text and adds the limited-tire-data note. The mockup has small illustrative bars and dots in those blocks.
4. **Options:** the mockup shows a merged “Box in 1 to 5 laps” choice from the earlier optimizer output. The fixed live optimizer instead shows “Wait and decide next lap”, box now on Hards, and box now on Mediums, followed by a disabled “Never stop” row under the two-compound rule. The live option values use 10,000 simulations.
5. **Race visuals:** the mockup contains hand-drawn sample SVGs. The live page uses the requested Altair race trace and stint chart with replay data, team-colored selected driver, nearest-rival labels, compound letters, and the outlined recommended stint.
6. **Uncertainty visuals:** the mockup's fan chart is a placeholder. The live page draws simulated fan bands through lap 57 and adds the probability strip for the current options.
7. **Model report:** the mockup includes stale pre-fix values and a note that they need updating. The live page displays the fixed-engine report: podium Brier 0.047, points Brier 0.144, 83% coverage, 17% team-action agreement, and 3.7 laps of stop-timing error.
8. **Glossary:** the mockup has small explanatory icons; the live page uses a quieter definition list without the icons.

The content uses the requested fonts, sentence case, tabular figures, team and tire colors, whitespace, and section order. No identical stat cards, rounded card grid, chart toolbar, deploy toolbar, or heading anchor icons remain. The only generic Streamlit styling still visible is the native control chrome and its numeric slider readout.

## Captures

- `mockup-1440.png` and `mockup-390.png` are the attached mockup rendered at each viewport.
- `live-1440.png` and `live-390.png` show the running Bahrain replay at each viewport.
- `compare-1440.png` and `compare-390.png` place the mockup on the left and the live page on the right.
- `contrast-ratios.md` records the measured text and data-color contrast ratios.
