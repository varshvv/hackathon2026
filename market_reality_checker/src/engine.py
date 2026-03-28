from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from config import ENGINE_CONFIG, METHOD_RATIONALE


@dataclass
class MarketEngine:
    config: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        self.config = self.config or ENGINE_CONFIG

    def _pip_size(self, symbol: str) -> float:
        return 0.01 if "JPY" in symbol else 0.0001

    def _safe_zscore(self, series: pd.Series, window: int) -> pd.Series:
        mean = series.rolling(window=window, min_periods=max(5, window // 2)).mean()
        std = series.rolling(window=window, min_periods=max(5, window // 2)).std(ddof=0)
        zscore = (series - mean) / std.replace(0, np.nan)
        return zscore.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    def _robust_zscore(self, series: pd.Series, window: int) -> pd.Series:
        median = series.rolling(window=window, min_periods=max(5, window // 2)).median()
        mad = series.rolling(window=window, min_periods=max(5, window // 2)).apply(
            lambda x: np.median(np.abs(x - np.median(x))),
            raw=True,
        )
        robust = 0.6745 * (series - median) / mad.replace(0, np.nan)
        return robust.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    def _normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        frame = df.copy()
        if "timestamp" not in frame.columns:
            frame = frame.reset_index().rename(columns={"index": "timestamp"})
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce", utc=True)
        frame = frame.dropna(subset=["timestamp", "close"]).sort_values("timestamp").reset_index(drop=True)
        frame["timestamp"] = frame["timestamp"].dt.tz_convert(None)
        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
        frame["close"] = frame["close"].ffill().bfill()
        frame["open"] = pd.to_numeric(frame.get("open", frame["close"]), errors="coerce").fillna(frame["close"])
        frame["high"] = pd.to_numeric(frame.get("high", frame["close"]), errors="coerce").fillna(frame["close"])
        frame["low"] = pd.to_numeric(frame.get("low", frame["close"]), errors="coerce").fillna(frame["close"])
        volume_source = frame["volume"] if "volume" in frame.columns else pd.Series(0.0, index=frame.index)
        frame["volume"] = pd.to_numeric(volume_source, errors="coerce").fillna(0.0)
        return frame

    def _return_spikes(self, frame: pd.DataFrame) -> dict[str, Any]:
        returns = frame["return"].abs()
        zscore = frame["return_abs_z"]
        robust_z = frame["return_abs_robust_z"]
        pip_moves = frame["return_pips"].abs()
        pip_floor = pip_moves.rolling(self.config["return_window"], min_periods=5).median().fillna(0.0) * 2.2
        triggered = (
            ((zscore > self.config["zscore_threshold"]) | (robust_z > self.config["robust_zscore_threshold"]))
            & (pip_moves > pip_floor.fillna(0.0))
        )
        severity_signal = pd.concat([zscore, robust_z], axis=1).max(axis=1)
        severity = float(severity_signal[triggered].mean()) if triggered.any() else 0.0
        return {
            "name": "Return Spike",
            "triggered": bool(triggered.any()),
            "mask": triggered.fillna(False),
            "severity": severity,
            "description": "Pip-normalized returns exceeded both the classical and robust short-window envelope.",
            "reason": "Used because abnormal one-bar displacement is the clearest fast signal that local price motion may be structurally off-regime.",
        }

    def _volatility_shocks(self, frame: pd.DataFrame) -> dict[str, Any]:
        baseline = frame["rolling_volatility"].rolling(
            window=self.config["vol_window"], min_periods=max(5, self.config["vol_window"] // 2)
        ).mean()
        ewm_baseline = frame["ewm_volatility"].replace(0, np.nan)
        ratio = frame["rolling_volatility"] / baseline.replace(0, np.nan)
        ratio_ewm = frame["rolling_volatility"] / ewm_baseline
        ratio = ratio.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        ratio_ewm = ratio_ewm.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        triggered = (ratio > self.config["vol_expansion_threshold"]) & (ratio_ewm > 1.4)
        severity = float(pd.concat([ratio, ratio_ewm], axis=1).max(axis=1)[triggered].mean()) if triggered.any() else 0.0
        return {
            "name": "Volatility Shock",
            "triggered": bool(triggered.any()),
            "mask": triggered.fillna(False),
            "severity": severity,
            "description": "Realized volatility expanded materially versus both rolling and exponentially weighted baselines.",
            "reason": "Used because unstable tape is often a regime expansion problem, not just a single spike problem.",
        }

    def _jump_revert(self, frame: pd.DataFrame) -> dict[str, Any]:
        jump = (frame["return_abs_z"] > self.config["zscore_threshold"]) | (
            frame["return_abs_robust_z"] > self.config["robust_zscore_threshold"]
        )
        next_return = frame["return"].shift(-1)
        reversion_ratio = (next_return.abs() / frame["return"].abs().replace(0, np.nan)).fillna(0.0)
        reverse_direction = frame["return"] * next_return < 0
        triggered = jump & reverse_direction & (reversion_ratio >= self.config["reversion_ratio"]) & (
            frame["return_pips"].abs() > frame["return_pips"].abs().rolling(self.config["revert_window"], min_periods=3).median().fillna(0.0) * 2
        )
        severity_signal = pd.concat([frame["return_abs_z"], frame["return_abs_robust_z"]], axis=1).max(axis=1).where(triggered, 0.0) + reversion_ratio.where(triggered, 0.0)
        severity = float(severity_signal[triggered].mean()) if triggered.any() else 0.0
        return {
            "name": "Jump-Revert",
            "triggered": bool(triggered.any()),
            "mask": triggered.fillna(False),
            "severity": severity,
            "description": "A sharp displacement was rapidly retraced by at least 70 percent on the following bar.",
            "reason": "Used because fast reversal after a shock is one of the most intuitive suspicious-motion signatures in live demos and real workflows.",
        }

    def _directional_drift(self, frame: pd.DataFrame) -> dict[str, Any]:
        drift_sum = frame["return"].rolling(window=self.config["drift_window"], min_periods=5).sum()
        drift_z = self._safe_zscore(drift_sum.abs().fillna(0.0), self.config["drift_window"])
        sign_persistence = frame["return"].rolling(window=self.config["drift_window"], min_periods=5).apply(
            lambda x: abs(np.sign(x).sum()) / max(len(x), 1),
            raw=False,
        )
        triggered = (drift_z > 2.6) & (sign_persistence > 0.85)
        severity = float((drift_z + sign_persistence)[triggered].mean()) if triggered.any() else 0.0
        return {
            "name": "Directional Drift",
            "triggered": bool(triggered.any()),
            "mask": triggered.fillna(False),
            "severity": severity,
            "description": "Directional persistence accumulated beyond what the short-term regime normally supports.",
            "reason": "Used because suspicious motion can be gradual and persistent rather than explosive.",
        }

    def _score(self, detections: list[dict[str, Any]]) -> dict[str, Any]:
        weights = self.config["score_weights"]
        suspiciousness = 0.0
        triggered = []
        for detection in detections:
            if not detection["triggered"]:
                continue
            weight = weights.get(detection["name"], 15)
            normalized = min(max(float(detection["severity"]) / 3.0, 0.0), 1.5)
            impact = weight * normalized
            suspiciousness += impact
            triggered.append(
                {
                    "name": detection["name"],
                    "impact": round(impact, 1),
                    "severity": round(normalized, 2),
                    "description": detection["description"],
                    "reason": detection.get("reason", ""),
                }
            )

        if len(triggered) >= 2:
            suspiciousness += weights["Rule Confluence"]

        integrity_score = max(0.0, min(100.0, 100.0 - suspiciousness))
        if integrity_score >= self.config["status_bands"]["Natural"]:
            status = "Natural"
        elif integrity_score >= self.config["status_bands"]["Watchlist"]:
            status = "Watchlist"
        else:
            status = "Suspicious"

        return {
            "integrity_score": round(integrity_score, 1),
            "status": status,
            "active_alerts": len(triggered),
            "triggered_rules": triggered,
        }

    def analyze(self, df: pd.DataFrame, symbol: str = "EUR/USD") -> dict[str, Any]:
        frame = self._normalize(df)
        if len(frame) < self.config["min_rows"]:
            raise ValueError(f"At least {self.config['min_rows']} rows are required for analysis.")

        pip_size = self._pip_size(symbol)
        frame["return"] = frame["close"].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
        frame["return_pips"] = (frame["close"].diff() / pip_size).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        frame["bar_range_pips"] = ((frame["high"] - frame["low"]) / pip_size).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        frame["return_abs_z"] = self._safe_zscore(frame["return"].abs(), self.config["return_window"])
        frame["return_abs_robust_z"] = self._robust_zscore(frame["return"].abs(), self.config["return_window"])
        frame["rolling_volatility"] = frame["return"].rolling(
            window=self.config["vol_window"], min_periods=max(5, self.config["vol_window"] // 2)
        ).std(ddof=0).fillna(0.0)
        frame["ewm_volatility"] = frame["return"].ewm(span=self.config["vol_window"], adjust=False, min_periods=5).std(
            bias=False
        ).fillna(0.0)

        detections = [
            self._return_spikes(frame),
            self._volatility_shocks(frame),
            self._jump_revert(frame),
            self._directional_drift(frame),
        ]

        anomaly_flag = pd.Series(False, index=frame.index)
        anomaly_score = pd.Series(0.0, index=frame.index)
        for detection in detections:
            if not detection["triggered"]:
                continue
            anomaly_flag |= detection["mask"]
            anomaly_score.loc[detection["mask"]] += min(float(detection["severity"]) * 12, 20)

        scored = self._score(detections)
        frame["anomaly_flag"] = anomaly_flag.fillna(False)
        frame["anomaly_score"] = anomaly_score.round(2)

        timestamps = frame.loc[frame["anomaly_flag"], "timestamp"].dt.strftime("%Y-%m-%d %H:%M").tolist()
        scored["summary"] = (
            "Motion is broadly consistent with the prevailing regime."
            if not scored["triggered_rules"]
            else "Multiple structural checks detected motion that deserves verification before trust."
        )
        scored["flag_timestamps"] = timestamps[:8]
        scored["analysis_df"] = frame
        scored["features"] = {
            "last_price": round(float(frame["close"].iloc[-1]), 5),
            "last_return_bp": round(float(frame["return"].iloc[-1] * 10000), 2),
            "last_move_pips": round(float(frame["return_pips"].iloc[-1]), 2),
            "peak_return_z": round(float(frame["return_abs_z"].max()), 2),
            "peak_robust_return_z": round(float(frame["return_abs_robust_z"].max()), 2),
            "peak_volatility_bp": round(float(frame["rolling_volatility"].max() * 10000), 2),
            "max_bar_range_pips": round(float(frame["bar_range_pips"].max()), 2),
        }
        scored["methodology"] = METHOD_RATIONALE
        scored["pair"] = symbol
        return scored
