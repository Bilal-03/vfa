# Current implementation evidence and review readiness

This is implementation evidence, not certification of faculty approval or publication acceptance. The PDF rubric is used as assessment criteria; it is not authorization to invent results, feedback or contributions.

| Requirement | Current evidence | State |
|---|---|---|
| Completed distinctive module | Three-tab Stock Insight card, shared calculation service, read-only APIs | Implemented |
| Methodology/design | `METHODOLOGY.md`; architecture in `README.md`; fixed `artifacts/configuration.json` | Recorded |
| Technical merit/practical relevance | Holdings-dependent purchase comparison, market-adjusted context, historical money outcomes | Implemented; faculty assessment remains external |
| Validation | Numerical/behavior/API tests, `artifacts/test_results.txt`; chronological study and saved rows | Recorded |
| Both markets | Fixed six-stock coverage; API demonstration checks in `artifacts/demo_api_checks.json` | Demonstrated with dated historical data |
| Portfolio durability | Explicit SQLite mode; save/load/nonmutation checks, local database reopening and atomic validation tests | Verified locally; cloud connectivity currently fails |
| Missing/provider data | Stale/partial/unavailable states; calendar, early-close and missing-window tests | Tested |
| Literature and comparison | `LITERATURE.md` | Working evidence; final citation formatting later |
| Real-event inspection | `REAL_ALERT_INSPECTION.md`; independently checked snapshot returns | Recorded; no causal labels or precision claims |
| Approved modules checklist | Existing calculators, stocks, charts, portfolios, mutual funds, currency, news and glossary retained | Actual approved-module list has not been supplied; do not assert guide approval |
| Review feedback/action log | `FEEDBACK.md` | Awaiting actual guide feedback |
| Individual contribution and AI disclosure | `CONTRIBUTION.md` | Draft factual disclosure; student must verify ownership and understanding |
| Final report and presentation | Current methodology/results/evidence available for reuse | Later deliverables, not completed in this feature implementation |
| Publication submission | No submission performed | No acknowledgement or submission marks claimed |
| Hosted environment | Laptop is primary review target | Hosting not verified |

## Honest demonstration boundaries

Live Indian price inputs in the current provider snapshot end on 9 October 2026. Newer expected sessions produce stale states. Historical-demo mode fixes the cutoff at 9 October 2026 and labels it visibly; it does not relabel historical prices as current. Recorded price inputs can demonstrate the three calculations even if the provider becomes unavailable, while the rest of the application may still require network access. Sector classifications can be Unknown when the profile provider is unavailable.

## Before guide review

Verify the approved module list with the guide, complete the later near-final report/slides, rehearse with a test portfolio, and record actual feedback. Optional usability work must use real participants and appropriate consent; no such study has been conducted. Keep current insight results separate from archived forecasting experiments.

## Recorded verification

- 48 Python tests and 6 Node visual-render tests passed in the latest rerun; see `artifacts/test_results.txt`.
- 18/18 real-price historical-demo API checks passed across all six stocks and three tabs.
- Desktop and 390-pixel mobile flows inspected; changing the mobile amount to USD 5,000 and horizon to six months changed the displayed results.
- Grounded explanations verified through the actual application endpoint for all three tabs.
- Existing three-month charts returned 65 Apple candles and 63 TCS candles; mobile EMI reference produced ₹12,398.57.
- SQLite test holdings survived application restart; calculation left holdings unchanged. Synthetic test records are removed after inspection.

See `artifacts/ui_checks.json`, `artifacts/app_smoke_checks.json`, `artifacts/portfolio_persistence_check.json` and the saved screenshots. These checks do not constitute exhaustive acceptance testing of every existing application module.
