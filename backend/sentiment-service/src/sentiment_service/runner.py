# runner.py
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from dotenv import load_dotenv

from sentiment_service.llm_connector import FinbertClient
from sentiment_service.objects.objects import Event, HourlyLevelScore

class Runner:
    def __init__(self):
        load_dotenv()
        api_key = os.getenv("HUGGING_FACE_API")
        self.fc = FinbertClient(api_key=api_key)

        self.events = list()
        self.hourly = dict()
        self.ticker = dict()
        '''
        {
            "TSLA": <HourlyLevelScore> for TSLA,
            "AAPL": <HourlyLevelScore> for AAPL,
        }
        '''
        return

    def run_event_level(self, data: dict):
        event = self.construct_event(data)
        self.fc.run(event)
        self.compute_event_level(event)

        self.events.append(event)
        return event

    def compute_event_level(self, event: Event):
        event.calculate()
        return

    def run_hourly_level(self, event: Event):
        ticker: str = event.ticker
        if self.hourly.get(ticker, None) is None:
            self.hourly[ticker] = self.construct_hourly_level_score(event)
        else:
            # update the hourly model
            self.update_hourly_level(ticker, event)
        return

    def update_hourly_level(self, ticker: str, event: Event,):
        hm: HourlyLevelScore = self.hourly.get(ticker, None)
        weight = self.get_count_weighting(event)
        hm.add_event(score=event.score, weight=weight, source=event.source)
        return

    def construct_event(self, data) -> Event:
        # print({data.get('ingestorEvent', {'eventId': '-1'}).get('eventId', '-1')}, "-", data.get('textView', {'textNormalized': ''}).get('textNormalized', '').replace("None", ''))
        return Event(
            id=data.get('ingestorEvent', {'eventId': '-1'}).get('eventId', '-1'),
            source=data.get('ingestorEvent', {'source'}).get('source', '-1'),
            timestamp=data.get('ingestorEvent', {'createdAtUtc': 0}).get('createdAtUtc', 0),
            metrics=data.get('ingestorEvent', {'metrics': {}}).get('metrics', {}),
            ticker=data.get('ingestorEvent', {'ticker': None}).get('ticker', None),
            content=data.get('textView', {'textNormalized': ''}).get('textNormalized', '').replace("None", ''),
            metadata=data.get('filterMeta', None),
        )

    def construct_hourly_level_score(self, event: Event) -> HourlyLevelScore:
        weight = self.get_count_weighting(event)
        start_time: int = int(event.timestamp // 3_600) * 3_600
        hm = HourlyLevelScore(
           _id=f"{event.ticker}|{start_time}",
            createdAtUtc=event.timestamp,
            hourStartUtc=start_time,
            hourEndUtc=start_time + 3_600,
            ticker=event.ticker,
            metrics=event.metrics,
        )
        hm.add_event(score=event.score, weight=weight, source=event.source)
        return hm

    def get_count_weighting(self, event):
        count: int = 0
        like: int = 0
        reply: int = 0
        comment: int = 0
        for k in event.metrics:
            if (
                isinstance(event.metrics.get(k, 0), (int, float, complex)) or
                (isinstance(event.metrics.get(k, ''), str) and event.metrics.get(k, '').isnumeric())
            ):
                count += int(event.metrics.get(k, 0))
                if k.startswith("like"):
                    like += int(event.metrics.get(k, 0))
                elif k.startswith("reply"):
                    reply += int(event.metrics.get(k, 0))
                elif k.startswith("comment"):
                    comment += int(event.metrics.get(k, 0))
                    
        # weighting: float = 1.0 + math.log1p(max(0, like) + max(0, comment) + max(0, reply))
        return count
    
    def return_hourly_level(self):
        res = list()
        for k in self.hourly:
            res.append(self.hourly[k])

        return res
'''
s1, 6
s2, 2

(s1 * 6 + s2 * 2) / 8
'''

# -----------------------------
# IO helpers
# -----------------------------

def read_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_hourly_history(path: Path) -> List[Dict[str, Any]]:
    """
    ticker_sentiment_hourly.json in your sample looks like a JSON array (not JSONL).
    """
    text = path.read_text(encoding="utf-8").strip()
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("Expected ticker_sentiment_hourly.json to be a JSON array of hourly rows.")
    return data


# -----------------------------
# Pipeline
# -----------------------------

def _extract_metrics(rec: Dict[str, Any]) -> dict:
    ing = rec.get("ingestorEvent", {}) or {}
    return ing.get("metrics", {}) or {}


def _event_meta_from_record(rec: Dict[str, Any]):
    from sentiment_service.Event_level_score import EventMeta

    metrics = _extract_metrics(rec)
    likes = int(metrics.get("likeCount") or 0)
    comments = int(metrics.get("commentCount") or metrics.get("replyCount") or 0)
    replies = int(metrics.get("replyCount") or 0)
    reposts = int(metrics.get("shareCount") or 0)
    return EventMeta(
        likes=likes,
        comments=comments + replies,
        reposts=reposts,
        cred_score=1.0,
        source_mult=1.0,
    )


def _parse_event_record(rec: Dict[str, Any]) -> Dict[str, Any]:
    ing = rec.get("ingestorEvent", {}) or {}
    tv = rec.get("textView", {}) or {}
    fm = rec.get("filterMeta", {}) or {}

    return {
        "event_id": str(ing.get("eventId", "")),
        "ticker": str(ing.get("ticker", "")),
        "created_at_utc": ing.get("createdAtUtc"),
        "title": str(ing.get("title") or ""),
        "text": str(ing.get("text") or ""),
        "text_normalized": str(tv.get("textNormalized") or ""),
        "filter_decision": fm.get("decision"),
        "raw": rec,
    }


def run(
    events_path: Path,
    history_path: Path,
    out_dir: Path,
    finbert_api_key: str,
    *,
    event_profile: str = "moderate",
    hour_profile: str = "moderate",
    ticker_profile: str = "moderate",
    max_hours: Optional[int] = 168,
) -> None:
    from sentiment_service.Event_level_score import ModelOutput as EventModelOutput
    from sentiment_service.Event_level_score import fuse_model_outputs
    from sentiment_service.Hour_level_score import aggregate_from_scores_weights
    from sentiment_service.Ticker_level_score import HourlyRow, compute_signal_for_ticker, normalize_hourly_row
    from sentiment_service.utils.time import bucket_epoch_seconds_to_hour

    finbert = FinbertClient(api_key=finbert_api_key)

    # 1) Read events (JSONL) and filter KEEP
    parsed = [_parse_event_record(r) for r in read_jsonl(events_path)]
    kept = [e for e in parsed if (e.get("filter_decision") or "").upper() == "KEEP"]
    if not kept:
        raise RuntimeError("No KEEP events found for this hour batch.")

    # 2) Event-level scoring (FinBERT + fusion-ready)
    event_out: List[Dict[str, Any]] = []
    for rec in kept:
        text = rec["text_normalized"].strip() or (rec["title"] + "\n\n" + rec["text"]).strip()
        meta = _event_meta_from_record(rec["raw"])
        finbert_out = finbert.score_with_confidence(text)

        outputs = [
            EventModelOutput(
                model_id="finbert",
                label=finbert_out.get("label", "neutral"),
                score=float(finbert_out.get("score", 0.0)),
                confidence=float(finbert_out.get("confidence", 0.0)),
            )
        ]
        fused = fuse_model_outputs(outputs, meta=meta, profile=event_profile)

        event_out.append(
            {
                "event_id": rec["event_id"],
                "ticker": rec["ticker"],
                "created_at_utc": rec["created_at_utc"],
                "event_score": fused.score,
                "event_confidence": fused.confidence,
                "event_weight": fused.weight,
            }
        )

    event_out_path = out_dir / "event_level.jsonl"
    write_jsonl(event_out_path, event_out)

    # 3) Hour-level aggregation per ticker (weighted)
    created_times = [e["created_at_utc"] for e in kept if isinstance(e.get("created_at_utc"), int)]
    if not created_times:
        raise RuntimeError("Events missing createdAtUtc; cannot derive hour window.")

    bucket = bucket_epoch_seconds_to_hour(min(created_times))
    hour_start_utc = bucket.hour_start_utc
    hour_end_utc = bucket.hour_end_utc

    by_ticker: Dict[str, List[Dict[str, Any]]] = {}
    for r in event_out:
        by_ticker.setdefault(r["ticker"], []).append(r)

    hour_rows: List[Dict[str, Any]] = []
    for ticker, rows in by_ticker.items():
        scores = [r["event_score"] for r in rows]
        weights = [r["event_weight"] for r in rows]
        confidences = [r["event_confidence"] for r in rows]
        agg = aggregate_from_scores_weights(
            scores, weights=weights, confidences=confidences, profile=hour_profile
        )
        score_sum = agg.weighted_score_sum if agg.weight_sum > 0 else agg.score_sum
        hour_rows.append(
            {
                "ticker": ticker,
                "hourStartUtc": hour_start_utc,
                "hourEndUtc": hour_end_utc,
                "count": agg.count,
                "scoreSum": score_sum,
                "avgScore": agg.weighted_hour_avg,
                "hourConfidence": agg.hour_confidence,
            }
        )

    hour_out_path = out_dir / "hour_level.jsonl"
    write_jsonl(hour_out_path, hour_rows)

    # 4) Ticker-level signal using available history (no fixed length)
    history = read_hourly_history(history_path)

    final_rows: List[Dict[str, Any]] = []
    for cur in hour_rows:
        hist_rows = [normalize_hourly_row(h) for h in history if h.get("ticker") == cur["ticker"]]
        hist_rows = [h for h in hist_rows if h is not None]
        hist_rows.append(
            HourlyRow(
                ticker=cur["ticker"],
                hour_start_utc=int(cur["hourStartUtc"]),
                hour_end_utc=int(cur["hourEndUtc"]),
                count=int(cur["count"]),
                score_sum=float(cur["scoreSum"]),
                updated_at_utc=None,
            )
        )
        snap = compute_signal_for_ticker(
            hist_rows, profile=ticker_profile, max_hours=max_hours
        )
        if not snap:
            continue
        final_rows.append(
            {
                "ticker": snap.ticker,
                "hourStartUtc": snap.hour_start_utc,
                "hourEndUtc": int(cur["hourEndUtc"]),
                "final_signal": snap.signal,
                "confidence": snap.confidence,
                "delta_1h": snap.delta_1h,
                "delta_24h": snap.delta_24h,
            }
        )

    final_out_path = out_dir / "final_signal.jsonl"
    write_jsonl(final_out_path, final_rows)


def get_finbert_api_key() -> str:
    load_dotenv()
    return os.getenv("HUGGING_FACE_API", "")


def main() -> None:
    events_path = Path("./ticker-events-data.json")
    history_path = Path("./ticker_sentiment_hourly.json")
    out_dir = Path("./out")
    finbert_api_key = get_finbert_api_key()
    run(events_path, history_path, out_dir, finbert_api_key)


if __name__ == "__main__":
    print("testing")
    # main()
