# EMA source and length comparison

For the fixed ZigZag + SMA20 entry, both EMA contact windows are shown. Each cell is `early rank / liquid stocks >10% / liquid stocks >20%`. Same = EMA on the signal timeframe; day = prior completed day; week = prior completed week. Lower early rank is earlier selection. The later history was already used in the policy screen.

| Signal TF | EMA source | EMA length | Same-bar contact | Current or prior five bars |
|---|---|---:|---:|---:|
| 1H | same | 9 | 35 / 7 / 3 | 16 / 10 / 3 |
| 1H | same | 20 | 49 / 5 / 1 | 28 / 7 / 2 |
| 1H | same | 50 | 63 / 3 / 1 | 39 / 10 / 4 |
| 1H | same | 100 | 72 / 1 / 0 | 47 / 7 / 2 |
| 1H | day | 9 | 89 / 0 / 0 | 57 / 1 / 0 |
| 1H | day | 20 | 100 / 1 / 0 | 69 / 1 / 0 |
| 1H | day | 50 | 92 / 0 / 0 | 80 / 0 / 0 |
| 1H | day | 100 | 106 / 0 / 0 | 82 / 0 / 0 |
| 1H | week | 9 | 118 / 0 / 0 | 81 / 0 / 0 |
| 1H | week | 20 | 109 / 0 / 0 | 98 / 0 / 0 |
| 1H | week | 50 | 110 / 0 / 0 | 119 / 0 / 0 |
| 1H | week | 100 | 107 / 0 / 0 | 108 / 0 / 0 |
| 4H | same | 9 | 33 / 7 / 1 | 3 / 8 / 3 |
| 4H | same | 20 | 46 / 2 / 2 | 2 / 6 / 3 |
| 4H | same | 50 | 62 / 2 / 0 | 37 / 7 / 0 |
| 4H | same | 100 | 79 / 2 / 0 | 52 / 3 / 1 |
| 4H | day | 9 | 61 / 3 / 0 | 36 / 4 / 0 |
| 4H | day | 20 | 70 / 0 / 0 | 53 / 1 / 0 |
| 4H | day | 50 | 84 / 1 / 0 | 65 / 1 / 0 |
| 4H | day | 100 | 99 / 0 / 0 | 76 / 1 / 0 |
| 4H | week | 9 | 123 / 1 / 0 | 75 / 0 / 0 |
| 4H | week | 20 | 116 / 0 / 0 | 87 / 0 / 0 |
| 4H | week | 50 | 117 / 0 / 0 | 95 / 0 / 0 |
| 4H | week | 100 | 114 / 0 / 0 | 115 / 0 / 0 |

All raw-ZigZag combinations and EMA-only controls are included in [the complete annual audit](TARGET_20_REVIEW.md).
