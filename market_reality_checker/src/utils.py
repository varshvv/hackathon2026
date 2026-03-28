from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


def ensure_datetime_index(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with a normalized timestamp column."""
    frame = df.copy()
    if "timestamp" not in frame.columns:
        if frame.index.name:
            frame = frame.reset_index().rename(columns={frame.index.name: "timestamp"})
        else:
            frame = frame.reset_index().rename(columns={"index": "timestamp"})

    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce", utc=True)
    frame = frame.dropna(subset=["timestamp"]).sort_values("timestamp").drop_duplicates("timestamp")
    frame["timestamp"] = frame["timestamp"].dt.tz_convert(None)
    return frame.reset_index(drop=True)


def safe_series(values: Iterable[float], index: pd.Index | None = None) -> pd.Series:
    series = pd.Series(values, index=index, dtype="float64")
    return series.replace([np.inf, -np.inf], np.nan)


def rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    baseline = series.rolling(window=window, min_periods=max(3, window // 2)).mean()
    spread = series.rolling(window=window, min_periods=max(3, window // 2)).std(ddof=0)
    zscore = (series - baseline) / spread.replace(0, np.nan)
    return zscore.replace([np.inf, -np.inf], np.nan).fillna(0.0)


def contiguous_windows(mask: pd.Series, timestamps: pd.Series) -> list[dict]:
    windows: list[dict] = []
    active = False
    start_ts = None
    previous_ts = None

    for idx, flagged in enumerate(mask.fillna(False).astype(bool).tolist()):
        ts = timestamps.iloc[idx]
        if flagged and not active:
            active = True
            start_ts = ts
        if active and not flagged:
            windows.append({"start": start_ts, "end": previous_ts})
            active = False
        previous_ts = ts

    if active and start_ts is not None:
        windows.append({"start": start_ts, "end": previous_ts})

    return windows


def format_timestamp_list(values: list[pd.Timestamp], limit: int = 4) -> list[str]:
    shown = values[:limit]
    output = [ts.strftime("%Y-%m-%d %H:%M") for ts in shown]
    if len(values) > limit:
        output.append(f"+{len(values) - limit} more")
    return output


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def summarize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    preview = df[["timestamp", "close", "return", "rolling_volatility", "anomaly_score"]].copy()
    preview["close"] = preview["close"].round(5)
    preview["return"] = (preview["return"] * 10_000).round(2)
    preview["rolling_volatility"] = (preview["rolling_volatility"] * 10_000).round(2)
    preview["anomaly_score"] = preview["anomaly_score"].round(2)
    return preview.tail(12).rename(
        columns={
            "return": "return_bps",
            "rolling_volatility": "rolling_vol_bps",
        }
    )
