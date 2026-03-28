from pathlib import Path

APP_NAME = "TruthLayer"
APP_SUBTITLE = "The Integrity Terminal"
APP_TAGLINE = "An explainable control layer for evaluating whether observed forex price formation remains consistent with its recent regime."
APP_DISCLAIMER = (
    "Research application built for short-horizon market verification. Uses recent Yahoo Finance forex data and should be treated as analytical decision support, not trading advice or a system of record."
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

DEFAULT_SYMBOL = "EUR/USD"
DEFAULT_INTERVAL = "5m"
DEFAULT_LOOKBACK = "1d"
SYMBOLS = {
    "EUR/USD": {"provider_symbol": "EURUSD=X"},
    "USD/JPY": {"provider_symbol": "JPY=X"},
    "GBP/USD": {"provider_symbol": "GBPUSD=X"},
    "AUD/USD": {"provider_symbol": "AUDUSD=X"},
    "USD/CHF": {"provider_symbol": "CHF=X"},
    "USD/CAD": {"provider_symbol": "CAD=X"},
}

CURRENCY_EVENT_MAP = {
    "EUR": ["Euro Area", "ECB", "Eurozone", "Germany", "France", "Italy", "Spain"],
    "USD": ["United States", "US", "Fed", "FOMC", "Treasury", "Nonfarm", "CPI", "PPI"],
    "JPY": ["Japan", "BOJ", "Tokyo"],
    "GBP": ["United Kingdom", "UK", "BOE", "Britain"],
    "AUD": ["Australia", "RBA"],
    "CHF": ["Switzerland", "SNB"],
    "CAD": ["Canada", "BOC"],
}

INTERVAL_CONFIG = {
    "1m": {"provider_interval": "1m", "provider_period": "1d", "freq": "1min"},
    "5m": {"provider_interval": "5m", "provider_period": "5d", "freq": "5min"},
    "15m": {"provider_interval": "15m", "provider_period": "5d", "freq": "15min"},
    "1h": {"provider_interval": "60m", "provider_period": "1mo", "freq": "1h"},
}

LOOKBACK_DAYS = {"1d": 1, "3d": 3, "5d": 5, "1w": 7}

ENGINE_CONFIG = {
    "return_window": 20,
    "vol_window": 20,
    "revert_window": 4,
    "drift_window": 10,
    "zscore_threshold": 3.0,
    "robust_zscore_threshold": 3.2,
    "vol_expansion_threshold": 3.4,
    "reversion_ratio": 0.70,
    "stale_after_minutes": {
        "1m": 8,
        "5m": 20,
        "15m": 45,
        "1h": 150,
    },
    "min_rows": 40,
    "score_weights": {
        "Return Spike": 24,
        "Volatility Shock": 10,
        "Jump-Revert": 28,
        "Directional Drift": 16,
        "Rule Confluence": 10,
    },
    "status_bands": {
        "Natural": 85,
        "Watchlist": 65,
    },
}

METHOD_RATIONALE = [
    {
        "name": "Return Spike",
        "why": "Large single-bar moves are often the clearest indication that current behavior has diverged from its recent distribution.",
        "used_for": "Identifies abrupt short-horizon displacement without making directional forecasts.",
    },
    {
        "name": "Volatility Shock",
        "why": "Important market dislocations often appear as volatility regime shifts rather than isolated returns.",
        "used_for": "Flags local instability when realized dispersion expands materially.",
    },
    {
        "name": "Jump-Revert",
        "why": "Sharp displacement followed by rapid reversion is a recognizable signature of unstable or low-conviction price formation.",
        "used_for": "Captures reversal patterns that are not fully explained by volatility alone.",
    },
    {
        "name": "Directional Drift",
        "why": "Some anomalous behavior emerges as persistent directional pressure rather than abrupt shocks.",
        "used_for": "Detects short-window one-sided movement that appears structurally unusual.",
    },
    {
        "name": "Pip Normalization",
        "why": "FX instruments do not share a common decimal scale, so raw price changes are not directly comparable across pairs.",
        "used_for": "Improves threshold consistency across major currency pairs.",
    },
    {
        "name": "Robust Statistics",
        "why": "Classical rolling statistics can be distorted by outliers; robust estimators are more stable in noisy live feeds.",
        "used_for": "Reduces false positives caused by a single abnormal observation contaminating the baseline.",
    },
    {
        "name": "Feed Freshness",
        "why": "Any integrity assessment is only as useful as the timeliness of the underlying data.",
        "used_for": "Surfaces staleness, sample depth, and latest-bar timing before interpretation.",
    },
]

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Source+Serif+4:wght@400;600;700&display=swap');

:root {
    --bg: #050505;
    --bg-soft: #0b0b0b;
    --panel: rgba(255,255,255,0.035);
    --panel-strong: rgba(255,255,255,0.055);
    --border: rgba(255,255,255,0.10);
    --border-strong: rgba(255,255,255,0.16);
    --text: #f5f5f1;
    --muted: #b0b0aa;
    --soft: #7a7a75;
    --shadow: rgba(0,0,0,0.34);
}

.stApp {
    background: linear-gradient(180deg, #030303 0%, #070707 50%, #040404 100%);
    color: var(--text);
}

* {
    font-family: "IBM Plex Mono", monospace;
}

.block-container {
    max-width: 1420px;
    padding-top: 1.2rem;
    padding-bottom: 2.3rem;
}

h1, h2, h3, h4 {
    font-family: "Source Serif 4", Georgia, serif !important;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(7,7,7,0.98), rgba(14,14,14,0.98));
    border-right: 1px solid var(--border);
}

[data-testid="stSidebar"] * {
    color: var(--text);
}

[data-testid="stMetric"] {
    background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.025));
    border: 1px solid var(--border);
    border-radius: 18px;
    box-shadow: none;
    padding: 0.9rem 0.95rem 0.8rem 0.95rem;
    min-height: 7.4rem;
}

[data-testid="stMetricLabel"] {
    color: var(--muted);
    font-size: 0.71rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    white-space: normal !important;
    overflow-wrap: anywhere;
    line-height: 1.35;
}

[data-testid="stMetricValue"] {
    font-family: "Source Serif 4", Georgia, serif !important;
    font-size: 1.6rem;
    white-space: normal !important;
    overflow-wrap: anywhere;
    line-height: 1.15;
}

[data-testid="stMetric"] > div {
    width: 100%;
}

.terminal-shell,
.terminal-panel,
.terminal-callout {
    background: linear-gradient(180deg, rgba(255,255,255,0.035), rgba(255,255,255,0.02));
    border: 1px solid var(--border);
    border-radius: 18px;
    box-shadow: none;
    backdrop-filter: blur(10px);
}

.terminal-shell {
    padding: 1.4rem 1.5rem;
}

.terminal-panel {
    padding: 1.1rem 1.2rem;
}

.hero-grid {
    display: grid;
    grid-template-columns: 1.5fr 0.9fr;
    gap: 1.1rem;
    align-items: stretch;
}

.hero-kicker,
.section-kicker,
.micro-label {
    color: var(--soft);
    font-size: 0.72rem;
    letter-spacing: 0.22em;
    text-transform: uppercase;
}

.hero-title {
    font-family: "Source Serif 4", Georgia, serif;
    font-size: 3.2rem;
    line-height: 0.98;
    margin: 0.15rem 0 0 0;
}

.hero-subtitle {
    font-size: 0.96rem;
    line-height: 1.6;
    max-width: 48rem;
    color: var(--muted);
    margin-top: 0.65rem;
}

.hero-right {
    border-left: 1px solid var(--border);
    padding-left: 1rem;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}

.hero-right p {
    color: var(--muted);
    line-height: 1.75;
}

.status-chip {
    display: inline-block;
    border-radius: 999px;
    border: 1px solid var(--border);
    padding: 0.36rem 0.66rem;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.18em;
    color: var(--text);
    margin-top: 0.5rem;
    background: rgba(255,255,255,0.03);
}

.info-band {
    border: 1px solid var(--border);
    border-radius: 22px;
    padding: 0.9rem 1rem;
    background: rgba(255,255,255,0.03);
    margin: 1rem 0 1.1rem 0;
    color: var(--muted);
}

.summary-grid {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 0.8rem;
    margin: 0.9rem 0 1rem 0;
}

.summary-card {
    background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.025));
    border: 1px solid var(--border);
    border-radius: 18px;
    padding: 0.95rem 1rem;
    min-height: 7.3rem;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}

.summary-label {
    color: var(--muted);
    font-size: 0.7rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    line-height: 1.35;
}

.summary-value {
    color: var(--text);
    font-family: "Source Serif 4", Georgia, serif;
    font-size: 1.45rem;
    line-height: 1.15;
    word-break: break-word;
}

.callout-label {
    color: var(--text);
    font-size: 0.75rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
}

.callout-description {
    margin-top: 0.5rem;
    color: var(--muted);
    line-height: 1.55;
    font-family: "Source Serif 4", Georgia, serif;
    font-size: 0.96rem;
}

.event-detail {
    color: var(--muted);
    font-size: 0.8rem;
    margin-top: 0.55rem;
    padding-top: 0.55rem;
    border-top: 1px solid rgba(255,255,255,0.08);
}

.alert-callout {
    border-color: var(--border-strong) !important;
}

.terminal-note {
    color: var(--soft);
    font-size: 0.8rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

.notice-panel {
    border-radius: 16px;
    border: 1px solid var(--border);
    background: rgba(255,255,255,0.04);
    color: var(--muted);
    padding: 0.8rem 0.95rem;
    margin: 0.7rem 0 0.9rem 0;
    line-height: 1.6;
}

.notice-subtle {
    background: rgba(255,255,255,0.025);
}

.source-caption {
    color: var(--soft);
    font-size: 0.76rem;
    letter-spacing: 0.08em;
    margin-top: 0.7rem;
}

.calendar-board {
    display: grid;
    gap: 0.8rem;
}

.calendar-item {
    background: linear-gradient(180deg, rgba(255,255,255,0.035), rgba(255,255,255,0.02));
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 0.95rem 1rem;
}

.calendar-topline {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: center;
    margin-bottom: 0.45rem;
}

.calendar-stamp {
    color: var(--soft);
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.16em;
}

.calendar-title {
    color: var(--text);
    font-size: 0.96rem;
    line-height: 1.5;
}

.calendar-meta {
    color: var(--muted);
    font-size: 0.8rem;
    margin-top: 0.35rem;
}

.calendar-reason {
    color: var(--soft);
    font-size: 0.77rem;
    margin-top: 0.55rem;
    letter-spacing: 0.06em;
}

.news-board {
    display: grid;
    gap: 0.8rem;
}

.news-item {
    background: linear-gradient(180deg, rgba(255,255,255,0.035), rgba(255,255,255,0.02));
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 1rem;
}

.news-meta {
    color: var(--soft);
    font-size: 0.72rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
}

.news-headline a {
    color: var(--text);
    text-decoration: none;
    font-family: "Source Serif 4", Georgia, serif;
    font-size: 0.98rem;
    line-height: 1.45;
}

.news-headline a:hover {
    text-decoration: underline;
}

.news-why {
    color: var(--muted);
    margin-top: 0.45rem;
    font-size: 0.86rem;
}

.stDataFrame, .stPlotlyChart {
    border-radius: 24px;
    overflow: hidden;
}

@media (max-width: 980px) {
    .summary-grid {
        grid-template-columns: 1fr 1fr;
    }

    .hero-grid {
        grid-template-columns: 1fr;
    }

    .hero-right {
        border-left: 0;
        border-top: 1px solid var(--border);
        padding-left: 0;
        padding-top: 1rem;
    }
}
</style>
"""
