from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from ase import Atoms

from ..i18n import tr
from ..plot_theme import (
    ACCENT_BLUE,
    ACCENT_RED,
    STRUCTURE_CAMERA,
    apply_standard_2d_style,
    apply_standard_3d_style,
)
from .structure import _charge_atom_sizes, _representation_bond_traces, _representation_config

def create_charge_figure(charges: pd.DataFrame, title: str) -> go.Figure:
    labels = [f"{row['element']}{int(row['index']) + 1}" for _, row in charges.iterrows()]
    colors = [ACCENT_RED if value > 0 else ACCENT_BLUE for value in charges["charge"]]
    figure = go.Figure(
        data=[
            go.Bar(
                x=labels,
                y=charges["charge"],
                marker_color=colors,
                marker_line={"color": "#ffffff", "width": 0.9},
                hovertemplate=f"%{{x}}<br>{tr('电荷')} %{{y:.4f}}<extra></extra>",
            )
        ]
    )
    apply_standard_2d_style(
        figure,
        title=title,
        xaxis_title=tr("原子"),
        yaxis_title=tr("电荷"),
        showlegend=False,
        margin={"l": 72, "r": 18, "t": 58, "b": 72},
    )
    return figure


def create_charge_3d_figure(
    atoms: Atoms,
    charges: pd.DataFrame,
    title: str,
    show_charge_labels: bool = True,
    representation: str = "ball_stick",
) -> go.Figure:
    if atoms is None or len(atoms) == 0:
        figure = go.Figure()
        figure.update_layout(template="plotly_white", title=title)
        return figure

    merged = _merge_charge_data(atoms, charges)
    positions = atoms.get_positions()
    atomic_numbers = atoms.get_atomic_numbers()
    charge_values = merged["charge"].to_numpy(dtype=float)
    charge_span = max(float(np.max(np.abs(charge_values))), 1e-6)
    style = _representation_config(representation)
    atom_sizes = _charge_atom_sizes(atomic_numbers, charge_values, representation)

    figure = go.Figure()
    for trace in _representation_bond_traces(atoms, representation=representation):
        figure.add_trace(trace)
    figure.add_trace(
        go.Scatter3d(
            x=positions[:, 0],
            y=positions[:, 1],
            z=positions[:, 2],
            mode="markers+text" if show_charge_labels else "markers",
            text=merged["label"] if show_charge_labels else None,
            textposition="top center",
            textfont={"size": 11, "color": "#111827"},
            customdata=np.stack(
                [
                    merged["atom_symbol"],
                    merged["atom_number"],
                    merged["charge"],
                    merged["charge_sign"],
                ],
                axis=1,
            ),
            hovertemplate=tr(
                "原子: %{customdata[0]}%{customdata[1]}<br>电荷: %{customdata[2]:+.4f}<br>类型: %{customdata[3]}<br>x=%{x:.3f}<br>y=%{y:.3f}<br>z=%{z:.3f}<extra></extra>"
            ),
            marker={
                "size": atom_sizes,
                "color": charge_values,
                "colorscale": "RdBu_r",
                "cmin": -charge_span,
                "cmax": charge_span,
                "cmid": 0,
                "colorbar": {"title": tr("原子电荷")},
                "line": {"color": "#111827", "width": 1.2},
                "opacity": style["atom_opacity"],
            },
            showlegend=False,
        )
    )
    apply_standard_3d_style(
        figure,
        title=title,
        camera=STRUCTURE_CAMERA,
        showlegend=False,
        margin={"l": 0, "r": 0, "t": 56, "b": 0},
    )
    return figure


def charge_extrema_dataframe(
    atoms: Atoms, charges: pd.DataFrame, top_n: int = 6
) -> pd.DataFrame:
    merged = _merge_charge_data(atoms, charges)
    ranked = merged.reindex(merged["charge"].abs().sort_values(ascending=False).index)
    return ranked[
        ["atom_label", "charge", "x", "y", "z", "charge_sign"]
    ].head(top_n).reset_index(drop=True)

def _merge_charge_data(atoms: Atoms, charges: pd.DataFrame) -> pd.DataFrame:
    if charges.empty:
        return pd.DataFrame(
            {
                "atom_index": np.arange(len(atoms)),
                "atom_number": np.arange(1, len(atoms) + 1),
                "atom_symbol": atoms.get_chemical_symbols(),
                "atom_label": [
                    f"{symbol}{index + 1}" for index, symbol in enumerate(atoms.get_chemical_symbols())
                ],
                "charge": np.zeros(len(atoms)),
                "x": atoms.get_positions()[:, 0],
                "y": atoms.get_positions()[:, 1],
                "z": atoms.get_positions()[:, 2],
                "charge_sign": ["neutral"] * len(atoms),
                "label": [f"{symbol}{index + 1}\n{0.0:+.3f}" for index, symbol in enumerate(atoms.get_chemical_symbols())],
            }
        )

    merged = charges.copy().reset_index(drop=True)
    merged["atom_index"] = merged["index"].astype(int)
    merged["atom_number"] = merged["atom_index"] + 1
    merged["atom_symbol"] = atoms.get_chemical_symbols()
    merged["atom_label"] = [
        f"{symbol}{atom_number}"
        for symbol, atom_number in zip(merged["element"], merged["atom_number"], strict=False)
    ]
    positions = atoms.get_positions()
    merged["x"] = positions[:, 0]
    merged["y"] = positions[:, 1]
    merged["z"] = positions[:, 2]
    merged["charge_sign"] = [
        "positive" if value > 1e-9 else "negative" if value < -1e-9 else "neutral"
        for value in merged["charge"]
    ]
    merged["label"] = [
        f"{label}\n{charge:+.3f}"
        for label, charge in zip(merged["atom_label"], merged["charge"], strict=False)
    ]
    return merged
