from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ..i18n import tr
from ..plot_theme import ACCENT_BLUE, ACCENT_BLUE_LIGHT, apply_standard_2d_style

def create_path_figure(
    data: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str,
    x_label: str,
    y_label: str | None = None,
    y_hover_format: str = ".8f",
    y_suffix: str = " Eh",
) -> go.Figure:
    figure = go.Figure()
    if data.empty:
        figure.update_layout(template="plotly_white", title=title)
        return figure
    plot_data = data.sort_values(x_col).reset_index(drop=True)
    axis_label = y_label or tr("能量 (Hartree)")
    figure.add_trace(
        go.Scatter(
            x=plot_data[x_col],
            y=plot_data[y_col],
            mode="lines+markers",
            line={"color": ACCENT_BLUE, "width": 3.4},
            marker={"color": ACCENT_BLUE_LIGHT, "size": 8.5, "line": {"color": "#ffffff", "width": 1.2}},
            hovertemplate=(
                f"{x_label}=%{{x}}<br>{axis_label}=%{{y:{y_hover_format}}}{y_suffix}<extra></extra>"
            ),
        )
    )
    apply_standard_2d_style(
        figure,
        title=title,
        xaxis_title=x_label,
        yaxis_title=axis_label,
        showlegend=False,
        margin={"l": 76, "r": 20, "t": 58, "b": 60},
    )
    return figure
