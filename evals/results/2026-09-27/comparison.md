# baseline vs skill v0.4

| | baseline | skill v0.4 |
| --- | --- | --- |
| Full pass (visual + quality gates) | 0/8 | 6/8 |
| Visual checks pass | 6/8 | 6/8 |
| Quality gates pass | 0/8 | 8/8 |
| Mean global SSIM | 0.9953 | 0.9958 |
| Mean worst-region SSIM | 0.939 | 0.959 |
| Text on target (≤ 2 px) | 99.5% | 99.6% |
| Lint errors (qmllint) (total) | 150 | 0 |
| Files not qmlformat-clean (total) | 93 | 0 |
| Runtime QML warnings (total) | 48 | 0 |
| Hard-coded colors/fonts outside Theme (total) | 239 | 0 |
| QML files / lines per project | 16 / 1309 | 31 / 2168 |

## Per case

| Case | Global SSIM (baseline → skill v0.4) | Worst region | Text on target | Gate errors | Result |
| --- | --- | --- | --- | --- | --- |
| 01-hmi-dolum | 0.9940 → 0.9948 | 0.946 → 0.927 | 0.958 → 0.968 | 65 → 0 | fail → fail |
| 02-kiosk-kafe | 0.9967 → 0.9985 | 0.947 → 0.992 | 1.000 → 1.000 | 24 → 0 | fail → pass |
| 03-dashboard-dark | 0.9969 → 0.9964 | 0.954 → 0.982 | 1.000 → 1.000 | 131 → 0 | fail → pass |
| 04-dashboard-light | 0.9965 → 0.9875 | 0.965 → 0.946 | 1.000 → 1.000 | 61 → 0 | fail → pass |
| 05-settings-form | 0.9975 → 0.9980 | 0.966 → 0.965 | 1.000 → 1.000 | 62 → 0 | fail → pass |
| 06-mobile-aliskanlik | 0.9980 → 0.9976 | 0.990 → 0.984 | 1.000 → 1.000 | 51 → 0 | fail → pass |
| 07-data-table | 0.9907 → 0.9985 | 0.784 → 0.889 | 1.000 → 1.000 | 64 → 0 | fail → fail |
| 08-glass-home | 0.9922 → 0.9953 | 0.962 → 0.985 | 1.000 → 1.000 | 72 → 0 | fail → pass |
