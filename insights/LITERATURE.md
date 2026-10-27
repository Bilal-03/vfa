# Literature and competitor comparison

| Reference | Existing capability / method | FinAssist adaptation and boundary |
|---|---|---|
| Ledoit & Wolf, *A Well-Conditioned Estimator for Large-Dimensional Covariance Matrices*, 2004; [implementation and original reference](https://scikit-learn.org/stable/modules/generated/sklearn.covariance.LedoitWolf.html) | Covariance shrinkage for portfolio estimation | Use an established estimator for an explainable proposed-purchase comparison; compare it with sample covariance. No new covariance algorithm claim. |
| [NIST handbook: outlier detection](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h.htm) | Median/MAD-based modified scores and outlier screening | Apply robust screening to one-step market-regression residuals with strictly preceding reference history. A statistical flag is not proof of a news-driven event. |
| [FinReport, 2024](https://arxiv.org/abs/2403.02647) | Financial reporting incorporating news analysis, earnings forecasting and risk assessment | FinAssist focuses on deterministic contextual stock explanations and purchase impact, rather than news-based forecasts. |
| [Tickertape Scorecard](https://www.tickertape.in/blog/introducing-scorecard-stock-analysis-got-quicker-and-better-with-quantitative-insights/) | Quantitative stock parameter scores and red flags | A generic score alone would be a weak project distinction. FinAssist shows computed before/after values and historical investment outcomes without a composite rating. |
| [Zerodha Stock Insights](https://support.zerodha.com/category/console/portfolio/holdings/articles/stock-insights) | Fundamentals and peer comparison through Tijori | FinAssist integrates holdings-dependent purchase impact, market context and money-denominated historical experience into its existing stock page. It does not claim competitors lack all related capabilities. |

## Defensible contribution

An implemented, lightweight decision-support workflow combines three linked views and traceable explanations, with explicit missing-data states and a reproducible comparative study on Indian and US stocks. The adaptation and evaluation are the project contribution. Component methods are established; neither global product uniqueness nor publication acceptance is established. The bibliography should be formatted to the institution's required style when the final report is produced.
