from __future__ import annotations

from collections import Counter
import importlib.util
import json
import subprocess
import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from ase import Atoms
from ase.data import chemical_symbols, covalent_radii, vdw_radii
from ase.data.colors import jmol_colors
from ase.neighborlist import NeighborList, natural_cutoffs
from plotly.offline import get_plotlyjs

from .cube import CubeData, cube_kind_label, esp_signed_surface_levels, sample_cube_grid
from .i18n import tr


PLOTLY_JS_BUNDLE = get_plotlyjs()
STATIC_IMAGE_EXPORT_AVAILABLE = False
ESP_COLOR_NEGATIVE = "rgb(190, 24, 93)"
ESP_COLOR_POSITIVE = "rgb(30, 64, 175)"
ORBITAL_COLOR_NEGATIVE = "rgb(37, 99, 235)"
ORBITAL_COLOR_POSITIVE = "rgb(217, 119, 6)"
ESP_SLICE_COLORSCALE = [
    [0.00, "#9f1239"],
    [0.18, "#ef4444"],
    [0.50, "#fff7ed"],
    [0.82, "#60a5fa"],
    [1.00, "#1d4ed8"],
]
ORBITAL_SLICE_COLORSCALE = [
    [0.00, "#1d4ed8"],
    [0.20, "#60a5fa"],
    [0.50, "#f8fafc"],
    [0.80, "#fbbf24"],
    [1.00, "#b45309"],
]


def _detect_static_export_support() -> bool:
    if importlib.util.find_spec("kaleido") is None:
        return False

    probe_code = (
        "import plotly.graph_objects as go, plotly.io as pio;"
        "fig = go.Figure(data=[go.Scatter(x=[0,1], y=[0,1])]);"
        "pio.to_image(fig, format='png', width=32, height=32, scale=1);"
        "print('ok')"
    )
    try:
        completed = subprocess.run(
            [sys.executable, "-c", probe_code],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception:
        return False
    return completed.returncode == 0 and "ok" in completed.stdout


STATIC_IMAGE_EXPORT_AVAILABLE = _detect_static_export_support()


def create_structure_figure(
    atoms: Atoms,
    representation: str = "ball_stick",
    show_atom_labels: bool = False,
) -> go.Figure:
    figure = go.Figure()
    bond_trace = _representation_bond_trace(atoms, representation=representation)
    if bond_trace is not None:
        figure.add_trace(bond_trace)
    for trace in _structure_traces(
        atoms,
        representation=representation,
        show_labels=show_atom_labels,
    ):
        figure.add_trace(trace)

    figure.update_layout(
        template="plotly_white",
        margin={"l": 0, "r": 0, "t": 30, "b": 0},
        scene={
            "xaxis_title": "X (A)",
            "yaxis_title": "Y (A)",
            "zaxis_title": "Z (A)",
            "aspectmode": "data",
        },
        showlegend=False,
    )
    return figure


def create_vibration_mode_figure(
    atoms: Atoms,
    mode_displacements: np.ndarray,
    amplitude: float = 0.6,
    frame_count: int = 16,
    show_vectors: bool = False,
) -> go.Figure:
    scaled_displacements = _normalize_mode(mode_displacements) * amplitude
    equilibrium_positions = atoms.get_positions()
    phases = np.sin(np.linspace(0, 2 * np.pi, frame_count, endpoint=False))
    bond_pairs = _build_bond_pairs(atoms)

    initial_atoms = atoms.copy()
    initial_atoms.set_positions(equilibrium_positions + phases[0] * scaled_displacements)

    initial_data = _structure_traces(initial_atoms, representation="ball_stick", show_labels=False)
    initial_bond_trace = _representation_bond_trace(initial_atoms, representation="ball_stick", bond_pairs=bond_pairs)
    if initial_bond_trace is not None:
        initial_data.append(initial_bond_trace)
    if show_vectors:
        initial_data.append(_combined_vector_trace(equilibrium_positions, scaled_displacements))
    figure = go.Figure(data=initial_data)

    frames: list[go.Frame] = []
    for frame_index, phase in enumerate(phases):
        frame_atoms = atoms.copy()
        frame_atoms.set_positions(equilibrium_positions + phase * scaled_displacements)
        frame_data = _structure_traces(frame_atoms, representation="ball_stick", show_labels=False)
        frame_bond_trace = _representation_bond_trace(frame_atoms, representation="ball_stick", bond_pairs=bond_pairs)
        if frame_bond_trace is not None:
            frame_data.append(frame_bond_trace)
        if show_vectors:
            frame_data.append(_combined_vector_trace(equilibrium_positions, phase * scaled_displacements))
        frames.append(go.Frame(data=frame_data, name=str(frame_index), traces=list(range(len(frame_data)))))

    figure.frames = frames
    figure.update_layout(
        template="plotly_white",
        margin={"l": 0, "r": 0, "t": 40, "b": 0},
        uirevision="vibration-mode",
        scene={
            "xaxis_title": "X (A)",
            "yaxis_title": "Y (A)",
            "zaxis_title": "Z (A)",
            "aspectmode": "data",
            "uirevision": "vibration-mode-camera",
        },
        showlegend=False,
        title=tr("振动模式动画"),
        updatemenus=[
            {
                "type": "buttons",
                "showactive": False,
                "buttons": [
                    {
                        "label": tr("播放"),
                        "method": "animate",
                        "args": [
                            None,
                            {
                                "frame": {"duration": 90, "redraw": True},
                                "transition": {"duration": 0},
                                "fromcurrent": True,
                            },
                        ],
                    },
                    {
                        "label": tr("暂停"),
                        "method": "animate",
                        "args": [
                            [None],
                            {"frame": {"duration": 0, "redraw": True}, "transition": {"duration": 0}},
                        ],
                    },
                ],
            }
        ],
        sliders=[
            {
                "steps": [
                    {
                        "method": "animate",
                        "label": str(frame_index),
                        "args": [
                            [str(frame_index)],
                            {
                                "frame": {"duration": 0, "redraw": True},
                                "transition": {"duration": 0},
                                "mode": "immediate",
                            },
                        ],
                    }
                    for frame_index in range(frame_count)
                ]
            }
        ],
    )
    return figure


def build_vibration_mode_html(
    atoms: Atoms,
    mode_displacements: np.ndarray,
    amplitude: float = 0.6,
    frame_count: int = 32,
    frame_duration_ms: int = 90,
    show_vectors: bool = False,
    component_id: str = "vibration-mode",
) -> str:
    scaled_displacements = _normalize_mode(mode_displacements) * amplitude
    positions = atoms.get_positions()
    numbers = atoms.get_atomic_numbers()
    symbols = atoms.get_chemical_symbols()
    bond_pairs = _build_bond_pairs(atoms)

    palette = {
        symbol: f"rgb({int(color[0] * 255)}, {int(color[1] * 255)}, {int(color[2] * 255)})"
        for symbol, color in (
            (chemical_symbols[number], jmol_colors[number]) for number in sorted(set(numbers))
        )
    }

    payload = {
        "component_id": component_id,
        "frame_count": frame_count,
        "frame_duration_ms": frame_duration_ms,
        "show_vectors": show_vectors,
        "symbols": symbols,
        "sizes": [max(covalent_radii[number] * 18, 12) for number in numbers],
        "colors": [palette[symbol] for symbol in symbols],
        "equilibrium_positions": positions.tolist(),
        "displacements": scaled_displacements.tolist(),
        "bond_pairs": bond_pairs,
    }

    return f"""
<div class="vib-root">
  <div id="{component_id}" style="width:100%; height:560px;"></div>
  <div class="vib-controls">
    <button id="{component_id}-toggle" type="button">{tr("播放")}</button>
    <input id="{component_id}-slider" type="range" min="0" max="{frame_count - 1}" value="0" step="1" />
    <span id="{component_id}-status">Frame 1/{frame_count}</span>
  </div>
</div>
<style>
  .vib-root {{
    width: 100%;
  }}
  .vib-controls {{
    display: flex;
    align-items: center;
    gap: 12px;
    padding-top: 8px;
    font-family: sans-serif;
  }}
  .vib-controls button {{
    border: 1px solid #d1d5db;
    background: #ffffff;
    padding: 6px 12px;
    border-radius: 8px;
    cursor: pointer;
  }}
  .vib-controls input[type="range"] {{
    flex: 1;
  }}
</style>
<script>{PLOTLY_JS_BUNDLE}</script>
<script>
(() => {{
  const payload = {json.dumps(payload, ensure_ascii=False)};
  const div = document.getElementById(payload.component_id);
  const toggle = document.getElementById(payload.component_id + "-toggle");
  const slider = document.getElementById(payload.component_id + "-slider");
  const status = document.getElementById(payload.component_id + "-status");
  const phases = Array.from({{ length: payload.frame_count }}, (_, i) =>
    Math.sin((i / payload.frame_count) * 2 * Math.PI)
  );
  let currentFrame = 0;
  let playing = false;
  let lastTs = 0;
  let isInteracting = false;
  let interactionTimer = null;

  function displacedPositions(phase) {{
    return payload.equilibrium_positions.map((pos, i) => [
      pos[0] + phase * payload.displacements[i][0],
      pos[1] + phase * payload.displacements[i][1],
      pos[2] + phase * payload.displacements[i][2],
    ]);
  }}

  function unpackAxes(positions) {{
    return {{
      x: positions.map((p) => p[0]),
      y: positions.map((p) => p[1]),
      z: positions.map((p) => p[2]),
    }};
  }}

  function bondTraceAxes(positions) {{
    const x = [];
    const y = [];
    const z = [];
    for (const [left, right] of payload.bond_pairs) {{
      x.push(positions[left][0], positions[right][0], null);
      y.push(positions[left][1], positions[right][1], null);
      z.push(positions[left][2], positions[right][2], null);
    }}
    return {{ x, y, z }};
  }}

  function vectorTraceAxes(phase) {{
    const x = [];
    const y = [];
    const z = [];
    for (let i = 0; i < payload.equilibrium_positions.length; i += 1) {{
      const origin = payload.equilibrium_positions[i];
      const target = [
        origin[0] + phase * payload.displacements[i][0],
        origin[1] + phase * payload.displacements[i][1],
        origin[2] + phase * payload.displacements[i][2],
      ];
      x.push(origin[0], target[0], null);
      y.push(origin[1], target[1], null);
      z.push(origin[2], target[2], null);
    }}
    return {{ x, y, z }};
  }}

  function makeData(phase) {{
    const positions = displacedPositions(phase);
    const atomAxes = unpackAxes(positions);
    const bondAxes = bondTraceAxes(positions);
    const data = [
      {{
        type: "scatter3d",
        mode: "markers+text",
        x: atomAxes.x,
        y: atomAxes.y,
        z: atomAxes.z,
        text: payload.symbols,
        textposition: "top center",
        hovertemplate: "{tr('原子')}: %{{text}}<br>x=%{{x:.3f}}<br>y=%{{y:.3f}}<br>z=%{{z:.3f}}<extra></extra>",
        marker: {{
          size: payload.sizes,
          color: payload.colors,
          line: {{ color: "#1f1f1f", width: 1 }},
          opacity: 0.95,
        }},
        showlegend: false,
      }},
      {{
        type: "scatter3d",
        mode: "lines",
        x: bondAxes.x,
        y: bondAxes.y,
        z: bondAxes.z,
        line: {{ color: "#6b7280", width: 6 }},
        hoverinfo: "skip",
        showlegend: false,
      }},
    ];

    if (payload.show_vectors) {{
      const vectorAxes = vectorTraceAxes(phase);
      data.push({{
        type: "scatter3d",
        mode: "lines",
        x: vectorAxes.x,
        y: vectorAxes.y,
        z: vectorAxes.z,
        line: {{ color: "#dc2626", width: 7 }},
        hoverinfo: "skip",
        showlegend: false,
      }});
    }}

    return data;
  }}

  function updateFrame(index) {{
    currentFrame = ((index % payload.frame_count) + payload.frame_count) % payload.frame_count;
    const phase = phases[currentFrame];
    const positions = displacedPositions(phase);
    const atomAxes = unpackAxes(positions);
    const bondAxes = bondTraceAxes(positions);
    Plotly.restyle(div, {{
      x: [atomAxes.x],
      y: [atomAxes.y],
      z: [atomAxes.z],
    }}, [0]);
    Plotly.restyle(div, {{
      x: [bondAxes.x],
      y: [bondAxes.y],
      z: [bondAxes.z],
    }}, [1]);
    if (payload.show_vectors) {{
      const vectorAxes = vectorTraceAxes(phase);
      Plotly.restyle(div, {{
        x: [vectorAxes.x],
        y: [vectorAxes.y],
        z: [vectorAxes.z],
      }}, [2]);
    }}
    slider.value = String(currentFrame);
    status.textContent = `Frame ${{currentFrame + 1}}/${{payload.frame_count}}`;
  }}

  function startInteraction() {{
    isInteracting = true;
    if (interactionTimer) {{
      window.clearTimeout(interactionTimer);
      interactionTimer = null;
    }}
  }}

  function endInteraction() {{
    if (interactionTimer) {{
      window.clearTimeout(interactionTimer);
    }}
    interactionTimer = window.setTimeout(() => {{
      isInteracting = false;
      lastTs = performance.now();
    }}, 120);
  }}

  function tick(ts) {{
    if (playing && !isInteracting && ts - lastTs >= payload.frame_duration_ms) {{
      updateFrame(currentFrame + 1);
      lastTs = ts;
    }} else if (playing && isInteracting) {{
      lastTs = ts;
    }}
    window.requestAnimationFrame(tick);
  }}

  toggle.addEventListener("click", () => {{
    playing = !playing;
    toggle.textContent = playing ? "{tr('暂停')}" : "{tr('播放')}";
    lastTs = performance.now();
  }});

  slider.addEventListener("input", (event) => {{
    updateFrame(Number(event.target.value));
    lastTs = performance.now();
  }});

  Plotly.newPlot(div, makeData(phases[0]), {{
    template: "plotly_white",
    margin: {{ l: 0, r: 0, t: 40, b: 0 }},
    uirevision: "vibration-mode-html",
    scene: {{
      xaxis: {{ title: "X (A)" }},
      yaxis: {{ title: "Y (A)" }},
      zaxis: {{ title: "Z (A)" }},
      aspectmode: "data",
      dragmode: "orbit",
      uirevision: "vibration-mode-html-camera",
    }},
    showlegend: false,
    title: "{tr('振动模式动画')}",
  }}, {{
    responsive: true,
    displayModeBar: true,
    scrollZoom: true,
  }}).then(() => {{
    div.on("plotly_relayouting", startInteraction);
    div.on("plotly_relayout", endInteraction);
    div.addEventListener("pointerdown", startInteraction);
    div.addEventListener("wheel", () => {{
      startInteraction();
      endInteraction();
    }}, {{ passive: true }});
    window.addEventListener("pointerup", endInteraction);
    window.addEventListener("pointercancel", endInteraction);
    window.requestAnimationFrame(tick);
  }});
}})();
</script>
"""


def create_mode_magnitude_figure(atoms: Atoms, mode_displacements: np.ndarray) -> go.Figure:
    magnitudes = np.linalg.norm(mode_displacements, axis=1)
    labels = [f"{symbol}{index + 1}" for index, symbol in enumerate(atoms.get_chemical_symbols())]
    figure = go.Figure(
        data=[
            go.Bar(
                x=labels,
                y=magnitudes,
                marker_color="#ea580c",
                hovertemplate=f"%{{x}}<br>{tr('位移强度')} %{{y:.4f}}<extra></extra>",
            )
        ]
    )
    figure.update_layout(
        template="plotly_white",
        xaxis_title=tr("原子"),
        yaxis_title=tr("相对位移强度"),
        margin={"l": 20, "r": 20, "t": 30, "b": 20},
    )
    return figure


def create_energy_figure(energies: list[float]) -> go.Figure:
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=list(range(1, len(energies) + 1)),
            y=energies,
            mode="lines+markers",
            line={"color": "#115e59", "width": 3},
            marker={"size": 8, "color": "#0f766e"},
            hovertemplate=f"{tr('步骤')} %{{x}}<br>{tr('能量 (Hartree)').replace(' (Hartree)', '')} %{{y:.8f}} Eh<extra></extra>",
        )
    )
    figure.update_layout(
        template="plotly_white",
        xaxis_title=tr("优化/单点步骤"),
        yaxis_title=tr("能量 (Hartree)"),
        margin={"l": 20, "r": 20, "t": 30, "b": 20},
    )
    return figure


def create_frequency_figure(frequencies: list[float]) -> go.Figure:
    colors = ["#dc2626" if value < 0 else "#2563eb" for value in frequencies]
    figure = go.Figure(
        data=[
            go.Bar(
                x=list(range(1, len(frequencies) + 1)),
                y=frequencies,
                marker_color=colors,
                hovertemplate=f"{tr('模态')} %{{x}}<br>%{{y:.2f}} cm^-1<extra></extra>",
            )
        ]
    )
    figure.update_layout(
        template="plotly_white",
        xaxis_title=tr("振动模态"),
        yaxis_title=tr("频率 (cm^-1)"),
        margin={"l": 20, "r": 20, "t": 30, "b": 20},
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
            line={"color": "#9333ea", "width": 3},
            hovertemplate=f"%{{x:.2f}} cm^-1<br>{tr('相对强度')} %{{y:.3f}}<extra></extra>",
        )
    )
    figure.update_layout(
        template="plotly_white",
        xaxis_title=tr("频率 (cm^-1)"),
        yaxis_title=tr("相对强度"),
        margin={"l": 20, "r": 20, "t": 30, "b": 20},
    )
    return figure


def create_charge_figure(charges: pd.DataFrame, title: str) -> go.Figure:
    labels = [f"{row['element']}{int(row['index']) + 1}" for _, row in charges.iterrows()]
    colors = ["#dc2626" if value > 0 else "#2563eb" for value in charges["charge"]]
    figure = go.Figure(
        data=[
            go.Bar(
                x=labels,
                y=charges["charge"],
                marker_color=colors,
                hovertemplate=f"%{{x}}<br>{tr('电荷')} %{{y:.4f}}<extra></extra>",
            )
        ]
    )
    figure.update_layout(
        template="plotly_white",
        title=title,
        xaxis_title=tr("原子"),
        yaxis_title=tr("电荷"),
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
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
    bond_trace = _representation_bond_trace(atoms, representation=representation)
    if bond_trace is not None:
        figure.add_trace(bond_trace)
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
                "colorbar": {"title": "Atomic charge"},
                "line": {"color": "#111827", "width": 1.2},
                "opacity": style["atom_opacity"],
            },
            showlegend=False,
        )
    )
    figure.update_layout(
        template="plotly_white",
        title=title,
        margin={"l": 0, "r": 0, "t": 50, "b": 0},
        scene={
            "xaxis_title": "X (A)",
            "yaxis_title": "Y (A)",
            "zaxis_title": "Z (A)",
            "aspectmode": "data",
        },
        showlegend=False,
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


def export_plotly_figure(
    figure: go.Figure,
    image_format: str = "png",
    width: int = 1800,
    height: int = 1200,
    scale: int = 2,
    publication_style: bool = True,
) -> bytes:
    export_figure = go.Figure(figure)
    if publication_style:
        export_figure = create_publication_ready_figure(export_figure)
    return pio.to_image(
        export_figure,
        format=image_format,
        width=width,
        height=height,
        scale=scale,
    )


def create_publication_ready_figure(figure: go.Figure) -> go.Figure:
    export_figure = go.Figure(figure)
    export_figure.update_layout(
        template="plotly_white",
        paper_bgcolor="white",
        plot_bgcolor="white",
        font={"family": "Helvetica, Arial, sans-serif", "size": 18, "color": "#111827"},
        title={"font": {"size": 24, "color": "#111827"}},
        margin={"l": 80, "r": 40, "t": 80, "b": 80},
    )
    export_figure.update_xaxes(
        showline=True,
        linewidth=2,
        linecolor="#111827",
        mirror=True,
        ticks="outside",
        tickwidth=2,
        ticklen=6,
    )
    export_figure.update_yaxes(
        showline=True,
        linewidth=2,
        linecolor="#111827",
        mirror=True,
        ticks="outside",
        tickwidth=2,
        ticklen=6,
    )

    scene_json = (
        export_figure.layout.scene.to_plotly_json()
        if export_figure.layout.scene is not None
        else {}
    )
    export_figure.update_layout(
        scene={
            **scene_json,
            "xaxis": {
                **scene_json.get("xaxis", {}),
                "backgroundcolor": "white",
                "gridcolor": "#d1d5db",
                "showbackground": False,
                "zerolinecolor": "#9ca3af",
                "title": {"font": {"size": 18}},
            },
            "yaxis": {
                **scene_json.get("yaxis", {}),
                "backgroundcolor": "white",
                "gridcolor": "#d1d5db",
                "showbackground": False,
                "zerolinecolor": "#9ca3af",
                "title": {"font": {"size": 18}},
            },
            "zaxis": {
                **scene_json.get("zaxis", {}),
                "backgroundcolor": "white",
                "gridcolor": "#d1d5db",
                "showbackground": False,
                "zerolinecolor": "#9ca3af",
                "title": {"font": {"size": 18}},
            },
        }
    )
    return export_figure


def create_uv_vis_figure(states: pd.DataFrame, sigma_ev: float = 0.12) -> go.Figure:
    figure = go.Figure()
    if states.empty:
        figure.update_layout(template="plotly_white", title=tr("未解析到 TDDFT 光谱"))
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
            line={"color": "#be123c", "width": 3},
            name=tr("展宽谱"),
            hovertemplate=f"%{{x:.3f}} eV<br>{tr('强度')} %{{y:.4f}}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Bar(
            x=states["energy_eV"],
            y=states["oscillator_strength"],
            width=0.03,
            marker_color="#0f766e",
            opacity=0.55,
            name=tr("跃迁棒谱"),
            hovertemplate=(
                "State %{customdata[0]}<br>%{x:.3f} eV<br>%{customdata[1]:.2f} nm"
                "<br>f=%{y:.4f}<extra></extra>"
            ),
            customdata=states[["state", "wavelength_nm"]].to_numpy(),
        )
    )
    figure.update_layout(
        template="plotly_white",
        xaxis_title=tr("跃迁能量 (eV)"),
        yaxis_title=tr("振子强度 / 相对吸收"),
        barmode="overlay",
        margin={"l": 20, "r": 20, "t": 30, "b": 20},
        legend={"orientation": "h", "y": 1.02, "x": 1, "xanchor": "right"},
    )
    return figure


def create_path_figure(
    data: pd.DataFrame, x_col: str, y_col: str, title: str, x_label: str
) -> go.Figure:
    figure = go.Figure()
    if data.empty:
        figure.update_layout(template="plotly_white", title=title)
        return figure
    figure.add_trace(
        go.Scatter(
            x=data[x_col],
            y=data[y_col],
            mode="lines+markers",
            line={"color": "#1d4ed8", "width": 3},
            marker={"color": "#1e40af", "size": 8},
            hovertemplate=f"{x_label}=%{{x}}<br>{tr('能量 (Hartree)').replace(' (Hartree)', '')}=%{{y:.8f}} Eh<extra></extra>",
        )
    )
    figure.update_layout(
        template="plotly_white",
        title=title,
        xaxis_title=x_label,
        yaxis_title=tr("能量 (Hartree)"),
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
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
            marker_color="#0f766e",
            hovertemplate="%{x}<br>%{y:.8f} Eh<extra></extra>",
        )
    )
    figure.update_layout(
        template="plotly_white",
        title=tr("批量总能量比较"),
        xaxis_title=tr("文件"),
        yaxis_title=tr("总能量 (Hartree)"),
        margin={"l": 20, "r": 20, "t": 50, "b": 80},
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
            marker_color="#be123c",
            hovertemplate=f"%{{x}}<br>{tr('激发态数')} %{{y}}<extra></extra>",
        )
    )
    figure.update_layout(
        template="plotly_white",
        title=tr("批量 TDDFT 激发态数比较"),
        xaxis_title=tr("文件"),
        yaxis_title=tr("激发态数"),
        margin={"l": 20, "r": 20, "t": 50, "b": 80},
    )
    return figure


def create_cube_slice_figure(cube: CubeData, axis: str = "z", index: int | None = None) -> go.Figure:
    axis_map = {"x": 0, "y": 1, "z": 2}
    axis_id = axis_map[axis]
    if index is None:
        index = cube.grid_shape[axis_id] // 2
    cube_kind = cube.metadata.get("cube_kind", "generic")

    if axis == "x":
        plane = cube.values[index, :, :]
        x_title, y_title = "j", "k"
    elif axis == "y":
        plane = cube.values[:, index, :]
        x_title, y_title = "i", "k"
    else:
        plane = cube.values[:, :, index]
        x_title, y_title = "i", "j"

    colorscale = _cube_slice_colorscale(cube_kind)
    z_mid = 0 if np.min(plane) < 0 < np.max(plane) else None
    colorbar_title = _cube_colorbar_title(cube_kind)
    figure = go.Figure(
        data=[
            go.Heatmap(
                z=plane,
                colorscale=colorscale,
                zmid=z_mid,
                colorbar={"title": colorbar_title},
                hovertemplate=f"{x_title}=%{{x}}<br>{y_title}=%{{y}}<br>{tr('值')}=%{{z:.6f}}<extra></extra>",
            )
        ]
    )
    figure.update_layout(
        template="plotly_white",
        title=tr(
            "{cube_kind_label} 切片 {axis} = {index}",
            cube_kind_label=cube_kind_label(cube_kind),
            axis=axis.upper(),
            index=index,
        ),
        xaxis_title=x_title,
        yaxis_title=y_title,
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
    )
    return figure


def create_cube_isosurface_figure(
    cube: CubeData,
    level: float = 0.03,
    quality: str = "精细",
    show_structure: bool = True,
    opacity: float | None = None,
) -> go.Figure:
    cube_kind = cube.metadata.get("cube_kind", "generic")
    stride = _cube_stride(cube, max_points=_cube_render_budget(cube_kind, quality))
    xs, ys, zs, values = sample_cube_grid(cube, stride=stride)
    positive_extent = float(np.max(values)) if values.size else 0.0
    negative_extent = float(np.max(-values)) if values.size else 0.0

    figure = go.Figure()
    if cube_kind == "esp":
        esp_opacity = opacity if opacity is not None else 0.20
        esp_levels = esp_signed_surface_levels(cube, abs(level))
        positive_level = esp_levels["positive_level"]
        negative_level = esp_levels["negative_level"]
        positive_cap = esp_levels["positive_cap"]
        negative_cap = esp_levels["negative_cap"]
        if positive_extent > positive_level:
            figure.add_trace(
                _single_signed_isosurface(
                    xs,
                    ys,
                    zs,
                    values,
                    level=positive_level,
                    max_extent=min(positive_extent, positive_cap),
                    color=ESP_COLOR_POSITIVE,
                    name=tr("ESP > 0"),
                    opacity=esp_opacity,
                )
            )
        if negative_extent > negative_level:
            figure.add_trace(
                _single_signed_isosurface(
                    xs,
                    ys,
                    zs,
                    -values,
                    level=negative_level,
                    max_extent=min(negative_extent, negative_cap),
                    color=ESP_COLOR_NEGATIVE,
                    name=tr("ESP < 0"),
                    opacity=esp_opacity,
                )
            )
    elif cube_kind == "orbital":
        orbital_opacity = opacity if opacity is not None else 0.82
        if positive_extent > abs(level):
            figure.add_trace(
                _single_signed_isosurface(
                    xs,
                    ys,
                    zs,
                    values,
                    level=abs(level),
                    max_extent=positive_extent,
                    color=ORBITAL_COLOR_POSITIVE,
                    name=tr("phase +"),
                    opacity=orbital_opacity,
                )
            )
        if negative_extent > abs(level):
            figure.add_trace(
                _single_signed_isosurface(
                    xs,
                    ys,
                    zs,
                    -values,
                    level=abs(level),
                    max_extent=negative_extent,
                    color=ORBITAL_COLOR_NEGATIVE,
                    name=tr("phase -"),
                    opacity=orbital_opacity,
                )
            )
    else:
        default_opacity = opacity if opacity is not None else 0.55
        if np.min(values) < 0 < np.max(values):
            figure.add_trace(
                go.Isosurface(
                    x=xs,
                    y=ys,
                    z=zs,
                    value=values,
                    isomin=-abs(level),
                    isomax=abs(level),
                    surface_count=2,
                    colorscale=_cube_slice_colorscale(cube_kind),
                    caps={"x_show": False, "y_show": False, "z_show": False},
                    opacity=default_opacity,
                    colorbar={"title": _cube_colorbar_title(cube_kind)},
                    showscale=True,
                )
            )
        else:
            extent = float(np.max(np.abs(values))) if values.size else abs(level)
            figure.add_trace(
                _single_signed_isosurface(
                    xs,
                    ys,
                    zs,
                    np.abs(values),
                    level=abs(level),
                    max_extent=extent,
                    color="rgb(20, 184, 166)",
                    name=_cube_colorbar_title(cube_kind),
                    opacity=default_opacity,
                )
            )

    if show_structure and cube.atoms is not None and len(cube.atoms) > 0:
        for trace in _subtle_structure_traces(cube.atoms, cube_kind):
            figure.add_trace(trace)

    title = _cube_isosurface_title(cube_kind, level)
    figure.update_layout(
        template="plotly_white",
        title=title,
        margin={"l": 0, "r": 0, "t": 50, "b": 0},
        scene={
            "aspectmode": "data",
            "xaxis_title": "X (A)",
            "yaxis_title": "Y (A)",
            "zaxis_title": "Z (A)",
            "camera": {"eye": {"x": 1.65, "y": 1.45, "z": 1.2}},
        },
        legend={"orientation": "h", "y": 1.02, "x": 1, "xanchor": "right"},
        showlegend=cube_kind in {"esp", "orbital"},
    )
    return figure


def structure_summary(atoms: Atoms) -> dict[str, str]:
    counter = Counter(atoms.get_chemical_symbols())
    composition = ", ".join(f"{element}:{count}" for element, count in sorted(counter.items()))
    return {
        "formula": atoms.get_chemical_formula(),
        "composition": composition,
        "atom_count": str(len(atoms)),
    }


def top_mode_atoms(atoms: Atoms, mode_displacements: np.ndarray, top_n: int = 8) -> pd.DataFrame:
    magnitudes = np.linalg.norm(mode_displacements, axis=1)
    data = pd.DataFrame(
        {
            "atom": [f"{symbol}{index + 1}" for index, symbol in enumerate(atoms.get_chemical_symbols())],
            "magnitude": magnitudes,
            "dx": mode_displacements[:, 0],
            "dy": mode_displacements[:, 1],
            "dz": mode_displacements[:, 2],
        }
    )
    return data.sort_values("magnitude", ascending=False).head(top_n).reset_index(drop=True)


def _cube_stride(cube: CubeData, max_points: int = 30_000) -> int:
    stride = 1
    point_count = cube.voxel_count
    while point_count / (stride**3) > max_points:
        stride += 1
    return stride


def _cube_render_budget(cube_kind: str, quality: str) -> int:
    normalized_quality = {
        "标准": "standard",
        "Standard": "standard",
        "精细": "fine",
        "Fine": "fine",
        "极致": "ultra",
        "Ultra": "ultra",
    }.get(quality, quality)
    base_budget = {
        "standard": 45_000,
        "fine": 120_000,
        "ultra": 220_000,
    }.get(normalized_quality, 120_000)
    if cube_kind in {"orbital", "esp"}:
        return int(base_budget * 1.25)
    return base_budget


def _normalize_mode(mode_displacements: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mode_displacements, axis=1)
    max_norm = float(np.max(norms)) if norms.size else 1.0
    if max_norm == 0:
        return mode_displacements.copy()
    return mode_displacements / max_norm


def _cube_slice_colorscale(cube_kind: str) -> list[list[float | str]] | str:
    if cube_kind == "esp":
        return ESP_SLICE_COLORSCALE
    if cube_kind == "orbital":
        return ORBITAL_SLICE_COLORSCALE
    if cube_kind in {"electron_density", "density"}:
        return "Viridis"
    if cube_kind == "spin_density":
        return "RdBu_r"
    return "RdBu"


def _cube_colorbar_title(cube_kind: str) -> str:
    return {
        "esp": "ESP",
        "orbital": "Orbital phase",
        "electron_density": "Density",
        "spin_density": "Spin density",
        "density": "Density",
    }.get(cube_kind, "Value")


def _cube_isosurface_title(cube_kind: str, level: float) -> str:
    if cube_kind == "esp":
        return tr("ESP 等势面 |V| = {level}", level=f"{abs(level):.3f}")
    if cube_kind == "orbital":
        return tr("轨道相位等值面 |psi| = {level}", level=f"{abs(level):.3f}")
    if cube_kind == "electron_density":
        return tr("电子密度等值面 rho = {level}", level=f"{abs(level):.3f}")
    if cube_kind == "spin_density":
        return tr("自旋密度等值面 |rho_s| = {level}", level=f"{abs(level):.3f}")
    return tr("Cube 等值面 |value| = {level}", level=f"{abs(level):.3f}")


def _single_signed_isosurface(
    xs: np.ndarray,
    ys: np.ndarray,
    zs: np.ndarray,
    values: np.ndarray,
    level: float,
    max_extent: float,
    color: str,
    name: str,
    opacity: float,
) -> go.Isosurface:
    iso_max = max(level + max(level * 0.04, 1e-6), max_extent)
    return go.Isosurface(
        x=xs,
        y=ys,
        z=zs,
        value=values,
        isomin=level,
        isomax=iso_max,
        surface_count=1,
        colorscale=[[0.0, color], [1.0, color]],
        caps={"x_show": False, "y_show": False, "z_show": False},
        opacity=opacity,
        flatshading=False,
        lighting={
            "ambient": 0.55,
            "diffuse": 0.9,
            "specular": 0.2,
            "roughness": 0.35,
            "fresnel": 0.12,
        },
        lightposition={"x": 120, "y": 160, "z": 80},
        showscale=False,
        name=name,
        hovertemplate=f"{name}<br>{tr('阈值')}={level:.4f}<extra></extra>",
    )


def _subtle_structure_traces(atoms: Atoms, cube_kind: str) -> list[go.Scatter3d]:
    positions = atoms.get_positions()
    atom_sizes = [max(covalent_radii[number] * 10, 6) for number in atoms.get_atomic_numbers()]
    atom_color = "rgba(71, 85, 105, 0.45)" if cube_kind == "esp" else "rgba(51, 65, 85, 0.60)"
    bond_color = "rgba(100, 116, 139, 0.45)" if cube_kind == "esp" else "rgba(71, 85, 105, 0.60)"
    bond_trace = _combined_bond_trace(atoms, _build_bond_pairs(atoms))
    traces = [
        go.Scatter3d(
            x=positions[:, 0],
            y=positions[:, 1],
            z=positions[:, 2],
            mode="markers",
            marker={
                "size": atom_sizes,
                "color": atom_color,
                "line": {"color": "rgba(15, 23, 42, 0.35)", "width": 0.8},
            },
            hoverinfo="skip",
            showlegend=False,
        ),
        go.Scatter3d(
            x=bond_trace.x,
            y=bond_trace.y,
            z=bond_trace.z,
            mode="lines",
            line={"color": bond_color, "width": 4},
            hoverinfo="skip",
            showlegend=False,
        ),
    ]
    return traces


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


def _structure_traces(
    atoms: Atoms,
    representation: str = "ball_stick",
    show_labels: bool = False,
) -> list[go.Scatter3d]:
    positions = atoms.get_positions()
    numbers = atoms.get_atomic_numbers()
    symbols = atoms.get_chemical_symbols()
    labels = [f"{symbol}{index + 1}" for index, symbol in enumerate(symbols)]
    style = _representation_config(representation)

    palette = {
        symbol: f"rgb({int(color[0] * 255)}, {int(color[1] * 255)}, {int(color[2] * 255)})"
        for symbol, color in (
            (chemical_symbols[number], jmol_colors[number]) for number in sorted(set(numbers))
        )
    }

    scatter = go.Scatter3d(
        x=positions[:, 0],
        y=positions[:, 1],
        z=positions[:, 2],
        mode="markers+text" if show_labels else "markers",
        text=labels if show_labels else None,
        textposition="top center",
        hovertemplate=tr(
            "原子: %{customdata[0]}<br>元素: %{customdata[1]}<br>x=%{x:.3f}<br>y=%{y:.3f}<br>z=%{z:.3f}<extra></extra>"
        ),
        customdata=np.array(list(zip(labels, symbols, strict=False)), dtype=object),
        marker={
            "size": _structure_atom_sizes(numbers, representation),
            "color": [palette[symbol] for symbol in symbols],
            "line": {"color": "#1f1f1f", "width": style["atom_line_width"]},
            "opacity": style["atom_opacity"],
        },
        showlegend=False,
    )
    return [scatter]


def _mode_vector_traces(
    positions: np.ndarray, displacements: np.ndarray
) -> list[go.Scatter3d]:
    traces: list[go.Scatter3d] = []
    for origin, delta in zip(positions, displacements, strict=False):
        if np.linalg.norm(delta) < 1e-9:
            continue
        target = origin + delta
        traces.append(
            go.Scatter3d(
                x=[origin[0], target[0]],
                y=[origin[1], target[1]],
                z=[origin[2], target[2]],
                mode="lines",
                line={"color": "#dc2626", "width": 7},
                hoverinfo="skip",
                showlegend=False,
            )
        )
    return traces


def _build_bond_pairs(atoms: Atoms) -> list[tuple[int, int]]:
    cutoffs = natural_cutoffs(atoms)
    neighbor_list = NeighborList(cutoffs, self_interaction=False, bothways=True)
    neighbor_list.update(atoms)

    pairs: list[tuple[int, int]] = []
    seen_pairs: set[tuple[int, int]] = set()
    for index in range(len(atoms)):
        neighbors, _ = neighbor_list.get_neighbors(index)
        for neighbor in neighbors:
            pair = tuple(sorted((index, int(neighbor))))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            pairs.append(pair)
    return pairs


def _combined_bond_trace(atoms: Atoms, bond_pairs: list[tuple[int, int]]) -> go.Scatter3d:
    positions = atoms.get_positions()
    x_coords: list[float | None] = []
    y_coords: list[float | None] = []
    z_coords: list[float | None] = []
    for left, right in bond_pairs:
        x0, y0, z0 = positions[left]
        x1, y1, z1 = positions[right]
        x_coords.extend([x0, x1, None])
        y_coords.extend([y0, y1, None])
        z_coords.extend([z0, z1, None])
    return go.Scatter3d(
        x=x_coords,
        y=y_coords,
        z=z_coords,
        mode="lines",
        line={"color": "#6b7280", "width": 6},
        hoverinfo="skip",
        showlegend=False,
    )


def _representation_config(representation: str) -> dict[str, float | bool]:
    return {
        "ball_stick": {
            "atom_scale": 15.0,
            "atom_min_size": 10.0,
            "atom_line_width": 1.0,
            "atom_opacity": 0.96,
            "show_bonds": True,
            "bond_width": 7.0,
            "bond_color": "#6b7280",
        },
        "space_filling": {
            "atom_scale": 18.0,
            "atom_min_size": 18.0,
            "atom_line_width": 0.8,
            "atom_opacity": 0.94,
            "show_bonds": False,
            "bond_width": 0.0,
            "bond_color": "#6b7280",
        },
        "stick": {
            "atom_scale": 5.0,
            "atom_min_size": 5.0,
            "atom_line_width": 0.6,
            "atom_opacity": 0.98,
            "show_bonds": True,
            "bond_width": 10.0,
            "bond_color": "#4b5563",
        },
        "wireframe": {
            "atom_scale": 3.6,
            "atom_min_size": 3.5,
            "atom_line_width": 0.0,
            "atom_opacity": 0.75,
            "show_bonds": True,
            "bond_width": 3.0,
            "bond_color": "#64748b",
        },
    }.get(representation, {
        "atom_scale": 15.0,
        "atom_min_size": 10.0,
        "atom_line_width": 1.0,
        "atom_opacity": 0.96,
        "show_bonds": True,
        "bond_width": 7.0,
        "bond_color": "#6b7280",
    })


def _structure_atom_sizes(numbers: list[int] | np.ndarray, representation: str) -> list[float]:
    style = _representation_config(representation)
    sizes: list[float] = []
    for number in numbers:
        if representation == "space_filling":
            radius = float(vdw_radii[number]) if number < len(vdw_radii) else float("nan")
            if not np.isfinite(radius) or radius <= 0:
                radius = covalent_radii[number] * 1.8
        else:
            radius = covalent_radii[number]
        sizes.append(max(radius * float(style["atom_scale"]), float(style["atom_min_size"])))
    return sizes


def _charge_atom_sizes(
    numbers: list[int] | np.ndarray,
    charge_values: np.ndarray,
    representation: str,
) -> list[float]:
    base_sizes = _structure_atom_sizes(numbers, representation)
    boost_factor = {
        "ball_stick": 16.0,
        "space_filling": 10.0,
        "stick": 8.0,
        "wireframe": 6.0,
    }.get(representation, 12.0)
    return [
        max(base + abs(charge) * boost_factor, 4.0)
        for base, charge in zip(base_sizes, charge_values, strict=False)
    ]


def _representation_bond_trace(
    atoms: Atoms,
    representation: str = "ball_stick",
    bond_pairs: list[tuple[int, int]] | None = None,
) -> go.Scatter3d | None:
    style = _representation_config(representation)
    if not bool(style["show_bonds"]):
        return None
    if bond_pairs is None:
        bond_pairs = _build_bond_pairs(atoms)
    bond_trace = _combined_bond_trace(atoms, bond_pairs)
    bond_trace.line.width = float(style["bond_width"])
    bond_trace.line.color = str(style["bond_color"])
    return bond_trace


def _combined_vector_trace(
    positions: np.ndarray, displacements: np.ndarray
) -> go.Scatter3d:
    x_coords: list[float | None] = []
    y_coords: list[float | None] = []
    z_coords: list[float | None] = []
    for origin, delta in zip(positions, displacements, strict=False):
        target = origin + delta
        x_coords.extend([origin[0], target[0], None])
        y_coords.extend([origin[1], target[1], None])
        z_coords.extend([origin[2], target[2], None])
    return go.Scatter3d(
        x=x_coords,
        y=y_coords,
        z=z_coords,
        mode="lines",
        line={"color": "#dc2626", "width": 7},
        hoverinfo="skip",
        showlegend=False,
    )


def _build_bond_traces(atoms: Atoms) -> list[go.Scatter3d]:
    cutoffs = natural_cutoffs(atoms)
    neighbor_list = NeighborList(cutoffs, self_interaction=False, bothways=True)
    neighbor_list.update(atoms)
    positions = atoms.get_positions()

    traces: list[go.Scatter3d] = []
    seen_pairs: set[tuple[int, int]] = set()
    for index in range(len(atoms)):
        neighbors, _ = neighbor_list.get_neighbors(index)
        for neighbor in neighbors:
            pair = tuple(sorted((index, int(neighbor))))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            x0, y0, z0 = positions[pair[0]]
            x1, y1, z1 = positions[pair[1]]
            traces.append(
                go.Scatter3d(
                    x=[x0, x1],
                    y=[y0, y1],
                    z=[z0, z1],
                    mode="lines",
                    line={"color": "#6b7280", "width": 6},
                    hoverinfo="skip",
                    showlegend=False,
                )
            )
    return traces
