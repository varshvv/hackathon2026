from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import pandas as pd

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover
    BeautifulSoup = None

from config import CURRENCY_EVENT_MAP

OANDA_CALENDAR_URL = "https://www.oanda.com/eu-de/calendar/economic"
OANDA_ANALYSIS_URL = "https://www.oanda.com/us-en/trade-tap-blog/analysis/"
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


@dataclass
class MarketContextPacket:
    daily_calendar: pd.DataFrame
    weekly_calendar: pd.DataFrame
    headlines: pd.DataFrame
    source_note: str
    warning: str | None = None
    daily_note: str | None = None
    weekly_note: str | None = None


def _pair_currencies(symbol: str) -> list[str]:
    base, quote = symbol.split("/")
    return [base, quote]


def _event_keywords(symbol: str) -> list[str]:
    keywords: list[str] = []
    for currency in _pair_currencies(symbol):
        keywords.extend(CURRENCY_EVENT_MAP.get(currency, []))
        keywords.append(currency)
    return list(dict.fromkeys(keywords))


def _score_relevance(text: str, symbol: str) -> tuple[int, str]:
    base, quote = _pair_currencies(symbol)
    score = 0
    reasons: list[str] = []
    upper_text = text.upper()
    keyword_blob = text.lower()

    if base in upper_text:
        score += 3
        reasons.append(f"mentions {base}")
    if quote in upper_text:
        score += 3
        reasons.append(f"mentions {quote}")

    for currency in (base, quote):
        for keyword in CURRENCY_EVENT_MAP.get(currency, []):
            if keyword.lower() in keyword_blob:
                score += 1
                reasons.append(keyword)

    if any(term in keyword_blob for term in ["inflation", "cpi", "ppi", "rates", "rate decision", "employment", "payroll", "gdp", "central bank"]):
        score += 2
        reasons.append("macro-sensitive")

    return score, ", ".join(dict.fromkeys(reasons[:3]))


def _fetch_calendar_table() -> pd.DataFrame:
    if requests is None:
        raise RuntimeError("requests is not installed.")
    response = requests.get(OANDA_CALENDAR_URL, headers=REQUEST_HEADERS, timeout=20)
    response.raise_for_status()
    tables = pd.read_html(response.text)
    if not tables:
        raise RuntimeError("No economic calendar tables were found on OANDA.")

    calendar = max(tables, key=lambda frame: len(frame))
    calendar.columns = [str(col).strip().lower() for col in calendar.columns]

    rename_map = {}
    for col in calendar.columns:
        if "time" in col or "stunde" in col:
            rename_map[col] = "time"
        elif "country" in col or "land" in col:
            rename_map[col] = "country"
        elif "date" in col or "datum" in col or "day" in col or "tag" in col:
            rename_map[col] = "date"
        elif "event" in col or "ereignis" in col:
            rename_map[col] = "event"
        elif "period" in col or "zeitraum" in col:
            rename_map[col] = "period"
        elif "prior" in col or "priority" in col:
            rename_map[col] = "priority"
        elif "forecast" in col or "prognose" in col:
            rename_map[col] = "forecast"
        elif "actual" in col or "aktuell" in col:
            rename_map[col] = "actual"
        elif "previous" in col or "zuvor" in col:
            rename_map[col] = "previous"

    calendar = calendar.rename(columns=rename_map)
    required = [col for col in ["time", "country", "event"] if col in calendar.columns]
    if len(required) < 3:
        raise RuntimeError("OANDA calendar structure changed and could not be parsed safely.")

    normalized = calendar[[col for col in ["date", "time", "country", "event", "period", "priority", "forecast", "actual", "previous"] if col in calendar.columns]].copy()
    normalized = normalized.dropna(subset=["country", "event"]).reset_index(drop=True)
    if "date" in normalized.columns:
        normalized["date"] = normalized["date"].replace({"": pd.NA, "nan": pd.NA}).ffill()
    normalized["time"] = normalized["time"].astype(str).str.strip()
    normalized["country"] = normalized["country"].astype(str).str.strip()
    normalized["event"] = normalized["event"].astype(str).str.strip()
    return normalized


def _prepare_dates(calendar: pd.DataFrame) -> pd.DataFrame:
    frame = calendar.copy()
    today = pd.Timestamp.now().normalize()
    if "date" not in frame.columns:
        frame["event_date"] = pd.NaT
        return frame

    parsed = pd.to_datetime(frame["date"], errors="coerce")
    if parsed.notna().any():
        frame["event_date"] = parsed.dt.normalize()
        return frame

    frame["event_date"] = pd.NaT
    return frame


def _calendar_for_symbol(calendar: pd.DataFrame, symbol: str) -> tuple[pd.DataFrame, pd.DataFrame, str | None, str | None]:
    calendar = _prepare_dates(calendar)
    keywords = _event_keywords(symbol)
    text_blob = (calendar["country"].fillna("") + " " + calendar["event"].fillna("")).str.lower()
    mask = pd.Series(False, index=calendar.index)
    for keyword in keywords:
        mask |= text_blob.str.contains(keyword.lower(), regex=False)

    filtered = calendar[mask].copy()
    if filtered.empty:
        filtered = calendar.copy()

    filtered["relevance_score"], filtered["why_it_matters"] = zip(
        *filtered.apply(lambda row: _score_relevance(f"{row['country']} {row['event']}", symbol), axis=1)
    )
    filtered = filtered.sort_values(["relevance_score", "event_date", "time"], ascending=[False, True, True]).reset_index(drop=True)

    today = pd.Timestamp.now().normalize()
    weekday = today.dayofweek
    daily_note = None
    weekly_note = None

    if weekday >= 5:
        daily = pd.DataFrame(
            [
                {
                    "time": "Closed",
                    "country": "FX Market",
                    "event": "Weekend trading pause",
                    "forecast": "-",
                    "actual": "-",
                    "previous": "-",
                    "why_it_matters": "Major spot forex trading is typically inactive on weekends, so scheduled price-moving releases are limited.",
                }
            ]
        )
        daily_note = "Today is a weekend, so the daily board is showing a market-status notice instead of a live trading calendar."
    else:
        if filtered["event_date"].notna().any():
            daily = filtered[filtered["event_date"] == today].copy()
        else:
            daily = filtered.copy()
            daily_note = "The source did not expose structured event dates, so the daily board is showing the most relevant loaded items."
        daily = daily.head(8)
        if daily.empty:
            daily_note = "No pair-relevant scheduled items were found for today."

    next_seven_days = pd.date_range(start=today, periods=7, freq="D")
    if filtered["event_date"].notna().any():
        weekly = filtered[filtered["event_date"].isin(next_seven_days)].copy()
        if weekly.empty:
            weekly_note = "No pair-relevant scheduled items were found in the next 7 days."
        weekly["day"] = weekly["event_date"].dt.strftime("%a")
        weekly["date_label"] = weekly["event_date"].dt.strftime("%Y-%m-%d")
        weekly = weekly.sort_values(["event_date", "time", "relevance_score"], ascending=[True, True, False]).head(24)
    else:
        weekly = filtered.head(14).copy()
        weekly["day"] = "Upcoming"
        weekly["date_label"] = "Date unavailable"
        weekly_note = "The source did not expose structured event dates, so the weekly board is showing the most relevant loaded items instead of a strict 7-day schedule."

    if not daily.empty and "event_date" in daily.columns:
        daily["day"] = daily["event_date"].dt.strftime("%a").fillna("")
        daily["date_label"] = daily["event_date"].dt.strftime("%Y-%m-%d").fillna("")
    elif not daily.empty:
        daily["day"] = ""
        daily["date_label"] = ""

    return daily.reset_index(drop=True), weekly.reset_index(drop=True), daily_note, weekly_note


def _fetch_oanda_headlines(symbol: str) -> pd.DataFrame:
    if requests is None or BeautifulSoup is None:
        raise RuntimeError("requests and beautifulsoup4 are required for news fetching.")
    response = requests.get(OANDA_ANALYSIS_URL, headers=REQUEST_HEADERS, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    links = soup.find_all("a", href=True)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for link in links:
        text = " ".join(link.stripped_strings)
        href = link.get("href", "")
        if not text or len(text) < 18:
            continue
        if href in seen:
            continue
        score, reason = _score_relevance(text, symbol)
        if score <= 0:
            continue
        seen.add(href)
        rows.append(
            {
                "headline": text,
                "url": urljoin(OANDA_ANALYSIS_URL, href),
                "relevance_score": score,
                "why_it_matters": reason or "pair relevance",
                "source": "OANDA Analysis",
            }
        )

    headlines = pd.DataFrame(rows)
    if headlines.empty:
        return pd.DataFrame(columns=["headline", "url", "relevance_score", "why_it_matters", "source"])
    return headlines.sort_values("relevance_score", ascending=False).drop_duplicates("headline").head(10).reset_index(drop=True)


def fetch_market_context(symbol: str) -> MarketContextPacket:
    warnings: list[str] = []

    try:
        calendar = _fetch_calendar_table()
        daily, weekly, daily_note, weekly_note = _calendar_for_symbol(calendar, symbol)
    except Exception as exc:
        daily = pd.DataFrame(columns=["time", "country", "event", "priority", "forecast", "actual", "previous", "why_it_matters"])
        weekly = daily.copy()
        daily_note = None
        weekly_note = None
        warnings.append(f"Economic calendar unavailable: {exc}")

    try:
        headlines = _fetch_oanda_headlines(symbol)
    except Exception as exc:
        headlines = pd.DataFrame(columns=["headline", "url", "relevance_score", "why_it_matters", "source"])
        warnings.append(f"OANDA headlines unavailable: {exc}")

    return MarketContextPacket(
        daily_calendar=daily,
        weekly_calendar=weekly,
        headlines=headlines,
        source_note="Economic calendar and headlines sourced from OANDA web pages when available.",
        warning=" | ".join(warnings) if warnings else None,
        daily_note=daily_note,
        weekly_note=weekly_note,
    )
