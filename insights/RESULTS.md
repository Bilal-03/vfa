# Stock Insight evaluation

Recorded historical study; no future-price or usability claims.

## Portfolio volatility estimation

| Market | Portfolio | Method | Origins | MAE (percentage points) |
|---|---|---|---:|---:|
| India | after | ledoit_wolf | 11 | 5.162 |
| India | after | sample | 11 | 5.156 |
| India | before | ledoit_wolf | 11 | 7.950 |
| India | before | sample | 11 | 7.898 |
| US | after | ledoit_wolf | 11 | 9.004 |
| US | after | sample | 11 | 9.127 |
| US | before | ledoit_wolf | 11 | 6.585 |
| US | before | sample | 11 | 6.573 |

## Movement interventions

Injected scenarios are controlled sensitivity checks, not ground-truth market event labels. Normal alert rates are descriptive, not false-positive rates.

| Market | Scenario | Cases | Raw alert rate | Adjusted alert rate | Unavailable |
|---|---|---:|---:|---:|---:|
| India | broad_market_shock | 36 | 80.6% | 0.0% | 0 |
| India | missing_stock_price | 36 | withheld | withheld | 36 |
| India | normal | 36 | 0.0% | 0.0% | 0 |
| India | stock_specific_shock | 36 | 94.4% | 97.2% | 0 |
| US | broad_market_shock | 36 | 80.6% | 2.8% | 0 |
| US | missing_stock_price | 36 | withheld | withheld | 36 |
| US | normal | 36 | 8.3% | 2.8% | 0 |
| US | stock_specific_shock | 36 | 86.1% | 94.4% | 0 |

## Limits

Six predefined symbols; five-year provider snapshots. Small numbers of chronological evaluation origins; no significance or general superiority claim. Historical prices may be revised by the provider. Common-date alignment reduces coverage. Headlines are not ground-truth causes. No user study has been performed. See snapshot metadata and the separate manual alert inspection.
