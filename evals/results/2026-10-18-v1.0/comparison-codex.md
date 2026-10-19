# opus vs sonnet vs codex run 1 vs codex run 2

| | opus | sonnet | codex run 1 | codex run 2 |
| --- | --- | --- | --- | --- |
| **Full pass** (visual + all gates) | **3/4** | **2/4** | **1/4** | **1/4** |
| Visual checks pass | 3/4 | 2/4 | 1/4 | 1/4 |
| All quality gates pass | 4/4 | 4/4 | 4/4 | 4/4 |
| Mean global SSIM | 0.9954 | 0.9948 | 0.9828 | 0.9798 |
| Mean worst-region SSIM | 0.954 | 0.954 | 0.881 | 0.888 |
| Text on target (≤ 2 px) | 98.9% | 97.4% | 90.8% | 89.7% |
| Real controls (Template-based, enabled) | 65 | 64 | 65 | 65 |
| … reachable with Tab, focus visible | 65/65 | 64/64 | 65/65 | 65/65 |
| MouseArea used as a button | 0 | 0 | 0 | 0 |
| QML files / lines per project | 26 / 2200 | 29 / 2392 | 11 / 1505 | 9 / 1985 |

## Per case

| Case | Global SSIM | Worst region | Text on target | Gate errors | Result |
| --- | --- | --- | --- | --- | --- |
| 05-settings-form | 0.9977 → 0.9986 → 0.9915 → 0.9928 | 0.969 → 0.976 → 0.923 → 0.911 | 1.000 → 1.000 → 0.924 → 0.906 | 0 → 0 → 0 → 0 | pass → pass → fail → fail |
| 09-dashboard-sales | 0.9884 → 0.9855 → 0.9719 → 0.9711 | 0.955 → 0.936 → 0.894 → 0.880 | 1.000 → 0.937 → 0.898 → 0.874 | 0 → 0 → 0 → 0 | pass → fail → fail → fail |
| 12-ev-charger | 0.9977 → 0.9964 → 0.9713 → 0.9737 | 0.946 → 0.958 → 0.751 → 0.832 | 0.957 → 0.957 → 0.808 → 0.808 | 0 → 0 → 0 → 0 | fail → fail → fail → fail |
| 18-html-tailwind-billing | 0.9978 → 0.9988 → 0.9964 → 0.9817 | 0.947 → 0.948 → 0.955 → 0.927 | 1.000 → 1.000 → 1.000 → 1.000 | 0 → 0 → 0 → 0 | pass → pass → pass → pass |

Per-case columns read opus → sonnet → codex run 1 → codex run 2.
