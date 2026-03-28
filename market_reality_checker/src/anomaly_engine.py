from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from config import DETECTION_THRESHOLDS, ROLLING_WINDOWS
from src.scoring import score_anomalies
from src.utils import contiguous_windows, format_timestamp_list, rolling_zscore, safe_series


def compute_returns(df: pd.DataFrame) -> pd.Series:
    return safe_series(df["close"].pct_change().fillna(0.0), index=df.index)


def compute_acceleration(df: pd.DataFrame) -> pd.Series:
    returns = compute_returns(df)
    return safe_series(returns.diff().fillna(0.0), index=df.index)


def compute_rolling_volatility(df: pd.DataFrame, window: int) -> pd.Series:
    returns = compute_returns(df)
    return safe_series(returns.rolling(window=window, min_periods=max(3, window // 2)).std(ddof=0), index=df.index).fillna(0.0)


def _build_result(
    df: pd.DataFrame,
    rule_name: str,
    flag_mask: pd.Series,
    severity_signal: pd.Series,
    description: str,
) -> dict[str, Any]:
    timestamps = df.loc[flag_mask.fillna(False), "timestamp"].tolist()
    windows = contiguous_windows(flag_mask, df["timestamp"])
    severity = float(severity_signal[flag_mask.fillna(False)].abs().mean()) if flag_mask.any() else 0.0
    return {
        "rule_name": rule_name,
        "triggered": bool(flag_mask.any()),
        "severity": min(severity / 3.0, 1.5),
        "indices": df.index[flag_mask.fillna(False)].tolist(),
        "timestamps": format_timestamp_list(timestamps),
        "windows": windows,
        "description": description,
    }


def detect_return_spikes(df: pd.DataFrame, params: dict[str, Any]) -> dict[str, Any]:
    returns = df["return"]
    zscore = rolling_zscore(returns.abs(), params["return_z_window"])
    baseline = returns.abs().rolling(params["return_z_window"], min_periods=4).mean().fillna(returns.abs().mean())
    mask = (zscore > DETECTION_THRESHOLDS["return_z"]) | (
        returns.abs() > baseline * DETECTION_THRESHOLDS["return_abs_multiplier"]
    )
    return _build_result(
        df,
        "Return Spike",
        mask,
        zscore,
        "Large bar-to-bar moves exceeded the recent return envelope.",
    )


def detect_acceleration_anomalies(df: pd.DataFrame, params: dict[str, Any]) -> dict[str, Any]:
    acceleration = df["acceleration"]
    zscore = rolling_zscore(acceleration.abs(), params["return_z_window"])
    mask = zscore > DETECTION_THRESHOLDS["acceleration_z"]
    return _build_result(
        df,
        "Acceleration Shock",
        mask,
        zscore,
        "The speed of price changes shifted abruptly versus the recent pattern.",
    )


def detect_volatility_bursts(df: pd.DataFrame, params: dict[str, Any]) -> dict[str, Any]:
    rolling_vol = df["rolling_volatility"]
    zscore = rolling_zscore(rolling_vol, params["vol_window"])
    mask = zscore > DETECTION_THRESHOLDS["volatility_z"]
    return _build_result(
        df,
        "Volatility Burst",
        mask,
        zscore,
        "Short-window realized volatility expanded sharply relative to baseline.",
    )


def detect_jump_events(df: pd.DataFrame, params: dict[str, Any]) -> dict[str, Any]:
    price_delta = df["close"].diff().abs().fillna(0.0)
    zscore = rolling_zscore(price_delta, params["return_z_window"])
    mask = zscore > DETECTION_THRESHOLDS["jump_z"]
    return _build_result(
        df,
        "Jump Signature",
        mask,
        zscore,
        "One or more bars showed a jump-like displacement versus nearby bars.",
    )


def detect_drift_events(df: pd.DataFrame, params: dict[str, Any]) -> dict[str, Any]:
    drift_signal = df["return"].rolling(params["drift_window"], min_periods=4).sum().fillna(0.0)
    zscore = rolling_zscore(drift_signal.abs(), params["drift_window"])
    monotonic_bias = df["return"].rolling(params["drift_window"], min_periods=4).apply(
        lambda values: abs(np.sign(values).sum()) / max(len(values), 1), raw=False
    ).fillna(0.0)
    mask = (zscore > DETECTION_THRESHOLDS["drift_z"]) & (monotonic_bias > 0.7)
    return _build_result(
        df,
        "Drift Instability",
        mask,
        zscore + monotonic_bias,
        "Persistent one-direction movement emerged without a normal oscillation pattern.",
    )


def detect_jump_revert_patterns(df: pd.DataFrame, params: dict[str, Any]) -> dict[str, Any]:
    returns = df["return"].fillna(0.0)
    price_move = returns.abs()
    zscore = rolling_zscore(price_move, params["jump_revert_window"])
    reverse_strength = returns.shift(-1) * returns
    recovery_ratio = (returns.shift(-1).abs() / returns.abs().replace(0, np.nan)).fillna(0.0)
    mask = (
        (zscore > DETECTION_THRESHOLDS["jump_revert_return_z"])
        & (reverse_strength < 0)
        & (recovery_ratio > DETECTION_THRESHOLDS["jump_revert_recovery_ratio"])
    )
    return _build_result(
        df,
        "Jump-Revert Signature",
        mask,
        zscore + recovery_ratio,
        "A sharp move was followed by a rapid reversal, which can indicate unstable or synthetic behavior.",
    )


def run_analysis(df: pd.DataFrame) -> dict[str, Any]:
    frame = df.copy()
    if frame.empty or len(frame) < 12:
        raise ValueError("Not enough rows to run integrity analysis.")

    params = {
        "return_z_window": min(ROLLING_WINDOWS["return_z"], max(6, len(frame) // 5)),
        "vol_window": min(ROLLING_WINDOWS["volatility"], max(6, len(frame) // 5)),
        "drift_window": min(ROLLING_WINDOWS["drift"], max(5, len(frame) // 6)),
        "jump_revert_window": min(ROLLING_WINDOWS["jump_revert"], max(4, len(frame) // 8)),
    }

    frame["return"] = compute_returns(frame)
    frame["acceleration"] = compute_acceleration(frame)
    frame["rolling_volatility"] = compute_rolling_volatility(frame, params["vol_window"])
    frame["return_zscore"] = rolling_zscore(frame["return"].abs(), params["return_z_window"])
    frame["acceleration_zscore"] = rolling_zscore(frame["acceleration"].abs(), params["return_z_window"])
    frame["volatility_zscore"] = rolling_zscore(frame["rolling_volatility"], params["vol_window"])
    frame["drift_signal"] = frame["return"].rolling(params["drift_window"], min_periods=4).sum().fillna(0.0)

    detections = [
        detect_return_spikes(frame, params),
        detect_acceleration_anomalies(frame, params),
        detect_volatility_bursts(frame, params),
        detect_jump_events(frame, params),
        detect_drift_events(frame, params),
        detect_jump_revert_patterns(frame, params),
    ]

    anomaly_score = pd.Series(0.0, index=frame.index)
    suspicious_windows: list[dict[str, Any]] = []
    for detection in detections:
        if detection["triggered"]:
            anomaly_score.loc[detection["indices"]] += detection["severity"] * 10
            suspicious_windows.extend(
                [{**window, "rule_name": detection["rule_name"]} for window in detection["windows"]]
            )

    frame["anomaly_score"] = anomaly_score
    score = score_anomalies(detections)
    score["suspicious_windows"] = suspicious_windows
    score["features_snapshot"] = {
        "latest_close": round(float(frame["close"].iloc[-1]), 5),
        "latest_return_bps": round(float(frame["return"].iloc[-1] * 10_000), 2),
        "peak_return_z": round(float(frame["return_zscore"].abs().max()), 2),
        "peak_volatility_z": round(float(frame["volatility_zscore"].max()), 2),
        "max_anomaly_score": round(float(frame["anomaly_score"].max()), 2),
    }
    score["analysis_df"] = frame
    return score
