from __future__ import annotations

import pandas as pd
import streamlit as st

from config import (
    APP_DISCLAIMER,
    APP_NAME,
    APP_SUBTITLE,
    APP_TAGLINE,
    CSS,
    DEFAULT_INTERVAL,
    DEFAULT_LOOKBACK,
    DEFAULT_SYMBOL,
    ENGINE_CONFIG,
    INTERVAL_CONFIG,
    LOOKBACK_DAYS,
    SYMBOLS,
)
from src.data_manager import fetch_data
from src.engine import MarketEngine
from src.market_context import fetch_market_context
from src.visuals import render_chart, render_gauge, render_release_timeline

st.set_page_config(page_title=f"{APP_NAME} | {APP_SUBTITLE}", page_icon="◆", layout="wide", initial_sidebar_state="expanded")


@st.cache_data(show_spinner=False)
def get_dataset(symbol: str, interval: str, lookback: str):
    return fetch_data(symbol=symbol, interval=interval, lookback=lookback)


@st.cache_data(show_spinner=False, ttl=1800)
def get_market_context(symbol: str):
    return fetch_market_context(symbol)


def draw_header(result: dict | None) -> None:
    status = result["status"] if result else "Idle"
    score = result["integrity_score"] if result else 100.0
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="terminal-shell">
            <div class="hero-grid">
                <div>
                    <div class="hero-kicker">Market Integrity Monitor</div>
                    <div class="hero-title">{APP_NAME}<br>{APP_SUBTITLE}</div>
                    <div class="hero-subtitle">{APP_TAGLINE}</div>
                    <div class="status-chip">{status}</div>
                </div>
                <div class="hero-right">
                    <p>This application does not forecast direction. It evaluates whether observed price behavior remains coherent relative to the surrounding market regime.</p>
                    <div class="terminal-note">{APP_DISCLAIMER}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    gauge = render_gauge(score=score, status=status)
    st.plotly_chart(gauge, use_container_width=True)


def sidebar_controls() -> dict:
    with st.sidebar:
        st.markdown("## Controls")
        symbol = st.selectbox("Symbol", list(SYMBOLS.keys()), index=list(SYMBOLS.keys()).index(DEFAULT_SYMBOL))
        interval = st.selectbox("Interval", list(INTERVAL_CONFIG.keys()), index=list(INTERVAL_CONFIG.keys()).index(DEFAULT_INTERVAL))
        lookback = st.selectbox("Lookback", list(LOOKBACK_DAYS.keys()), index=list(LOOKBACK_DAYS.keys()).index(DEFAULT_LOOKBACK))
        analyze = st.button("Run Analysis", type="primary", use_container_width=True)
        st.caption("TruthLayer evaluates recent live forex bars from Yahoo Finance. If current data is unavailable, analysis does not proceed.")
    return {
        "symbol": symbol,
        "interval": interval,
        "lookback": lookback,
        "analyze": analyze,
    }


def render_notice(message: str, tone: str = "neutral") -> None:
    tone_class = "notice-panel"
    if tone == "subtle":
        tone_class += " notice-subtle"
    st.markdown(f'<div class="{tone_class}">{message}</div>', unsafe_allow_html=True)


def _assessment_definition(status: str) -> str:
    definitions = {
        "Stable": "Observed behavior remains aligned with the recent local regime.",
        "Under Review": "Observed behavior shows some stress relative to the local regime and warrants closer review.",
        "Escalated": "Observed behavior is not fully explained by the recent local regime.",
    }
    return definitions.get(status, "Assessment reflects the relationship between current price behavior and the recent local regime.")


def _clean_context_warning(message: str | None) -> str | None:
    if not message:
        return None
    lowered = message.lower()
    if "economic calendar unavailable" in lowered or "not enough values to unpack" in lowered:
        return "Structured economic-calendar coverage is temporarily unavailable. The event boards are showing the terminal's forex watchlist instead."
    if "headlines unavailable" in lowered:
        return "External FX headlines are temporarily unavailable. The news board is showing the terminal's internal relevance set instead."
    return message


def render_callouts(triggered_rules: list[dict], timestamps: list[str]) -> None:
    st.markdown("### Exception Summary")
    if not triggered_rules:
        st.markdown(
            """
            <div class="terminal-callout terminal-panel">
                <div class="callout-label">No Material Exceptions</div>
                <div class="callout-description">No active rule breached its review threshold. Recent price behavior remains aligned with the current baseline.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    for rule in triggered_rules:
        event_lines = ""
        if rule.get("events"):
            details: list[str] = []
            for event in rule["events"]:
                detail = (
                    f"{event['timestamp']} | {event['direction']} {abs(event['pip_move']):.2f} pips"
                )
                if "threshold" in event:
                    detail += f" vs envelope {event['threshold']:.2f} pips"
                elif "vol_ratio" in event:
                    detail += f" | vol ratio {event['vol_ratio']:.2f}x"
                elif "reversion_ratio" in event:
                    detail += f" | reversion {event['reversion_ratio']:.0f}%"
                elif "drift_z" in event:
                    detail += f" | drift z {event['drift_z']:.2f}"
                details.append(f'<div class="event-detail">{detail}</div>')
            event_lines = "".join(details)
        st.markdown(
            f"""
            <div class="terminal-callout terminal-panel alert-callout" style="margin-bottom:0.8rem;">
                <div class="callout-label">{rule['name']} | Impact {rule['impact']:.1f}</div>
                <div class="callout-description">{rule['description']}</div>
                <div class="terminal-note" style="margin-top:0.65rem;">Rationale: {rule['reason']}</div>
                {event_lines}
            </div>
            """,
            unsafe_allow_html=True,
        )

    if timestamps:
        st.caption("Flagged intervals: " + ", ".join(timestamps))


def render_summary(result: dict, packet, interval: str) -> None:
    now_et = pd.Timestamp.now(tz="America/New_York")
    weekend_market = now_et.dayofweek >= 5
    freshness = "Weekend Close" if weekend_market else (f"{packet.staleness_minutes} min" if packet.staleness_minutes is not None else "Unavailable")
    summary_cards = [
        ("Integrity Score", f"{result['integrity_score']:.1f}"),
        ("Assessment", result["status"]),
        ("Exceptions", str(result["active_alerts"])),
        ("Data Venue", "Yahoo Finance FX"),
        ("Feed State", freshness),
    ]
    summary_columns = st.columns(len(summary_cards))
    for column, (label, value) in zip(summary_columns, summary_cards):
        column.markdown(
            f"""
            <div class="summary-card">
                <div class="summary-label">{label}</div>
                <div class="summary-value">{value}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    render_notice(f"<strong>{result['status']}</strong> = {_assessment_definition(result['status'])}", tone="subtle")

    freshness_limit = ENGINE_CONFIG["stale_after_minutes"][interval]
    freshness_note = ""
    if packet.staleness_minutes is not None:
        if weekend_market:
            freshness_note = "The spot forex market is in its weekend closure window. Friday's final bar timing is therefore expected."
        elif packet.staleness_minutes <= freshness_limit:
            freshness_note = "Latest-bar timing remains within the expected tolerance for the selected interval."
        else:
            freshness_note = "Latest-bar timing is outside the expected tolerance for the selected interval."
    latest_bar = packet.latest_bar or "Unavailable"
    provider_symbol = ""
    if packet.note and "Symbol:" in packet.note:
        provider_symbol = packet.note.split("Symbol:", maxsplit=1)[1].split("|", maxsplit=1)[0].strip()
    provider_detail = f"{packet.provider or 'Yahoo Finance via yfinance'}"
    if provider_symbol:
        provider_detail += f" | Ticker: {provider_symbol}"
    provider_detail += f" | Latest bar: {latest_bar}"
    data_context = freshness_note or "Feed timing is unavailable."
    sample_depth = packet.row_count or "n/a"

    st.markdown(
        f"""
        <div class="info-band">
            <strong>Assessment:</strong> {result['summary']}<br>
            <span class="terminal-note">Market data:</span> {provider_detail}<br>
            <span class="terminal-note">Context:</span> {data_context} Sample depth: {sample_depth} observations.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if packet.staleness_minutes is not None and packet.staleness_minutes > freshness_limit and not weekend_market:
        render_notice(
            f"Latest-bar timing is slower than expected for the selected {interval} interval. Interpret the current assessment with additional caution.",
            tone="subtle",
        )


def render_feature_table(result: dict) -> None:
    st.markdown("### Diagnostic Snapshot")
    frame = pd.DataFrame(
        [{"Metric": key.replace("_", " ").title(), "Value": value} for key, value in result["features"].items()]
    )
    st.dataframe(frame, use_container_width=True, hide_index=True)


def render_methodology(result: dict) -> None:
    with st.expander("Methodology", expanded=False):
        st.markdown(
            "Each component is included to improve interpretability, cross-pair consistency, and signal discipline."
        )
        for item in result["methodology"]:
            st.markdown(f"**{item['name']}**")
            st.markdown(f"- Why: {item['why']}")
            st.markdown(f"- Function: {item['used_for']}")


def _today_calendar_frame(frame: pd.DataFrame) -> pd.DataFrame:
    today = pd.Timestamp.now().normalize()
    weekday = today.day_name()
    date_label = today.strftime("%Y-%m-%d")
    if today.dayofweek >= 5:
        return pd.DataFrame(
            [
                {
                    "day": weekday[:3],
                    "date_label": date_label,
                    "time": "Weekend",
                    "country": "FX Market",
                    "event": "Spot forex weekend pause",
                    "forecast": "-",
                    "actual": "-",
                    "previous": "-",
                    "why_it_matters": "Major spot forex liquidity is materially reduced, so scheduled event risk is limited until the market reopens.",
                    "release_status": "Weekend",
                    "time_to_release": "Closed",
                    "release_stamp_et": "Weekend ET",
                    "urgency_score": 5,
                }
            ]
        )

    if not frame.empty:
        return frame.copy()

    return pd.DataFrame(
        [
            {
                "day": weekday[:3],
                "date_label": date_label,
                "time": "Today",
                "country": "Macro Desk",
                "event": "No pair-linked event loaded for today",
                "forecast": "-",
                "actual": "-",
                "previous": "-",
                "why_it_matters": "No pair-specific scheduled release was loaded for today. The board remains available for discretionary monitoring.",
                "release_status": "Today",
                "time_to_release": "Open",
                "release_stamp_et": "Today ET",
                "urgency_score": 12,
            }
        ]
    )


def _weekly_schedule_frame(frame: pd.DataFrame) -> pd.DataFrame:
    today = pd.Timestamp.now().normalize()
    upcoming_days = pd.date_range(today, periods=7, freq="D")
    rows: list[dict] = []

    source = frame.copy() if not frame.empty else pd.DataFrame()
    if not source.empty:
        source["lookup_key"] = source.get("date_label", "").astype(str)

    for date_value in upcoming_days:
        date_label = date_value.strftime("%Y-%m-%d")
        day_label = date_value.strftime("%a")
        day_rows = pd.DataFrame()
        if not source.empty and "lookup_key" in source.columns:
            day_rows = source[source["lookup_key"] == date_label].copy()

        if day_rows.empty:
            if date_value.dayofweek >= 5:
                rows.append(
                    {
                        "day": day_label,
                        "date_label": date_label,
                        "time": "",
                        "country": "FX Market",
                        "event": "Weekend trading pause",
                        "forecast": "-",
                        "actual": "-",
                        "previous": "-",
                        "why_it_matters": "Liquidity and scheduled macro flow are typically lighter because major spot forex venues are closed.",
                        "release_status": "Weekend",
                        "time_to_release": "Closed",
                        "release_stamp_et": "Weekend ET",
                        "urgency_score": 5,
                    }
                )
            else:
                rows.append(
                    {
                        "day": day_label,
                        "date_label": date_label,
                        "time": "",
                        "country": "Macro Desk",
                        "event": "No pair-linked release loaded",
                        "forecast": "-",
                        "actual": "-",
                        "previous": "-",
                        "why_it_matters": "No pair-relevant scheduled release was parsed for this day. The board therefore displays a neutral placeholder.",
                        "release_status": "Scheduled",
                        "time_to_release": "Pending",
                        "release_stamp_et": f"{date_label} ET",
                        "urgency_score": 10,
                    }
                )
        else:
            rows.extend(day_rows.to_dict("records"))

    weekly = pd.DataFrame(rows)
    if "lookup_key" in weekly.columns:
        weekly = weekly.drop(columns=["lookup_key"])
    if not weekly.empty:
        weekly["time"] = ""
        weekly["release_stamp_et"] = weekly.get("date_label", "")
        weekly["time_to_release"] = ""
        weekly["release_status"] = weekly["release_status"].replace(
            {
                "Imminent": "This Week",
                "Approaching": "This Week",
                "Later": "This Week",
                "Live Window": "This Week",
                "Passed": "Earlier This Week",
                "Date/Time Pending": "Upcoming",
            }
        )
    return weekly.reset_index(drop=True)


def _render_calendar_cards(frame: pd.DataFrame, empty_message: str, show_intraday: bool = True) -> None:
    if frame.empty:
        render_notice(empty_message, tone="subtle")
        return

    st.markdown('<div class="calendar-board">', unsafe_allow_html=True)
    for row in frame.to_dict("records"):
        stamp_values = [row.get("day", ""), row.get("date_label", "")]
        if show_intraday:
            stamp_values.append(row.get("time", ""))
        stamp_parts = [part for part in stamp_values if part]
        stamp = " • ".join(stamp_parts)
        meta_parts = [part for part in [row.get("country", ""), row.get("forecast", ""), row.get("actual", ""), row.get("previous", "")] if part and part != "-"]
        meta = " | ".join(meta_parts)
        if show_intraday:
            status_fields = [row.get("release_status", ""), row.get("time_to_release", ""), row.get("release_stamp_et", "")]
        else:
            status_fields = [row.get("release_status", ""), row.get("country", "")]
        status_line = " | ".join([part for part in status_fields if part and part != "-"])
        st.markdown(
            f"""
            <div class="calendar-item">
                <div class="calendar-topline">
                    <div class="calendar-stamp">{stamp}</div>
                </div>
                <div class="calendar-title">{row.get('event', '')}</div>
                <div class="calendar-meta">{meta}</div>
                <div class="calendar-meta">{status_line}</div>
                <div class="calendar-reason">Market relevance: {row.get('why_it_matters', 'pair relevance')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def render_market_context(context_packet, symbol: str) -> None:
    timeline = getattr(context_packet, "timeline", pd.DataFrame())
    daily_note = getattr(context_packet, "daily_note", None)
    weekly_note = getattr(context_packet, "weekly_note", None)
    warning = _clean_context_warning(getattr(context_packet, "warning", None))
    headlines = getattr(context_packet, "headlines", pd.DataFrame())
    source_note = getattr(context_packet, "source_note", "Market context sources unavailable.")

    st.markdown("### Market Context")
    st.caption(f"For {symbol}, this panel surfaces scheduled macro events and relevant headlines with potential implications for short-horizon price formation.")

    if warning:
        render_notice(warning, tone="subtle")

    daily_tab, weekly_tab, news_tab = st.tabs(["Daily Calendar", "Weekly Calendar", "Relevant News"])

    with daily_tab:
        if daily_note:
            render_notice(daily_note, tone="subtle")
        _render_calendar_cards(_today_calendar_frame(context_packet.daily_calendar), "No daily event data could be loaded right now.", show_intraday=True)

    with weekly_tab:
        if weekly_note:
            render_notice(weekly_note, tone="subtle")
        st.plotly_chart(render_release_timeline(timeline), use_container_width=True)
        _render_calendar_cards(_weekly_schedule_frame(context_packet.weekly_calendar), "No weekly event data could be loaded right now.", show_intraday=False)

    with news_tab:
        if headlines.empty:
            render_notice("No relevant external headlines are available at the moment.", tone="subtle")
        else:
            st.markdown('<div class="news-board">', unsafe_allow_html=True)
            for row in headlines.to_dict("records"):
                st.markdown(
                    f"""
                    <div class="news-item">
                        <div class="news-meta">{row.get('source', 'Source')} • {row.get('market_angle', 'Macro')} • {row.get('relevance_label', 'Relevant')}</div>
                        <div class="news-headline"><a href="{row['url']}" target="_blank">{row['headline']}</a></div>
                        <div class="news-why">Market relevance: {row['why_it_matters']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            st.markdown("</div>", unsafe_allow_html=True)
        st.markdown(f'<div class="source-caption">{source_note}</div>', unsafe_allow_html=True)


def main() -> None:
    controls = sidebar_controls()
    engine = MarketEngine()

    if not controls["analyze"] and "last_result" not in st.session_state:
        draw_header(None)
        render_notice("Run the analysis to load the live market view. This terminal is forex-specific and evaluates current Yahoo Finance data only.", tone="subtle")
        return

    if controls["analyze"]:
        with st.spinner("Refreshing market data and running analytical checks..."):
            try:
                packet = get_dataset(
                    symbol=controls["symbol"],
                    interval=controls["interval"],
                    lookback=controls["lookback"],
                )
                context_packet = get_market_context(controls["symbol"])
                result = engine.analyze(packet.df.copy(), symbol=controls["symbol"])
                st.session_state["last_packet"] = packet
                st.session_state["last_context"] = context_packet
                st.session_state["last_result"] = result
            except Exception as exc:
                st.error(f"Analysis could not be completed: {exc}")
                return

    packet = st.session_state["last_packet"]
    context_packet = st.session_state.get("last_context")
    result = st.session_state["last_result"]

    draw_header(result)
    render_summary(result, packet, controls["interval"])

    left, right = st.columns([1.45, 1])
    with left:
        st.markdown("### Price Monitor")
        chart = render_chart(result["analysis_df"], injection_meta=None)
        st.plotly_chart(chart, use_container_width=True)
    with right:
        render_callouts(result["triggered_rules"], result["flag_timestamps"])

    render_feature_table(result)
    render_methodology(result)
    if context_packet is not None:
        render_market_context(context_packet, controls["symbol"])
    st.markdown("### Recent Observations")
    preview = result["analysis_df"][["timestamp", "close", "return_pips", "bar_range_pips", "rolling_volatility", "anomaly_score"]].tail(14).copy()
    preview["close"] = preview["close"].round(5)
    preview["return_pips"] = preview["return_pips"].round(2)
    preview["bar_range_pips"] = preview["bar_range_pips"].round(2)
    preview["rolling_volatility"] = (preview["rolling_volatility"] * 10000).round(2)
    st.dataframe(preview, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
