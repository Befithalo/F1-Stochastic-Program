# UI v2 contrast audit

Measured with the WCAG relative-luminance formula (`f1si.ui_theme.contrast_ratio`) on the colors the page renders, across every FastF1 team color for 2023 to 2025. Text needs 4.5:1; chart marks need 3:1. Tarmac is `#1B1D23`; the decision band is the team color mixed 22% into tarmac.

| Kind | Color pair | Ratio | Needs | Result |
| --- | --- | ---: | ---: | --- |
| Text | Chalk #F2F2F0 on tarmac | 15.03:1 | 4.5:1 | Pass |
| Text | Fog #A9AEB8 on tarmac | 7.57:1 | 4.5:1 | Pass |
| Text | Soft text #DADDE2 on tarmac | 12.37:1 | 4.5:1 | Pass |
| Text | Worse #FF6B6B on tarmac | 6.07:1 | 4.5:1 | Pass |
| Text | Better #4ADE80 on tarmac | 9.67:1 | 4.5:1 | Pass |
| Text | Caution #F5C518 on tarmac | 10.33:1 | 4.5:1 | Pass |
| Text | Band grey (fog lightened per team) on decision band, lowest team | 4.60:1 | 4.5:1 | Pass |
| Text | Chalk on decision band, lowest team (2024 Mercedes) | 8.56:1 | 4.5:1 | Pass |
| Text | Soft text on decision band, lowest team (2024 Mercedes) | 7.05:1 | 4.5:1 | Pass |
| Text | White on team fill (driver code, Recommended tag), lowest team (2023 Mercedes) | 4.66:1 | 4.5:1 | Pass |
| Mark | Team line on tarmac (gap trace, plan outline, strips), lowest team (2023 Alfa Romeo) | 3.18:1 | 3:1 | Pass |
| Mark | Team bars on decision band (histogram), lowest team (2023 Alfa Romeo) | 3.05:1 | 3:1 | Pass |
| Mark | Grey bars on decision band (histogram P11 to P20), lowest team (2024 Mercedes) | 3.15:1 | 3:1 | Pass |
| Mark | Fan bands and probability-strip cells, weakest shade, lowest team (2023 Ferrari) | 3.02:1 | 3:1 | Pass |
| Mark | Other cars' gap lines #6B7180 | 3.45:1 | 3:1 | Pass |
| Mark | Starting-grid bar and empty-dot outline #6B7180 | 3.45:1 | 3:1 | Pass |
| Mark | Median line chalk on tarmac | 15.03:1 | 3:1 | Pass |
| Mark | Soft tyre #E8323C on tarmac | 3.97:1 | 3:1 | Pass |
| Mark | Medium tyre #F5C518 on tarmac | 10.33:1 | 3:1 | Pass |
| Mark | Hard tyre #F2F2F0 on tarmac | 15.03:1 | 3:1 | Pass |
| Mark | Intermediate tyre #43B047 on tarmac | 6.05:1 | 3:1 | Pass |
| Mark | Wet tyre #2F7FD6 on tarmac | 4.11:1 | 3:1 | Pass |
| Mark | Tyre colors in the race strip on the decision band, lightened per team (raw lowest 2.26:1, Soft) | 3.01:1 | 3:1 | Pass |

Light team colors are lightened toward chalk for lines and bars (`readable_on`) and darkened toward black behind white text (`team_fill`) until they pass; the raw FastF1 color stays for the band's top rule and the recommended row's border, which carry no text or data.

Plain fog measured 4.31:1 on the 2024 Mercedes band, so text inside the band uses `--band-fog`: fog lightened toward chalk until it reaches 4.5:1 on that team's band.

Background tracks (`kerb` `#30343E`) are surfaces, not data marks, and are not held to 3:1.
