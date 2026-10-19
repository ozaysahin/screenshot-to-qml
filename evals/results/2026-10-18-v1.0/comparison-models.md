# opus vs sonnet vs haiku vs codex run 1 vs codex run 2

| | opus | sonnet | haiku | codex run 1 | codex run 2 |
| --- | --- | --- | --- | --- | --- |
| **Full pass** (visual + all gates) | **2/3** | **2/3** | **0/3** | **1/3** | **1/3** |
| Visual checks pass | 2/3 | 2/3 | 0/3 | 1/3 | 1/3 |
| All quality gates pass | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| Mean global SSIM | 0.9977 | 0.9979 | 0.9890 | 0.9864 | 0.9827 |
| Mean worst-region SSIM | 0.954 | 0.961 | 0.910 | 0.876 | 0.890 |
| Text on target (≤ 2 px) | 98.6% | 98.6% | 91.9% | 91.1% | 90.5% |
| Real controls (Template-based, enabled) | 52 | 52 | 51 | 52 | 52 |
| … reachable with Tab, focus visible | 52/52 | 52/52 | 51/51 | 52/52 | 52/52 |
| MouseArea used as a button | 0 | 0 | 0 | 0 | 0 |
| QML files / lines per project | 27 / 2134 | 31 / 2377 | 25 / 2021 | 11 / 1574 | 8 / 2219 |

## Per case

| Case | Global SSIM | Worst region | Text on target | Gate errors | Result |
| --- | --- | --- | --- | --- | --- |
| 05-settings-form | 0.9977 → 0.9986 → 0.9901 → 0.9915 → 0.9928 | 0.969 → 0.976 → 0.929 → 0.923 → 0.911 | 1.000 → 1.000 → 0.906 → 0.924 → 0.906 | 0 → 0 → 0 → 0 → 0 | pass → pass → fail → fail → fail |
| 12-ev-charger | 0.9977 → 0.9964 → 0.9897 → 0.9713 → 0.9737 | 0.946 → 0.958 → 0.903 → 0.751 → 0.832 | 0.957 → 0.957 → 0.851 → 0.808 → 0.808 | 0 → 0 → 0 → 0 → 0 | fail → fail → fail → fail → fail |
| 18-html-tailwind-billing | 0.9978 → 0.9988 → 0.9872 → 0.9964 → 0.9817 | 0.947 → 0.948 → 0.898 → 0.955 → 0.927 | 1.000 → 1.000 → 1.000 → 1.000 → 1.000 | 0 → 0 → 0 → 0 → 0 | pass → pass → fail → pass → pass |

Per-case columns read opus → sonnet → haiku → codex run 1 → codex run 2.
