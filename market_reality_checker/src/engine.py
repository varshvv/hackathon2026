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

    def _top_events(
        self,
        frame: pd.DataFrame,
        triggered: pd.Series,
        *,
        score_series: pd.Series,
        threshold_series: pd.Series | None = None,
        extra_fields: dict[str, pd.Series] | None = None,
        limit: int = 2,
    ) -> list[dict[str, Any]]:
        if not triggered.any():
            return []

        event_frame = frame.loc[triggered, ["timestamp", "return_pips"]].copy()
        event_frame["score"] = score_series.loc[triggered].fillna(0.0)
        if threshold_series is not None:
            event_frame["threshold"] = threshold_series.loc[triggered].fillna(0.0)
        if extra_fields:
            for name, series in extra_fields.items():
                event_frame[name] = series.loc[triggered]

        event_frame = event_frame.sort_values("score", ascending=False).head(limit)
        events: list[dict[str, Any]] = []
        for _, row in event_frame.iterrows():
            pip_move = float(row["return_pips"])
            event = {
                "timestamp": pd.Timestamp(row["timestamp"]).strftime("%Y-%m-%d %H:%M"),
                "direction": "Up" if pip_move >= 0 else "Down",
                "pip_move": round(pip_move, 2),
                "score": round(float(row["score"]), 2),
            }
            if "threshold" in row and pd.notna(row["threshold"]):
                event["threshold"] = round(float(row["threshold"]), 2)
            if extra_fields:
                for name in extra_fields:
                    if name in row and pd.notna(row[name]):
                        event[name] = round(float(row[name]), 2)
            events.append(event)
        return events

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
            "events": self._top_events(
                frame,
                triggered.fillna(False),
                score_series=severity_signal,
                threshold_series=pip_floor.fillna(0.0),
                extra_fields={
                    "return_z": zscore,
                    "robust_z": robust_z,
                },
            ),
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
            "events": self._top_events(
                frame,
                triggered.fillna(False),
                score_series=pd.concat([ratio, ratio_ewm], axis=1).max(axis=1),
                extra_fields={"vol_ratio": ratio, "ewm_ratio": ratio_ewm},
            ),
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
            "events": self._top_events(
                frame,
                triggered.fillna(False),
                score_series=severity_signal.fillna(0.0),
                extra_fields={"reversion_ratio": reversion_ratio * 100},
            ),
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
            "events": self._top_events(
                frame,
                triggered.fillna(False),
                score_series=(drift_z + sign_persistence).fillna(0.0),
                extra_fields={"drift_z": drift_z, "sign_persistence": sign_persistence * 100},
            ),
        }

    def _score(self, detections: list[dict[str, Any]]) -> dict[str, Any]:
        weights = self.config["score_weights"]
        suspiciousness = 0.0
        triggered = []
        for detection in detections:
            if not detection["triggered"]:
                continue
            weight = weights.get(detection["name"], 15)
            raw_severity = max(float(detection["severity"]), 0.0)
            normalized = min(np.log1p(raw_severity) / np.log(5.0), 1.25)
            event_count = max(len(detection.get("events", [])), 1)
            persistence_multiplier = min(1.0 + 0.08 * (event_count - 1), 1.24)
            impact = weight * normalized * persistence_multiplier
            suspiciousness += impact
            triggered.append(
                {
                    "name": detection["name"],
                    "impact": round(impact, 1),
                    "severity": round(normalized, 2),
                    "description": detection["description"],
                    "reason": detection.get("reason", ""),
                    "events": detection.get("events", []),
                }
            )

        if len(triggered) >= 2:
            suspiciousness += weights["Rule Confluence"]

        integrity_score = max(0.0, min(100.0, 100.0 - suspiciousness))
        if integrity_score >= self.config["status_bands"]["Natural"]:
            status = "Stable"
        elif integrity_score >= self.config["status_bands"]["Watchlist"]:
            status = "Under Review"
        else:
            status = "Escalated"

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
            "Observed behavior remains broadly consistent with the recent local regime."
            if not scored["triggered_rules"]
            else "Observed behavior is not fully explained by the recent local regime. Review the flagged intervals before relying on the move."
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
