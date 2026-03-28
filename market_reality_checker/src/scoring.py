from __future__ import annotations

from typing import Any

from config import SCORE_WEIGHTS, STATUS_THRESHOLDS
from src.utils import clamp


def classify_integrity(score: float) -> tuple[str, str]:
    if score >= STATUS_THRESHOLDS["normal"]:
        return "Normal", "Low"
    if score >= STATUS_THRESHOLDS["elevated"]:
        return "Elevated Risk", "Medium"
    return "Suspicious", "High"


def score_anomalies(detection_results: list[dict[str, Any]]) -> dict[str, Any]:
    suspiciousness = 0.0
    triggered_rules: list[dict[str, Any]] = []
    overlapping_windows = 0

    for result in detection_results:
        if not result["triggered"]:
            continue
        weight = SCORE_WEIGHTS.get(result["rule_name"], 10)
        severity = clamp(float(result["severity"]), 0.0, 1.6)
        impact = weight * severity
        suspiciousness += impact
        overlapping_windows += len(result.get("windows", []))
        triggered_rules.append(
            {
                "rule_name": result["rule_name"],
                "severity": round(severity, 2),
                "impact": round(impact, 2),
                "description": result["description"],
                "timestamps": result.get("timestamps", []),
            }
        )

    if len(triggered_rules) >= 3:
        suspiciousness += SCORE_WEIGHTS["Confluence Bonus"]
    if overlapping_windows >= 3:
        suspiciousness += SCORE_WEIGHTS["Persistence Bonus"]

    integrity_score = clamp(100 - suspiciousness, 0, 100)
    status_label, severity_label = classify_integrity(integrity_score)

    explanations = [rule["description"] for rule in triggered_rules[:4]]
    if not explanations:
        explanations = ["No statistically unusual short-window behavior was detected."]

    return {
        "integrity_score": round(integrity_score, 1),
        "status_label": status_label,
        "severity_label": severity_label,
        "triggered_rules": triggered_rules,
        "explanation_text": explanations,
    }
