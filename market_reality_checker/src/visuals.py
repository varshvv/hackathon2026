from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go


def render_gauge(score: float, status: str) -> go.Figure:
    bar_color = "#f2f2ee"
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
                    {"range": [0, 35], "color": "rgba(255,255,255,0.03)"},
                    {"range": [35, 65], "color": "rgba(255,255,255,0.06)"},
                    {"range": [65, 100], "color": "rgba(255,255,255,0.10)"},
                ],
                "threshold": {"line": {"color": "#f2f2ee", "width": 2}, "thickness": 0.7, "value": 65},
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
                marker={"symbol": "x", "size": 8, "color": "#f2f2ee", "line": {"width": 1, "color": "#f2f2ee"}},
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


def render_release_timeline(timeline: pd.DataFrame) -> go.Figure:
    figure = go.Figure()
    if timeline.empty:
        figure.update_layout(
            height=280,
            paper_bgcolor="#050505",
            plot_bgcolor="#050505",
            font={"color": "#f2f2ee", "family": "IBM Plex Mono, monospace"},
            annotations=[
                {
                    "text": "No timed releases available",
                    "xref": "paper",
                    "yref": "paper",
                    "x": 0.5,
                    "y": 0.5,
                    "showarrow": False,
                    "font": {"size": 16},
                }
            ],
        )
        return figure

    ordered = timeline.copy()
    ordered["display_label"] = ordered["event"].str.slice(0, 46)
    color_map = {
        "Imminent": "#f2f2ee",
        "Approaching": "#f2f2ee",
        "Later": "#a8a8a2",
        "Live Window": "#f2f2ee",
        "Passed": "#666660",
        "Date/Time Pending": "#8a8a84",
    }
    colors = [color_map.get(value, "#f2f2ee") for value in ordered["release_status"]]
    customdata = ordered[["release_stamp_et", "time_to_release", "country", "release_status"]].fillna("").values

    figure.add_trace(
        go.Bar(
            x=ordered["urgency_score"],
            y=ordered["display_label"],
            orientation="h",
            marker={"color": colors, "line": {"color": "rgba(255,255,255,0.12)", "width": 1}},
            customdata=customdata,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Release: %{customdata[0]}<br>"
                "Timing: %{customdata[1]}<br>"
                "Country: %{customdata[2]}<br>"
                "Status: %{customdata[3]}<extra></extra>"
            ),
            name="Release Urgency",
        )
    )
    figure.update_layout(
        height=340,
        margin={"l": 18, "r": 18, "t": 20, "b": 18},
        paper_bgcolor="#050505",
        plot_bgcolor="#050505",
        font={"color": "#f2f2ee", "family": "IBM Plex Mono, monospace"},
        xaxis={"title": "Release Urgency", "gridcolor": "rgba(255,255,255,0.08)", "range": [0, 100]},
        yaxis={"title": None, "autorange": "reversed"},
        showlegend=False,
    )
    return figure
