# baseline vs skill v0.4 vs skill v0.5

| | baseline | skill v0.4 | skill v0.5 |
| --- | --- | --- | --- |
| **Full pass** (visual + all gates) | **0/8** | **0/8** | **5/8** |
| Visual checks pass | 6/8 | 6/8 | 5/8 |
| All quality gates pass | 0/8 | 0/8 | 8/8 |
| Mean global SSIM | 0.9953 | 0.9958 | 0.9965 |
| Mean worst-region SSIM | 0.939 | 0.959 | 0.963 |
| Text on target (≤ 2 px) | 99.5% | 99.6% | 99.6% |
| Real controls (Template-based, enabled) | 19 | 153 | 161 |
| … reachable with Tab, focus visible | 9/19 | 152/153 | 161/161 |
| MouseArea used as a button | 46 | 0 | 0 |
| Lint errors (qmllint) (total) | 150 | 0 | 0 |
| Files not qmlformat-clean (total) | 93 | 0 | 0 |
| Runtime QML warnings (total) | 48 | 0 | 0 |
| Hard-coded colors/fonts outside Theme (total) | 239 | 0 | 0 |
| Accessibility errors (total) | 64 | 1 | 0 |
| Controls without a visible pressed state (total) | 0 | 19 | 0 |
| Strings not wrapped in qsTr() (total) | 142 | 4 | 0 |
| QML files / lines per project | 16 / 1309 | 31 / 2168 | 26 / 2123 |

## Per case

| Case | Global SSIM | Worst region | Text on target | Gate errors | Result |
| --- | --- | --- | --- | --- | --- |
| 01-hmi-dolum | 0.9940 → 0.9948 → 0.9961 | 0.946 → 0.927 → 0.930 | 0.958 → 0.968 → 0.990 | 80 → 1 → 0 | fail → fail → fail |
| 02-kiosk-kafe | 0.9967 → 0.9985 → 0.9984 | 0.947 → 0.992 → 0.992 | 1.000 → 1.000 → 1.000 | 33 → 3 → 0 | fail → fail → pass |
| 03-dashboard-dark | 0.9969 → 0.9964 → 0.9960 | 0.954 → 0.982 → 0.960 | 1.000 → 1.000 → 0.991 | 165 → 2 → 0 | fail → fail → fail |
| 04-dashboard-light | 0.9965 → 0.9875 → 0.9946 | 0.965 → 0.946 → 0.981 | 1.000 → 1.000 → 1.000 | 85 → 4 → 0 | fail → fail → pass |
| 05-settings-form | 0.9975 → 0.9980 → 0.9978 | 0.966 → 0.965 → 0.965 | 1.000 → 1.000 → 1.000 | 113 → 2 → 0 | fail → fail → pass |
| 06-mobile-aliskanlik | 0.9980 → 0.9976 → 0.9971 | 0.990 → 0.984 → 0.987 | 1.000 → 1.000 → 1.000 | 78 → 2 → 0 | fail → fail → pass |
| 07-data-table | 0.9907 → 0.9985 → 0.9983 | 0.784 → 0.889 → 0.923 | 1.000 → 1.000 → 0.991 | 87 → 4 → 0 | fail → fail → fail |
| 08-glass-home | 0.9922 → 0.9953 → 0.9934 | 0.962 → 0.985 → 0.967 | 1.000 → 1.000 → 1.000 | 95 → 6 → 0 | fail → fail → pass |

Per-case columns read baseline → skill v0.4 → skill v0.5.
