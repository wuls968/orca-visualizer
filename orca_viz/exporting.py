from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
from typing import Any

import numpy as np
import plotly.graph_objects as go
import plotly.io as pio

from .plot_theme import (
    CHART_PAPER_BG,
    PAPER_CAMERA,
    SCIENTIFIC_FONT_FAMILY,
    STRUCTURE_CAMERA,
    TEXT_MUTED,
    TEXT_PRIMARY,
    standard_3d_axis_layout,
    standard_export_margin,
)


THREE_D_TRACE_TYPES = {"scatter3d", "mesh3d", "isosurface", "surface", "volume", "cone", "streamtube"}
SURFACE_TRACE_TYPES = {"mesh3d", "isosurface", "surface", "volume"}
MOLECULE_TRACE_TYPES = {"scatter3d"}


@dataclass(frozen=True)
class ExportPreset:
    key: str
    label: str
    width: int
    height: int
    scale: int
    font_size: int
    title_size: int
    transparent_background: bool = False


EXPORT_PRESETS_2D: dict[str, ExportPreset] = {
    "paper": ExportPreset("paper", "Paper", 2200, 1400, 3, 18, 24),
    "presentation": ExportPreset("presentation", "Presentation", 1920, 1080, 2, 22, 30),
    "web": ExportPreset("web", "Web Preview", 1600, 1000, 2, 16, 22),
}

EXPORT_PRESETS_3D: dict[str, ExportPreset] = {
    "paper": ExportPreset("paper", "Paper", 1800, 1800, 3, 16, 22),
    "presentation": ExportPreset("presentation", "Presentation", 1800, 1400, 2, 18, 26),
    "web": ExportPreset("web", "Web Preview", 1400, 1200, 2, 15, 20),
}

# Backward-compatible alias for older imports; UI should use `export_presets_for_figure`.
EXPORT_PRESETS = EXPORT_PRESETS_2D


def is_3d_figure(figure: go.Figure) -> bool:
    if any(getattr(trace, "type", "") in THREE_D_TRACE_TYPES for trace in figure.data):
        return True
    scene = getattr(figure.layout, "scene", None)
    return bool(scene and scene.to_plotly_json())


def is_webgl_figure(figure: go.Figure) -> bool:
    return is_3d_figure(figure)


def export_presets_for_figure(figure: go.Figure) -> dict[str, ExportPreset]:
    return EXPORT_PRESETS_3D if is_3d_figure(figure) else EXPORT_PRESETS_2D


def export_preset(key: str, *, is_3d: bool = False) -> ExportPreset:
    preset_map = EXPORT_PRESETS_3D if is_3d else EXPORT_PRESETS_2D
    return preset_map.get(key, preset_map["paper"])


def normalized_export_file_name(
    file_stem: str,
    preset_key: str,
    image_format: str,
    *,
    profile_key: str | None = None,
    view_key: str | None = None,
) -> str:
    suffix = image_format.lower().lstrip(".")
    parts = [_slug_segment(file_stem)]
    if profile_key:
        parts.append(_slug_segment(profile_key))
    if preset_key and preset_key != profile_key:
        parts.append(_slug_segment(preset_key))
    if view_key and view_key != "current":
        parts.append(_slug_segment(view_key))
    return f"{'_'.join(part for part in parts if part)}.{suffix}"


def apply_export_preset(
    figure: go.Figure,
    *,
    preset_key: str = "paper",
    width: int | None = None,
    height: int | None = None,
    font_size: int | None = None,
    title_size: int | None = None,
    transparent_background: bool | None = None,
    profile_key: str = "paper",
    view_mode: str = "current",
    hide_axes: bool = False,
    hide_legend: bool = False,
    hide_colorbar: bool = False,
    margin_mode: str = "balanced",
) -> go.Figure:
    return prepare_export_figure(
        figure,
        preset_key=preset_key,
        width=width,
        height=height,
        font_size=font_size,
        title_size=title_size,
        transparent_background=transparent_background,
        profile_key=profile_key,
        view_mode=view_mode,
        hide_axes=hide_axes,
        hide_legend=hide_legend,
        hide_colorbar=hide_colorbar,
        margin_mode=margin_mode,
    )


def prepare_export_figure(
    figure: go.Figure,
    *,
    preset_key: str = "paper",
    width: int | None = None,
    height: int | None = None,
    font_size: int | None = None,
    title_size: int | None = None,
    transparent_background: bool | None = None,
    profile_key: str = "paper",
    view_mode: str = "current",
    hide_axes: bool = False,
    hide_legend: bool = False,
    hide_colorbar: bool = False,
    margin_mode: str = "balanced",
) -> go.Figure:
    export_figure = go.Figure(figure)
    three_d = is_3d_figure(export_figure)
    preset = export_preset(preset_key, is_3d=three_d)
    bg_color = (
        "rgba(0,0,0,0)"
        if (transparent_background if transparent_background is not None else preset.transparent_background)
        else CHART_PAPER_BG
    )
    resolved_width = width or preset.width
    resolved_height = height or preset.height

    export_figure.update_layout(
        width=resolved_width,
        height=resolved_height,
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
    )
    if hide_legend:
        export_figure.update_layout(showlegend=False)

    if hide_colorbar:
        _hide_colorbars(export_figure)

    if profile_key == "paper":
        _apply_paper_layout(
            export_figure,
            is_3d=three_d,
            font_size=font_size or preset.font_size,
            title_size=title_size or preset.title_size,
            background_color=bg_color,
            margin_mode=margin_mode,
        )
    elif margin_mode == "tight":
        export_figure.update_layout(
            margin=standard_export_margin(is_3d=three_d, crop_mode="tight"),
        )

    if three_d:
        _apply_3d_view_mode(export_figure, view_mode=view_mode)
        _apply_3d_axis_visibility(
            export_figure,
            show_axes=not hide_axes,
            background_color=bg_color,
        )
    elif hide_axes:
        export_figure.update_xaxes(visible=False, showgrid=False, zeroline=False, title_text=None)
        export_figure.update_yaxes(visible=False, showgrid=False, zeroline=False, title_text=None)

    return export_figure


def export_plotly_figure(
    figure: go.Figure,
    *,
    image_format: str = "png",
    preset_key: str = "paper",
    width: int | None = None,
    height: int | None = None,
    scale: int | None = None,
    font_size: int | None = None,
    title_size: int | None = None,
    transparent_background: bool | None = None,
    profile_key: str = "paper",
    view_mode: str = "current",
    hide_axes: bool = False,
    hide_legend: bool = False,
    hide_colorbar: bool = False,
    margin_mode: str = "balanced",
) -> bytes:
    if image_format.lower() == "html":
        return export_plotly_html(
            figure,
            preset_key=preset_key,
            width=width,
            height=height,
            font_size=font_size,
            title_size=title_size,
            transparent_background=transparent_background,
            profile_key=profile_key,
            view_mode=view_mode,
            hide_axes=hide_axes,
            hide_legend=hide_legend,
            hide_colorbar=hide_colorbar,
            margin_mode=margin_mode,
        )

    if not static_image_export_available():
        raise RuntimeError("Static image export is unavailable because kaleido could not be initialized.")

    preset = export_preset(preset_key, is_3d=is_3d_figure(figure))
    export_figure = prepare_export_figure(
        figure,
        preset_key=preset_key,
        width=width,
        height=height,
        font_size=font_size,
        title_size=title_size,
        transparent_background=transparent_background,
        profile_key=profile_key,
        view_mode=view_mode,
        hide_axes=hide_axes,
        hide_legend=hide_legend,
        hide_colorbar=hide_colorbar,
        margin_mode=margin_mode,
    )
    return pio.to_image(
        export_figure,
        format=image_format,
        width=width or preset.width,
        height=height or preset.height,
        scale=scale or preset.scale,
    )


def export_plotly_html(
    figure: go.Figure,
    *,
    preset_key: str = "paper",
    width: int | None = None,
    height: int | None = None,
    font_size: int | None = None,
    title_size: int | None = None,
    transparent_background: bool | None = None,
    profile_key: str = "faithful",
    view_mode: str = "current",
    hide_axes: bool = False,
    hide_legend: bool = False,
    hide_colorbar: bool = False,
    margin_mode: str = "balanced",
) -> bytes:
    export_figure = prepare_export_figure(
        figure,
        preset_key=preset_key,
        width=width,
        height=height,
        font_size=font_size,
        title_size=title_size,
        transparent_background=transparent_background,
        profile_key=profile_key,
        view_mode=view_mode,
        hide_axes=hide_axes,
        hide_legend=hide_legend,
        hide_colorbar=hide_colorbar,
        margin_mode=margin_mode,
    )
    html = pio.to_html(
        export_figure,
        include_plotlyjs=True,
        full_html=True,
        config={"displaylogo": False, "responsive": True},
    )
    return html.encode("utf-8")


def create_publication_ready_figure(figure: go.Figure) -> go.Figure:
    return prepare_export_figure(figure, preset_key="paper", profile_key="paper")


@lru_cache(maxsize=1)
def static_image_export_available() -> bool:
    try:
        probe = go.Figure(data=[go.Scatter(x=[0, 1], y=[0, 1])])
        pio.to_image(probe, format="png", width=32, height=32, scale=1)
    except Exception:
        return False
    return True


def _apply_paper_layout(
    figure: go.Figure,
    *,
    is_3d: bool,
    font_size: int,
    title_size: int,
    background_color: str,
    margin_mode: str,
) -> None:
    figure.update_layout(
        font={
            "family": SCIENTIFIC_FONT_FAMILY,
            "size": font_size,
            "color": TEXT_PRIMARY,
        },
        title={
            "font": {
                "family": SCIENTIFIC_FONT_FAMILY,
                "size": title_size,
                "color": TEXT_PRIMARY,
            }
        },
        margin=standard_export_margin(is_3d=is_3d, crop_mode=margin_mode),
    )
    if is_3d:
        scene = figure.layout.scene.to_plotly_json() if figure.layout.scene else {}
        scene.setdefault("aspectmode", "data")
        scene["bgcolor"] = background_color
        figure.update_layout(scene=scene)
    else:
        figure.update_xaxes(
            title_font={"size": font_size + 1, "color": TEXT_PRIMARY},
            tickfont={"size": max(font_size - 1, 10), "color": TEXT_MUTED},
        )
        figure.update_yaxes(
            title_font={"size": font_size + 1, "color": TEXT_PRIMARY},
            tickfont={"size": max(font_size - 1, 10), "color": TEXT_MUTED},
        )


def _apply_3d_axis_visibility(
    figure: go.Figure,
    *,
    show_axes: bool,
    background_color: str,
) -> None:
    scene = figure.layout.scene.to_plotly_json() if figure.layout.scene else {}
    axis_defaults = standard_3d_axis_layout(show_axes=show_axes, background_color=background_color)
    for axis_name in ("xaxis", "yaxis", "zaxis"):
        existing_axis = scene.get(axis_name, {})
        merged_axis = {**axis_defaults[axis_name], **existing_axis}
        if not show_axes:
            merged_axis.update(
                {
                    "visible": False,
                    "showbackground": False,
                    "showgrid": False,
                    "showticklabels": False,
                    "title": {"text": None},
                }
            )
        else:
            existing_title = existing_axis.get("title")
            default_title = axis_defaults[axis_name]["title"]
            if isinstance(existing_title, dict):
                title_payload = {**default_title, **existing_title}
                if "font" in default_title:
                    title_payload["font"] = {**default_title["font"], **existing_title.get("font", {})}
                merged_axis["title"] = title_payload
            elif existing_title is None:
                merged_axis["title"] = default_title
        scene[axis_name] = merged_axis
    figure.update_layout(scene=scene)


def _apply_3d_view_mode(figure: go.Figure, *, view_mode: str) -> None:
    normalized = view_mode.strip().lower()
    if normalized == "current":
        return

    scene = figure.layout.scene.to_plotly_json() if figure.layout.scene else {}
    if normalized == "paper_default":
        points = _figure_3d_focus_points(figure, focus="all")
        if points is not None:
            _apply_scene_fit(scene, points, camera=PAPER_CAMERA)
        else:
            scene["camera"] = PAPER_CAMERA
        figure.update_layout(scene=scene)
        return

    focus = "molecule" if normalized == "fit_molecule" else "surface" if normalized == "fit_surface" else "all"
    points = _figure_3d_focus_points(figure, focus=focus)
    if points is None and focus != "all":
        points = _figure_3d_focus_points(figure, focus="all")
    if points is None:
        return
    _apply_scene_fit(scene, points, camera=_fit_camera(points))
    figure.update_layout(scene=scene)


def _apply_scene_fit(scene: dict[str, Any], points: np.ndarray, *, camera: dict[str, Any]) -> None:
    mins = np.min(points, axis=0)
    maxs = np.max(points, axis=0)
    spans = np.maximum(maxs - mins, 0.2)
    max_span = float(np.max(spans))
    padding = max(max_span * 0.14, 0.45)
    ranges = []
    for axis_min, axis_max in zip(mins, maxs, strict=False):
        center = float((axis_min + axis_max) / 2.0)
        half_span = float(max(axis_max - axis_min, 0.2) / 2.0 + padding)
        ranges.append([center - half_span, center + half_span])
    scene.setdefault("aspectmode", "data")
    scene.setdefault("xaxis", {})
    scene.setdefault("yaxis", {})
    scene.setdefault("zaxis", {})
    scene["xaxis"]["range"] = ranges[0]
    scene["yaxis"]["range"] = ranges[1]
    scene["zaxis"]["range"] = ranges[2]
    scene["camera"] = camera


def _fit_camera(points: np.ndarray) -> dict[str, Any]:
    mins = np.min(points, axis=0)
    maxs = np.max(points, axis=0)
    spans = np.maximum(maxs - mins, 0.2)
    max_span = float(np.max(spans))
    normalized = spans / max_span if max_span > 0 else np.ones(3)
    scale = 1.04 if max_span < 6.0 else 1.10
    return {
        "eye": {
            "x": scale * (1.02 + 0.22 * float(normalized[0])),
            "y": scale * (0.94 + 0.22 * float(normalized[1])),
            "z": scale * (0.84 + 0.18 * float(normalized[2])),
        }
    }


def _figure_3d_focus_points(figure: go.Figure, *, focus: str) -> np.ndarray | None:
    point_sets: list[np.ndarray] = []
    for trace in figure.data:
        trace_points = _trace_focus_points(trace, focus=focus)
        if trace_points is not None and trace_points.size:
            point_sets.append(trace_points)
    if not point_sets:
        return None
    return np.vstack(point_sets)


def _trace_focus_points(trace: Any, *, focus: str) -> np.ndarray | None:
    trace_type = getattr(trace, "type", "")
    if focus == "molecule" and trace_type not in MOLECULE_TRACE_TYPES:
        return None
    if focus == "surface" and trace_type not in SURFACE_TRACE_TYPES:
        return None

    if trace_type == "scatter3d":
        return _points_from_xyz(trace.x, trace.y, trace.z)
    if trace_type == "mesh3d":
        return _points_from_xyz(trace.x, trace.y, trace.z)
    if trace_type == "surface":
        return _points_from_xyz(trace.x, trace.y, trace.z)
    if trace_type == "isosurface":
        return _isosurface_points(trace)
    return None


def _isosurface_points(trace: Any) -> np.ndarray | None:
    x = np.asarray(getattr(trace, "x", []), dtype=float)
    y = np.asarray(getattr(trace, "y", []), dtype=float)
    z = np.asarray(getattr(trace, "z", []), dtype=float)
    value = np.asarray(getattr(trace, "value", []), dtype=float)
    if x.size == 0 or y.size == 0 or z.size == 0 or value.size == 0:
        return None
    mask = np.isfinite(x) & np.isfinite(y) & np.isfinite(z) & np.isfinite(value)
    isomin = getattr(trace, "isomin", None)
    isomax = getattr(trace, "isomax", None)
    if isomin is not None:
        try:
            lower = float(isomin)
            upper = float(isomax) if isomax is not None else None
            if lower < 0 < (upper or 0):
                threshold = min(abs(lower), abs(upper or lower))
                mask &= np.abs(value) >= threshold
            else:
                mask &= value >= lower
        except (TypeError, ValueError):
            pass
    points = np.column_stack([x[mask], y[mask], z[mask]])
    return _downsample_points(points)


def _points_from_xyz(x_values: Any, y_values: Any, z_values: Any) -> np.ndarray | None:
    x = np.asarray(x_values, dtype=float).ravel()
    y = np.asarray(y_values, dtype=float).ravel()
    z = np.asarray(z_values, dtype=float).ravel()
    if x.size == 0 or y.size == 0 or z.size == 0:
        return None
    mask = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    if not np.any(mask):
        return None
    points = np.column_stack([x[mask], y[mask], z[mask]])
    return _downsample_points(points)


def _downsample_points(points: np.ndarray, limit: int = 12000) -> np.ndarray:
    if points.shape[0] <= limit:
        return points
    step = max(1, math.ceil(points.shape[0] / limit))
    return points[::step]


def _hide_colorbars(figure: go.Figure) -> None:
    for trace in figure.data:
        trace_type = getattr(trace, "type", "")
        if hasattr(trace, "showscale"):
            try:
                trace.showscale = False
            except ValueError:
                pass
        if hasattr(trace, "marker") and trace.marker is not None and hasattr(trace.marker, "showscale"):
            try:
                trace.marker.showscale = False
            except ValueError:
                pass
        if trace_type == "mesh3d" and hasattr(trace, "colorbar"):
            try:
                trace.update(showscale=False)
            except ValueError:
                pass


def _slug_segment(value: str) -> str:
    return (
        value.strip()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(".", "_")
        .lower()
    )
