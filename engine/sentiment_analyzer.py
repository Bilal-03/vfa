"""Actual frozen ProsusAI/finbert inference, with a persistent content cache."""

import hashlib
import json
from pathlib import Path
import numpy as np


class FinancialSentimentEngine:
    def __init__(self, cache_path="research/sentiment_cache.json", **kwargs):
        self.path = Path(cache_path)
        self.cache = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.pipeline = None

    def _save(self):
        import fcntl

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(self.path) + ".lock", "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            merged = json.loads(self.path.read_text()) if self.path.exists() else {}
            merged.update(self.cache)
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps(merged))
            temp.replace(self.path)
            self.cache = merged

    def cache_headlines(self, headlines):
        missing = [
            h
            for h in dict.fromkeys(headlines)
            if hashlib.sha256(h.encode()).hexdigest() not in self.cache
        ]
        if not missing:
            return
        if self.pipeline is None:
            from transformers import pipeline

            self.pipeline = pipeline(
                "text-classification",
                model="ProsusAI/finbert",
                revision="0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031",
                device=-1,
            )
        for start in range(0, len(missing), 8):
            batch = missing[start : start + 8]
            results = self.pipeline(
                batch, top_k=None, truncation=True, max_length=96, batch_size=8
            )
            for headline, scores in zip(batch, results):
                self.cache[hashlib.sha256(headline.encode()).hexdigest()] = {
                    s["label"].lower(): float(s["score"]) for s in scores
                }
            self._save()
        print(f"Cached {len(missing)} real FinBERT headline scores", flush=True)

    def analyze_headline(self, headline):
        key = hashlib.sha256(headline.encode()).hexdigest()
        if key not in self.cache:
            if self.pipeline is None:
                from transformers import pipeline

                self.pipeline = pipeline(
                    "text-classification",
                    model="ProsusAI/finbert",
                    revision="0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031",
                    device=-1,
                )
            scores = self.pipeline(headline, top_k=None, truncation=True, max_length=96)
            self.cache[key] = {s["label"].lower(): float(s["score"]) for s in scores}
            self._save()
        return self.cache[key]

    def aggregate_sentiment(self, headlines_with_age_hours):
        if not headlines_with_age_hours:
            return np.zeros(7, dtype=np.float32)
        scores = np.array(
            [
                [
                    self.analyze_headline(t)[k]
                    for k in ("positive", "neutral", "negative")
                ]
                for t, a in headlines_with_age_hours
            ]
        )
        ages = np.array([a for t, a in headlines_with_age_hours])
        w = np.exp(-np.log(2) * ages / 24)
        avg = np.average(scores, axis=0, weights=w)
        return np.array(
            [
                *avg,
                min(float(np.average(ages, weights=w)), 168) / 168,
                np.log1p(len(ages)),
                float(np.std(scores[:, 0] - scores[:, 2])),
                1,
            ],
            dtype=np.float32,
        )
