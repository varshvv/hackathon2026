from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from config import DEMO_SEED


@dataclass
class SimulationResult:
    df: pd.DataFrame
    metadata: dict


def _pick_index(length: int, width: int, seed: int, index: Optional[int] = None) -> int:
    if index is not None:
        return max(3, min(index, max(3, length - width - 2)))
    rng = np.random.default_rng(seed)
    return int(rng.integers(low=8, high=max(9, length - width - 3)))


def _sync_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["open"] = out["close"].shift(1).fillna(out["close"])
    spread = out["close"].rolling(3, min_periods=1).std().fillna(0) * 0.6
    out["high"] = np.maximum(out["open"], out["close"]) + spread
    out["low"] = np.minimum(out["open"], out["close"]) - spread
    return out


def inject_spike(
    df: pd.DataFrame,
    direction: str,
    magnitude: float,
    index: Optional[int] = None,
    seed: int = DEMO_SEED,
) -> SimulationResult:
    out = df.copy()
    idx = _pick_index(len(out), width=1, seed=seed, index=index)
    factor = 1 + magnitude if direction == "up" else 1 - magnitude
    out.loc[idx, "close"] = out.loc[idx, "close"] * factor
    out = _sync_ohlc(out)
    return SimulationResult(
        df=out,
        metadata={
            "anomaly_type": "Spike Up" if direction == "up" else "Spike Down",
            "start_idx": idx,
            "end_idx": idx,
            "timestamps": [out.loc[idx, "timestamp"]],
        },
    )


def inject_volatility_burst(
    df: pd.DataFrame,
    magnitude: float,
    width: int = 8,
    index: Optional[int] = None,
    seed: int = DEMO_SEED,
) -> SimulationResult:
    out = df.copy()
    idx = _pick_index(len(out), width=width, seed=seed, index=index)
    rng = np.random.default_rng(seed)
    pattern = rng.choice([-1, 1], size=width) * rng.uniform(magnitude * 0.4, magnitude, size=width)
    for offset, shock in enumerate(pattern):
        out.loc[idx + offset, "close"] = out.loc[idx + offset - 1, "close"] * (1 + shock)
    out = _sync_ohlc(out)
    return SimulationResult(
        df=out,
        metadata={
            "anomaly_type": "Volatility Burst",
            "start_idx": idx,
            "end_idx": idx + width - 1,
            "timestamps": out.loc[idx : idx + width - 1, "timestamp"].tolist(),
        },
    )


def inject_drift(
    df: pd.DataFrame,
    magnitude: float,
    width: int = 10,
    index: Optional[int] = None,
    seed: int = DEMO_SEED,
) -> SimulationResult:
    out = df.copy()
    idx = _pick_index(len(out), width=width, seed=seed, index=index)
    incremental = np.linspace(magnitude / width, magnitude, width)
    for offset, drift in enumerate(incremental):
        base_price = out.loc[idx + offset - 1, "close"] if offset > 0 else out.loc[idx, "close"]
        out.loc[idx + offset, "close"] = base_price * (1 + drift / width)
    out = _sync_ohlc(out)
    return SimulationResult(
        df=out,
        metadata={
            "anomaly_type": "Drift",
            "start_idx": idx,
            "end_idx": idx + width - 1,
            "timestamps": out.loc[idx : idx + width - 1, "timestamp"].tolist(),
        },
    )


def inject_jump_revert(
    df: pd.DataFrame,
    magnitude: float,
    width: int = 5,
    index: Optional[int] = None,
    seed: int = DEMO_SEED,
) -> SimulationResult:
    out = df.copy()
    idx = _pick_index(len(out), width=width, seed=seed, index=index)
    base = out.loc[idx - 1, "close"]
    out.loc[idx, "close"] = base * (1 + magnitude)
    out.loc[idx + 1, "close"] = base * (1 + magnitude * 0.45)
    out.loc[idx + 2, "close"] = base * (1 + magnitude * 0.1)
    out.loc[idx + 3, "close"] = base * (1 - magnitude * 0.08)
    out.loc[idx + 4, "close"] = base * (1 + magnitude * 0.03)
    out = _sync_ohlc(out)
    return SimulationResult(
        df=out,
        metadata={
            "anomaly_type": "Jump and Revert",
            "start_idx": idx,
            "end_idx": idx + width - 1,
            "timestamps": out.loc[idx : idx + width - 1, "timestamp"].tolist(),
        },
    )


def apply_simulation(
    df: pd.DataFrame,
    anomaly_type: str,
    severity: float,
    width: int,
    index: Optional[int] = None,
    seed: int = DEMO_SEED,
) -> SimulationResult:
    if anomaly_type == "Spike Up":
        return inject_spike(df, direction="up", magnitude=severity, index=index, seed=seed)
    if anomaly_type == "Spike Down":
        return inject_spike(df, direction="down", magnitude=severity, index=index, seed=seed)
    if anomaly_type == "Volatility Burst":
        return inject_volatility_burst(df, magnitude=severity, width=width, index=index, seed=seed)
    if anomaly_type == "Drift":
        return inject_drift(df, magnitude=severity, width=width, index=index, seed=seed)
    if anomaly_type == "Jump and Revert":
        return inject_jump_revert(df, magnitude=severity, width=max(width, 5), index=index, seed=seed)
    raise ValueError(f"Unsupported anomaly type: {anomaly_type}")
