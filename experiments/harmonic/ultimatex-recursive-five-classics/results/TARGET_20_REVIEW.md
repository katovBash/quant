# Annual threshold audit

Every one of the 48 timeframe x rule settings was checked. The policy threshold is strictly above 10% on the latest 12 complete months after costs for a liquid stock. User target is strictly above 20%. Late history is seen history.

| Early rank | TF | Rule | Closed trades | Stocks with trades | Liquid stocks >10% | Any stocks >20% |
|---:|---|---|---:|---:|---:|---:|
| 1 | 1H | `union_l0_w8` | 788 | 236 | 0 | 0 |
| 2 | 1H | `union_l0_w5` | 974 | 244 | 0 | 0 |
| 3 | 1H | `bat_l0_w5` | 18 | 17 | 0 | 0 |
| 4 | 1H | `bat_l0_w8` | 21 | 20 | 0 | 0 |
| 5 | 1H | `bat_l1_w5` | 11 | 11 | 0 | 0 |
| 6 | 1H | `bat_l1_w8` | 9 | 9 | 0 | 0 |
| 7 | 1H | `butterfly_l1_w5` | 261 | 159 | 0 | 0 |
| 8 | 1H | `butterfly_l1_w8` | 191 | 126 | 0 | 0 |
| 9 | 1H | `crab_l0_w5` | 64 | 55 | 0 | 0 |
| 10 | 1H | `crab_l0_w8` | 40 | 39 | 0 | 0 |
| 11 | 1H | `crab_l1_w5` | 38 | 37 | 0 | 0 |
| 12 | 1H | `crab_l1_w8` | 29 | 28 | 0 | 0 |
| 13 | 1H | `deepcrab_l0_w5` | 251 | 151 | 0 | 0 |
| 14 | 1H | `deepcrab_l0_w8` | 209 | 144 | 0 | 0 |
| 15 | 1H | `deepcrab_l1_w5` | 137 | 105 | 0 | 0 |
| 16 | 1H | `deepcrab_l1_w8` | 92 | 85 | 0 | 0 |
| 17 | 1H | `gartley_l0_w5` | 141 | 113 | 0 | 0 |
| 18 | 1H | `gartley_l0_w8` | 125 | 102 | 0 | 0 |
| 19 | 1H | `gartley_l1_w5` | 51 | 46 | 0 | 0 |
| 20 | 1H | `gartley_l1_w8` | 26 | 25 | 0 | 0 |
| 21 | 1H | `union_l1_w8` | 327 | 178 | 0 | 0 |
| 22 | 4H | `bat_l0_w5` | 9 | 9 | 0 | 0 |
| 23 | 4H | `bat_l0_w8` | 8 | 8 | 0 | 0 |
| 24 | 4H | `bat_l1_w5` | 5 | 5 | 0 | 0 |
| 25 | 4H | `bat_l1_w8` | 4 | 4 | 0 | 0 |
| 26 | 4H | `butterfly_l0_w5` | 277 | 162 | 0 | 0 |
| 27 | 4H | `butterfly_l0_w8` | 188 | 125 | 0 | 0 |
| 28 | 4H | `butterfly_l1_w5` | 93 | 80 | 0 | 0 |
| 29 | 4H | `butterfly_l1_w8` | 51 | 46 | 0 | 0 |
| 30 | 4H | `crab_l0_w5` | 32 | 32 | 0 | 0 |
| 31 | 4H | `crab_l0_w8` | 32 | 31 | 0 | 0 |
| 32 | 4H | `crab_l1_w5` | 15 | 14 | 0 | 0 |
| 33 | 4H | `crab_l1_w8` | 14 | 14 | 0 | 0 |
| 34 | 4H | `deepcrab_l0_w5` | 132 | 96 | 0 | 0 |
| 35 | 4H | `deepcrab_l0_w8` | 93 | 77 | 0 | 0 |
| 36 | 4H | `deepcrab_l1_w5` | 55 | 53 | 0 | 0 |
| 37 | 4H | `deepcrab_l1_w8` | 31 | 30 | 0 | 0 |
| 38 | 4H | `gartley_l0_w5` | 55 | 48 | 0 | 0 |
| 39 | 4H | `gartley_l0_w8` | 38 | 37 | 0 | 0 |
| 40 | 4H | `gartley_l1_w5` | 19 | 18 | 0 | 0 |
| 41 | 4H | `gartley_l1_w8` | 11 | 11 | 0 | 0 |
| 42 | 4H | `union_l0_w8` | 347 | 176 | 0 | 0 |
| 43 | 4H | `union_l1_w5` | 173 | 130 | 0 | 0 |
| 44 | 4H | `union_l1_w8` | 105 | 86 | 0 | 0 |
| 45 | 1H | `butterfly_l0_w8` | 438 | 203 | 0 | 0 |
| 46 | 1H | `union_l1_w5` | 472 | 209 | 0 | 0 |
| 47 | 4H | `union_l0_w5` | 477 | 201 | 0 | 0 |
| 48 | 1H | `butterfly_l0_w5` | 547 | 218 | 0 | 0 |

Maximum stock-level trailing-12m return over all variants: 11.51% for SVAV, 4H, union_l0_w8, from 1 closed trade(s). The same stock and a second rule are the only two rows above 10%, and neither passes the liquidity gate. No row exceeds 20%.

Inputs: `paper_review.json`, `all_variants.csv`, `monthly_returns.csv`.
