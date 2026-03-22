from __future__ import annotations

from collections import Counter
from functools import lru_cache
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from ase import Atoms
from ase.data import covalent_radii, vdw_radii
from ase.data.colors import jmol_colors
from ase.neighborlist import NeighborList, natural_cutoffs
from plotly.offline import get_plotlyjs
from plotly.utils import PlotlyJSONEncoder

from ..i18n import tr
from ..pathway import PathwayResult, build_frame_point_mapping
from ..plot_theme import (
    ACCENT_ORANGE,
    ModelSizeSettings,
    PAPER_CAMERA,
    STRUCTURE_CAMERA,
    apply_standard_2d_style,
    apply_standard_3d_style,
    model_size_preset,
    resolve_visual_style,
    standard_3d_axis_layout,
)
from .pathways import create_path_figure

PLOTLY_JS_BUNDLE = get_plotlyjs()

@lru_cache(maxsize=1)
def _embedded_3dmol_script() -> str:
    script_path = Path(__file__).resolve().parents[1] / "assets" / "3Dmol-min.js"
    script_text = script_path.read_text(encoding="utf-8")
    return script_text.replace("</script", "<\\/script")


def _rgba(hex_color: str, alpha: float) -> str:
    stripped = hex_color.lstrip("#")
    if len(stripped) != 6:
        return hex_color
    red = int(stripped[0:2], 16)
    green = int(stripped[2:4], 16)
    blue = int(stripped[4:6], 16)
    return f"rgba({red}, {green}, {blue}, {alpha:.3f})"


def create_structure_figure(
    atoms: Atoms,
    representation: str = "ball_stick",
    show_atom_labels: bool = False,
    measurement_atoms: dict[str, list[int]] | None = None,
    model_size_settings: ModelSizeSettings | None = None,
    visual_style_key: str | None = None,
) -> go.Figure:
    visual_style = resolve_visual_style(visual_style_key)
    figure = go.Figure()
    for trace in _representation_bond_traces(
        atoms,
        representation=representation,
        model_size_settings=model_size_settings,
        visual_style_key=visual_style.key,
    ):
        figure.add_trace(trace)
    for trace in _measurement_traces(atoms, measurement_atoms, visual_style_key=visual_style.key):
        figure.add_trace(trace)
    for trace in _structure_traces(
        atoms,
        representation=representation,
        show_labels=show_atom_labels,
        model_size_settings=model_size_settings,
        visual_style_key=visual_style.key,
    ):
        figure.add_trace(trace)

    apply_standard_3d_style(
        figure,
        camera=visual_style.cameras["structure"],
        showlegend=False,
        margin={"l": 0, "r": 0, "t": 36, "b": 0},
        visual_style_key=visual_style.key,
    )
    figure.update_layout(
        clickmode="event+select",
        scene={
            **figure.layout.scene.to_plotly_json(),
            "xaxis_title": "X (A)",
            "yaxis_title": "Y (A)",
            "zaxis_title": "Z (A)",
        },
    )
    return figure


def create_pathway_frame_figure(
    atoms: Atoms,
    *,
    representation: str = "ball_stick",
    show_atom_labels: bool = False,
    model_size_settings: ModelSizeSettings | None = None,
    bounds: dict[str, list[list[float]] | dict[str, Any]] | None = None,
    show_axes: bool = False,
    frame_label: str | None = None,
    camera: dict[str, Any] | None = None,
    visual_style_key: str | None = None,
) -> go.Figure:
    visual_style = resolve_visual_style(visual_style_key)
    figure = create_structure_figure(
        atoms,
        representation=representation,
        show_atom_labels=show_atom_labels,
        model_size_settings=model_size_settings,
        visual_style_key=visual_style.key,
    )
    scene = figure.layout.scene.to_plotly_json() if figure.layout.scene else {}
    if bounds is None:
        bounds = structure_scene_bounds([atoms])
    scene.update(standard_3d_axis_layout(show_axes=show_axes, visual_style_key=visual_style.key))
    scene["camera"] = camera or bounds.get("camera", visual_style.cameras["structure"])
    for axis_name, axis_range in zip(["xaxis", "yaxis", "zaxis"], bounds["ranges"], strict=False):
        scene.setdefault(axis_name, {})
        scene[axis_name]["range"] = axis_range
    figure.update_layout(
        scene=scene,
        margin={"l": 0, "r": 0, "t": 16 if not frame_label else 34, "b": 0},
        showlegend=False,
        title={"text": ""},
        annotations=(
            [
                {
                    "text": frame_label,
                    "xref": "paper",
                    "yref": "paper",
                    "x": 0.01,
                    "y": 0.99,
                    "showarrow": False,
                    "align": "left",
                    "font": {"size": 16, "color": visual_style.palette["annotation_text"]},
                    "bgcolor": visual_style.palette["annotation_bg"],
                    "bordercolor": visual_style.palette["annotation_border"],
                    "borderwidth": 1,
                    "borderpad": 5,
                }
            ]
            if frame_label
            else []
        ),
    )
    return figure


def structure_scene_bounds(
    atoms_or_frames: list[Atoms],
    *,
    padding_ratio: float = 0.18,
    min_padding: float = 0.55,
    camera: dict[str, Any] | None = None,
) -> dict[str, list[list[float]] | dict[str, Any]]:
    if not atoms_or_frames:
        return {
            "ranges": [[-2.0, 2.0], [-2.0, 2.0], [-2.0, 2.0]],
            "camera": camera or STRUCTURE_CAMERA,
        }
    all_positions = np.vstack([atoms.get_positions() for atoms in atoms_or_frames])
    mins = np.min(all_positions, axis=0)
    maxs = np.max(all_positions, axis=0)
    spans = np.maximum(maxs - mins, 0.4)
    max_span = float(np.max(spans))
    padding = max(min_padding, max_span * padding_ratio)
    ranges: list[list[float]] = []
    for axis_min, axis_max in zip(mins, maxs, strict=False):
        center = float((axis_min + axis_max) / 2.0)
        half_span = float((axis_max - axis_min) / 2.0 + padding)
        ranges.append([center - half_span, center + half_span])
    return {
        "ranges": ranges,
        "camera": camera or (PAPER_CAMERA if max_span > 8.0 else STRUCTURE_CAMERA),
    }


def build_pathway_animation_html(
    pathway: PathwayResult,
    *,
    display_df: pd.DataFrame,
    path_x_col: str,
    path_y_col: str,
    path_title: str,
    path_x_label: str,
    path_y_label: str,
    y_hover_format: str,
    y_suffix: str,
    representation: str = "ball_stick",
    show_atom_labels: bool = False,
    model_size_settings: ModelSizeSettings | None = None,
    show_axes: bool = False,
    default_camera_mode: str = "fixed_all_frames",
    component_id: str = "pathway-animation",
    visual_style_key: str | None = None,
) -> str:
    if not pathway.frames:
        raise ValueError("Pathway animation requires at least one structural frame.")

    visual_style = resolve_visual_style(visual_style_key)
    palette = visual_style.palette
    total_frames = len(pathway.frames)
    global_bounds = structure_scene_bounds(
        [frame.atoms for frame in pathway.frames],
        camera=visual_style.cameras["paper"],
    )
    frame_to_point, point_to_frame = build_frame_point_mapping(pathway)

    structure_frames: list[dict[str, Any]] = []
    for frame_index, frame in enumerate(pathway.frames):
        frame_bounds = (
            global_bounds
            if default_camera_mode == "fixed_all_frames"
            else structure_scene_bounds([frame.atoms], camera=visual_style.cameras["structure"])
        )
        label = tr("帧 {current}/{total}", current=frame_index + 1, total=total_frames)
        frame_figure = create_pathway_frame_figure(
            frame.atoms,
            representation=representation,
            show_atom_labels=show_atom_labels,
            model_size_settings=model_size_settings,
            bounds=frame_bounds,
            show_axes=show_axes,
            frame_label=label,
            camera=frame_bounds.get("camera"),  # type: ignore[arg-type]
            visual_style_key=visual_style.key,
        )
        structure_frames.append(
            {
                "data": [trace.to_plotly_json() for trace in frame_figure.data],
                "layout": frame_figure.layout.to_plotly_json(),
            }
        )

    path_payload: dict[str, Any] | None = None
    if not display_df.empty:
        plot_data = display_df.sort_values(path_x_col, kind="mergesort").reset_index(drop=True).copy()
        plot_data["_point_index"] = plot_data.index
        point_positions = {
            int(row["_point_index"]): {
                "x": row[path_x_col],
                "y": row[path_y_col],
                "label": row.get("label", row["_point_index"]),
            }
            for _, row in plot_data.iterrows()
            if pd.notna(row.get(path_x_col)) and pd.notna(row.get(path_y_col))
        }
        initial_highlight = next((value for value in frame_to_point if value is not None), 0)
        path_figure = create_path_figure(
            display_df,
            path_x_col,
            path_y_col,
            path_title,
            path_x_label,
            y_label=path_y_label,
            y_hover_format=y_hover_format,
            y_suffix=y_suffix,
            highlight_index=initial_highlight,
            visual_style_key=visual_style.key,
        )
        path_payload = {
            "figure": path_figure.to_plotly_json(),
            "highlight_trace_index": len(path_figure.data) - 1 if path_figure.data else None,
            "points": point_positions,
        }

    payload = {
        "component_id": component_id,
        "frame_count": total_frames,
        "default_camera_mode": default_camera_mode,
        "show_path_plot": bool(path_payload),
        "structure_frames": structure_frames,
        "global_ranges": global_bounds["ranges"],
        "default_camera": global_bounds["camera"],
        "frame_to_point": frame_to_point,
        "point_to_frame": {str(key): value for key, value in point_to_frame.items()},
        "path_payload": path_payload,
        "default_frame_duration_ms": 120,
        "speed_options": [
            {"label": "0.5x", "value": 0.5},
            {"label": "1.0x", "value": 1.0},
            {"label": "1.5x", "value": 1.5},
            {"label": "2.0x", "value": 2.0},
            {"label": "4.0x", "value": 4.0},
        ],
        "text": {
            "play": tr("播放"),
            "pause": tr("暂停"),
            "previous": tr("上一帧"),
            "next": tr("下一帧"),
            "speed": tr("播放速度"),
            "camera_mode": tr("视角模式"),
            "fixed_all_frames": tr("固定视角（全路径）"),
            "fit_current_frame": tr("逐帧适配"),
            "frame_status": tr("当前帧"),
            "path_status": tr("路径联动"),
            "path_status_enabled": tr("点击路径点可跳转到对应帧。"),
        },
    }

    payload_json = json.dumps(payload, ensure_ascii=False, cls=PlotlyJSONEncoder)
    return f"""
<div class="orca-path-animation-root">
  <div class="orca-path-animation-toolbar">
    <button type="button" id="{component_id}-prev"></button>
    <button type="button" id="{component_id}-toggle"></button>
    <button type="button" id="{component_id}-next"></button>
    <input id="{component_id}-slider" type="range" min="0" max="{total_frames - 1}" value="0" step="1" />
    <span id="{component_id}-status"></span>
    <label>
      <span id="{component_id}-speed-label"></span>
      <select id="{component_id}-speed"></select>
    </label>
    <label>
      <span id="{component_id}-camera-label"></span>
      <select id="{component_id}-camera-mode"></select>
    </label>
  </div>
  <div class="orca-path-animation-grid {'with-path' if path_payload else 'without-path'}">
    <div id="{component_id}-structure" class="orca-path-structure-panel"></div>
    <div id="{component_id}-path" class="orca-path-curve-panel"></div>
  </div>
  <div class="orca-path-animation-footnote">{tr("点击路径点可跳转到对应帧。") if path_payload else ""}</div>
</div>
<style>
  .orca-path-animation-root {{
    width: 100%;
    color: {palette["text_primary"]};
  }}
  .orca-path-animation-toolbar {{
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: center;
    margin-bottom: 10px;
    font-family: {json.dumps(visual_style.font_family)};
  }}
  .orca-path-animation-toolbar button,
  .orca-path-animation-toolbar select {{
    border: 1px solid {palette["border"]};
    background: {palette["viewer_card_bg"]};
    color: {palette["text_primary"]};
    border-radius: 10px;
    padding: 6px 12px;
    font-size: 13px;
  }}
  .orca-path-animation-toolbar label {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: {palette["text_muted"]};
  }}
  .orca-path-animation-toolbar input[type="range"] {{
    flex: 1 1 240px;
    min-width: 200px;
  }}
  .orca-path-animation-grid {{
    display: grid;
    gap: 12px;
  }}
  .orca-path-animation-grid.with-path {{
    grid-template-columns: minmax(0, 1.3fr) minmax(320px, 0.9fr);
  }}
  .orca-path-animation-grid.without-path {{
    grid-template-columns: minmax(0, 1fr);
  }}
  .orca-path-structure-panel,
  .orca-path-curve-panel {{
    border: 1px solid {palette["viewer_border"]};
    border-radius: 16px;
    overflow: hidden;
    background: {palette["viewer_card_bg"]};
    min-height: 560px;
  }}
  .orca-path-animation-footnote {{
    margin-top: 8px;
    font-size: 13px;
    color: {palette["text_muted"]};
  }}
</style>
<script>{PLOTLY_JS_BUNDLE}</script>
<script>
(() => {{
  const payload = {payload_json};
  const structureDiv = document.getElementById(payload.component_id + "-structure");
  const pathDiv = document.getElementById(payload.component_id + "-path");
  const toggle = document.getElementById(payload.component_id + "-toggle");
  const prevBtn = document.getElementById(payload.component_id + "-prev");
  const nextBtn = document.getElementById(payload.component_id + "-next");
  const slider = document.getElementById(payload.component_id + "-slider");
  const status = document.getElementById(payload.component_id + "-status");
  const speedLabel = document.getElementById(payload.component_id + "-speed-label");
  const speedSelect = document.getElementById(payload.component_id + "-speed");
  const cameraLabel = document.getElementById(payload.component_id + "-camera-label");
  const cameraSelect = document.getElementById(payload.component_id + "-camera-mode");
  const structureConfig = {{ displaylogo: false, responsive: true, scrollZoom: true }};
  const pathConfig = {{ displaylogo: false, responsive: true, scrollZoom: false }};
  let currentFrame = 0;
  let timerHandle = null;
  let playing = false;
  let speedMultiplier = 1.0;
  let currentCamera = null;

  function clone(value) {{
    return JSON.parse(JSON.stringify(value));
  }}

  function currentFrameLayout(index) {{
    const frame = payload.structure_frames[index];
    const layout = clone(frame.layout);
    if (cameraSelect.value === "fixed_all_frames") {{
      layout.scene.xaxis.range = payload.global_ranges[0];
      layout.scene.yaxis.range = payload.global_ranges[1];
      layout.scene.zaxis.range = payload.global_ranges[2];
      layout.scene.camera = currentCamera || payload.default_camera;
    }}
    return layout;
  }}

  function updateStatus() {{
    status.textContent = `${{payload.text.frame_status}} ${{currentFrame + 1}} / ${{payload.frame_count}}`;
    slider.value = String(currentFrame);
    toggle.textContent = playing ? payload.text.pause : payload.text.play;
  }}

  function updatePathHighlight(frameIndex) {{
    if (!payload.show_path_plot || !payload.path_payload) return;
    const pointIndex = payload.frame_to_point[frameIndex];
    const highlightTraceIndex = payload.path_payload.highlight_trace_index;
    if (highlightTraceIndex == null || !pathDiv.data) return;
    if (pointIndex == null) {{
      Plotly.restyle(pathDiv, {{ x: [[]], y: [[]] }}, [highlightTraceIndex]);
      return;
    }}
    const point = payload.path_payload.points[String(pointIndex)] || payload.path_payload.points[pointIndex];
    if (!point) return;
    Plotly.restyle(
      pathDiv,
      {{ x: [[point.x]], y: [[point.y]], customdata: [[[point.label, Number(pointIndex)]]] }},
      [highlightTraceIndex],
    );
  }}

  function renderFrame(frameIndex, preserveCamera = true) {{
    currentFrame = Math.max(0, Math.min(payload.frame_count - 1, frameIndex));
    if (preserveCamera && structureDiv.layout && structureDiv.layout.scene && structureDiv.layout.scene.camera) {{
      currentCamera = structureDiv.layout.scene.camera;
    }}
    const frame = payload.structure_frames[currentFrame];
    Plotly.react(structureDiv, frame.data, currentFrameLayout(currentFrame), structureConfig).then(() => {{
      if (cameraSelect.value === "fixed_all_frames" && currentCamera) {{
        Plotly.relayout(structureDiv, {{ "scene.camera": currentCamera }});
      }}
    }});
    updatePathHighlight(currentFrame);
    updateStatus();
  }}

  function stopPlayback() {{
    if (timerHandle) {{
      window.clearInterval(timerHandle);
      timerHandle = null;
    }}
    playing = false;
    updateStatus();
  }}

  function startPlayback() {{
    stopPlayback();
    playing = true;
    const intervalMs = Math.max(40, Math.round(payload.default_frame_duration_ms / speedMultiplier));
    timerHandle = window.setInterval(() => {{
      const nextFrame = (currentFrame + 1) % payload.frame_count;
      renderFrame(nextFrame, true);
    }}, intervalMs);
    updateStatus();
  }}

  prevBtn.textContent = payload.text.previous;
  nextBtn.textContent = payload.text.next;
  speedLabel.textContent = payload.text.speed;
  cameraLabel.textContent = payload.text.camera_mode;
  payload.speed_options.forEach((option) => {{
    const el = document.createElement("option");
    el.value = String(option.value);
    el.textContent = option.label;
    if (option.value === 1.0) el.selected = true;
    speedSelect.appendChild(el);
  }});
  [["fixed_all_frames", payload.text.fixed_all_frames], ["fit_current_frame", payload.text.fit_current_frame]].forEach(([value, label]) => {{
    const el = document.createElement("option");
    el.value = value;
    el.textContent = label;
    if (value === payload.default_camera_mode) el.selected = true;
    cameraSelect.appendChild(el);
  }});

  toggle.addEventListener("click", () => {{
    if (playing) {{
      stopPlayback();
    }} else {{
      startPlayback();
    }}
  }});
  prevBtn.addEventListener("click", () => {{
    stopPlayback();
    renderFrame(currentFrame - 1, true);
  }});
  nextBtn.addEventListener("click", () => {{
    stopPlayback();
    renderFrame(currentFrame + 1, true);
  }});
  slider.addEventListener("input", (event) => {{
    stopPlayback();
    renderFrame(Number(event.target.value), true);
  }});
  speedSelect.addEventListener("change", () => {{
    speedMultiplier = Number(speedSelect.value || "1.0");
    if (playing) {{
      startPlayback();
    }}
  }});
  cameraSelect.addEventListener("change", () => {{
    stopPlayback();
    currentCamera = null;
    renderFrame(currentFrame, false);
  }});

  Plotly.newPlot(
    structureDiv,
    payload.structure_frames[0].data,
    currentFrameLayout(0),
    structureConfig,
  ).then(() => {{
    if (payload.show_path_plot && payload.path_payload) {{
      Plotly.newPlot(
        pathDiv,
        payload.path_payload.figure.data,
        payload.path_payload.figure.layout,
        pathConfig,
      ).then(() => {{
        pathDiv.on("plotly_click", (event) => {{
          const customData = event?.points?.[0]?.customdata;
          if (!customData || customData.length < 2) return;
          const pointIndex = Number(customData[1]);
          const frameIndex = payload.point_to_frame[String(pointIndex)];
          if (frameIndex == null) return;
          stopPlayback();
          renderFrame(Number(frameIndex), true);
        }});
      }});
    }} else {{
      pathDiv.style.display = "none";
    }}
    structureDiv.on("plotly_relayout", (event) => {{
      if (event["scene.camera"]) {{
        currentCamera = event["scene.camera"];
      }}
    }});
    renderFrame(0, false);
  }});
}})();
</script>
"""


def build_structure_viewer_html(
    atoms: Atoms,
    representation: str = "ball_stick",
    show_atom_labels: bool = False,
    enable_measurement: bool = True,
    component_id: str = "structure-viewer",
    model_size_settings: ModelSizeSettings | None = None,
    visual_style_key: str | None = None,
) -> str:
    visual_style = resolve_visual_style(visual_style_key)
    palette = visual_style.palette
    xyz_lines = [str(len(atoms)), "ORCA Visualizer structure"]
    atom_records: list[dict[str, float | int | str]] = []
    for index, (symbol, position) in enumerate(
        zip(atoms.get_chemical_symbols(), atoms.get_positions(), strict=False)
    ):
        xyz_lines.append(f"{symbol} {position[0]:.8f} {position[1]:.8f} {position[2]:.8f}")
        atom_records.append(
            {
                "index": index,
                "label": f"{symbol}{index + 1}",
                "symbol": symbol,
                "x": float(position[0]),
                "y": float(position[1]),
                "z": float(position[2]),
            }
        )

    payload = {
        "xyz": "\n".join(xyz_lines),
        "style": _structure_viewer_style(
            representation,
            model_size_settings=model_size_settings,
            visual_style_key=visual_style.key,
        ),
        "show_atom_labels": show_atom_labels,
        "enable_measurement": enable_measurement,
        "component_id": component_id,
        "atoms": atom_records,
        "atom_colors": {
            str(index): _display_atom_color(
                atoms.get_atomic_numbers()[index],
                visual_style_key=visual_style.key,
            )
            for index in range(len(atoms))
        },
        "theme": {
            "viewer_background": palette["paper_bg"],
            "label_background": palette["annotation_bg"],
            "label_font": palette["annotation_text"],
            "label_border": palette["annotation_border"],
        },
        "measurement_colors": {
            "distance": palette["measure_distance"],
            "angle": palette["measure_angle"],
            "dihedral": palette["measure_dihedral"],
            "selection": palette["measure_selection"],
        },
        "text": {
            "undo": tr("撤销上一个"),
            "clear": tr("清空点选"),
            "selected_atoms": tr("已选原子"),
            "measurement_result": tr("测量结果"),
            "viewer_hint": tr("点击原子开始测量，旋转和缩放不会中断选择。"),
            "viewer_hint_idle": tr("点选 3D 结构中的原子以开始测量。"),
            "viewer_hint_auto": tr("连续点选 2/3/4 个原子后会自动显示距离、键角和二面角。"),
            "pending": tr("至少选择 2 个原子开始测量。"),
            "none": tr("未选择"),
            "load_failed": tr("3D 结构查看器加载失败"),
            "distance_value": tr("距离 (Å)"),
            "angle_value": tr("键角 (°)"),
            "dihedral_value": tr("二面角 (°)"),
        },
    }

    payload_json = json.dumps(payload, ensure_ascii=False)
    return f"""
<div class="orca-structure-shell">
  <div class="orca-structure-header">{tr("连续点选 2/3/4 个原子后会自动显示距离、键角和二面角。") if enable_measurement else ""}</div>
  {"<div class='orca-structure-toolbar'><button type='button' data-action='undo'></button><button type='button' data-action='clear'></button></div>" if enable_measurement else ""}
  <div id="{component_id}-viewer" class="orca-structure-viewer"></div>
  {"<div class='orca-structure-meta'><div class='orca-measure-card'><div class='orca-measure-title' id='" + component_id + "-selected-title'></div><div class='orca-measure-body' id='" + component_id + "-selected'></div></div><div class='orca-measure-card'><div class='orca-measure-title' id='" + component_id + "-result-title'></div><div class='orca-measure-body' id='" + component_id + "-result'></div></div></div>" if enable_measurement else ""}
</div>
<style>
  html, body {{
    margin: 0;
    padding: 0;
    background: {palette["paper_bg"]};
    font-family: {json.dumps(visual_style.font_family)};
    color: {palette["text_primary"]};
  }}
  .orca-structure-shell {{
    width: 100%;
  }}
  .orca-structure-header {{
    margin: 0 0 10px 0;
    font-size: 14px;
    color: {palette["text_muted"]};
  }}
  .orca-structure-toolbar {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 10px;
  }}
  .orca-structure-toolbar button {{
    border: 1px solid {palette["border"]};
    background: {palette["viewer_card_alt_bg"]};
    color: {palette["text_primary"]};
    border-radius: 999px;
    padding: 6px 12px;
    font-size: 13px;
    cursor: pointer;
  }}
  .orca-structure-toolbar button.active {{
    background: {palette["accent_secondary"]};
    border-color: {palette["accent_secondary"]};
    color: {palette["text_inverse"]};
  }}
  .orca-structure-viewer {{
    width: 100%;
    height: 560px;
    border: 1px solid {palette["viewer_border"]};
    border-radius: 16px;
    overflow: hidden;
    background: {palette["viewer_bg"]};
  }}
  .orca-structure-meta {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
    margin-top: 10px;
  }}
  .orca-measure-card {{
    border: 1px solid {palette["viewer_border"]};
    border-radius: 14px;
    padding: 10px 12px;
    background: {palette["viewer_card_bg"]};
  }}
  .orca-measure-title {{
    font-size: 12px;
    color: {palette["text_muted"]};
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }}
  .orca-measure-body {{
    font-size: 14px;
    line-height: 1.5;
    color: {palette["text_primary"]};
    white-space: pre-wrap;
  }}
</style>
<script>{_embedded_3dmol_script()}</script>
<script>
  (function() {{
    const data = {payload_json};
    const viewerId = "{component_id}-viewer";
    const viewerDiv = document.getElementById(viewerId);
    const toolbar = document.querySelector(".orca-structure-toolbar");
    const header = document.querySelector(".orca-structure-header");
    const selectedTitle = document.getElementById("{component_id}-selected-title");
    const selectedBody = document.getElementById("{component_id}-selected");
    const resultTitle = document.getElementById("{component_id}-result-title");
    const resultBody = document.getElementById("{component_id}-result");
    let viewer = null;
    let allAtoms = [];
    let selected = [];
    let dynamicShapes = [];
    let dynamicLabels = [];
    let staticLabels = [];

    function load3Dmol() {{
      return new Promise((resolve, reject) => {{
        if (window.$3Dmol) {{
          resolve(window.$3Dmol);
          return;
        }}
        reject(new Error("3dmol-not-available"));
      }});
    }}

    function midpoint(a, b) {{
      return {{ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, z: (a.z + b.z) / 2 }};
    }}

    function centroid(points) {{
      return {{
        x: points.reduce((acc, point) => acc + point.x, 0) / points.length,
        y: points.reduce((acc, point) => acc + point.y, 0) / points.length,
        z: points.reduce((acc, point) => acc + point.z, 0) / points.length,
      }};
    }}

    function distanceValue(a, b) {{
      return Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
    }}

    function angleValue(a, b, c) {{
      const ba = [a.x - b.x, a.y - b.y, a.z - b.z];
      const bc = [c.x - b.x, c.y - b.y, c.z - b.z];
      const dot = ba[0] * bc[0] + ba[1] * bc[1] + ba[2] * bc[2];
      const normBa = Math.hypot(...ba);
      const normBc = Math.hypot(...bc);
      if (normBa < 1e-12 || normBc < 1e-12) return null;
      const cosine = Math.min(1, Math.max(-1, dot / (normBa * normBc)));
      return Math.acos(cosine) * 180 / Math.PI;
    }}

    function dihedralValue(a, b, c, d) {{
      const b0 = [b.x - a.x, b.y - a.y, b.z - a.z];
      const b1 = [c.x - b.x, c.y - b.y, c.z - b.z];
      const b2 = [d.x - c.x, d.y - c.y, d.z - c.z];
      const b1Norm = Math.hypot(...b1);
      if (b1Norm < 1e-12) return null;
      const b1Unit = b1.map((value) => value / b1Norm);
      const dot01 = b0[0] * b1Unit[0] + b0[1] * b1Unit[1] + b0[2] * b1Unit[2];
      const dot21 = b2[0] * b1Unit[0] + b2[1] * b1Unit[1] + b2[2] * b1Unit[2];
      const v = [b0[0] - dot01 * b1Unit[0], b0[1] - dot01 * b1Unit[1], b0[2] - dot01 * b1Unit[2]];
      const w = [b2[0] - dot21 * b1Unit[0], b2[1] - dot21 * b1Unit[1], b2[2] - dot21 * b1Unit[2]];
      const cross = [
        b1Unit[1] * v[2] - b1Unit[2] * v[1],
        b1Unit[2] * v[0] - b1Unit[0] * v[2],
        b1Unit[0] * v[1] - b1Unit[1] * v[0],
      ];
      const x = v[0] * w[0] + v[1] * w[1] + v[2] * w[2];
      const y = cross[0] * w[0] + cross[1] * w[1] + cross[2] * w[2];
      return Math.atan2(y, x) * 180 / Math.PI;
    }}

    function atomByIndex(index) {{
      return allAtoms.find((atom) => atom.index === index) || null;
    }}

    function clearDynamicOverlays() {{
      dynamicShapes.forEach((shape) => viewer.removeShape(shape));
      dynamicShapes = [];
      dynamicLabels.forEach((label) => viewer.removeLabel(label));
      dynamicLabels = [];
    }}

    function addHighlight(atom) {{
      dynamicShapes.push(viewer.addSphere({{
        center: {{ x: atom.x, y: atom.y, z: atom.z }},
        radius: data.style.highlight_radius,
        color: data.measurement_colors.selection,
        alpha: 0.24,
      }}));
    }}

    function updateMeasurementView() {{
      if (!data.enable_measurement) return;
      clearDynamicOverlays();
      const selectedAtoms = selected.map(atomByIndex).filter(Boolean);
      selectedAtoms.forEach(addHighlight);

      const orderedLabels = selectedAtoms.map((atom) => `${{atom.elem || atom.symbol}}${{atom.index + 1}}`);
      selectedTitle.textContent = data.text.selected_atoms;
      selectedBody.textContent = orderedLabels.length ? orderedLabels.join(" -> ") : data.text.none;
      resultTitle.textContent = data.text.measurement_result;

      if (selectedAtoms.length < 2) {{
        resultBody.textContent = data.text.pending;
        header.textContent = orderedLabels.length ? data.text.viewer_hint : data.text.viewer_hint_idle;
        viewer.render();
        return;
      }}

      const lines = [];
      if (selectedAtoms.length === 2) {{
        const [a, b] = selectedAtoms;
        const value = distanceValue(a, b);
        dynamicShapes.push(viewer.addLine({{
          start: {{ x: a.x, y: a.y, z: a.z }},
          end: {{ x: b.x, y: b.y, z: b.z }},
          dashed: true,
          color: data.measurement_colors.distance,
          linewidth: 3,
        }}));
        dynamicLabels.push(viewer.addLabel(`${{data.text.distance_value}}: ${{value.toFixed(4)}} Å`, {{
          position: midpoint(a, b),
          backgroundColor: data.theme.label_background,
          fontColor: data.theme.label_font,
          borderColor: data.measurement_colors.distance,
          inFront: true,
        }}));
        lines.push(`${{data.text.distance_value}}: ${{value.toFixed(4)}} Å`);
      }}

      if (selectedAtoms.length >= 3) {{
        const [a, b, c] = selectedAtoms;
        const value = angleValue(a, b, c);
        dynamicShapes.push(viewer.addLine({{
          start: {{ x: a.x, y: a.y, z: a.z }},
          end: {{ x: b.x, y: b.y, z: b.z }},
          dashed: true,
          color: data.measurement_colors.angle,
          linewidth: 3,
        }}));
        dynamicShapes.push(viewer.addLine({{
          start: {{ x: b.x, y: b.y, z: b.z }},
          end: {{ x: c.x, y: c.y, z: c.z }},
          dashed: true,
          color: data.measurement_colors.angle,
          linewidth: 3,
        }}));
        dynamicLabels.push(viewer.addLabel(`${{data.text.angle_value}}: ${{value.toFixed(2)}}°`, {{
          position: centroid([a, b, c]),
          backgroundColor: data.theme.label_background,
          fontColor: data.theme.label_font,
          borderColor: data.measurement_colors.angle,
          inFront: true,
        }}));
        lines.push(`${{data.text.angle_value}}: ${{value.toFixed(2)}}°`);
      }}

      if (selectedAtoms.length >= 4) {{
        const [a, b, c, d] = selectedAtoms;
        const value = dihedralValue(a, b, c, d);
        dynamicShapes.push(viewer.addLine({{
          start: {{ x: a.x, y: a.y, z: a.z }},
          end: {{ x: b.x, y: b.y, z: b.z }},
          dashed: true,
          color: data.measurement_colors.dihedral,
          linewidth: 3,
        }}));
        dynamicShapes.push(viewer.addLine({{
          start: {{ x: b.x, y: b.y, z: b.z }},
          end: {{ x: c.x, y: c.y, z: c.z }},
          dashed: true,
          color: data.measurement_colors.dihedral,
          linewidth: 3,
        }}));
        dynamicShapes.push(viewer.addLine({{
          start: {{ x: c.x, y: c.y, z: c.z }},
          end: {{ x: d.x, y: d.y, z: d.z }},
          dashed: true,
          color: data.measurement_colors.dihedral,
          linewidth: 3,
        }}));
        dynamicLabels.push(viewer.addLabel(`${{data.text.dihedral_value}}: ${{value.toFixed(2)}}°`, {{
          position: centroid([a, b, c, d]),
          backgroundColor: data.theme.label_background,
          fontColor: data.theme.label_font,
          borderColor: data.measurement_colors.dihedral,
          inFront: true,
        }}));
        lines.push(`${{data.text.dihedral_value}}: ${{value.toFixed(2)}}°`);
      }}
      resultBody.textContent = lines.join("\\n");
      header.textContent = data.text.viewer_hint_auto;
      viewer.render();
    }}

    function onAtomClick(atom) {{
      const atomIndex = atom.index;
      const existingIndex = selected.indexOf(atomIndex);
      if (existingIndex >= 0) {{
        selected.splice(existingIndex, 1);
        updateMeasurementView();
        return;
      }}
      selected.push(atomIndex);
      selected = selected.slice(-4);
      updateMeasurementView();
    }}

    function initViewer() {{
      const baseStyle = JSON.parse(JSON.stringify(data.style.base));
      const atomColors = data.atom_colors || {{}};
      function atomStyleForColor(color) {{
        const style = {{}};
        if (baseStyle.sphere) style.sphere = {{ ...baseStyle.sphere, color }};
        if (baseStyle.stick) style.stick = {{ ...baseStyle.stick, color }};
        if (baseStyle.line) style.line = {{ ...baseStyle.line, color }};
        if (baseStyle.cross) style.cross = {{ ...baseStyle.cross, color }};
        if (baseStyle.clicksphere) style.clicksphere = {{ ...baseStyle.clicksphere }};
        return style;
      }}
      viewer = window.$3Dmol.createViewer(viewerDiv, {{
        backgroundColor: data.theme.viewer_background,
        antialias: true,
      }});
      viewer.addModel(data.xyz, "xyz");
      viewer.setStyle({{}}, baseStyle);
      Object.entries(atomColors).forEach(([atomIndex, color]) => {{
        viewer.setStyle({{ index: Number(atomIndex) }}, atomStyleForColor(color));
      }});
      viewer.setClickable({{}}, true, onAtomClick);
      viewer.zoomTo();
      viewer.render();
      allAtoms = viewer.selectedAtoms({{}});

      if (data.show_atom_labels) {{
        allAtoms.forEach((atom) => {{
          staticLabels.push(viewer.addLabel(`${{atom.elem}}${{atom.index + 1}}`, {{
            position: atom,
            backgroundColor: data.theme.label_background,
            fontColor: data.theme.label_font,
            borderColor: data.theme.label_border,
            inFront: true,
            fontSize: 12,
          }}));
        }});
      }}

      if (toolbar) {{
        toolbar.querySelector('[data-action="undo"]').textContent = data.text.undo;
        toolbar.querySelector('[data-action="undo"]').addEventListener("click", () => {{
          selected = selected.slice(0, -1);
          updateMeasurementView();
        }});
        toolbar.querySelector('[data-action="clear"]').textContent = data.text.clear;
        toolbar.querySelector('[data-action="clear"]').addEventListener("click", () => {{
          selected = [];
          updateMeasurementView();
        }});
      }}

      updateMeasurementView();
      window.addEventListener("resize", () => viewer.resize(), {{ passive: true }});
    }}

    load3Dmol()
      .then(initViewer)
      .catch((error) => {{
        if (header) {{
          header.textContent = `${{data.text.load_failed}}: ${{error.message}}`;
        }}
      }});
  }})();
</script>
"""


def atom_reference_dataframe(atoms: Atoms) -> pd.DataFrame:
    positions = atoms.get_positions()
    symbols = atoms.get_chemical_symbols()
    labels = [f"{symbol}{index + 1}" for index, symbol in enumerate(symbols)]
    return pd.DataFrame(
        {
            "atom_index": np.arange(1, len(atoms) + 1),
            "atom_label": labels,
            "element": symbols,
            "x": positions[:, 0],
            "y": positions[:, 1],
            "z": positions[:, 2],
        }
    )


def measure_atom_distance(atoms: Atoms, atom_a: int, atom_b: int) -> float | None:
    indices = [atom_a, atom_b]
    if not _measurement_indices_are_valid(atoms, indices, expected_size=2):
        return None
    positions = atoms.get_positions()
    return float(np.linalg.norm(positions[atom_a] - positions[atom_b]))


def measure_atom_angle(atoms: Atoms, atom_a: int, atom_b: int, atom_c: int) -> float | None:
    indices = [atom_a, atom_b, atom_c]
    if not _measurement_indices_are_valid(atoms, indices, expected_size=3):
        return None
    positions = atoms.get_positions()
    vector_ba = positions[atom_a] - positions[atom_b]
    vector_bc = positions[atom_c] - positions[atom_b]
    denominator = float(np.linalg.norm(vector_ba) * np.linalg.norm(vector_bc))
    if denominator <= 1e-12:
        return None
    cosine = float(np.clip(np.dot(vector_ba, vector_bc) / denominator, -1.0, 1.0))
    return float(np.degrees(np.arccos(cosine)))


def measure_atom_dihedral(
    atoms: Atoms,
    atom_a: int,
    atom_b: int,
    atom_c: int,
    atom_d: int,
) -> float | None:
    indices = [atom_a, atom_b, atom_c, atom_d]
    if not _measurement_indices_are_valid(atoms, indices, expected_size=4):
        return None
    positions = atoms.get_positions()
    p0, p1, p2, p3 = (positions[index] for index in indices)
    b0 = -(p1 - p0)
    b1 = p2 - p1
    b2 = p3 - p2
    norm_b1 = np.linalg.norm(b1)
    if norm_b1 <= 1e-12:
        return None
    b1_unit = b1 / norm_b1
    v = b0 - np.dot(b0, b1_unit) * b1_unit
    w = b2 - np.dot(b2, b1_unit) * b1_unit
    norm_v = np.linalg.norm(v)
    norm_w = np.linalg.norm(w)
    if norm_v <= 1e-12 or norm_w <= 1e-12:
        return None
    x_value = np.dot(v, w)
    y_value = np.dot(np.cross(b1_unit, v), w)
    return float(np.degrees(np.arctan2(y_value, x_value)))


def create_vibration_mode_figure(
    atoms: Atoms,
    mode_displacements: np.ndarray,
    amplitude: float = 0.6,
    frame_count: int = 16,
    show_vectors: bool = False,
    representation: str = "ball_stick",
    model_size_settings: ModelSizeSettings | None = None,
    visual_style_key: str | None = None,
) -> go.Figure:
    visual_style = resolve_visual_style(visual_style_key)
    scaled_displacements = _normalize_mode(mode_displacements) * amplitude
    equilibrium_positions = atoms.get_positions()
    phases = np.sin(np.linspace(0, 2 * np.pi, frame_count, endpoint=False))
    bond_pairs = _build_bond_pairs(atoms)

    initial_atoms = atoms.copy()
    initial_atoms.set_positions(equilibrium_positions + phases[0] * scaled_displacements)

    initial_data = _representation_bond_traces(
        initial_atoms,
        representation=representation,
        bond_pairs=bond_pairs,
        model_size_settings=model_size_settings,
        visual_style_key=visual_style.key,
    ) + _structure_traces(
        initial_atoms,
        representation=representation,
        show_labels=False,
        model_size_settings=model_size_settings,
        visual_style_key=visual_style.key,
    )
    if show_vectors:
        initial_data.append(
            _combined_vector_trace(
                equilibrium_positions,
                scaled_displacements,
                visual_style_key=visual_style.key,
            )
        )
    figure = go.Figure(data=initial_data)

    frames: list[go.Frame] = []
    for frame_index, phase in enumerate(phases):
        frame_atoms = atoms.copy()
        frame_atoms.set_positions(equilibrium_positions + phase * scaled_displacements)
        frame_data = _representation_bond_traces(
            frame_atoms,
            representation=representation,
            bond_pairs=bond_pairs,
            model_size_settings=model_size_settings,
            visual_style_key=visual_style.key,
        ) + _structure_traces(
            frame_atoms,
            representation=representation,
            show_labels=False,
            model_size_settings=model_size_settings,
            visual_style_key=visual_style.key,
        )
        if show_vectors:
            frame_data.append(
                _combined_vector_trace(
                    equilibrium_positions,
                    phase * scaled_displacements,
                    visual_style_key=visual_style.key,
                )
            )
        frames.append(go.Frame(data=frame_data, name=str(frame_index), traces=list(range(len(frame_data)))))

    figure.frames = frames
    apply_standard_3d_style(
        figure,
        title=tr("振动模式动画"),
        camera=visual_style.cameras["structure"],
        showlegend=False,
        margin={"l": 0, "r": 0, "t": 40, "b": 0},
        visual_style_key=visual_style.key,
    )
    figure.update_layout(
        uirevision="vibration-mode",
        scene={
            **figure.layout.scene.to_plotly_json(),
            "xaxis_title": "X (A)",
            "yaxis_title": "Y (A)",
            "zaxis_title": "Z (A)",
            "aspectmode": "data",
            "uirevision": "vibration-mode-camera",
        },
        showlegend=False,
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
    representation: str = "ball_stick",
    model_size_settings: ModelSizeSettings | None = None,
    visual_style_key: str | None = None,
) -> str:
    visual_style = resolve_visual_style(visual_style_key)
    theme_palette = visual_style.palette
    scaled_displacements = _normalize_mode(mode_displacements) * amplitude
    positions = atoms.get_positions()
    numbers = atoms.get_atomic_numbers()
    symbols = atoms.get_chemical_symbols()
    bond_pairs = _build_bond_pairs(atoms)

    style = _resolved_model_size_settings(model_size_settings)
    atom_colors = _structure_atom_colors(numbers, visual_style_key=visual_style.key)
    payload = {
        "component_id": component_id,
        "frame_count": frame_count,
        "frame_duration_ms": frame_duration_ms,
        "show_vectors": show_vectors,
        "representation": representation,
        "symbols": symbols,
        "sizes": _structure_atom_sizes(numbers, representation, model_size_settings=style),
        "bond_width": float(
            _representation_config(
                representation,
                model_size_settings=style,
                visual_style_key=visual_style.key,
            )["bond_width"]
        ),
        "colors": atom_colors,
        "theme": {
            "paper_bg": theme_palette["paper_bg"],
            "text_primary": theme_palette["text_primary"],
            "text_muted": theme_palette["text_muted"],
            "border": theme_palette["border"],
            "viewer_card_bg": theme_palette["viewer_card_bg"],
            "scene_bg": theme_palette["scene_bg"],
            "axis": theme_palette["axis"],
            "grid": theme_palette["grid"],
            "bond": theme_palette["structure_bond"],
            "vector": theme_palette["accent_positive"],
            "atom_outline": theme_palette["atom_outline"],
            "font_family": visual_style.font_family,
            "camera": visual_style.cameras["structure"],
            "plotly_template": visual_style.plotly_template,
        },
        "equilibrium_positions": positions.tolist(),
        "displacements": scaled_displacements.tolist(),
        "bond_pairs": bond_pairs,
        "text": {
            "frame_status": tr("当前帧"),
        },
    }

    return f"""
<div class="vib-root">
  <div id="{component_id}" style="width:100%; height:560px;"></div>
  <div class="vib-controls">
    <button id="{component_id}-toggle" type="button">{tr("播放")}</button>
    <input id="{component_id}-slider" type="range" min="0" max="{frame_count - 1}" value="0" step="1" />
    <span id="{component_id}-status">{tr("当前帧")} 1/{frame_count}</span>
  </div>
</div>
<style>
  .vib-root {{
    width: 100%;
    color: {theme_palette["text_primary"]};
  }}
  .vib-controls {{
    display: flex;
    align-items: center;
    gap: 12px;
    padding-top: 8px;
    font-family: {json.dumps(visual_style.font_family)};
  }}
  .vib-controls button {{
    border: 1px solid {theme_palette["border"]};
    background: {theme_palette["viewer_card_bg"]};
    color: {theme_palette["text_primary"]};
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
          line: {{ color: payload.theme.atom_outline, width: 1.2 }},
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
        line: {{ color: payload.theme.bond, width: payload.bond_width }},
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
        line: {{ color: payload.theme.vector, width: 7 }},
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
    status.textContent = `${{payload.text.frame_status}} ${{currentFrame + 1}}/${{payload.frame_count}}`;
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
    template: payload.theme.plotly_template,
    margin: {{ l: 0, r: 0, t: 40, b: 0 }},
    paper_bgcolor: payload.theme.paper_bg,
    plot_bgcolor: payload.theme.paper_bg,
    font: {{ family: payload.theme.font_family, color: payload.theme.text_primary, size: 14 }},
    uirevision: "vibration-mode-html",
    scene: {{
      xaxis: {{ title: "X (A)", gridcolor: payload.theme.grid, linecolor: payload.theme.axis, tickfont: {{ color: payload.theme.text_muted }} }},
      yaxis: {{ title: "Y (A)", gridcolor: payload.theme.grid, linecolor: payload.theme.axis, tickfont: {{ color: payload.theme.text_muted }} }},
      zaxis: {{ title: "Z (A)", gridcolor: payload.theme.grid, linecolor: payload.theme.axis, tickfont: {{ color: payload.theme.text_muted }} }},
      bgcolor: payload.theme.scene_bg,
      aspectmode: "data",
      dragmode: "orbit",
      camera: payload.theme.camera,
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


def create_mode_magnitude_figure(
    atoms: Atoms,
    mode_displacements: np.ndarray,
    *,
    visual_style_key: str | None = None,
) -> go.Figure:
    visual_style = resolve_visual_style(visual_style_key)
    palette = visual_style.palette
    magnitudes = np.linalg.norm(mode_displacements, axis=1)
    labels = [f"{symbol}{index + 1}" for index, symbol in enumerate(atoms.get_chemical_symbols())]
    figure = go.Figure(
        data=[
            go.Bar(
                x=labels,
                y=magnitudes,
                marker_color=palette["accent_warning"],
                marker_line={"color": palette["bar_edge"], "width": 0.8},
                hovertemplate=f"%{{x}}<br>{tr('位移强度')} %{{y:.4f}}<extra></extra>",
            )
        ]
    )
    apply_standard_2d_style(
        figure,
        title=tr("振动模态位移强度"),
        xaxis_title=tr("原子"),
        yaxis_title=tr("相对位移强度"),
        showlegend=False,
        margin={"l": 72, "r": 18, "t": 58, "b": 72},
        visual_style_key=visual_style.key,
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

def _normalize_mode(mode_displacements: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(mode_displacements, axis=1)
    max_norm = float(np.max(norms)) if norms.size else 1.0
    if max_norm == 0:
        return mode_displacements.copy()
    return mode_displacements / max_norm

def _structure_traces(
    atoms: Atoms,
    representation: str = "ball_stick",
    show_labels: bool = False,
    model_size_settings: ModelSizeSettings | None = None,
    visual_style_key: str | None = None,
) -> list[go.Scatter3d]:
    visual_style = resolve_visual_style(visual_style_key)
    positions = atoms.get_positions()
    numbers = atoms.get_atomic_numbers()
    symbols = atoms.get_chemical_symbols()
    labels = [f"{symbol}{index + 1}" for index, symbol in enumerate(symbols)]
    style = _representation_config(
        representation,
        model_size_settings=model_size_settings,
        visual_style_key=visual_style.key,
    )
    colors = _structure_atom_colors(numbers, visual_style_key=visual_style.key)

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
        customdata=np.array(
            list(zip(labels, symbols, np.arange(len(atoms)), strict=False)),
            dtype=object,
        ),
        marker={
            "size": _structure_atom_sizes(numbers, representation, model_size_settings=model_size_settings),
            "color": colors,
            "line": {"color": visual_style.palette["atom_outline"], "width": style["atom_line_width"]},
            "opacity": style["atom_opacity"],
        },
        showlegend=False,
        name="_structure_atoms",
    )
    return [scatter]


def _mode_vector_traces(
    positions: np.ndarray,
    displacements: np.ndarray,
    *,
    visual_style_key: str | None = None,
) -> list[go.Scatter3d]:
    visual_style = resolve_visual_style(visual_style_key)
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
                line={"color": visual_style.palette["accent_positive"], "width": 7},
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


def _measurement_indices_are_valid(
    atoms: Atoms, indices: list[int], expected_size: int
) -> bool:
    if len(indices) != expected_size:
        return False
    if len(set(indices)) != len(indices):
        return False
    return all(0 <= index < len(atoms) for index in indices)


def _measurement_traces(
    atoms: Atoms,
    measurement_atoms: dict[str, list[int]] | None = None,
    *,
    visual_style_key: str | None = None,
) -> list[go.Scatter3d]:
    if not measurement_atoms:
        return []

    visual_style = resolve_visual_style(visual_style_key)
    positions = atoms.get_positions()
    traces: list[go.Scatter3d] = []
    highlighted_indices: list[int] = []
    line_specs = [
        ("distance", visual_style.palette["measure_distance"], [(0, 1)]),
        ("angle", visual_style.palette["measure_angle"], [(0, 1), (1, 2)]),
        ("dihedral", visual_style.palette["measure_dihedral"], [(0, 1), (1, 2), (2, 3)]),
    ]
    for key, color, segments in line_specs:
        indices = measurement_atoms.get(key, [])
        if not _measurement_indices_are_valid(atoms, indices, expected_size=len(segments) + 1):
            continue
        highlighted_indices.extend(indices)
        for start_index, end_index in segments:
            start = positions[indices[start_index]]
            end = positions[indices[end_index]]
            traces.append(
                go.Scatter3d(
                    x=[start[0], end[0]],
                    y=[start[1], end[1]],
                    z=[start[2], end[2]],
                    mode="lines",
                    line={"color": color, "width": 8, "dash": "dash"},
                    hoverinfo="skip",
                    showlegend=False,
                    name="_measurement_line",
                )
            )
    if not highlighted_indices:
        return traces

    unique_indices = sorted(set(highlighted_indices))
    selected_positions = positions[unique_indices]
    traces.append(
        go.Scatter3d(
            x=selected_positions[:, 0],
            y=selected_positions[:, 1],
            z=selected_positions[:, 2],
            mode="markers",
            marker={
                "size": 19,
                "color": "rgba(248, 250, 252, 0.18)",
                "line": {"color": visual_style.palette["measure_selection"], "width": 5},
                "symbol": "circle-open",
            },
            hoverinfo="skip",
            showlegend=False,
            name="_measurement_selection",
        )
    )
    return traces


def _combined_bond_trace(
    atoms: Atoms,
    bond_pairs: list[tuple[int, int]],
    *,
    color: str = "#6b7280",
    width: float = 6.0,
    name: str = "_structure_bonds",
) -> go.Scatter3d:
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
        line={"color": color, "width": width},
        hoverinfo="skip",
        showlegend=False,
        name=name,
    )


def _representation_config(
    representation: str,
    *,
    model_size_settings: ModelSizeSettings | None = None,
    visual_style_key: str | None = None,
) -> dict[str, float | bool]:
    visual_style = resolve_visual_style(visual_style_key)
    style = _resolved_model_size_settings(model_size_settings)
    return {
        "ball_stick": {
            "atom_scale": 40.0 * style.sphere_scale,
            "atom_min_size": 5.8 * (style.sphere_scale / 0.30),
            "atom_line_width": 1.0,
            "atom_opacity": 0.98,
            "show_bonds": True,
            "bond_width": 20.0 * style.stick_radius,
            "bond_color": visual_style.palette["structure_bond"],
        },
        "space_filling": {
            "atom_scale": 16.5 * style.space_filling_scale,
            "atom_min_size": 12.0 * style.space_filling_scale,
            "atom_line_width": 0.8,
            "atom_opacity": 0.94,
            "show_bonds": False,
            "bond_width": 0.0,
            "bond_color": visual_style.palette["structure_bond"],
        },
        "stick": {
            "atom_scale": 18.0 * max(style.sphere_scale, 0.18),
            "atom_min_size": 4.0,
            "atom_line_width": 0.5,
            "atom_opacity": 0.98,
            "show_bonds": True,
            "bond_width": 28.0 * style.stick_radius,
            "bond_color": visual_style.palette["structure_stick"],
        },
        "wireframe": {
            "atom_scale": 10.0 + style.wireframe_line_width * 1.4,
            "atom_min_size": 2.8,
            "atom_line_width": 0.0,
            "atom_opacity": 0.74,
            "show_bonds": True,
            "bond_width": style.wireframe_line_width,
            "bond_color": visual_style.palette["structure_wire"],
        },
    }.get(
        representation,
        {
            "atom_scale": 40.0 * style.sphere_scale,
            "atom_min_size": 5.8,
            "atom_line_width": 1.0,
            "atom_opacity": 0.96,
            "show_bonds": True,
            "bond_width": 20.0 * style.stick_radius,
            "bond_color": visual_style.palette["structure_bond"],
        },
    )


def _structure_viewer_style(
    representation: str,
    model_size_settings: ModelSizeSettings | None = None,
    visual_style_key: str | None = None,
) -> dict[str, Any]:
    visual_style = resolve_visual_style(visual_style_key)
    style = _resolved_model_size_settings(model_size_settings)
    if representation == "space_filling":
        return {
            "base": {
                "sphere": {"scale": style.space_filling_scale},
                "clicksphere": {"radius": 0.6},
            },
            "highlight_radius": 0.55,
            "highlight_color": visual_style.palette["measure_selection"],
        }
    if representation == "stick":
        return {
            "base": {
                "stick": {"radius": style.stick_radius},
                "sphere": {"scale": max(0.16, style.sphere_scale * 0.55)},
                "clicksphere": {"radius": 0.55},
            },
            "highlight_radius": 0.42,
            "highlight_color": visual_style.palette["measure_selection"],
        }
    if representation == "wireframe":
        return {
            "base": {
                "line": {"linewidth": style.wireframe_line_width},
                "cross": {"radius": max(0.12, 0.08 + style.wireframe_line_width * 0.02)},
                "clicksphere": {"radius": 0.48},
            },
            "highlight_radius": 0.36,
            "highlight_color": visual_style.palette["measure_selection"],
        }
    return {
        "base": {
            "stick": {"radius": style.stick_radius},
            "sphere": {"scale": style.sphere_scale},
            "clicksphere": {"radius": 0.62},
        },
        "highlight_radius": 0.50,
        "highlight_color": visual_style.palette["measure_selection"],
    }


def _structure_atom_sizes(
    numbers: list[int] | np.ndarray,
    representation: str,
    *,
    model_size_settings: ModelSizeSettings | None = None,
) -> list[float]:
    style = _representation_config(representation, model_size_settings=model_size_settings)
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
    model_size_settings: ModelSizeSettings | None = None,
) -> list[float]:
    base_sizes = _structure_atom_sizes(numbers, representation, model_size_settings=model_size_settings)
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
    model_size_settings: ModelSizeSettings | None = None,
    visual_style_key: str | None = None,
) -> go.Scatter3d | None:
    traces = _representation_bond_traces(
        atoms,
        representation=representation,
        bond_pairs=bond_pairs,
        model_size_settings=model_size_settings,
        visual_style_key=visual_style_key,
    )
    if not traces:
        return None
    return traces[0]


def _representation_bond_traces(
    atoms: Atoms,
    representation: str = "ball_stick",
    bond_pairs: list[tuple[int, int]] | None = None,
    model_size_settings: ModelSizeSettings | None = None,
    visual_style_key: str | None = None,
) -> list[go.Scatter3d]:
    style = _representation_config(
        representation,
        model_size_settings=model_size_settings,
        visual_style_key=visual_style_key,
    )
    if not bool(style["show_bonds"]):
        return []
    if bond_pairs is None:
        bond_pairs = _build_bond_pairs(atoms)
    if not bond_pairs:
        return []
    if representation == "ball_stick":
        return _ball_stick_bond_traces(
            atoms,
            bond_pairs,
            width=float(style["bond_width"]),
            visual_style_key=visual_style_key,
        )
    return [
        _combined_bond_trace(
            atoms,
            bond_pairs,
            color=str(style["bond_color"]),
            width=float(style["bond_width"]),
        )
    ]


def _ball_stick_bond_traces(
    atoms: Atoms,
    bond_pairs: list[tuple[int, int]],
    *,
    width: float,
    visual_style_key: str | None = None,
) -> list[go.Scatter3d]:
    positions = atoms.get_positions()
    atom_colors = _structure_atom_colors(atoms.get_atomic_numbers(), visual_style_key=visual_style_key)
    segments_by_color: dict[str, dict[str, list[float | None]]] = {}

    for left, right in bond_pairs:
        start = positions[left]
        end = positions[right]
        midpoint = (start + end) / 2.0
        left_color = atom_colors[left]
        right_color = atom_colors[right]
        for segment_start, segment_end, color in (
            (start, midpoint, left_color),
            (midpoint, end, right_color),
        ):
            coords = segments_by_color.setdefault(color, {"x": [], "y": [], "z": []})
            coords["x"].extend([float(segment_start[0]), float(segment_end[0]), None])
            coords["y"].extend([float(segment_start[1]), float(segment_end[1]), None])
            coords["z"].extend([float(segment_start[2]), float(segment_end[2]), None])

    traces: list[go.Scatter3d] = []
    for color in sorted(segments_by_color):
        coords = segments_by_color[color]
        traces.append(
            go.Scatter3d(
                x=coords["x"],
                y=coords["y"],
                z=coords["z"],
                mode="lines",
                line={"color": color, "width": width},
                hoverinfo="skip",
                showlegend=False,
                name="_structure_bonds",
            )
        )
    return traces


def _resolved_model_size_settings(model_size_settings: ModelSizeSettings | None) -> ModelSizeSettings:
    return model_size_preset("standard") if model_size_settings is None else model_size_settings


def _structure_atom_colors(
    numbers: list[int] | np.ndarray,
    *,
    visual_style_key: str | None = None,
) -> list[str]:
    palette = {
        number: _display_atom_color(number, visual_style_key=visual_style_key)
        for number in sorted(set(int(number) for number in numbers))
    }
    return [palette[int(number)] for number in numbers]


def _display_atom_color(number: int, *, visual_style_key: str | None = None) -> str:
    visual_style = resolve_visual_style(visual_style_key)
    if int(number) == 1:
        return visual_style.palette["hydrogen_fill"]
    red, green, blue = jmol_colors[int(number)]
    return f"rgb({int(red * 255)}, {int(green * 255)}, {int(blue * 255)})"


def _combined_vector_trace(
    positions: np.ndarray,
    displacements: np.ndarray,
    *,
    visual_style_key: str | None = None,
) -> go.Scatter3d:
    visual_style = resolve_visual_style(visual_style_key)
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
        line={"color": visual_style.palette["accent_positive"], "width": 7},
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
