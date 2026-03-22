from __future__ import annotations

from typing import Any

import plotly.graph_objects as go


SCIENTIFIC_FONT_FAMILY = '"Avenir Next", "Helvetica Neue", "PingFang SC", "Microsoft YaHei", sans-serif'
CHART_SURFACE_BG = "#f8fafc"
CHART_PAPER_BG = "#ffffff"
TEXT_PRIMARY = "#0f172a"
TEXT_MUTED = "#475569"
GRID_COLOR = "rgba(148, 163, 184, 0.22)"
AXIS_COLOR = "#334155"
BORDER_COLOR = "#cbd5e1"

ACCENT_TEAL = "#0f766e"
ACCENT_TEAL_DARK = "#115e59"
ACCENT_RED = "#be123c"
ACCENT_RED_DARK = "#9f1239"
ACCENT_BLUE = "#1d4ed8"
ACCENT_BLUE_LIGHT = "#60a5fa"
ACCENT_GOLD = "#d97706"
ACCENT_VIOLET = "#7c3aed"
ACCENT_SLATE = "#64748b"
ACCENT_ORANGE = "#f97316"

PAPER_CAMERA = {"eye": {"x": 1.54, "y": 1.42, "z": 1.18}}
CUBE_CAMERA = {"eye": {"x": 1.68, "y": 1.48, "z": 1.22}}
STRUCTURE_CAMERA = {"eye": {"x": 1.38, "y": 1.32, "z": 1.08}}


def base_layout() -> dict[str, Any]:
    return {
        "template": "plotly_white",
        "paper_bgcolor": CHART_PAPER_BG,
        "plot_bgcolor": CHART_PAPER_BG,
        "font": {"family": SCIENTIFIC_FONT_FAMILY, "size": 14, "color": TEXT_PRIMARY},
        "title": {
            "font": {"family": SCIENTIFIC_FONT_FAMILY, "size": 20, "color": TEXT_PRIMARY},
            "x": 0.01,
            "xanchor": "left",
            "y": 0.98,
            "yanchor": "top",
        },
        "margin": {"l": 72, "r": 28, "t": 62, "b": 60},
        "hoverlabel": {
            "bgcolor": "rgba(255,255,255,0.96)",
            "bordercolor": BORDER_COLOR,
            "font": {"family": SCIENTIFIC_FONT_FAMILY, "size": 13, "color": TEXT_PRIMARY},
        },
        "legend": {
            "orientation": "h",
            "y": 1.04,
            "x": 1,
            "xanchor": "right",
            "bgcolor": "rgba(255,255,255,0.75)",
            "bordercolor": BORDER_COLOR,
            "borderwidth": 1,
            "font": {"size": 12, "color": TEXT_PRIMARY},
        },
    }


def apply_standard_2d_style(
    figure: go.Figure,
    *,
    title: str | None = None,
    xaxis_title: str | None = None,
    yaxis_title: str | None = None,
    height: int | None = None,
    showlegend: bool | None = None,
    margin: dict[str, int] | None = None,
    zeroline: bool = True,
    **layout_overrides: Any,
) -> go.Figure:
    layout = base_layout()
    if title is not None:
        layout["title"]["text"] = title
    if margin is not None:
        layout["margin"] = margin
    if height is not None:
        layout["height"] = height
    if showlegend is not None:
        layout["showlegend"] = showlegend
    layout.update(layout_overrides)
    figure.update_layout(**layout)
    figure.update_xaxes(
        title_text=xaxis_title,
        showline=True,
        linewidth=1.6,
        linecolor=AXIS_COLOR,
        mirror=False,
        ticks="outside",
        tickcolor=AXIS_COLOR,
        tickwidth=1.2,
        ticklen=6,
        showgrid=True,
        gridcolor=GRID_COLOR,
        zeroline=False,
        title_font={"size": 15, "color": TEXT_PRIMARY},
        tickfont={"size": 13, "color": TEXT_MUTED},
    )
    figure.update_yaxes(
        title_text=yaxis_title,
        showline=True,
        linewidth=1.6,
        linecolor=AXIS_COLOR,
        mirror=False,
        ticks="outside",
        tickcolor=AXIS_COLOR,
        tickwidth=1.2,
        ticklen=6,
        showgrid=True,
        gridcolor=GRID_COLOR,
        zeroline=zeroline,
        zerolinecolor="rgba(148, 163, 184, 0.40)",
        title_font={"size": 15, "color": TEXT_PRIMARY},
        tickfont={"size": 13, "color": TEXT_MUTED},
    )
    return figure


def apply_standard_3d_style(
    figure: go.Figure,
    *,
    title: str | None = None,
    camera: dict[str, Any] | None = None,
    height: int | None = None,
    showlegend: bool | None = None,
    margin: dict[str, int] | None = None,
) -> go.Figure:
    layout = base_layout()
    if title is not None:
        layout["title"]["text"] = title
    if height is not None:
        layout["height"] = height
    if showlegend is not None:
        layout["showlegend"] = showlegend
    layout["margin"] = margin or {"l": 0, "r": 0, "t": 56, "b": 0}
    layout["scene"] = {
        "aspectmode": "data",
        "bgcolor": CHART_PAPER_BG,
        "xaxis": {
            "title": {"font": {"size": 14, "color": TEXT_PRIMARY}},
            "backgroundcolor": CHART_PAPER_BG,
            "showbackground": False,
            "gridcolor": GRID_COLOR,
            "linecolor": AXIS_COLOR,
            "zerolinecolor": GRID_COLOR,
            "tickfont": {"size": 12, "color": TEXT_MUTED},
        },
        "yaxis": {
            "title": {"font": {"size": 14, "color": TEXT_PRIMARY}},
            "backgroundcolor": CHART_PAPER_BG,
            "showbackground": False,
            "gridcolor": GRID_COLOR,
            "linecolor": AXIS_COLOR,
            "zerolinecolor": GRID_COLOR,
            "tickfont": {"size": 12, "color": TEXT_MUTED},
        },
        "zaxis": {
            "title": {"font": {"size": 14, "color": TEXT_PRIMARY}},
            "backgroundcolor": CHART_PAPER_BG,
            "showbackground": False,
            "gridcolor": GRID_COLOR,
            "linecolor": AXIS_COLOR,
            "zerolinecolor": GRID_COLOR,
            "tickfont": {"size": 12, "color": TEXT_MUTED},
        },
        "camera": camera or STRUCTURE_CAMERA,
    }
    figure.update_layout(**layout)
    return figure


def standard_3d_axis_layout(
    *,
    show_axes: bool = True,
    background_color: str = CHART_PAPER_BG,
) -> dict[str, Any]:
    axis_visibility = bool(show_axes)
    return {
        "xaxis": {
            "visible": axis_visibility,
            "title": {"text": None, "font": {"size": 14, "color": TEXT_PRIMARY}},
            "backgroundcolor": background_color,
            "showbackground": False,
            "showgrid": axis_visibility,
            "gridcolor": GRID_COLOR,
            "linecolor": AXIS_COLOR,
            "zeroline": False,
            "zerolinecolor": GRID_COLOR,
            "showticklabels": axis_visibility,
            "tickfont": {"size": 12, "color": TEXT_MUTED},
        },
        "yaxis": {
            "visible": axis_visibility,
            "title": {"text": None, "font": {"size": 14, "color": TEXT_PRIMARY}},
            "backgroundcolor": background_color,
            "showbackground": False,
            "showgrid": axis_visibility,
            "gridcolor": GRID_COLOR,
            "linecolor": AXIS_COLOR,
            "zeroline": False,
            "zerolinecolor": GRID_COLOR,
            "showticklabels": axis_visibility,
            "tickfont": {"size": 12, "color": TEXT_MUTED},
        },
        "zaxis": {
            "visible": axis_visibility,
            "title": {"text": None, "font": {"size": 14, "color": TEXT_PRIMARY}},
            "backgroundcolor": background_color,
            "showbackground": False,
            "showgrid": axis_visibility,
            "gridcolor": GRID_COLOR,
            "linecolor": AXIS_COLOR,
            "zeroline": False,
            "zerolinecolor": GRID_COLOR,
            "showticklabels": axis_visibility,
            "tickfont": {"size": 12, "color": TEXT_MUTED},
        },
    }


def standard_export_margin(*, is_3d: bool, crop_mode: str = "balanced") -> dict[str, int]:
    normalized = crop_mode.strip().lower()
    if is_3d:
        if normalized == "tight":
            return {"l": 0, "r": 0, "t": 38, "b": 0}
        return {"l": 0, "r": 0, "t": 54, "b": 0}
    if normalized == "tight":
        return {"l": 42, "r": 18, "t": 54, "b": 42}
    return {"l": 72, "r": 28, "t": 62, "b": 60}
