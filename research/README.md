> Archived project direction: these forecasting experiments are retained for provenance. The current application contribution and evidence are in [Explainable Stock Insights](../insights/README.md). Do not mix their results or narrative.

# FinAssist research v2

This supersedes the unverified legacy research claims. Nothing in `retired/` is current evidence. Original application changes were retained; heavyweight packages are isolated in `.venv_research`.

## Run

Python 3.11 on this Intel Mac:

```sh
.venv_research/bin/python research/prepare_data.py
.venv_research/bin/python train_benchmark.py --market India --prices research/data --news research/data/India_news.csv
.venv_research/bin/python train_benchmark.py --market US --prices research/data --news research/data/US_news.csv
.venv_research/bin/python -m pytest tests/test_research.py
.venv_research/bin/python app.py
```

Repeat training with `--seed 43` and `--seed 44`. If news cannot be validated or FinBERT downloaded, omit `--news` to produce an explicitly technical-only result. There is no synthetic data fallback. Do not call a single chronological holdout walk-forward validation. Checkpoint files are local artifacts ignored by Git; copy them with the application for the review.

## Evidence and limits

All benchmark metrics come from saved predictions. Models use frozen actual FinBERT probabilities (not embeddings or fine-tuning), a trained BiLSTM and supervised fusion. The gate is not a new invention; the contribution under study is a resource-limited application and controlled freshness/availability comparison. India has sparse six-month coverage. Date-only news becomes eligible strictly after its date. Live forecasts use daily bars and uncalibrated probabilities. No causal explanations or trading-return claims are supported.

No publication has been submitted. Any submission requires a complete manuscript and all authors' approval. Guide feedback, approvals, and contributions must be supplied as real records, not generated historical evidence.

## Local app environment
The research environment has the Flask/market/portfolio packages installed for the local demo. Start with `.venv_research/bin/python app.py` so saved PyTorch models can load; the original `venv` does not have PyTorch. `environment.lock.txt` records the actual installed versions. The six selected symbols are the evaluated universe; other stocks remain available in the general market application but do not receive a research forecast.
