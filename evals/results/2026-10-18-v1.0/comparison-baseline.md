# baseline vs skill v1.0

| | baseline | skill v1.0 |
| --- | --- | --- |
| **Full pass** (visual + all gates) | **0/8** | **4/8** |
| Visual checks pass | 6/8 | 4/8 |
| All quality gates pass | 0/8 | 7/8 |
| Mean global SSIM | 0.9953 | 0.9951 |
| Mean worst-region SSIM | 0.939 | 0.947 |
| Text on target (≤ 2 px) | 99.5% | 99.7% |
| Real controls (Template-based, enabled) | 19 | 153 |
| … reachable with Tab, focus visible | 9/19 | 153/153 |
| MouseArea used as a button | 46 | 0 |
| Lint errors (qmllint) (total) | 166 | 7 |
| Files not qmlformat-clean (total) | 93 | 0 |
| Runtime QML warnings (total) | 48 | 0 |
| Hard-coded colors/fonts outside Theme (total) | 239 | 0 |
| Accessibility errors (total) | 64 | 0 |
| Strings not wrapped in qsTr() (total) | 142 | 0 |
| QML files / lines per project | 16 / 1309 | 31 / 2510 |

## Per case

| Case | Global SSIM | Worst region | Text on target | Gate errors | Result |
| --- | --- | --- | --- | --- | --- |
| 01-hmi-dolum | 0.9940 → 0.9972 | 0.946 → 0.878 | 0.958 → 1.000 | 80 → 0 | fail → fail |
| 02-kiosk-kafe | 0.9967 → 0.9982 | 0.947 → 0.990 | 1.000 → 0.974 | 33 → 0 | fail → fail |
| 03-dashboard-dark | 0.9969 → 0.9971 | 0.954 → 0.976 | 1.000 → 1.000 | 166 → 0 | fail → pass |
| 04-dashboard-light | 0.9965 → 0.9873 | 0.965 → 0.968 | 1.000 → 1.000 | 87 → 0 | fail → pass |
| 05-settings-form | 0.9975 → 0.9977 | 0.966 → 0.969 | 1.000 → 1.000 | 113 → 0 | fail → pass |
| 06-mobile-aliskanlik | 0.9980 → 0.9975 | 0.990 → 0.989 | 1.000 → 1.000 | 84 → 0 | fail → pass |
| 07-data-table | 0.9907 → 0.9922 | 0.784 → 0.859 | 1.000 → 1.000 | 89 → 0 | fail → fail |
| 08-glass-home | 0.9922 → 0.9934 | 0.962 → 0.945 | 1.000 → 1.000 | 100 → 7 | fail → fail |

Per-case columns read baseline → skill v1.0.
