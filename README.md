# FinAssist

FinAssist is a Flask application for financial education, Indian and US market information, portfolio tracking, calculators, and explainable stock insights.

- Live application: https://vfa-9tbs.onrender.com
- Source: https://github.com/Bilal-03/vfa
- Current contribution: [Explainable Stock Insights](insights/README.md)
- Archived experiments and limitations: [Research](research/README.md)

## Run locally

Use Python 3.11.18 and install the locked CPU runtime:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
PORTFOLIO_STORAGE=sqlite PORT=5003 .venv/bin/python app.py
```

Open http://127.0.0.1:5003. SQLite is an explicit local option and stores private holdings in ignored `instance/portfolio.sqlite3`. Production uses Supabase; there is no automatic storage failover or migration. To use cloud portfolios locally, set `PORTFOLIO_STORAGE=supabase` and supply `SUPABASE_URL` and `SUPABASE_KEY` privately.

The desktop and mobile layouts support stock search, market information, news, portfolios, EMI/SIP/FD/Zakat calculators, and chat. The Stock Information card provides Portfolio Fit, Unusual Movement, and Historical Experience. Insights use completed exchange sessions, identify their analysis date, and explicitly label missing, delayed, or unavailable data. They do not predict future prices or recommend trades. Groq chat requires `GROQ_API_KEY`; deterministic insight explanations do not.

Use `/?view=desktop` or `/?view=mobile` to preview a layout. Leave `STOCK_INSIGHTS_AS_OF` and `STOCK_INSIGHTS_SNAPSHOT_DIR` empty for current provider data. Historical replay is an optional, explicitly labelled local demonstration described in the insights documentation.

## Verify

```sh
.venv/bin/python -m pip install pytest==9.1.1
.venv/bin/python -m pytest tests/test_insights.py tests/test_stock_news.py tests/test_release.py -q
node --test tests/test_insight_visuals.cjs
```

Archived research tests use a separate environment with `requirements-research.txt`. The hosted application does not install PyTorch or Transformers, download FinBERT, train models, or ship private checkpoints. Archived forecast endpoints return an explicit unavailable status when checkpoints are absent. Withdrawn academic downloads remain HTTP 410.

## Deployment

The existing Render service **finassist** in Oregon deploys automatically from GitHub `main`. Keep the existing service and URL; `render.yaml` documents its configuration and must not be used to create a duplicate. Settings changes on this existing service must also be applied in Render.

- Python: 3.11.18; build: `pip install -r requirements.txt`
- Start: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120`
- HTTP health check: `/health`
- Production configuration: `FLASK_ENV=production`, `PORTFOLIO_STORAGE=supabase`, `SKIP_NSE=true`
- Required private settings: `FLASK_SECRET_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`
- Provider settings: `GROQ_API_KEY`, `GROQ_MODEL`, `TWELVE_DATA_KEY`
- `GET /api/version` returns the deployed commit from `RENDER_GIT_COMMIT`; local assets use that commit in their URLs to refresh browser caches.

Cloud portfolios retain the existing username-only identity scheme; usernames are not passwords. The production debug endpoint is disabled. Never commit secrets, local databases, provider snapshots, virtual environments, or temporary review outputs.

Run checks on a release branch before merging to `main`. After merging, monitor the automatic Render deployment, compare its commit with `/api/version`, and verify desktop/mobile, insights, and cloud portfolio persistence. Do not manually trigger a duplicate deploy. For a faulty release, restore the previous working deployment and revert the release commit while preserving database records.

`requirements.in` contains direct dependencies; `requirements.txt` locks direct and transitive versions. Regenerate with `uv pip compile requirements.in --python-version 3.11 --output-file requirements.txt --no-header`, then test a fresh install before committing.

Market data depends on external providers and may be delayed or unavailable. FinAssist is an educational application; statistical historical analysis is not a guarantee of investment results.

## Free-source coverage and retained market data

Market data uses a server-only `market_data_cache` table in the existing Supabase project. Apply the checked-in migrations before enabling the new release. RLS is enabled and all access for `anon` and `authenticated` is revoked; only the backend service role can read/write the cache. No portfolio data is stored there. The migrations also grant the backend a security-invoker RPC that atomically retains the newest successful value for each field across local/cloud writers.

The application serves retained data while refreshing one task per symbol/category. Quotes and news refresh at most every 15 minutes, fundamentals/analyst data daily, and profiles weekly. Completed daily prices refresh when another exchange session becomes eligible; delayed daily history is retried every 15 minutes. Failures use backoff; permission denials are suppressed for 24 hours on the failing origin, so a Render block does not prevent a local network from retrieving data. In-memory entries recheck the shared cache every five minutes. Cache storage failures fall back to memory. Database and memory retention are capped at 100 recently accessed symbols plus the Nifty/S&P benchmarks, with non-benchmark entries unused for 30 days removed.

`data_quality` is additive on stock API responses. It identifies field sources, observation dates when supplied, retrieval times, freshness and unavailable reasons. Do not treat retrieval time as a financial reporting date. Missing values and provider failures cannot erase successful fields; retained values preserve their original timestamps. Quotes remain labelled as last available when stale. Set `MARKET_CACHE_ENABLED=false` to disable the shared cache; isolated tests use this setting by default.

When observed daily data supports it, FinAssist calculates 20-session average volume, a full 52-calendar-week high/low range rebased for splits, and beta from up to 252 aligned adjusted daily returns (minimum 120) against Nifty 50 or S&P 500. Missing sessions are not bridged. Insufficient history is explicit; insight analysis and calculated metrics older than seven calendar days are unavailable. Historical replay bypasses the production shared history cache.

No new paid data feed is used. Provider permissions and coverage can still leave fundamentals or analyst ratings unavailable. Analyst data without a supplied consensus has no rating gauge. RSS news is filtered by company aliases and syndicated headline punctuation is normalized for deduplication.
