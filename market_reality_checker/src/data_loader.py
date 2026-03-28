from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

from config import INTERVAL_OPTIONS, SYMBOLS
from src.utils import ensure_datetime_index

try:
    import yfinance as yf
except Exception:  # pragma: no cover - import failure is handled downstream
    yf = None


@dataclass
class DataLoadResult:
    df: pd.DataFrame
    source: str
    warning: Optional[str] = None


def normalize_price_data(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize provider or sample data into a stable OHLC schema."""
    if df is None or df.empty:
        raise ValueError("Received empty market data.")

    frame = ensure_datetime_index(df)
    columns = {col.lower(): col for col in frame.columns}

    normalized = pd.DataFrame()
    normalized["timestamp"] = frame["timestamp"]
    normalized["open"] = frame[columns["open"]] if "open" in columns else frame[columns.get("close", "close")]
    normalized["high"] = frame[columns["high"]] if "high" in columns else normalized["open"]
    normalized["low"] = frame[columns["low"]] if "low" in columns else normalized["open"]
    normalized["close"] = frame[columns["close"]] if "close" in columns else normalized["open"]
    normalized["volume"] = frame[columns["volume"]] if "volume" in columns else 0.0

    normalized = normalized.dropna(subset=["close"]).sort_values("timestamp").reset_index(drop=True)
    normalized["volume"] = normalized["volume"].fillna(0.0)
    return normalized


def fetch_market_data(symbol: str, interval: str, lookback: str) -> pd.DataFrame:
    """Fetch recent data from yfinance using the configured symbol mapping."""
    if yf is None:
        raise RuntimeError("yfinance is not installed in this environment.")

    symbol_cfg = SYMBOLS[symbol]
    interval_cfg = INTERVAL_OPTIONS[interval]
    ticker = yf.Ticker(symbol_cfg["provider_symbol"])
    raw = ticker.history(
        interval=interval_cfg["provider_interval"],
        period=interval_cfg["provider_period"],
        auto_adjust=False,
        actions=False,
    )

    if raw.empty:
        raise ValueError("Provider returned no rows.")

    normalized = normalize_price_data(raw)
    days = {"1d": 1, "3d": 3, "5d": 5, "1w": 7}.get(lookback, 1)
    cutoff = normalized["timestamp"].max() - pd.Timedelta(days=days)
    filtered = normalized[normalized["timestamp"] >= cutoff].copy()
    if filtered.empty:
        raise ValueError("No rows available after lookback filtering.")
    return filtered.reset_index(drop=True)


def load_sample_data(path: Path | str) -> pd.DataFrame:
    sample_path = Path(path)
    if not sample_path.exists():
        raise FileNotFoundError(f"Sample data file not found: {sample_path}")
    raw = pd.read_csv(sample_path)
    return normalize_price_data(raw)


def get_market_data(symbol: str, interval: str, lookback: str) -> DataLoadResult:
    sample_path = SYMBOLS[symbol]["sample_path"]
    try:
        live_df = fetch_market_data(symbol=symbol, interval=interval, lookback=lookback)
        return DataLoadResult(df=live_df, source="live")
    except Exception as exc:
        fallback_df = load_sample_data(sample_path)
        warning = (
            "Live/recent data unavailable; using offline sample data for analysis. "
            f"Reason: {exc}"
        )
        return DataLoadResult(df=fallback_df, source="sample", warning=warning)
