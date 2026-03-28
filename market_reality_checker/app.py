from __future__ import annotations

import pandas as pd
import streamlit as st

from config import (
    APP_DISCLAIMER,
    APP_NAME,
    APP_SUBTITLE,
    APP_TAGLINE,
    CSS,
    DEFAULT_INJECTION,
    DEFAULT_INTERVAL,
    DEFAULT_LOOKBACK,
    DEFAULT_MODE,
    DEFAULT_SEED,
    DEFAULT_SYMBOL,
    ENGINE_CONFIG,
    INTERVAL_CONFIG,
    LOOKBACK_DAYS,
    SIMULATION_TYPES,
    SYMBOLS,
)
from src.data_manager import fetch_data, inject_anomaly
from src.engine import MarketEngine
from src.market_context import fetch_market_context
from src.visuals import render_chart, render_gauge

st.set_page_config(page_title=f"{APP_NAME} | {APP_SUBTITLE}", page_icon="◆", layout="wide", initial_sidebar_state="expanded")


@st.cache_data(show_spinner=False)
def get_dataset(symbol: str, interval: str, lookback: str, seed: int):
    return fetch_data(symbol=symbol, interval=interval, lookback=lookback, seed=seed)


@st.cache_data(show_spinner=False, ttl=1800)
def get_market_context(symbol: str):
    return fetch_market_context(symbol)


def draw_header(result: dict | None) -> None:
    status = result["status"] if result else "Awaiting Run"
    score = result["integrity_score"] if result else 100.0
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="terminal-shell">
            <div class="hero-grid">
                <div>
                    <div class="hero-kicker">Private-Bank Terminal</div>
                    <div class="hero-title">{APP_NAME}<br>{APP_SUBTITLE}</div>
                    <div class="hero-subtitle">{APP_TAGLINE}</div>
                    <div class="status-chip">{status}</div>
                </div>
                <div class="hero-right">
                    <p>This console does not forecast. It verifies whether the price behavior already on screen looks coherent enough to trust.</p>
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
        st.markdown("## Terminal Controls")
        symbol = st.selectbox("Symbol", list(SYMBOLS.keys()), index=list(SYMBOLS.keys()).index(DEFAULT_SYMBOL))
        interval = st.selectbox("Interval", list(INTERVAL_CONFIG.keys()), index=list(INTERVAL_CONFIG.keys()).index(DEFAULT_INTERVAL))
        lookback = st.selectbox("Lookback", list(LOOKBACK_DAYS.keys()), index=list(LOOKBACK_DAYS.keys()).index(DEFAULT_LOOKBACK))
        mode = st.radio("Mode", [DEFAULT_MODE, "Simulator Mode"], index=0)
        severity = 0.018
        width = 4
        injection = DEFAULT_INJECTION
        if mode == "Simulator Mode":
            st.markdown("### Injection")
            injection = st.selectbox("Pattern", SIMULATION_TYPES, index=SIMULATION_TYPES.index(DEFAULT_INJECTION))
            severity = st.slider("Severity", min_value=0.005, max_value=0.06, value=0.018, step=0.001)
            width = st.slider("Width", min_value=3, max_value=12, value=4, step=1)

        seed = st.number_input("Deterministic Seed", min_value=1, max_value=9999, value=DEFAULT_SEED, step=1)
        analyze = st.button("Run Integrity Audit", type="primary", use_container_width=True)
        st.caption("Live mode uses real Yahoo Finance forex data only. If the feed is unavailable, the audit stops and shows an error.")
    return {
        "symbol": symbol,
        "interval": interval,
        "lookback": lookback,
        "mode": mode,
        "injection": injection,
        "severity": severity,
        "width": width,
        "seed": seed,
        "analyze": analyze,
    }


def render_callouts(triggered_rules: list[dict], timestamps: list[str]) -> None:
    st.markdown("### Premium Trigger Feed")
    if not triggered_rules:
        st.markdown(
            """
            <div class="terminal-callout terminal-panel">
                <div class="callout-label">Security Callout | Clear Tape</div>
                <div class="callout-description">No structural rule crossed its escalation threshold. Current motion reads as statistically coherent.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    for rule in triggered_rules:
        st.markdown(
            f"""
            <div class="terminal-callout terminal-panel alert-callout" style="margin-bottom:0.8rem;">
                <div class="callout-label">{rule['name']} | Impact {rule['impact']:.1f} | Severity {rule['severity']:.2f}</div>
                <div class="callout-description">{rule['description']}</div>
                <div class="terminal-note" style="margin-top:0.65rem;">Why used: {rule['reason']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if timestamps:
        st.caption("Flagged windows: " + ", ".join(timestamps))


def render_summary(result: dict, packet, interval: str, simulation_meta: dict | None) -> None:
    metrics = st.columns(5)
    metrics[0].metric("Integrity", f"{result['integrity_score']:.1f}")
    metrics[1].metric("Status", result["status"])
    metrics[2].metric("Active Alerts", result["active_alerts"])
    metrics[3].metric("Data Source", "Live Forex Feed")
    freshness = f"{packet.staleness_minutes} min" if packet.staleness_minutes is not None else "n/a"
    metrics[4].metric("Feed Freshness", freshness)

    freshness_limit = ENGINE_CONFIG["stale_after_minutes"][interval]
    freshness_note = ""
    if packet.staleness_minutes is not None:
        freshness_note = (
            "Feed freshness is within the expected window."
            if packet.staleness_minutes <= freshness_limit
            else "Feed may be stale for the selected interval, so treat the verdict with caution."
        )
    context_note = packet.note or "Provider: Yahoo Finance via yfinance."
    if simulation_meta:
        context_note = f"Simulator injected {simulation_meta['anomaly_type']} across {', '.join(simulation_meta['timestamps'][:3])}."

    st.markdown(
        f"""
        <div class="info-band">
            <strong>Desk Summary:</strong> {result['summary']}<br>
            <span class="terminal-note">Context:</span> {context_note}<br>
            <span class="terminal-note">Quality:</span> {freshness_note} Rows loaded: {packet.row_count or 'n/a'}.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if packet.staleness_minutes is not None and packet.staleness_minutes > freshness_limit:
        st.warning(
            f"Latest bar is {packet.staleness_minutes} minutes old for the selected {interval} interval. The feed may be stale."
        )


def render_feature_table(result: dict) -> None:
    st.markdown("### System Readout")
    frame = pd.DataFrame(
        [{"Metric": key.replace("_", " ").title(), "Value": value} for key, value in result["features"].items()]
    )
    st.dataframe(frame, use_container_width=True, hide_index=True)


def render_methodology(result: dict) -> None:
    with st.expander("Why These Checks Exist", expanded=False):
        st.markdown(
            "Each component is included to improve explainability, cross-pair consistency, and live-demo trustworthiness."
        )
        for item in result["methodology"]:
            st.markdown(f"**{item['name']}**")
            st.markdown(f"- Why: {item['why']}")
            st.markdown(f"- Used for: {item['used_for']}")


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
                    "why_it_matters": "Major spot forex trading is largely closed, so scheduled price-sensitive flow is limited until the market reopens.",
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
                "why_it_matters": "The current source did not provide a scheduled release for this pair today, but the board remains active for manual monitoring.",
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
                        "time": "Weekend",
                        "country": "FX Market",
                        "event": "Weekend trading pause",
                        "forecast": "-",
                        "actual": "-",
                        "previous": "-",
                        "why_it_matters": "Liquidity and scheduled macro flow are typically lighter because major spot forex markets are closed.",
                    }
                )
            else:
                rows.append(
                    {
                        "day": day_label,
                        "date_label": date_label,
                        "time": "Scheduled",
                        "country": "Macro Desk",
                        "event": "No pair-linked release loaded",
                        "forecast": "-",
                        "actual": "-",
                        "previous": "-",
                        "why_it_matters": "No relevant scheduled event was parsed for this day, so the board shows a clean placeholder instead of leaving the schedule blank.",
                    }
                )
        else:
            rows.extend(day_rows.to_dict("records"))

    weekly = pd.DataFrame(rows)
    if "lookup_key" in weekly.columns:
        weekly = weekly.drop(columns=["lookup_key"])
    return weekly.reset_index(drop=True)


def _render_calendar_cards(frame: pd.DataFrame, empty_message: str) -> None:
    if frame.empty:
        st.info(empty_message)
        return

    st.markdown('<div class="calendar-board">', unsafe_allow_html=True)
    for row in frame.to_dict("records"):
        stamp_parts = [part for part in [row.get("day", ""), row.get("date_label", ""), row.get("time", "")] if part]
        stamp = " • ".join(stamp_parts)
        meta_parts = [part for part in [row.get("country", ""), row.get("forecast", ""), row.get("actual", ""), row.get("previous", "")] if part and part != "-"]
        meta = " | ".join(meta_parts)
        st.markdown(
            f"""
            <div class="calendar-item">
                <div class="calendar-topline">
                    <div class="calendar-stamp">{stamp}</div>
                </div>
                <div class="calendar-title">{row.get('event', '')}</div>
                <div class="calendar-meta">{meta}</div>
                <div class="calendar-reason">Why it matters: {row.get('why_it_matters', 'pair relevance')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


def render_market_context(context_packet, symbol: str) -> None:
    st.markdown("### Event And Announcement Calendar")
    st.caption(f"For {symbol}, the terminal surfaces scheduled macro events and relevant OANDA headlines that may affect price action.")

    if context_packet.warning:
        st.warning(context_packet.warning)

    daily_tab, weekly_tab, news_tab = st.tabs(["Daily Calendar", "Weekly Calendar", "Relevant News"])

    with daily_tab:
        if context_packet.daily_note:
            st.info(context_packet.daily_note)
        _render_calendar_cards(_today_calendar_frame(context_packet.daily_calendar), "No daily event data could be loaded right now.")

    with weekly_tab:
        if context_packet.weekly_note:
            st.info(context_packet.weekly_note)
        _render_calendar_cards(_weekly_schedule_frame(context_packet.weekly_calendar), "No weekly event data could be loaded right now.")

    with news_tab:
        if context_packet.headlines.empty:
            st.info("No relevant OANDA headlines could be loaded right now.")
        else:
            for row in context_packet.headlines.to_dict("records"):
                st.markdown(
                    f"- [{row['headline']}]({row['url']}) — {row['why_it_matters']}"
                )
            st.caption(context_packet.source_note)


def main() -> None:
    controls = sidebar_controls()
    engine = MarketEngine()

    if not controls["analyze"] and "last_result" not in st.session_state:
        draw_header(None)
        st.info("Run the integrity audit to load the terminal. This build is forex-only and uses live Yahoo Finance data rather than synthetic fallback.")
        return

    if controls["analyze"]:
        with st.spinner("Refreshing tape and running integrity checks..."):
            try:
                packet = get_dataset(
                    symbol=controls["symbol"],
                    interval=controls["interval"],
                    lookback=controls["lookback"],
                    seed=controls["seed"],
                )
                context_packet = get_market_context(controls["symbol"])
                working_df = packet.df.copy()
                simulation_meta = None
                if controls["mode"] == "Simulator Mode":
                    working_df, simulation_meta = inject_anomaly(
                        working_df,
                        anomaly_type=controls["injection"],
                        severity=controls["severity"],
                        width=controls["width"],
                        seed=controls["seed"],
                    )
                result = engine.analyze(working_df, symbol=controls["symbol"])
                st.session_state["last_packet"] = packet
                st.session_state["last_context"] = context_packet
                st.session_state["last_result"] = result
                st.session_state["last_simulation"] = simulation_meta
            except Exception as exc:
                st.error(f"TruthLayer could not complete the audit safely: {exc}")
                return

    packet = st.session_state["last_packet"]
    context_packet = st.session_state.get("last_context")
    result = st.session_state["last_result"]
    simulation_meta = st.session_state.get("last_simulation")

    draw_header(result)
    render_summary(result, packet, controls["interval"], simulation_meta)

    left, right = st.columns([1.45, 1])
    with left:
        st.markdown("### Monochrome Price Terminal")
        chart = render_chart(result["analysis_df"], injection_meta=simulation_meta)
        st.plotly_chart(chart, use_container_width=True)
    with right:
        render_callouts(result["triggered_rules"], result["flag_timestamps"])

    render_feature_table(result)
    render_methodology(result)
    if context_packet is not None:
        render_market_context(context_packet, controls["symbol"])
    st.markdown("### Tape Preview")
    preview = result["analysis_df"][["timestamp", "close", "return_pips", "bar_range_pips", "rolling_volatility", "anomaly_score"]].tail(14).copy()
    preview["close"] = preview["close"].round(5)
    preview["return_pips"] = preview["return_pips"].round(2)
    preview["bar_range_pips"] = preview["bar_range_pips"].round(2)
    preview["rolling_volatility"] = (preview["rolling_volatility"] * 10000).round(2)
    st.dataframe(preview, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
