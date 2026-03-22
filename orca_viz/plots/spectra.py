from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ..i18n import tr
from ..plot_theme import (
    apply_standard_2d_style,
    resolve_visual_style,
)

def create_energy_figure(energies: list[float], *, visual_style_key: str | None = None) -> go.Figure:
    style = resolve_visual_style(visual_style_key)
    palette = style.palette
    figure = go.Figure()
    if not energies:
        apply_standard_2d_style(
            figure,
            title=tr("优化能量轨迹"),
            xaxis_title=tr("优化/单点步骤"),
            yaxis_title=tr("能量 (Hartree)"),
            showlegend=False,
            visual_style_key=style.key,
        )
        return figure
    figure.add_trace(
        go.Scatter(
            x=list(range(1, len(energies) + 1)),
            y=energies,
            mode="lines+markers",
            line={"color": palette["accent_secondary_dark"], "width": 3.6 * style.line_scale},
            marker={
                "size": 8.5 * style.marker_scale,
                "color": palette["accent_secondary"],
                "line": {"color": palette["bar_edge"], "width": 1.2},
            },
            hovertemplate=f"{tr('步骤')} %{{x}}<br>{tr('能量 (Hartree)').replace(' (Hartree)', '')} %{{y:.8f}} Eh<extra></extra>",
        )
    )
    apply_standard_2d_style(
        figure,
        title=tr("优化能量轨迹"),
        xaxis_title=tr("优化/单点步骤"),
        yaxis_title=tr("能量 (Hartree)"),
        showlegend=False,
        margin={"l": 72, "r": 18, "t": 58, "b": 60},
        visual_style_key=style.key,
    )
    return figure


def create_frequency_figure(frequencies: list[float], *, visual_style_key: str | None = None) -> go.Figure:
    style = resolve_visual_style(visual_style_key)
    palette = style.palette
    colors = [palette["accent_positive"] if value < 0 else palette["accent_primary"] for value in frequencies]
    figure = go.Figure(
        data=[
            go.Bar(
                x=list(range(1, len(frequencies) + 1)),
                y=frequencies,
                marker_color=colors,
                marker_line={"color": palette["bar_edge"], "width": 0.8},
                hovertemplate=f"{tr('模态')} %{{x}}<br>%{{y:.2f}} cm^-1<extra></extra>",
            )
        ]
    )
    apply_standard_2d_style(
        figure,
        title=tr("振动频率分布"),
        xaxis_title=tr("振动模态"),
        yaxis_title=tr("频率 (cm^-1)"),
        showlegend=False,
        margin={"l": 72, "r": 18, "t": 58, "b": 60},
        visual_style_key=style.key,
    )
    return figure


def create_vibrational_density_figure(
    frequencies: list[float], sigma_cm1: float = 25.0, *, visual_style_key: str | None = None
) -> go.Figure:
    style = resolve_visual_style(visual_style_key)
    palette = style.palette
    positive = [value for value in frequencies if value > 0]
    figure = go.Figure()
    if not positive:
        apply_standard_2d_style(
            figure,
            title=tr("无可用于展宽的正频率"),
            xaxis_title=tr("频率 (cm^-1)"),
            yaxis_title=tr("相对强度"),
            showlegend=False,
            visual_style_key=style.key,
        )
        return figure

    x_grid = np.linspace(max(min(positive) - 200, 0), max(positive) + 200, 1200)
    intensity = np.zeros_like(x_grid)
    for center in positive:
        intensity += np.exp(-0.5 * ((x_grid - center) / sigma_cm1) ** 2)

    figure.add_trace(
        go.Scatter(
            x=x_grid,
            y=intensity,
            mode="lines",
            line={"color": palette["accent_emphasis"], "width": 3.4 * style.line_scale},
            fill="tozeroy",
            fillcolor=_rgba(palette["accent_emphasis"], 0.14),
            hovertemplate=f"%{{x:.2f}} cm^-1<br>{tr('相对强度')} %{{y:.3f}}<extra></extra>",
        )
    )
    apply_standard_2d_style(
        figure,
        title=tr("振动展宽谱"),
        xaxis_title=tr("频率 (cm^-1)"),
        yaxis_title=tr("相对强度"),
        showlegend=False,
        margin={"l": 72, "r": 18, "t": 58, "b": 60},
        visual_style_key=style.key,
    )
    return figure

def create_uv_vis_figure(
    states: pd.DataFrame,
    sigma_ev: float = 0.12,
    *,
    visual_style_key: str | None = None,
) -> go.Figure:
    style = resolve_visual_style(visual_style_key)
    palette = style.palette
    figure = go.Figure()
    if states.empty:
        apply_standard_2d_style(
            figure,
            title=tr("未解析到 TDDFT 光谱"),
            xaxis_title=tr("跃迁能量 (eV)"),
            yaxis_title=tr("振子强度 / 相对吸收"),
            visual_style_key=style.key,
        )
        return figure

    x_grid = np.linspace(0, max(states["energy_eV"].max() + 1.0, 6.0), 1600)
    intensity = np.zeros_like(x_grid)
    for row in states.itertuples():
        intensity += row.oscillator_strength * np.exp(
            -0.5 * ((x_grid - row.energy_eV) / sigma_ev) ** 2
        )

    figure.add_trace(
        go.Scatter(
            x=x_grid,
            y=intensity,
            mode="lines",
            line={"color": palette["accent_positive"], "width": 3.6 * style.line_scale},
            fill="tozeroy",
            fillcolor=_rgba(palette["accent_positive"], 0.10),
            name=tr("展宽谱"),
            hovertemplate=f"%{{x:.3f}} eV<br>{tr('强度')} %{{y:.4f}}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Bar(
            x=states["energy_eV"],
            y=states["oscillator_strength"],
            width=0.03,
            marker_color=palette["accent_secondary"],
            marker_line={"color": palette["bar_edge"], "width": 0.6},
            opacity=0.62,
            name=tr("跃迁棒谱"),
            hovertemplate=(
                "State %{customdata[0]}<br>%{x:.3f} eV<br>%{customdata[1]:.2f} nm"
                "<br>f=%{y:.4f}<extra></extra>"
            ),
            customdata=states[["state", "wavelength_nm"]].to_numpy(),
        )
    )
    apply_standard_2d_style(
        figure,
        title=tr("TDDFT 吸收光谱"),
        xaxis_title=tr("跃迁能量 (eV)"),
        yaxis_title=tr("振子强度 / 相对吸收"),
        barmode="overlay",
        margin={"l": 76, "r": 20, "t": 58, "b": 60},
        visual_style_key=style.key,
    )
    return figure

def create_batch_energy_figure(summary_df: pd.DataFrame, *, visual_style_key: str | None = None) -> go.Figure:
    style = resolve_visual_style(visual_style_key)
    palette = style.palette
    data = summary_df.dropna(subset=["total_energy_hartree"])
    figure = go.Figure()
    if data.empty:
        apply_standard_2d_style(
            figure,
            title=tr("批量文件中无可比较能量"),
            xaxis_title=tr("文件"),
            yaxis_title=tr("总能量 (Hartree)"),
            showlegend=False,
            visual_style_key=style.key,
        )
        return figure
    figure.add_trace(
        go.Bar(
            x=data["file"],
            y=data["total_energy_hartree"],
            marker_color=palette["accent_secondary"],
            marker_line={"color": palette["bar_edge"], "width": 0.8},
            hovertemplate="%{x}<br>%{y:.8f} Eh<extra></extra>",
        )
    )
    apply_standard_2d_style(
        figure,
        title=tr("批量总能量比较"),
        xaxis_title=tr("文件"),
        yaxis_title=tr("总能量 (Hartree)"),
        showlegend=False,
        margin={"l": 76, "r": 20, "t": 58, "b": 96},
        visual_style_key=style.key,
    )
    return figure


def create_batch_excited_state_figure(
    summary_df: pd.DataFrame, *, visual_style_key: str | None = None
) -> go.Figure:
    style = resolve_visual_style(visual_style_key)
    palette = style.palette
    data = summary_df[summary_df["excited_states"].notna()]
    figure = go.Figure()
    if data.empty:
        apply_standard_2d_style(
            figure,
            title=tr("批量文件中无 TDDFT 数据"),
            xaxis_title=tr("文件"),
            yaxis_title=tr("激发态数"),
            showlegend=False,
            visual_style_key=style.key,
        )
        return figure
    figure.add_trace(
        go.Bar(
            x=data["file"],
            y=data["excited_states"],
            marker_color=palette["accent_positive"],
            marker_line={"color": palette["bar_edge"], "width": 0.8},
            hovertemplate=f"%{{x}}<br>{tr('激发态数')} %{{y}}<extra></extra>",
        )
    )
    apply_standard_2d_style(
        figure,
        title=tr("批量 TDDFT 激发态数比较"),
        xaxis_title=tr("文件"),
        yaxis_title=tr("激发态数"),
        showlegend=False,
        margin={"l": 76, "r": 20, "t": 58, "b": 96},
        visual_style_key=style.key,
    )
    return figure


def _rgba(hex_color: str, alpha: float) -> str:
    stripped = hex_color.lstrip("#")
    if len(stripped) != 6:
        return hex_color
    red = int(stripped[0:2], 16)
    green = int(stripped[2:4], 16)
    blue = int(stripped[4:6], 16)
    return f"rgba({red}, {green}, {blue}, {alpha:.3f})"
