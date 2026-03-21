from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ..i18n import tr
from ..plot_theme import (
    ACCENT_BLUE,
    ACCENT_RED,
    ACCENT_RED_DARK,
    ACCENT_TEAL,
    ACCENT_TEAL_DARK,
    ACCENT_VIOLET,
    apply_standard_2d_style,
)

def create_energy_figure(energies: list[float]) -> go.Figure:
    figure = go.Figure()
    if not energies:
        apply_standard_2d_style(
            figure,
            title=tr("优化能量轨迹"),
            xaxis_title=tr("优化/单点步骤"),
            yaxis_title=tr("能量 (Hartree)"),
            showlegend=False,
        )
        return figure
    figure.add_trace(
        go.Scatter(
            x=list(range(1, len(energies) + 1)),
            y=energies,
            mode="lines+markers",
            line={"color": ACCENT_TEAL_DARK, "width": 3.6},
            marker={"size": 8.5, "color": ACCENT_TEAL, "line": {"color": "#ffffff", "width": 1.2}},
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
    )
    return figure


def create_frequency_figure(frequencies: list[float]) -> go.Figure:
    colors = [ACCENT_RED if value < 0 else ACCENT_BLUE for value in frequencies]
    figure = go.Figure(
        data=[
            go.Bar(
                x=list(range(1, len(frequencies) + 1)),
                y=frequencies,
                marker_color=colors,
                marker_line={"color": "#ffffff", "width": 0.8},
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
    )
    return figure


def create_vibrational_density_figure(
    frequencies: list[float], sigma_cm1: float = 25.0
) -> go.Figure:
    positive = [value for value in frequencies if value > 0]
    figure = go.Figure()
    if not positive:
        figure.update_layout(template="plotly_white", title=tr("无可用于展宽的正频率"))
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
            line={"color": ACCENT_VIOLET, "width": 3.4},
            fill="tozeroy",
            fillcolor="rgba(124, 58, 237, 0.12)",
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
    )
    return figure

def create_uv_vis_figure(states: pd.DataFrame, sigma_ev: float = 0.12) -> go.Figure:
    figure = go.Figure()
    if states.empty:
        apply_standard_2d_style(
            figure,
            title=tr("未解析到 TDDFT 光谱"),
            xaxis_title=tr("跃迁能量 (eV)"),
            yaxis_title=tr("振子强度 / 相对吸收"),
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
            line={"color": ACCENT_RED_DARK, "width": 3.6},
            fill="tozeroy",
            fillcolor="rgba(159, 18, 57, 0.10)",
            name=tr("展宽谱"),
            hovertemplate=f"%{{x:.3f}} eV<br>{tr('强度')} %{{y:.4f}}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Bar(
            x=states["energy_eV"],
            y=states["oscillator_strength"],
            width=0.03,
            marker_color=ACCENT_TEAL,
            marker_line={"color": "#ffffff", "width": 0.6},
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
    )
    return figure

def create_batch_energy_figure(summary_df: pd.DataFrame) -> go.Figure:
    data = summary_df.dropna(subset=["total_energy_hartree"])
    figure = go.Figure()
    if data.empty:
        figure.update_layout(template="plotly_white", title=tr("批量文件中无可比较能量"))
        return figure
    figure.add_trace(
        go.Bar(
            x=data["file"],
            y=data["total_energy_hartree"],
            marker_color=ACCENT_TEAL,
            marker_line={"color": "#ffffff", "width": 0.8},
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
    )
    return figure


def create_batch_excited_state_figure(summary_df: pd.DataFrame) -> go.Figure:
    data = summary_df[summary_df["excited_states"].notna()]
    figure = go.Figure()
    if data.empty:
        figure.update_layout(template="plotly_white", title=tr("批量文件中无 TDDFT 数据"))
        return figure
    figure.add_trace(
        go.Bar(
            x=data["file"],
            y=data["excited_states"],
            marker_color=ACCENT_RED,
            marker_line={"color": "#ffffff", "width": 0.8},
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
    )
    return figure
