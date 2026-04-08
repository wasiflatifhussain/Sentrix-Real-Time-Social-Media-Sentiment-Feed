from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from filtering_service_b.relevance.context_terms import finance_context_text


@dataclass(frozen=True)
class TickerProfile:
    ticker: str
    company: str
    profile_text: str


class TickerProfileStore:
    def __init__(self, profiles: dict[str, TickerProfile]) -> None:
        self._profiles = dict(profiles)

    def get(self, ticker: str) -> TickerProfile | None:
        return self._profiles.get(ticker.upper())

    @property
    def profiles(self) -> dict[str, TickerProfile]:
        return dict(self._profiles)

    @classmethod
    def from_json(cls, ticker_profiles_path: str | Path) -> "TickerProfileStore":
        path = Path(ticker_profiles_path).resolve()
        if not path.is_file():
            raise ValueError(f"Ticker profiles file not found: {path}")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except OSError as ex:
            raise ValueError(f"Failed to read ticker profiles file: {path}") from ex
        except json.JSONDecodeError as ex:
            raise ValueError(f"Ticker profiles file is not valid JSON: {path}") from ex
        if not isinstance(raw, list):
            raise ValueError(f"Ticker profile file must contain a list: {path}")

        profiles: dict[str, TickerProfile] = {}
        for item in raw:
            ticker = str(_require(item, "ticker")).upper()
            company = str(_require(item, "company")).strip()
            queries = _extract_queries(item.get("queries"))
            profile_text = _build_profile_text(ticker, company, queries)
            if ticker in profiles:
                raise ValueError(f"Duplicate ticker in profile file: {ticker}")
            profiles[ticker] = TickerProfile(
                ticker=ticker,
                company=company,
                profile_text=profile_text,
            )
        return cls(profiles)


def _require(item: dict[str, Any], key: str) -> Any:
    val = item.get(key)
    if val is None or (isinstance(val, str) and val.strip() == ""):
        raise ValueError(f"Missing required ticker profile field: {key}")
    return val


def _extract_queries(raw_queries: Any) -> list[str]:
    if raw_queries is None:
        return []
    if not isinstance(raw_queries, list):
        raise ValueError("Ticker profile field 'queries' must be a list when provided")
    queries: list[str] = []
    for query in raw_queries:
        if isinstance(query, str) and query.strip():
            queries.append(query)
    return queries


def _extract_keywords(queries: list[str]) -> list[str]:
    keywords: set[str] = set()
    for query in queries:
        if not isinstance(query, str):
            continue
        cleaned = query.replace("(", " ").replace(")", " ")
        for token in re.split(r"[^A-Za-z0-9.$]+", cleaned):
            token = token.strip().lower()
            if token in {"", "or", "and", "not"}:
                continue
            if token.startswith("$"):
                token = token[1:]
            if len(token) < 2:
                continue
            keywords.add(token)
    return sorted(keywords)


def _build_profile_text(ticker: str, company: str, queries: list[str]) -> str:
    query_keywords = " ".join(_extract_keywords(queries))
    company_identity = f"{company} {company} {company} {ticker} {ticker}"
    finance_terms = finance_context_text()
    ambiguous_hint = ""
    if len(ticker) <= 2:
        ambiguous_hint = f" {company} corporation brand company identity"

    return (
        f"{company_identity} "
        f"{finance_terms} "
        f"{query_keywords}"
        f"{ambiguous_hint}"
    ).strip()
