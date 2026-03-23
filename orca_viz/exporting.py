from __future__ import annotations

from io import BytesIO
from dataclasses import dataclass
import importlib.util
from functools import lru_cache
import math
import os
from pathlib import Path
import tempfile
from typing import Any

import imageio.v2 as imageio
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
from PIL import Image

from .pathway import PathwayResult, build_frame_point_mapping
from .plots.pathways import create_path_figure
from .plots.structure import create_pathway_frame_figure, structure_scene_bounds

from .plot_theme import (
    ModelSizeSettings,
    figure_visual_style_key,
    resolve_visual_style,
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


@dataclass(frozen=True)
class AnimationExportPreset:
    key: str
    label: str
    width: int
    height: int
    fps: int
    scale: int
    structure_fraction: float = 0.62


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

ANIMATION_EXPORT_PRESETS: dict[str, AnimationExportPreset] = {
    "paper": AnimationExportPreset("paper", "Paper", 2400, 1400, 12, 2, 0.64),
    "presentation": AnimationExportPreset("presentation", "Presentation", 1920, 1080, 16, 2, 0.62),
    "web": AnimationExportPreset("web", "Web Preview", 1440, 900, 10, 1, 0.60),
}


def _should_shutdown_kaleido_after_static_export() -> bool:
    # Kaleido < 1 can leave a helper process running on Windows after pio.to_image().
    # In CI this keeps `python -m unittest` alive until the GitHub Actions 6h hard limit.
    return os.name == "nt"


def _shutdown_kaleido_backend() -> None:
    scope = getattr(getattr(pio, "kaleido", None), "scope", None)
    shutdown = getattr(scope, "_shutdown_kaleido", None)
    if callable(shutdown):
        try:
            shutdown()
        except Exception:
            pass


def _plotly_to_image(*, shutdown_after: bool | None = None, **kwargs: Any) -> bytes:
    try:
        return pio.to_image(**kwargs)
    finally:
        should_shutdown = shutdown_after if shutdown_after is not None else _should_shutdown_kaleido_after_static_export()
        if should_shutdown:
            _shutdown_kaleido_backend()


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


def normalized_animation_file_name(file_stem: str, preset_key: str, video_format: str) -> str:
    suffix = video_format.lower().lstrip(".")
    return f"{_slug_segment(file_stem)}_path_{_slug_segment(preset_key)}.{suffix}"


def animation_export_preset(key: str) -> AnimationExportPreset:
    return ANIMATION_EXPORT_PRESETS.get(key, ANIMATION_EXPORT_PRESETS["paper"])


def video_export_available(video_format: str) -> bool:
    normalized = video_format.strip().lower()
    if normalized == "gif":
        return static_image_export_available()
    if normalized == "mp4":
        return static_image_export_available() and importlib.util.find_spec("imageio_ffmpeg") is not None
    return False


def available_video_formats() -> list[str]:
    return [video_format for video_format in ["gif", "mp4"] if video_export_available(video_format)]


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
    visual_style_key: str | None = None,
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
        visual_style_key=visual_style_key,
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
    visual_style_key: str | None = None,
) -> go.Figure:
    export_figure = go.Figure(figure)
    three_d = is_3d_figure(export_figure)
    preset = export_preset(preset_key, is_3d=three_d)
    resolved_style_key = visual_style_key or figure_visual_style_key(export_figure)
    visual_style = resolve_visual_style(resolved_style_key)
    bg_color = (
        "rgba(0,0,0,0)"
        if (transparent_background if transparent_background is not None else preset.transparent_background)
        else visual_style.palette["paper_bg"]
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
            visual_style_key=visual_style.key,
        )
    elif margin_mode == "tight":
        export_figure.update_layout(
            margin=standard_export_margin(
                is_3d=three_d,
                crop_mode="tight",
                visual_style_key=visual_style.key,
            ),
        )

    if three_d:
        _apply_3d_view_mode(export_figure, view_mode=view_mode)
        _apply_3d_axis_visibility(
            export_figure,
            show_axes=not hide_axes,
            background_color=bg_color,
            visual_style_key=visual_style.key,
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
    visual_style_key: str | None = None,
    _shutdown_kaleido: bool | None = None,
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
            visual_style_key=visual_style_key,
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
        visual_style_key=visual_style_key,
    )
    return _plotly_to_image(
        fig=export_figure,
        format=image_format,
        width=width or preset.width,
        height=height or preset.height,
        scale=scale or preset.scale,
        shutdown_after=_shutdown_kaleido,
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
    visual_style_key: str | None = None,
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
        visual_style_key=visual_style_key,
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


def export_pathway_animation(
    pathway: PathwayResult,
    *,
    display_df: Any,
    path_x_col: str,
    path_y_col: str,
    path_title: str,
    path_x_label: str,
    path_y_label: str,
    y_hover_format: str,
    y_suffix: str,
    representation: str = "ball_stick",
    show_atom_labels: bool = False,
    show_axes: bool = False,
    show_frame_number: bool = True,
    show_path_plot: bool = True,
    preset_key: str = "paper",
    video_format: str = "gif",
    width: int | None = None,
    height: int | None = None,
    fps: int | None = None,
    scale: int | None = None,
    background_mode: str = "white",
    camera_mode: str = "fixed_all_frames",
    model_size_settings: ModelSizeSettings | None = None,
    visual_style_key: str | None = None,
) -> bytes:
    if not pathway.frames:
        raise ValueError("Pathway animation export requires structural frames.")
    normalized_format = video_format.strip().lower()
    if not video_export_available(normalized_format):
        raise RuntimeError(f"Video export backend for `{normalized_format}` is unavailable.")

    visual_style = resolve_visual_style(visual_style_key)
    preset = animation_export_preset(preset_key)
    resolved_width = int(width or preset.width)
    resolved_height = int(height or preset.height)
    resolved_fps = int(fps or preset.fps)
    resolved_scale = int(scale or preset.scale)
    include_path_plot = bool(show_path_plot and display_df is not None and not getattr(display_df, "empty", True))
    frame_to_point, _ = build_frame_point_mapping(pathway)
    background_is_transparent = background_mode == "transparent" and normalized_format == "gif"
    global_bounds = structure_scene_bounds(
        [frame.atoms for frame in pathway.frames],
        camera=visual_style.cameras["paper"] if camera_mode == "paper_default" else visual_style.cameras["structure"],
    )

    structure_width = resolved_width
    path_width = 0
    if include_path_plot:
        structure_width = int(resolved_width * preset.structure_fraction)
        path_width = resolved_width - structure_width

    with tempfile.TemporaryDirectory(prefix="orca_viz_animation_") as temp_dir:
        output_path = Path(temp_dir) / f"path_animation.{normalized_format}"
        writer = _open_animation_writer(
            output_path,
            video_format=normalized_format,
            fps=resolved_fps,
        )
        try:
            for frame_index, frame in enumerate(pathway.frames):
                bounds = (
                    global_bounds
                    if camera_mode in {"fixed_all_frames", "paper_default"}
                    else structure_scene_bounds([frame.atoms], camera=visual_style.cameras["structure"])
                )
                frame_label = f"Frame {frame_index + 1}/{len(pathway.frames)}" if show_frame_number else None
                structure_figure = create_pathway_frame_figure(
                    frame.atoms,
                    representation=representation,
                    show_atom_labels=show_atom_labels,
                    model_size_settings=model_size_settings,
                    bounds=bounds,
                    show_axes=show_axes,
                    frame_label=frame_label,
                    camera=bounds.get("camera"),  # type: ignore[arg-type]
                    visual_style_key=visual_style.key,
                )
                structure_image = _export_figure_to_pil(
                    structure_figure,
                    width=structure_width,
                    height=resolved_height,
                    scale=resolved_scale,
                    background_is_transparent=background_is_transparent,
                    shutdown_after=False,
                )

                composed = structure_image
                if include_path_plot:
                    highlight_index = frame_to_point[frame_index] if frame_index < len(frame_to_point) else None
                    path_figure = create_path_figure(
                        display_df,
                        path_x_col,
                        path_y_col,
                        path_title,
                        path_x_label,
                        y_label=path_y_label,
                        y_hover_format=y_hover_format,
                        y_suffix=y_suffix,
                        highlight_index=highlight_index,
                        visual_style_key=visual_style.key,
                    )
                    path_image = _export_figure_to_pil(
                        path_figure,
                        width=path_width,
                        height=resolved_height,
                        scale=resolved_scale,
                        background_is_transparent=background_is_transparent,
                        shutdown_after=False,
                    )
                    composed = _compose_animation_frame(
                        structure_image,
                        path_image,
                        width=resolved_width * resolved_scale,
                        height=resolved_height * resolved_scale,
                        background_is_transparent=background_is_transparent,
                    )
                writer.append_data(_image_to_ndarray(composed, transparent=background_is_transparent))
        finally:
            writer.close()
            _shutdown_kaleido_backend()
        return output_path.read_bytes()


@lru_cache(maxsize=1)
def static_image_export_available() -> bool:
    try:
        probe = go.Figure(data=[go.Scatter(x=[0, 1], y=[0, 1])])
        _plotly_to_image(fig=probe, format="png", width=32, height=32, scale=1, shutdown_after=True)
    except Exception:
        return False
    return True


def _export_figure_to_pil(
    figure: go.Figure,
    *,
    width: int,
    height: int,
    scale: int,
    background_is_transparent: bool,
    shutdown_after: bool | None = None,
) -> Image.Image:
    image_bytes = export_plotly_figure(
        figure,
        image_format="png",
        width=width,
        height=height,
        scale=scale,
        preset_key="paper",
        profile_key="faithful",
        transparent_background=background_is_transparent,
        _shutdown_kaleido=shutdown_after,
    )
    image = Image.open(BytesIO(image_bytes))
    return image.convert("RGBA")


def _compose_animation_frame(
    structure_image: Image.Image,
    path_image: Image.Image,
    *,
    width: int,
    height: int,
    background_is_transparent: bool,
) -> Image.Image:
    background = (255, 255, 255, 0 if background_is_transparent else 255)
    canvas = Image.new("RGBA", (width, height), background)
    canvas.alpha_composite(structure_image)
    canvas.alpha_composite(path_image, dest=(width - path_image.width, 0))
    return canvas


def _image_to_ndarray(image: Image.Image, *, transparent: bool) -> np.ndarray:
    if transparent:
        return np.asarray(image.convert("RGBA"))
    rgb_image = Image.new("RGB", image.size, (255, 255, 255))
    rgb_image.paste(image, mask=image.split()[-1] if image.mode == "RGBA" else None)
    return np.asarray(rgb_image)


def _open_animation_writer(output_path: Path, *, video_format: str, fps: int):
    if video_format == "gif":
        return imageio.get_writer(output_path, format="GIF", mode="I", duration=1 / max(fps, 1), loop=0)
    if video_format == "mp4":
        return imageio.get_writer(
            output_path,
            format="FFMPEG",
            mode="I",
            fps=max(fps, 1),
            codec="libx264",
            macro_block_size=None,
        )
    raise ValueError(f"Unsupported animation format: {video_format}")


def _apply_paper_layout(
    figure: go.Figure,
    *,
    is_3d: bool,
    font_size: int,
    title_size: int,
    background_color: str,
    margin_mode: str,
    visual_style_key: str | None = None,
) -> None:
    visual_style = resolve_visual_style(visual_style_key or figure_visual_style_key(figure))
    figure.update_layout(
        font={
            "family": visual_style.font_family,
            "size": font_size,
            "color": visual_style.palette["text_primary"],
        },
        title={
            "font": {
                "family": visual_style.font_family,
                "size": title_size,
                "color": visual_style.palette["text_primary"],
            }
        },
        margin=standard_export_margin(
            is_3d=is_3d,
            crop_mode=margin_mode,
            visual_style_key=visual_style.key,
        ),
    )
    if is_3d:
        scene = figure.layout.scene.to_plotly_json() if figure.layout.scene else {}
        scene.setdefault("aspectmode", "data")
        scene["bgcolor"] = background_color
        figure.update_layout(scene=scene)
    else:
        figure.update_xaxes(
            title_font={"size": font_size + 1, "color": visual_style.palette["text_primary"]},
            tickfont={"size": max(font_size - 1, 10), "color": visual_style.palette["text_muted"]},
        )
        figure.update_yaxes(
            title_font={"size": font_size + 1, "color": visual_style.palette["text_primary"]},
            tickfont={"size": max(font_size - 1, 10), "color": visual_style.palette["text_muted"]},
        )


def _apply_3d_axis_visibility(
    figure: go.Figure,
    *,
    show_axes: bool,
    background_color: str,
    visual_style_key: str | None = None,
) -> None:
    scene = figure.layout.scene.to_plotly_json() if figure.layout.scene else {}
    axis_defaults = standard_3d_axis_layout(
        show_axes=show_axes,
        background_color=background_color,
        visual_style_key=visual_style_key or figure_visual_style_key(figure),
    )
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

    visual_style = resolve_visual_style(figure_visual_style_key(figure))
    scene = figure.layout.scene.to_plotly_json() if figure.layout.scene else {}
    if normalized == "paper_default":
        points = _figure_3d_focus_points(figure, focus="all")
        if points is not None:
            _apply_scene_fit(scene, points, camera=visual_style.cameras["paper"])
        else:
            scene["camera"] = visual_style.cameras["paper"]
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
