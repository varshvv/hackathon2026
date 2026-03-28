from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from config import DEFAULT_SEED, INTERVAL_CONFIG, LOOKBACK_DAYS, SYMBOLS

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None


@dataclass
class DataPacket:
    df: pd.DataFrame
    source: str
    note: str | None = None
    provider: str | None = None
    latest_bar: str | None = None
    staleness_minutes: int | None = None
    row_count: int | None = None


def _normalize(raw: pd.DataFrame) -> pd.DataFrame:
    if raw is None or raw.empty:
        raise ValueError("Empty dataset")

    frame = raw.copy()
    if "timestamp" not in frame.columns:
        if frame.index.name:
            frame = frame.reset_index().rename(columns={frame.index.name: "timestamp"})
        else:
            frame = frame.reset_index().rename(columns={"index": "timestamp"})

    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce", utc=True)
    frame = frame.dropna(subset=["timestamp"]).sort_values("timestamp").drop_duplicates("timestamp")
    frame["timestamp"] = frame["timestamp"].dt.tz_convert(None)

    lowered = {col.lower(): col for col in frame.columns}
    normalized = pd.DataFrame()
    normalized["timestamp"] = frame["timestamp"]
    normalized["close"] = pd.to_numeric(frame[lowered["close"]], errors="coerce")
    normalized["open"] = pd.to_numeric(frame[lowered.get("open", lowered["close"])], errors="coerce")
    normalized["high"] = pd.to_numeric(frame[lowered.get("high", lowered["close"])], errors="coerce")
    normalized["low"] = pd.to_numeric(frame[lowered.get("low", lowered["close"])], errors="coerce")
    normalized["volume"] = pd.to_numeric(frame[lowered["volume"]], errors="coerce") if "volume" in lowered else 0.0
    normalized = normalized.replace([np.inf, -np.inf], np.nan).dropna(subset=["close"]).reset_index(drop=True)
    normalized["open"] = normalized["open"].fillna(normalized["close"])
    normalized["high"] = normalized["high"].fillna(normalized["close"])
    normalized["low"] = normalized["low"].fillna(normalized["close"])
    normalized["volume"] = normalized["volume"].fillna(0.0)
    return normalized


def fetch_data(symbol: str, interval: str, lookback: str, seed: int = DEFAULT_SEED) -> DataPacket:
    provider_symbol = SYMBOLS[symbol]["provider_symbol"]
    interval_cfg = INTERVAL_CONFIG[interval]

    if yf is None:
        raise RuntimeError("yfinance is unavailable, so the app cannot access the live forex feed.")

    ticker = yf.Ticker(provider_symbol)
    raw = ticker.history(
        interval=interval_cfg["provider_interval"],
        period=interval_cfg["provider_period"],
        auto_adjust=False,
        actions=False,
    )
    live_df = _normalize(raw)
    cutoff = live_df["timestamp"].max() - pd.Timedelta(days=LOOKBACK_DAYS.get(lookback, 1))
    live_df = live_df[live_df["timestamp"] >= cutoff].reset_index(drop=True)

    if live_df.empty:
        raise RuntimeError(f"No live forex rows were returned for {symbol} from Yahoo Finance.")

    latest_dt = live_df["timestamp"].max()
    latest_ts = latest_dt.strftime("%Y-%m-%d %H:%M")
    now_utc = pd.Timestamp.now(tz="UTC").tz_convert(None)
    staleness_minutes = int(max((now_utc - latest_dt).total_seconds() // 60, 0))
    return DataPacket(
        df=live_df,
        source="live",
        note=f"Provider: Yahoo Finance via yfinance | Symbol: {provider_symbol} | Latest bar: {latest_ts}",
        provider="Yahoo Finance via yfinance",
        latest_bar=latest_ts,
        staleness_minutes=staleness_minutes,
        row_count=len(live_df),
    )


def inject_anomaly(
    df: pd.DataFrame,
    anomaly_type: str,
    severity: float,
    width: int,
    seed: int = DEFAULT_SEED,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = df.copy().reset_index(drop=True)
    rng = np.random.default_rng(seed)
    width = max(3, int(width))
    idx = int(rng.integers(low=15, high=max(16, len(frame) - width - 3)))
    metadata: dict[str, Any] = {
        "anomaly_type": anomaly_type,
        "start_idx": idx,
        "end_idx": idx + width - 1,
    }

    if anomaly_type == "Spike Up":
        frame.loc[idx, "close"] *= 1 + severity
        metadata["end_idx"] = idx
    elif anomaly_type == "Spike Down":
        frame.loc[idx, "close"] *= 1 - severity
        metadata["end_idx"] = idx
    elif anomaly_type == "Drift":
        increments = np.linspace(severity / width, severity, width)
        for offset, step in enumerate(increments):
            anchor = frame.loc[idx + offset - 1, "close"] if offset > 0 else frame.loc[idx, "close"]
            frame.loc[idx + offset, "close"] = anchor * (1 + step / width)
    elif anomaly_type == "Jump-Revert":
        base = frame.loc[idx - 1, "close"]
        frame.loc[idx, "close"] = base * (1 + severity)
        frame.loc[idx + 1, "close"] = base * (1 + severity * 0.25)
        frame.loc[idx + 2, "close"] = base * (1 - severity * 0.72)
        frame.loc[idx + 3, "close"] = base * (1 + severity * 0.05)
        metadata["end_idx"] = idx + 3
    else:
        raise ValueError(f"Unsupported anomaly type: {anomaly_type}")

    frame["open"] = frame["close"].shift(1).fillna(frame["close"])
    spread = frame["close"].rolling(3, min_periods=1).std(ddof=0).fillna(0.0) + frame["close"].abs() * 0.00015
    frame["high"] = np.maximum(frame["open"], frame["close"]) + spread
    frame["low"] = np.minimum(frame["open"], frame["close"]) - spread
    metadata["timestamps"] = frame.loc[metadata["start_idx"] : metadata["end_idx"], "timestamp"].dt.strftime(
        "%Y-%m-%d %H:%M"
    ).tolist()
    return frame, metadata
