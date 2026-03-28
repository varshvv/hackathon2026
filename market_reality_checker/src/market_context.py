from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from typing import Any
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

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
    timeline: pd.DataFrame
    source_note: str
    warning: str | None = None
    daily_note: str | None = None
    weekly_note: str | None = None


def _pair_currencies(symbol: str) -> list[str]:
    base, quote = symbol.split("/")
    return [base, quote]


def _central_bank_label(currency: str) -> str:
    return {
        "USD": "Federal Reserve",
        "EUR": "European Central Bank",
        "JPY": "Bank of Japan",
        "GBP": "Bank of England",
        "AUD": "Reserve Bank of Australia",
        "CHF": "Swiss National Bank",
        "CAD": "Bank of Canada",
    }.get(currency, f"{currency} Central Bank")


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


def _news_angle(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ["cpi", "inflation", "ppi"]):
        return "Inflation"
    if any(term in lowered for term in ["rate", "fed", "ecb", "boj", "boe", "rba", "boc", "snb"]):
        return "Central Bank"
    if any(term in lowered for term in ["jobs", "payroll", "employment", "labor"]):
        return "Labor"
    if any(term in lowered for term in ["gdp", "growth", "recession"]):
        return "Growth"
    if any(term in lowered for term in ["risk", "geopolitical", "tariff", "trade"]):
        return "Risk Sentiment"
    return "Macro"


def _fallback_daily_watchlist(symbol: str) -> tuple[pd.DataFrame, str]:
    today_et = pd.Timestamp.now(tz=ZoneInfo("America/New_York")).normalize()
    weekday = today_et.day_name()
    date_label = today_et.strftime("%Y-%m-%d")
    base, quote = _pair_currencies(symbol)

    if today_et.dayofweek >= 5:
        next_open = today_et + pd.offsets.BDay(1)
        next_open_label = next_open.strftime("%Y-%m-%d")
        rows = [
            {
                "day": weekday[:3],
                "date_label": date_label,
                "time": "05:00 PM",
                "country": "FX Market",
                "event": "Sunday reopen gap-risk monitor",
                "forecast": "-",
                "actual": "-",
                "previous": "-",
                "why_it_matters": "Weekend headlines, geopolitical developments, and rate repricing can create opening gaps when forex liquidity returns.",
                "release_status": "Weekend Prep",
                "time_to_release": "Before reopen",
                "release_stamp_et": f"{date_label} 05:00 PM ET",
                "urgency_score": 55,
            },
            {
                "day": weekday[:3],
                "date_label": date_label,
                "time": "06:00 PM",
                "country": "Asia-Pacific",
                "event": "Asia open and futures repricing window",
                "forecast": "-",
                "actual": "-",
                "previous": "-",
                "why_it_matters": "Initial repricing in Asia and correlated futures markets often sets the tone for the first liquid FX session after the weekend.",
                "release_status": "Weekend Prep",
                "time_to_release": "After reopen",
                "release_stamp_et": f"{date_label} 06:00 PM ET",
                "urgency_score": 48,
            },
            {
                "day": next_open.strftime("%a"),
                "date_label": next_open_label,
                "time": "03:00 AM",
                "country": "Europe",
                "event": "European macro release window",
                "forecast": "-",
                "actual": "-",
                "previous": "-",
                "why_it_matters": "Early European data often provides the first high-signal fundamental input for EUR and GBP crosses after the weekend reopen.",
                "release_status": "Next Session",
                "time_to_release": "Upcoming",
                "release_stamp_et": f"{next_open_label} 03:00 AM ET",
                "urgency_score": 44,
            },
            {
                "day": weekday[:3],
                "date_label": date_label,
                "time": "All Day",
                "country": f"{base}/{quote}",
                "event": f"{_central_bank_label(base)} vs {_central_bank_label(quote)} policy gap watch",
                "forecast": "-",
                "actual": "-",
                "previous": "-",
                "why_it_matters": "Relative rate expectations are one of the biggest structural drivers of major FX pairs and often shape Monday reopening tone.",
                "release_status": "Weekend Prep",
                "time_to_release": "Active",
                "release_stamp_et": "Weekend ET",
                "urgency_score": 42,
            },
        ]
        note = "Weekend view is showing the principal reopening risks and structural FX drivers ahead of the next market open."
        return pd.DataFrame(rows), note

    weekday_playbook = {
        0: [
            ("08:30 AM", "US session setup and macro repricing", "Monday often starts with position resetting, weekend news digestion, and early repricing of central-bank expectations."),
            ("11:00 AM", f"{_central_bank_label(base)} / {_central_bank_label(quote)} speaker-risk scan", "Central-bank comments can move FX quickly when the market is still defining the week’s narrative."),
        ],
        1: [
            ("08:30 AM", "Inflation and growth surprise window", "Tuesday frequently carries inflation, survey, or growth releases that can reset rate-path expectations."),
            ("02:00 PM", "Rates narrative check-in", "By Tuesday afternoon the market often sharpens its view on the week’s major macro narrative."),
        ],
        2: [
            ("08:30 AM", "Midweek macro release cluster", "Wednesday often concentrates high-signal macro data and central-bank sensitivity."),
            ("02:00 PM", "Policy path repricing", "Midweek is where rate-sensitive FX pairs often see the strongest repricing if data surprises land."),
        ],
        3: [
            ("08:30 AM", "Labor and yield sensitivity watch", "Thursday data can move yields and quickly spill into major FX crosses."),
            ("10:00 AM", "Risk sentiment transmission", "Late-week growth and sentiment data can shift carry trades and USD demand."),
        ],
        4: [
            ("08:30 AM", "Friday payroll / close-risk window", "Friday macro surprises can trigger sharp FX moves and end-of-week position squaring."),
            ("03:00 PM", "Weekend positioning unwind", "Into the close, traders often reduce risk ahead of the weekend, affecting short-term price action."),
        ],
    }
    rows = []
    for time_value, title, reason in weekday_playbook[today_et.dayofweek]:
        rows.append(
            {
                "day": weekday[:3],
                "date_label": date_label,
                "time": time_value,
                "country": f"{base}/{quote}",
                "event": title,
                "forecast": "-",
                "actual": "-",
                "previous": "-",
                "why_it_matters": reason,
                "release_status": "Watchlist",
                "time_to_release": "Scheduled",
                "release_stamp_et": f"{date_label} {time_value} ET",
                "urgency_score": 35,
            }
        )
    note = "Structured pair-specific releases were not available, so the daily board is showing a live forex watchlist of the most relevant risk windows."
    return pd.DataFrame(rows), note


def _fallback_weekly_watchlist(symbol: str) -> tuple[pd.DataFrame, str]:
    today_et = pd.Timestamp.now(tz=ZoneInfo("America/New_York")).normalize()
    base, quote = _pair_currencies(symbol)
    upcoming_days = pd.date_range(today_et, periods=7, freq="D")
    rows: list[dict[str, Any]] = []

    for date_value in upcoming_days:
        day_idx = date_value.dayofweek
        day_label = date_value.strftime("%a")
        date_label = date_value.strftime("%Y-%m-%d")
        if day_idx >= 5:
            rows.append(
                {
                    "day": day_label,
                    "date_label": date_label,
                    "time": "Weekend",
                    "country": "FX Market",
                    "event": "Weekend headline and reopen-risk watch",
                    "forecast": "-",
                    "actual": "-",
                    "previous": "-",
                    "why_it_matters": "Weekend geopolitical and policy headlines can create Monday gap risk as forex trading resumes.",
                    "release_status": "Weekend Prep",
                    "time_to_release": "Watch",
                    "release_stamp_et": "Weekend ET",
                    "urgency_score": 30,
                }
            )
            continue

        if day_idx == 0:
            event = "Monday positioning and weekend repricing"
            reason = "Position resets and fresh macro interpretation often define Monday FX direction."
            time_value = "08:30 AM"
        elif day_idx == 1:
            event = "Inflation / PMI sensitivity window"
            reason = "Tuesday often carries inflation and activity releases that reprice rate expectations."
            time_value = "08:30 AM"
        elif day_idx == 2:
            event = "Midweek central-bank and macro focus"
            reason = "Wednesday is frequently the heaviest day for policy-sensitive FX narrative shifts."
            time_value = "02:00 PM"
        elif day_idx == 3:
            event = "Labor / rates spillover watch"
            reason = "Thursday data often transmits through yields into the major currency complex."
            time_value = "08:30 AM"
        else:
            event = "Friday close-risk and macro surprise window"
            reason = "Friday brings payroll-style risk, profit taking, and end-of-week de-risking."
            time_value = "08:30 AM"

        rows.append(
            {
                "day": day_label,
                "date_label": date_label,
                "time": time_value,
                "country": f"{base}/{quote}",
                "event": event,
                "forecast": "-",
                "actual": "-",
                "previous": "-",
                "why_it_matters": reason,
                "release_status": "Watchlist",
                "time_to_release": "Scheduled",
                "release_stamp_et": f"{date_label} {time_value} ET",
                "urgency_score": 28,
            }
        )

        rows.append(
            {
                "day": day_label,
                "date_label": date_label,
                "time": "11:00 AM",
                "country": f"{base}/{quote}",
                "event": f"{_central_bank_label(base)} vs {_central_bank_label(quote)} policy divergence watch",
                "forecast": "-",
                "actual": "-",
                "previous": "-",
                "why_it_matters": "Relative central-bank stance remains one of the cleanest structural drivers of major FX trends.",
                "release_status": "Structural Driver",
                "time_to_release": "Scheduled",
                "release_stamp_et": f"{date_label} 11:00 AM ET",
                "urgency_score": 24,
            }
        )

    weekly = pd.DataFrame(rows)
    note = "The weekly board is using a forex watchlist because structured calendar coverage was unavailable or incomplete."
    return weekly, note


def _fallback_headlines(symbol: str) -> pd.DataFrame:
    base, quote = _pair_currencies(symbol)
    rows = [
        {
            "headline": f"{symbol} focus: watch the {_central_bank_label(base)} versus {_central_bank_label(quote)} policy gap",
            "url": OANDA_ANALYSIS_URL,
            "relevance_score": 8,
            "why_it_matters": "Relative rate expectations are often the most important structural driver for major forex pairs.",
            "market_angle": "Central Bank",
            "source": "TruthLayer FX Watchlist",
            "relevance_label": "High Relevance",
        },
        {
            "headline": f"{symbol} focus: US yields, inflation surprises, and labor data can spill directly into majors",
            "url": OANDA_CALENDAR_URL,
            "relevance_score": 7,
            "why_it_matters": "Yield repricing and macro surprises frequently transmit into USD crosses and broader G10 FX.",
            "market_angle": "Macro",
            "source": "TruthLayer FX Watchlist",
            "relevance_label": "High Relevance",
        },
        {
            "headline": f"{symbol} focus: risk sentiment and session handoff can distort short-term price action",
            "url": OANDA_ANALYSIS_URL,
            "relevance_score": 5,
            "why_it_matters": "Asia, London, and New York session transitions can amplify moves when liquidity or risk appetite shifts quickly.",
            "market_angle": "Risk Sentiment",
            "source": "TruthLayer FX Watchlist",
            "relevance_label": "Relevant",
        },
    ]
    return pd.DataFrame(rows)


def _fetch_calendar_table() -> pd.DataFrame:
    if requests is None:
        raise RuntimeError("requests is not installed.")
    response = requests.get(OANDA_CALENDAR_URL, headers=REQUEST_HEADERS, timeout=20)
    response.raise_for_status()
    tables = pd.read_html(StringIO(response.text))
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


def _parse_event_datetime_et(row: pd.Series) -> pd.Timestamp | pd.NaT:
    if pd.isna(row.get("event_date")):
        return pd.NaT

    time_value = str(row.get("time", "")).strip().lower()
    if not time_value or time_value in {"nan", "none", "all day", "holiday", "tentative", "closed", "weekend", "today", "scheduled"}:
        return pd.NaT

    cleaned = (
        time_value.replace("et", "")
        .replace("edt", "")
        .replace("est", "")
        .replace(".", ":")
        .strip()
    )
    parsed_time = pd.to_datetime(cleaned, format="%H:%M", errors="coerce")
    if pd.isna(parsed_time):
        parsed_time = pd.to_datetime(cleaned, errors="coerce")
    if pd.isna(parsed_time):
        return pd.NaT

    event_date = pd.Timestamp(row["event_date"]).date()
    naive = pd.Timestamp.combine(event_date, parsed_time.time())
    return pd.Timestamp(naive, tz=ZoneInfo("America/New_York"))


def _release_proximity_fields(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    if out.empty:
        return out

    now_et = pd.Timestamp.now(tz=ZoneInfo("America/New_York"))
    if "event_date" in out.columns:
        out["event_datetime_et"] = out.apply(_parse_event_datetime_et, axis=1)
    else:
        out["event_datetime_et"] = pd.NaT

    mins: list[float | None] = []
    labels: list[str] = []
    urgencies: list[int] = []
    stamps: list[str] = []

    for value in out["event_datetime_et"].tolist():
        if pd.isna(value):
            mins.append(None)
            labels.append("Date/Time Pending")
            urgencies.append(10)
            stamps.append("Pending ET")
            continue

        minutes = int((value - now_et).total_seconds() // 60)
        mins.append(minutes)
        stamps.append(value.strftime("%b %d, %I:%M %p ET"))
        abs_minutes = abs(minutes)
        if minutes > 180:
            labels.append("Later")
        elif 60 < minutes <= 180:
            labels.append("Approaching")
        elif 0 <= minutes <= 60:
            labels.append("Imminent")
        elif -30 <= minutes < 0:
            labels.append("Live Window")
        else:
            labels.append("Passed")

        if minutes >= 0:
            urgency = max(20, 100 - min(minutes, 480) // 6)
        else:
            urgency = max(15, 85 - min(abs_minutes, 240) // 4)
        urgencies.append(int(urgency))

    out["minutes_to_release"] = mins
    out["release_status"] = labels
    out["urgency_score"] = urgencies
    out["release_stamp_et"] = stamps
    out["time_to_release"] = out["minutes_to_release"].apply(_format_minutes_to_release)
    return out


def _format_minutes_to_release(minutes: float | None) -> str:
    if minutes is None or pd.isna(minutes):
        return "Pending"
    minutes = int(minutes)
    if minutes > 0:
        hours, mins = divmod(minutes, 60)
        return f"In {hours}h {mins}m" if hours else f"In {mins}m"
    if minutes == 0:
        return "Now"
    minutes = abs(minutes)
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins}m ago" if hours else f"{mins}m ago"


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
    filtered = _release_proximity_fields(filtered)

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
        daily_note = "The daily board is in weekend mode and is therefore focused on market status rather than timed releases."
    else:
        if filtered["event_date"].notna().any():
            daily = filtered[filtered["event_date"] == today].copy()
        else:
            daily = filtered.copy()
            daily_note = "Structured event dates were not available, so the daily board is ordered by pair relevance rather than release time."
        daily = daily.head(8)
        if daily.empty:
            daily_note = "No pair-specific scheduled releases were identified for today."

    next_seven_days = pd.date_range(start=today, periods=7, freq="D")
    if filtered["event_date"].notna().any():
        weekly = filtered[filtered["event_date"].isin(next_seven_days)].copy()
        if weekly.empty:
            weekly_note = "No pair-specific scheduled releases were identified in the next seven days."
        weekly["day"] = weekly["event_date"].dt.strftime("%a")
        weekly["date_label"] = weekly["event_date"].dt.strftime("%Y-%m-%d")
        weekly = weekly.sort_values(["event_date", "event_datetime_et", "time", "relevance_score"], ascending=[True, True, True, False]).head(24)
    else:
        weekly = filtered.head(14).copy()
        weekly["day"] = "Upcoming"
        weekly["date_label"] = "Date unavailable"
        weekly_note = "Structured event dates were not available, so the weekly board is ordered by pair relevance instead of a strict seven-day schedule."

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
                "market_angle": _news_angle(text),
                "source": "OANDA Analysis",
            }
        )

    headlines = pd.DataFrame(rows)
    if headlines.empty:
        return pd.DataFrame(columns=["headline", "url", "relevance_score", "why_it_matters", "market_angle", "source"])
    headlines = headlines.sort_values(["relevance_score", "headline"], ascending=[False, True]).drop_duplicates("headline").head(10).reset_index(drop=True)
    headlines["relevance_label"] = headlines["relevance_score"].apply(
        lambda score: "High Relevance" if score >= 7 else "Relevant" if score >= 4 else "Peripheral"
    )
    return headlines


def _timeline_from_calendar(weekly: pd.DataFrame) -> pd.DataFrame:
    if weekly.empty:
        return pd.DataFrame(columns=["event", "release_stamp_et", "urgency_score", "release_status", "time_to_release", "country"])

    timeline = weekly.copy()
    cols = [col for col in ["event", "release_stamp_et", "urgency_score", "release_status", "time_to_release", "country", "event_datetime_et"] if col in timeline.columns]
    timeline = timeline[cols].copy()
    if "event_datetime_et" in timeline.columns:
        timeline = timeline.sort_values(["event_datetime_et", "urgency_score"], ascending=[True, False])
    else:
        timeline = timeline.sort_values("urgency_score", ascending=False)
    return timeline.head(12).reset_index(drop=True)


def fetch_market_context(symbol: str) -> MarketContextPacket:
    warnings: list[str] = []
    source_note = "Market context is sourced from OANDA pages when structured coverage is available."

    try:
        calendar = _fetch_calendar_table()
        daily, weekly, daily_note, weekly_note = _calendar_for_symbol(calendar, symbol)
    except Exception:
        daily, daily_note = _fallback_daily_watchlist(symbol)
        weekly, weekly_note = _fallback_weekly_watchlist(symbol)
        warnings.append("Structured economic-calendar coverage is temporarily unavailable. The event boards are showing the terminal's forex watchlist instead.")
        source_note = "Structured OANDA calendar coverage was unavailable, so the terminal is using its internal forex watchlist."

    try:
        headlines = _fetch_oanda_headlines(symbol)
    except Exception:
        headlines = _fallback_headlines(symbol)
        warnings.append("External FX headlines are temporarily unavailable. The news board is showing the terminal's internal relevance set instead.")
        source_note = "External market-context coverage was partially unavailable, so the terminal is supplementing with internal forex monitoring items."

    if daily.empty:
        daily, fallback_daily_note = _fallback_daily_watchlist(symbol)
        daily_note = daily_note or fallback_daily_note
    if weekly.empty:
        weekly, fallback_weekly_note = _fallback_weekly_watchlist(symbol)
        weekly_note = weekly_note or fallback_weekly_note
    if headlines.empty:
        headlines = _fallback_headlines(symbol)

    return MarketContextPacket(
        daily_calendar=daily,
        weekly_calendar=weekly,
        headlines=headlines,
        timeline=_timeline_from_calendar(weekly),
        source_note=source_note,
        warning=" | ".join(warnings) if warnings else None,
        daily_note=daily_note,
        weekly_note=weekly_note,
    )
