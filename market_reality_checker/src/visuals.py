from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go


def render_gauge(score: float, status: str) -> go.Figure:
    bar_color = "#f2f2ee" if status != "Suspicious" else "#d63a3a"
    figure = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={"font": {"size": 42, "family": "Source Serif 4, Georgia, serif", "color": "#f2f2ee"}},
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": "Integrity Score", "font": {"size": 14, "family": "IBM Plex Mono, monospace", "color": "#a8a8a2"}},
            gauge={
                "shape": "angular",
                "axis": {"range": [0, 100], "tickcolor": "#6f6f69", "tickfont": {"color": "#9d9d97"}},
                "bar": {"color": bar_color, "thickness": 0.34},
                "bgcolor": "rgba(255,255,255,0.03)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 35], "color": "rgba(214,58,58,0.12)"},
                    {"range": [35, 65], "color": "rgba(255,255,255,0.06)"},
                    {"range": [65, 100], "color": "rgba(255,255,255,0.11)"},
                ],
                "threshold": {"line": {"color": "#d63a3a", "width": 3}, "thickness": 0.7, "value": 65},
            },
        )
    )
    figure.update_layout(
        margin={"l": 20, "r": 20, "t": 18, "b": 0},
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        font={"color": "#f2f2ee", "family": "IBM Plex Mono, monospace"},
    )
    return figure


def render_chart(
    df: pd.DataFrame,
    injection_meta: dict[str, Any] | None = None,
) -> go.Figure:
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["close"],
            mode="lines",
            name="Price",
            line={"color": "#f4f4ef", "width": 2.15},
        )
    )

    flagged = df[df["anomaly_flag"]]
    if not flagged.empty:
        figure.add_trace(
            go.Scatter(
                x=flagged["timestamp"],
                y=flagged["close"],
                mode="markers",
                name="Integrity Alerts",
                marker={"symbol": "x", "size": 9, "color": "#d63a3a", "line": {"width": 1, "color": "#d63a3a"}},
            )
        )

    if injection_meta:
        figure.add_vrect(
            x0=df.loc[injection_meta["start_idx"], "timestamp"],
            x1=df.loc[injection_meta["end_idx"], "timestamp"],
            fillcolor="rgba(255,255,255,0.06)",
            line_width=0,
            annotation_text="Simulator window",
            annotation_position="top left",
        )

    figure.update_layout(
        height=520,
        margin={"l": 18, "r": 18, "t": 20, "b": 18},
        paper_bgcolor="#050505",
        plot_bgcolor="#050505",
        font={"color": "#f2f2ee", "family": "IBM Plex Mono, monospace"},
        legend={"orientation": "h", "x": 0, "y": 1.08, "bgcolor": "rgba(0,0,0,0)"},
        hovermode="x unified",
        xaxis={"showgrid": False, "title": None},
        yaxis={"gridcolor": "rgba(255,255,255,0.08)", "title": "Price"},
    )
    return figure
