from pathlib import Path

APP_NAME = "TruthLayer"
APP_SUBTITLE = "The Integrity Terminal"
APP_TAGLINE = "A verification layer that assesses whether market price action looks natural or suspicious."
APP_DISCLAIMER = (
    "Explainable prototype for hackathon demonstration. Uses recent live Yahoo Finance forex data when available. Not a trading signal or surveillance-grade compliance system."
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

DEFAULT_SYMBOL = "EUR/USD"
DEFAULT_INTERVAL = "5m"
DEFAULT_LOOKBACK = "1d"
DEFAULT_MODE = "Live Mode"
DEFAULT_INJECTION = "Jump-Revert"
DEFAULT_SEED = 21

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

SIMULATION_TYPES = ["Spike Up", "Spike Down", "Drift", "Jump-Revert"]

METHOD_RATIONALE = [
    {
        "name": "Return Spike",
        "why": "Large one-bar moves are the fastest visible sign that price behavior may have detached from its recent regime.",
        "used_for": "Captures sudden short-term displacement without pretending to forecast direction.",
    },
    {
        "name": "Volatility Shock",
        "why": "Sometimes the move is not a single spike, but a regime break where dispersion expands all at once.",
        "used_for": "Flags unstable tape when the entire local environment becomes noisier than normal.",
    },
    {
        "name": "Jump-Revert",
        "why": "A sharp move followed by quick reversion is a strong visual signature of unnatural or low-conviction motion.",
        "used_for": "Improves demo clarity and catches suspicious structures that simple volatility rules can miss.",
    },
    {
        "name": "Directional Drift",
        "why": "Not all suspicious behavior is spike-shaped. Some anomalies creep in one direction more persistently than expected.",
        "used_for": "Detects short-window one-way motion that looks structurally unusual rather than explosive.",
    },
    {
        "name": "Pip Normalization",
        "why": "Forex pairs do not move on the same price scale. USD/JPY and EUR/USD need to be compared in pip terms, not raw decimals.",
        "used_for": "Makes thresholds more consistent across major FX pairs.",
    },
    {
        "name": "Robust Statistics",
        "why": "Classical rolling z-scores can be distorted by outliers. Median and MAD are more stable in noisy live feeds.",
        "used_for": "Improves accuracy and reduces false alarms from a single abnormal bar contaminating the baseline.",
    },
    {
        "name": "Feed Freshness",
        "why": "A verdict is only useful if the tape is recent enough to trust.",
        "used_for": "Surfaces staleness, row count, and latest bar timing so the user can judge data quality before believing the score.",
    },
]

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Source+Serif+4:wght@400;600;700&display=swap');

:root {
    --bg: #060606;
    --bg-soft: #0d0d0d;
    --panel: rgba(255,255,255,0.045);
    --panel-strong: rgba(255,255,255,0.07);
    --border: rgba(255,255,255,0.12);
    --border-strong: rgba(255,255,255,0.18);
    --text: #f3f3ef;
    --muted: #b5b5ae;
    --soft: #878780;
    --alert: #d63a3a;
    --shadow: rgba(0,0,0,0.42);
}

.stApp {
    background:
        radial-gradient(circle at top left, rgba(255,255,255,0.04), transparent 22%),
        linear-gradient(180deg, #030303 0%, #090909 50%, #050505 100%);
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
    background: linear-gradient(180deg, var(--panel-strong), var(--panel));
    border: 1px solid var(--border);
    border-radius: 24px;
    box-shadow: 0 24px 48px var(--shadow);
    padding: 1rem 1rem 0.85rem 1rem;
}

[data-testid="stMetricLabel"] {
    color: var(--muted);
    font-size: 0.71rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
}

[data-testid="stMetricValue"] {
    font-family: "Source Serif 4", Georgia, serif !important;
    font-size: 2rem;
}

.terminal-shell,
.terminal-panel,
.terminal-callout {
    background: linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.025));
    border: 1px solid var(--border);
    border-radius: 26px;
    box-shadow: 0 28px 60px var(--shadow);
    backdrop-filter: blur(14px);
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
    font-size: 3.7rem;
    line-height: 0.95;
    margin: 0.15rem 0 0 0;
}

.hero-subtitle {
    font-size: 1.02rem;
    line-height: 1.7;
    max-width: 56rem;
    color: var(--muted);
    margin-top: 0.85rem;
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
    border: 1px solid var(--border-strong);
    padding: 0.42rem 0.78rem;
    font-size: 0.74rem;
    text-transform: uppercase;
    letter-spacing: 0.18em;
    color: var(--text);
    margin-top: 0.5rem;
}

.info-band {
    border: 1px solid var(--border);
    border-radius: 22px;
    padding: 0.9rem 1rem;
    background: rgba(255,255,255,0.03);
    margin: 1rem 0 1.1rem 0;
    color: var(--muted);
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
    line-height: 1.7;
    font-family: "Source Serif 4", Georgia, serif;
    font-size: 1rem;
}

.alert-callout {
    border-color: rgba(214,58,58,0.42) !important;
    box-shadow: 0 24px 52px rgba(214,58,58,0.12);
}

.terminal-note {
    color: var(--soft);
    font-size: 0.8rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

.stAlert {
    border-radius: 18px;
    border: 1px solid var(--border);
    background: rgba(255,255,255,0.05);
}

.calendar-board {
    display: grid;
    gap: 0.8rem;
}

.calendar-item {
    background: linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.025));
    border: 1px solid var(--border);
    border-radius: 22px;
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

.stDataFrame, .stPlotlyChart {
    border-radius: 24px;
    overflow: hidden;
}

@media (max-width: 980px) {
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
