"""Download real sources; normalize explicit company mentions; no synthetic fallbacks."""

import io, json, hashlib, re, sys
from pathlib import Path
import pandas as pd
import requests
import yfinance as yf

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)
SOURCES = {
    "India": "https://zenodo.org/api/records/16991843/files/IN-FINews%20Dataset.csv/content",
    "US": "https://raw.githubusercontent.com/pmoe7/Stock-Market-Data/main/sp500_news_290k_articles.csv",
}
ALIASES = {
    "TCS.NS": r"\btcs\b|tata consultancy",
    "INFY.NS": r"\binfosys\b",
    "SBIN.NS": r"\bsbi\b|state bank of india",
    "AAPL": r"\bapple\b",
    "MSFT": r"\bmicrosoft\b",
    "NVDA": r"\bnvidia\b",
}
manifest = {}
for market, url in SOURCES.items():
    response = requests.get(url, timeout=90)
    response.raise_for_status()
    raw = response.content
    (DATA / f"{market}_source.csv").write_bytes(raw)
    df = pd.read_csv(io.BytesIO(raw))
    rows = []
    syms = list(ALIASES)[:3] if market == "India" else list(ALIASES)[3:]
    for sym in syms:
        if market == "India":
            subset = df[
                df.Title.str.contains(ALIASES[sym], case=False, regex=True, na=False)
            ]
            title = "Title"
            date = "Date"
        else:
            subset = df[
                (df.ticker == sym)
                & df.headline.str.contains(
                    ALIASES[sym], case=False, regex=True, na=False
                )
            ]
            title = "headline"
            date = "date"
        for _, r in subset.iterrows():
            d = pd.to_datetime(r[date], utc=True, errors="coerce")
            if pd.notna(d):
                rows.append(dict(symbol=sym, date=str(d.date()), headline=r[title]))
    news = (
        pd.DataFrame(rows)
        .drop_duplicates(["symbol", "date", "headline"])
        .sort_values("date")
    )
    if market == "US":
        news = news[
            pd.to_datetime(news.date)
            >= pd.to_datetime(news.date).max() - pd.Timedelta(days=365)
        ]
    news.to_csv(DATA / f"{market}_news.csv", index=False)
    manifest[market] = dict(
        source=url,
        sha256=hashlib.sha256(raw).hexdigest(),
        raw_rows=len(df),
        accepted_rows=len(news),
        start=news.date.min(),
        end=news.date.max(),
        date_policy="Date only: eligible strictly after publication day",
        symbols=syms,
    )
    for sym in syms:
        start = pd.to_datetime(news.date.min()) - pd.Timedelta(days=180)
        end = pd.to_datetime(news.date.max()) + pd.Timedelta(days=10)
        hist = yf.Ticker(sym).history(
            start=str(start.date()), end=str(end.date()), auto_adjust=True
        )
        if len(hist) < 100:
            raise RuntimeError(
                f"{sym}: insufficient real price history; no synthetic substitute"
            )
        hist.to_csv(DATA / f"{sym}.csv")
        print(sym, len(hist), flush=True)
(ROOT / "artifacts/data_manifest.json").write_text(json.dumps(manifest, indent=2))
