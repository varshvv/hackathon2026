from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go


def plot_price_with_flags(
    df: pd.DataFrame,
    suspicious_windows: list[dict[str, Any]],
    injection_metadata: dict[str, Any] | None = None,
) -> go.Figure:
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["close"],
            mode="lines",
            name="Close",
            line={"color": "#F5F5F0", "width": 2.2},
        )
    )

    flagged = df[df["anomaly_score"] > 0]
    if not flagged.empty:
        figure.add_trace(
            go.Scatter(
                x=flagged["timestamp"],
                y=flagged["close"],
                mode="markers",
                name="Suspicious Motion",
                marker={"size": 8, "color": "#FFFFFF", "symbol": "diamond-open"},
            )
        )

    for window in suspicious_windows:
        start = window["start"]
        end = window["end"]
        if pd.isna(start) or pd.isna(end):
            continue
        figure.add_vrect(
            x0=start,
            x1=end,
            fillcolor="rgba(255,255,255,0.09)",
            line_width=0,
            annotation_text=window["rule_name"],
            annotation_position="top left",
        )

    if injection_metadata:
        start_idx = injection_metadata["start_idx"]
        end_idx = injection_metadata["end_idx"]
        figure.add_vrect(
            x0=df.loc[start_idx, "timestamp"],
            x1=df.loc[end_idx, "timestamp"],
            fillcolor="rgba(255,255,255,0.14)",
            line_width=0,
            annotation_text="Injected anomaly",
            annotation_position="bottom left",
        )

    figure.update_layout(
        height=480,
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
        paper_bgcolor="#060606",
        plot_bgcolor="#060606",
        font={"color": "#F4F4F1", "family": "Baskerville, Times New Roman, serif"},
        legend={"orientation": "h", "y": 1.08, "x": 0},
        xaxis={"showgrid": False, "title": ""},
        yaxis={"gridcolor": "rgba(255,255,255,0.10)", "title": "Price"},
        hovermode="x unified",
    )
    return figure
