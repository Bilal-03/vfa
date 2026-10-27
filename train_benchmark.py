"""Reproducible chronological benchmark. Never generates data or news from labels."""

import argparse, copy, hashlib, json, random
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    matthews_corrcoef,
    confusion_matrix,
)
from sklearn.linear_model import LogisticRegression
from engine.technical_features import extract_technical_features
from engine.multimodal_model import ForecastModel
from engine.sentiment_analyzer import FinancialSentimentEngine

ROOT = Path(__file__).resolve().parent
ART = ROOT / "research/artifacts"
SYMBOLS = {"India": ["TCS.NS", "INFY.NS", "SBIN.NS"], "US": ["AAPL", "MSFT", "NVDA"]}


def metrics(y, p):
    return dict(
        accuracy_pct=100 * accuracy_score(y, p),
        balanced_accuracy_pct=100 * balanced_accuracy_score(y, p),
        macro_f1=f1_score(y, p, labels=[0, 1, 2], average="macro", zero_division=0),
        mcc=matthews_corrcoef(y, p),
        confusion_matrix=confusion_matrix(y, p, labels=[0, 1, 2]).tolist(),
        samples=len(y),
    )


def partitions(dates, ends):
    unique = sorted(set(dates))
    a = unique[int(len(unique) * 0.70)]
    b = unique[int(len(unique) * 0.85)]
    return [
        np.array(
            [i for i, (d, e) in enumerate(zip(dates, ends)) if (d < a and e < a)],
            dtype=int,
        ),
        np.array(
            [i for i, (d, e) in enumerate(zip(dates, ends)) if a <= d < b and e < b],
            dtype=int,
        ),
        np.array([i for i, d in enumerate(dates) if d >= b], dtype=int),
    ]


def dataset(market, prices, news_path=None):
    news = (
        pd.read_csv(news_path)
        if news_path
        else pd.DataFrame(columns=["symbol", "date", "headline"])
    )
    if len(news):
        news["date"] = (
            pd.to_datetime(news.date, utc=True).dt.tz_localize(None).dt.normalize()
        )
    engine = FinancialSentimentEngine(str(ROOT / "research/sentiment_cache.json"))
    X = []
    N = []
    Y = []
    D = []
    E = []
    S = []
    columns = None
    for sym in SYMBOLS[market]:
        df = pd.read_csv(prices / f"{sym}.csv", index_col=0, parse_dates=True)
        df.index = pd.to_datetime(df.index, utc=True).tz_localize(None).normalize()
        df = df.sort_index()
        df = df[~df.index.duplicated()]
        feat = extract_technical_features(df)
        columns = list(feat.columns)
        rows = news[news.symbol == sym]
        used = []
        for day in df.index[69:-3]:
            eligible = (
                rows[(rows.date < day) & (rows.date >= day - pd.Timedelta(days=7))]
                .drop_duplicates("headline")
                .sort_values("date")
                .tail(2)
            )
            used.extend(eligible.headline.tolist())
        engine.cache_headlines(used)
        for i in range(69, len(df) - 3):
            day = df.index[i]
            if len(news) and not (news.date.min() <= day <= news.date.max()):
                continue
            eligible = (
                rows[(rows.date < day) & (rows.date >= day - pd.Timedelta(days=7))]
                .drop_duplicates("headline")
                .sort_values("date")
                .tail(2)
            )
            n = engine.aggregate_sentiment(
                [
                    (r.headline, (day - r.date).total_seconds() / 3600)
                    for r in eligible.itertuples()
                ]
            )
            ret = (df.Close.iloc[i + 3] / df.Close.iloc[i] - 1) * 100
            X.append(feat.iloc[i - 19 : i + 1].values)
            N.append(n)
            Y.append(2 if ret > 0.75 else 0 if ret < -0.75 else 1)
            D.append(day)
            E.append(df.index[i + 3])
            S.append(sym)
    if not X:
        raise ValueError("No valid samples; check real price/news coverage")
    return np.array(X, dtype=np.float32), np.array(N), np.array(Y), D, E, S, columns


def run(market, args):
    torch.set_num_threads(2)
    np.random.seed(args.seed)
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    X, N, y, dates, ends, symbols, cols = dataset(market, Path(args.prices), args.news)
    tr, va, te = partitions(dates, ends)
    if min(map(len, (tr, va, te))) < 10 or len(set(y[tr])) < 2:
        raise ValueError("Insufficient split/class support")
    mean = X[tr].mean(axis=(0, 1))
    std = X[tr].std(axis=(0, 1))
    std = np.maximum(std, 1e-6)
    X = (X - mean) / std
    xt = torch.tensor(X)
    nt = torch.tensor(N)
    yt = torch.tensor(y, dtype=torch.long)
    out = {}
    predictions = []
    ART.mkdir(parents=True, exist_ok=True)

    def record(name, p):
        out[name] = metrics(y[te], p)
        predictions.extend(
            dict(
                model=name,
                symbol=symbols[i],
                date=str(dates[i].date()),
                target_end=str(ends[i].date()),
                actual=int(y[i]),
                predicted=int(v),
            )
            for i, v in zip(te, p)
        )

    record("Majority", np.full(len(te), np.bincount(y[tr], minlength=3).argmax()))
    logistic = LogisticRegression(max_iter=1000).fit(X[tr, -1], y[tr])
    record("Technical logistic regression", logistic.predict(X[te, -1]))
    metadata = dict(
        market=market,
        seed=args.seed,
        feature_order=cols,
        mean=mean.tolist(),
        std=std.tolist(),
        symbols=SYMBOLS[market],
        horizon_sessions=3,
        threshold_pct=0.75,
        news_enabled=bool(args.news),
        split_counts=dict(train=len(tr), validation=len(va), test=len(te)),
        split_dates={
            k: [
                str(min(dates[i] for i in idx).date()),
                str(max(dates[i] for i in idx).date()),
            ]
            for k, idx in zip(["train", "validation", "test"], [tr, va, te])
        },
        missing_news_rate=float(np.mean(N[:, 6] == 0)),
        class_counts=np.bincount(y, minlength=3).tolist(),
        news_sha256=(
            hashlib.sha256(Path(args.news).read_bytes()).hexdigest()
            if args.news
            else None
        ),
        epochs_requested=args.epochs,
        version="finassist-v2",
        protocol="Chronological 70/15/15 holdout with purged target boundaries",
        prices_sha256={
            sym: hashlib.sha256(
                (Path(args.prices) / f"{sym}.csv").read_bytes()
            ).hexdigest()
            for sym in SYMBOLS[market]
        },
    )
    modes = (
        ["technical"]
        if not args.news
        else ["technical", "sentiment", "concat", "gated", "no_freshness", "no_mask"]
    )
    for mode in modes:
        torch.manual_seed(args.seed)
        model = ForecastModel(len(cols), mode)
        opt = torch.optim.Adam(model.parameters(), lr=0.001)
        best = -1
        stale = 0
        weights = None
        for epoch in range(args.epochs):
            model.train()
            order = np.random.permutation(tr)
            for start in range(0, len(order), 32):
                idx = order[start : start + 32]
                opt.zero_grad()
                loss = torch.nn.functional.cross_entropy(
                    model(xt[idx], nt[idx]), yt[idx]
                )
                loss.backward()
                opt.step()
            model.eval()
            with torch.no_grad():
                score = f1_score(
                    y[va],
                    model(xt[va], nt[va]).argmax(1).numpy(),
                    labels=[0, 1, 2],
                    average="macro",
                    zero_division=0,
                )
            if score > best:
                best = score
                weights = copy.deepcopy(model.state_dict())
                stale = 0
            else:
                stale += 1
            if stale >= 5:
                break
        model.load_state_dict(weights)
        model.eval()
        with torch.no_grad():
            record(mode, model(xt[te], nt[te]).argmax(1).numpy())
        if mode in ("gated", "technical"):
            torch.save(
                dict(
                    state_dict=weights,
                    metadata={
                        **metadata,
                        "mode": mode,
                        "validation_macro_f1": float(best),
                    },
                ),
                ART / f"{market}_{mode}_{args.seed}.pt",
            )
        if mode == "gated":
            for condition in ("missing", "stale"):
                modified = nt[te].clone()
                if condition == "missing":
                    modified[:] = 0
                else:
                    modified[:, 3] = 1
                with torch.no_grad():
                    record(
                        "gated_" + condition, model(xt[te], modified).argmax(1).numpy()
                    )
    pd.DataFrame(predictions).to_csv(
        ART / f"{market}_{args.seed}_predictions.csv", index=False
    )
    per_symbol = {}
    for name in out:
        per_symbol[name] = {}
        for sym in sorted(set(symbols)):
            selected = [
                r for r in predictions if r["model"] == name and r["symbol"] == sym
            ]
            if selected:
                per_symbol[name][sym] = metrics(
                    np.array([r["actual"] for r in selected]),
                    np.array([r["predicted"] for r in selected]),
                )
    result = dict(metadata=metadata, models=out, per_symbol=per_symbol)
    (ART / f"{market}_{args.seed}_results.json").write_text(
        json.dumps(result, indent=2)
    )
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--market", choices=list(SYMBOLS), required=True)
    p.add_argument("--prices", required=True)
    p.add_argument("--news")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--epochs", type=int, default=30)
    args = p.parse_args()
    run(args.market, args)
