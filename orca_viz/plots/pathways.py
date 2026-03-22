from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ..i18n import tr
from ..plot_theme import apply_standard_2d_style, resolve_visual_style

def create_path_figure(
    data: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str,
    x_label: str,
    y_label: str | None = None,
    y_hover_format: str = ".8f",
    y_suffix: str = " Eh",
    highlight_index: int | None = None,
    visual_style_key: str | None = None,
) -> go.Figure:
    style = resolve_visual_style(visual_style_key)
    palette = style.palette
    figure = go.Figure()
    if data.empty:
        apply_standard_2d_style(
            figure,
            title=title,
            xaxis_title=x_label,
            yaxis_title=y_label or tr("能量 (Hartree)"),
            showlegend=False,
            visual_style_key=style.key,
        )
        return figure
    plot_data = data.sort_values(x_col).reset_index(drop=True)
    plot_data["_point_index"] = plot_data.index
    axis_label = y_label or tr("能量 (Hartree)")
    hovertemplate = _path_hover_template(plot_data, x_label, axis_label, y_hover_format, y_suffix)

    if "branch_id" in plot_data.columns and plot_data["branch_id"].dropna().nunique() > 1:
        color_cycle = list(style.path_branch_colors)
        for branch_index, branch_id in enumerate(plot_data["branch_id"].fillna("unknown").unique()):
            branch_data = plot_data[plot_data["branch_id"].fillna("unknown") == branch_id]
            figure.add_trace(
                go.Scatter(
                    x=branch_data[x_col],
                    y=branch_data[y_col],
                    mode="lines+markers",
                    name=str(branch_id),
                    line={"color": color_cycle[branch_index % len(color_cycle)], "width": 3.2 * style.line_scale},
                    marker={
                        "color": palette["accent_primary_light"],
                        "size": 8.0 * style.marker_scale,
                        "line": {"color": palette["bar_edge"], "width": 1.0},
                    },
                    customdata=_path_custom_data(branch_data),
                    hovertemplate=hovertemplate,
                )
            )
    else:
        figure.add_trace(
            go.Scatter(
                x=plot_data[x_col],
                y=plot_data[y_col],
                mode="lines+markers",
                line={"color": palette["accent_primary"], "width": 3.4 * style.line_scale},
                marker={
                    "color": palette["accent_primary_light"],
                    "size": 8.5 * style.marker_scale,
                    "line": {"color": palette["bar_edge"], "width": 1.2},
                },
                customdata=_path_custom_data(plot_data),
                hovertemplate=hovertemplate,
                showlegend=False,
            )
        )
    if "point_type" in plot_data.columns and (plot_data["point_type"] != "image").any():
        highlight_points = plot_data[plot_data["point_type"] != "image"]
        figure.add_trace(
            go.Scatter(
                x=highlight_points[x_col],
                y=highlight_points[y_col],
                mode="markers+text",
                text=highlight_points["label"] if "label" in highlight_points.columns else None,
                textposition="top center",
                marker={
                    "color": palette["accent_positive"],
                    "size": 12 * style.marker_scale,
                    "symbol": "diamond",
                    "line": {"color": palette["bar_edge"], "width": 1.4},
                },
                customdata=_path_custom_data(highlight_points),
                hovertemplate=hovertemplate,
                showlegend=False,
            )
        )
    highest_row = plot_data.loc[plot_data[y_col].idxmax()]
    figure.add_trace(
        go.Scatter(
            x=[highest_row[x_col]],
            y=[highest_row[y_col]],
            mode="markers",
            marker={
                "color": palette["accent_warning"],
                "size": 13 * style.marker_scale,
                "symbol": "star",
                "line": {"color": palette["bar_edge"], "width": 1.4},
            },
            customdata=_path_custom_data(highest_row.to_frame().T),
            hovertemplate=hovertemplate,
            showlegend=False,
        )
    )
    if highlight_index is not None and 0 <= highlight_index < len(plot_data):
        highlight_row = plot_data.iloc[int(highlight_index)]
        figure.add_trace(
            go.Scatter(
                x=[highlight_row[x_col]],
                y=[highlight_row[y_col]],
                mode="markers",
                marker={
                    "color": palette["path_current"],
                    "size": 14 * style.marker_scale,
                    "symbol": "circle-open-dot",
                    "line": {"color": palette["text_primary"], "width": 1.3},
                },
                customdata=_path_custom_data(highlight_row.to_frame().T),
                hovertemplate=hovertemplate,
                name=tr("当前帧"),
                showlegend=False,
            )
        )
    apply_standard_2d_style(
        figure,
        title=title,
        xaxis_title=x_label,
        yaxis_title=axis_label,
        showlegend="branch_id" in plot_data.columns and plot_data["branch_id"].dropna().nunique() > 1,
        margin={"l": 76, "r": 20, "t": 58, "b": 60},
        visual_style_key=style.key,
    )
    return figure


def _path_custom_data(data: pd.DataFrame):
    if "label" in data.columns:
        point_index = data["_point_index"] if "_point_index" in data.columns else data.index
        return pd.DataFrame({"label": data["label"], "point_index": point_index}).to_numpy()
    return None


def _path_hover_template(
    plot_data: pd.DataFrame,
    x_label: str,
    axis_label: str,
    y_hover_format: str,
    y_suffix: str,
) -> str:
    if "label" in plot_data.columns:
        return (
            "%{customdata[0]}<br>"
            f"{x_label}=%{{x}}<br>{axis_label}=%{{y:{y_hover_format}}}{y_suffix}<extra></extra>"
        )
    return f"{x_label}=%{{x}}<br>{axis_label}=%{{y:{y_hover_format}}}{y_suffix}<extra></extra>"
