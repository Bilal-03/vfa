# Inspection of recorded historical movement examples

These are analyst inspections of price calculations, not human-participant labels or verified event causes. Select the largest absolute adjusted score among the pre-sampled evaluation dates for each of the six fixed stocks. This deliberately selects informative examples; it cannot estimate detector precision. Most examples do not cross the alert threshold. The dates were not used to change settings.

| Stock / session | Stock return | Market return | Raw robust score | Adjusted robust score | Inspection |
|---|---:|---:|---:|---:|---|
| MSFT / 2025-12-10 | −2.74% | +0.67% | −2.96 | −4.37 | Stock and market moved in opposite directions. The adjusted method flags this case while the raw-return baseline does not. No headline cause was established. |
| SBI / 2026-02-11 | +3.39% | +0.07% | +2.94 | +3.00 | Both scores remain below 3.5. A large positive return alone is not an alert under the fixed threshold. |
| TCS / 2026-02-11 | −2.51% | +0.07% | −2.09 | −2.86 | Stock moved against a slightly positive market, but the residual score still does not cross the threshold. |
| AAPL / 2026-07-15 | +4.01% | +0.38% | +2.60 | +2.53 | Both methods remain below threshold; this example does not establish an anomaly or news effect. |
| Infosys / 2026-05-19 | +4.76% | −0.14% | +2.62 | +2.51 | A sizeable opposing move is not automatically flagged. Historical variability affects the standardized assessment. |
| NVDA / 2025-11-10 | +5.79% | +1.54% | +3.56 | +2.13 | The raw baseline flags the move, while the market-adjusted score does not. This is consistent with part of the movement aligning with broader market exposure; it does not prove a causal explanation. |

Each selected stock and benchmark return was independently recomputed as consecutive adjusted-close ratios from the hashed input snapshots and checked against the saved evaluation row. See `artifacts/inspected_examples.csv`. Historical news attribution was not verified, so none is supplied. Raw and adjusted alerts are screening outputs; neither is a ground-truth annotation.
