from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import plotly.graph_objects as go


@dataclass(frozen=True)
class VisualizationStyle:
    key: str
    label: str
    font_family: str
    plotly_template: str
    font_size: int
    title_size: int
    line_scale: float
    marker_scale: float
    palette: dict[str, str]
    cameras: dict[str, dict[str, Any]]
    path_branch_colors: tuple[str, ...]
    esp_slice_colorscale: tuple[tuple[float, str], ...]
    orbital_slice_colorscale: tuple[tuple[float, str], ...]
    charge_colorscale: str = "RdBu_r"
    scene_axis_visible: bool = True


@dataclass(frozen=True)
class ModelSizeSettings:
    preset_key: str
    sphere_scale: float
    stick_radius: float
    space_filling_scale: float
    wireframe_line_width: float


_BASE_FONT = '"Avenir Next", "Helvetica Neue", "PingFang SC", "Microsoft YaHei", sans-serif'

_BASE_STYLE = VisualizationStyle(
    key="scientific_standard",
    label="科研标准",
    font_family=_BASE_FONT,
    plotly_template="plotly_white",
    font_size=14,
    title_size=20,
    line_scale=1.0,
    marker_scale=1.0,
    palette={
        "paper_bg": "#ffffff",
        "plot_bg": "#ffffff",
        "page_top": "#f8fafc",
        "page_bottom": "#ffffff",
        "page_spot_a": "rgba(14, 116, 144, 0.08)",
        "page_spot_b": "rgba(15, 118, 110, 0.10)",
        "scene_bg": "#ffffff",
        "viewer_bg": "radial-gradient(circle at top, #f8fafc 0%, #ffffff 68%)",
        "viewer_card_bg": "#ffffff",
        "viewer_card_alt_bg": "#f8fafc",
        "viewer_border": "#e2e8f0",
        "text_primary": "#0f172a",
        "text_muted": "#475569",
        "text_inverse": "#f8fafc",
        "border": "#cbd5e1",
        "grid": "rgba(148, 163, 184, 0.22)",
        "axis": "#334155",
        "legend_bg": "rgba(255,255,255,0.78)",
        "hover_bg": "rgba(255,255,255,0.96)",
        "hover_border": "#cbd5e1",
        "accent_primary": "#1d4ed8",
        "accent_primary_light": "#60a5fa",
        "accent_secondary": "#0f766e",
        "accent_secondary_dark": "#115e59",
        "accent_positive": "#be123c",
        "accent_negative": "#1d4ed8",
        "accent_warning": "#d97706",
        "accent_emphasis": "#7c3aed",
        "accent_neutral": "#64748b",
        "path_current": "#0f766e",
        "structure_bond": "#6b7280",
        "structure_stick": "#4b5563",
        "structure_wire": "#64748b",
        "annotation_bg": "rgba(255,255,255,0.90)",
        "annotation_border": "#cbd5e1",
        "annotation_text": "#0f172a",
        "measure_distance": "#f59e0b",
        "measure_angle": "#10b981",
        "measure_dihedral": "#8b5cf6",
        "measure_selection": "#f97316",
        "structure_overlay": "#94a3b8",
        "cube_orbital_positive": "#d97706",
        "cube_orbital_negative": "#1d4ed8",
        "cube_esp_positive": "#1d4ed8",
        "cube_esp_negative": "#be123c",
        "cube_spin_positive": "#be123c",
        "cube_spin_negative": "#1d4ed8",
        "cube_density_surface": "#0f766e",
        "charge_positive": "#be123c",
        "charge_negative": "#1d4ed8",
        "bar_edge": "#ffffff",
        "atom_outline": "#8b97a9",
        "hydrogen_fill": "#dce3ec",
    },
    cameras={
        "paper": {"eye": {"x": 1.54, "y": 1.42, "z": 1.18}},
        "cube": {"eye": {"x": 1.68, "y": 1.48, "z": 1.22}},
        "structure": {"eye": {"x": 1.38, "y": 1.32, "z": 1.08}},
    },
    path_branch_colors=("#1d4ed8", "#3b7dd8", "#6aa3ff", "#88a9c3"),
    esp_slice_colorscale=(
        (0.00, "#9f1239"),
        (0.18, "#ef4444"),
        (0.50, "#fff7ed"),
        (0.82, "#60a5fa"),
        (1.00, "#1d4ed8"),
    ),
    orbital_slice_colorscale=(
        (0.00, "#1d4ed8"),
        (0.20, "#60a5fa"),
        (0.50, "#f8fafc"),
        (0.80, "#fbbf24"),
        (1.00, "#b45309"),
    ),
)

def _scheme(
    key: str,
    label: str,
    *,
    font_size: int | None = None,
    title_size: int | None = None,
    line_scale: float | None = None,
    marker_scale: float | None = None,
    palette_overrides: dict[str, str] | None = None,
    path_branch_colors: tuple[str, ...] | None = None,
    esp_slice_colorscale: tuple[tuple[float, str], ...] | None = None,
    orbital_slice_colorscale: tuple[tuple[float, str], ...] | None = None,
) -> VisualizationStyle:
    return replace(
        _BASE_STYLE,
        key=key,
        label=label,
        font_size=font_size or _BASE_STYLE.font_size,
        title_size=title_size or _BASE_STYLE.title_size,
        line_scale=line_scale or _BASE_STYLE.line_scale,
        marker_scale=marker_scale or _BASE_STYLE.marker_scale,
        palette={**_BASE_STYLE.palette, **(palette_overrides or {})},
        path_branch_colors=path_branch_colors or _BASE_STYLE.path_branch_colors,
        esp_slice_colorscale=esp_slice_colorscale or _BASE_STYLE.esp_slice_colorscale,
        orbital_slice_colorscale=orbital_slice_colorscale or _BASE_STYLE.orbital_slice_colorscale,
    )


VISUAL_STYLE_PRESETS: dict[str, VisualizationStyle] = {
    _BASE_STYLE.key: _BASE_STYLE,
    "cobalt_amber": _scheme(
        "cobalt_amber",
        "蓝橙对比",
        font_size=15,
        title_size=21,
        line_scale=1.08,
        marker_scale=1.06,
        palette_overrides={
            "accent_primary": "#1d4ed8",
            "accent_primary_light": "#93c5fd",
            "accent_secondary": "#d97706",
            "accent_secondary_dark": "#b45309",
            "accent_positive": "#c2410c",
            "accent_negative": "#1e3a8a",
            "accent_warning": "#ea580c",
            "accent_emphasis": "#7c3aed",
            "path_current": "#b45309",
            "cube_orbital_positive": "#ea580c",
            "cube_orbital_negative": "#1d4ed8",
            "cube_density_surface": "#d97706",
            "charge_positive": "#c2410c",
            "charge_negative": "#1d4ed8",
        },
        path_branch_colors=("#1d4ed8", "#ea580c", "#7c3aed", "#0f766e"),
        orbital_slice_colorscale=(
            (0.00, "#1d4ed8"),
            (0.18, "#60a5fa"),
            (0.50, "#f8fafc"),
            (0.82, "#fdba74"),
            (1.00, "#c2410c"),
        ),
    ),
    "teal_crimson": _scheme(
        "teal_crimson",
        "青红对比",
        palette_overrides={
            "accent_primary": "#0f766e",
            "accent_primary_light": "#5eead4",
            "accent_secondary": "#be123c",
            "accent_secondary_dark": "#9f1239",
            "accent_positive": "#be123c",
            "accent_negative": "#0f766e",
            "accent_warning": "#ea580c",
            "accent_emphasis": "#2563eb",
            "path_current": "#be123c",
            "cube_orbital_positive": "#be123c",
            "cube_orbital_negative": "#0f766e",
            "cube_density_surface": "#0f766e",
            "charge_positive": "#be123c",
            "charge_negative": "#0f766e",
        },
        path_branch_colors=("#0f766e", "#be123c", "#2563eb", "#d97706"),
        orbital_slice_colorscale=(
            (0.00, "#115e59"),
            (0.20, "#2dd4bf"),
            (0.50, "#f8fafc"),
            (0.80, "#fb7185"),
            (1.00, "#9f1239"),
        ),
    ),
    "violet_cyan": _scheme(
        "violet_cyan",
        "紫青对比",
        font_size=15,
        line_scale=1.06,
        marker_scale=1.08,
        palette_overrides={
            "accent_primary": "#7c3aed",
            "accent_primary_light": "#c4b5fd",
            "accent_secondary": "#0891b2",
            "accent_secondary_dark": "#0e7490",
            "accent_positive": "#db2777",
            "accent_negative": "#0891b2",
            "accent_warning": "#f59e0b",
            "accent_emphasis": "#0f766e",
            "path_current": "#0891b2",
            "cube_orbital_positive": "#db2777",
            "cube_orbital_negative": "#0891b2",
            "cube_density_surface": "#0e7490",
            "charge_positive": "#db2777",
            "charge_negative": "#0891b2",
        },
        path_branch_colors=("#7c3aed", "#0891b2", "#db2777", "#0f766e"),
        orbital_slice_colorscale=(
            (0.00, "#0e7490"),
            (0.22, "#67e8f9"),
            (0.50, "#f8fafc"),
            (0.80, "#f9a8d4"),
            (1.00, "#be185d"),
        ),
    ),
    "monochrome_accent": _scheme(
        "monochrome_accent",
        "灰阶强调",
        title_size=19,
        line_scale=0.98,
        marker_scale=0.94,
        palette_overrides={
            "accent_primary": "#334155",
            "accent_primary_light": "#94a3b8",
            "accent_secondary": "#475569",
            "accent_secondary_dark": "#1e293b",
            "accent_positive": "#b91c1c",
            "accent_negative": "#334155",
            "accent_warning": "#a16207",
            "accent_emphasis": "#0f172a",
            "path_current": "#b91c1c",
            "cube_orbital_positive": "#a16207",
            "cube_orbital_negative": "#334155",
            "cube_density_surface": "#475569",
            "charge_positive": "#b91c1c",
            "charge_negative": "#334155",
            "grid": "rgba(100, 116, 139, 0.16)",
        },
        path_branch_colors=("#0f172a", "#475569", "#94a3b8", "#b91c1c"),
        esp_slice_colorscale=(
            (0.00, "#991b1b"),
            (0.22, "#dc2626"),
            (0.50, "#f8fafc"),
            (0.78, "#64748b"),
            (1.00, "#1e293b"),
        ),
        orbital_slice_colorscale=(
            (0.00, "#334155"),
            (0.22, "#94a3b8"),
            (0.50, "#f8fafc"),
            (0.80, "#d6d3d1"),
            (1.00, "#92400e"),
        ),
    ),
}


def visual_style_preset(key: str | None) -> VisualizationStyle:
    normalized = str(key or "scientific_standard").strip().lower()
    normalized = normalized.replace(" ", "_").replace("-", "_")
    alias_map = {
        "scientific": "scientific_standard",
        "standard": "scientific_standard",
        "blue_orange": "cobalt_amber",
        "cobalt_orange": "cobalt_amber",
        "cobalt_amber": "cobalt_amber",
        "publication": "monochrome_accent",
        "minimal": "monochrome_accent",
        "presentation": "cobalt_amber",
        "bold": "cobalt_amber",
        "teal_red": "teal_crimson",
        "teal_crimson": "teal_crimson",
        "violet": "violet_cyan",
        "violet_cyan": "violet_cyan",
        "monochrome": "monochrome_accent",
        "dark": "scientific_standard",
        "dark_mode": "scientific_standard",
        "soft": "scientific_standard",
        "soft_clean": "scientific_standard",
        "publication_minimal": "monochrome_accent",
        "presentation_bold": "cobalt_amber",
    }
    preset_key = alias_map.get(normalized, normalized)
    return VISUAL_STYLE_PRESETS.get(preset_key, VISUAL_STYLE_PRESETS["scientific_standard"])


def resolve_visual_style(style_key: str | None = None) -> VisualizationStyle:
    return visual_style_preset(style_key)


def visual_style_palette(style_key: str | None = None) -> dict[str, str]:
    return resolve_visual_style(style_key).palette


def visual_style_display_map() -> dict[str, str]:
    return {key: preset.label for key, preset in VISUAL_STYLE_PRESETS.items()}


def figure_visual_style_key(figure: go.Figure) -> str:
    meta = getattr(figure.layout, "meta", None)
    if isinstance(meta, dict):
        orca_meta = meta.get("orca_viz", {})
        if isinstance(orca_meta, dict) and orca_meta.get("visual_style_key"):
            return str(orca_meta["visual_style_key"])
    return "scientific_standard"


def register_figure_visual_style(figure: go.Figure, style_key: str | None) -> str:
    style = resolve_visual_style(style_key)
    meta = getattr(figure.layout, "meta", None)
    meta_dict = dict(meta) if isinstance(meta, dict) else {}
    orca_meta = dict(meta_dict.get("orca_viz", {})) if isinstance(meta_dict.get("orca_viz"), dict) else {}
    orca_meta["visual_style_key"] = style.key
    meta_dict["orca_viz"] = orca_meta
    figure.update_layout(meta=meta_dict)
    return style.key


# These defaults follow the mainstream ball-and-stick conventions used by
# ChimeraX and PyMOL examples:
# - ChimeraX commonly starts with ballScale 0.3 and stickRadius 0.2 A
# - PyMOL ball-and-stick examples often use sphere_scale 0.25 and stick_radius 0.14
# ORCA Visualizer therefore uses 0.30 / 0.20 A as the standard cross-tool compromise.
MODEL_SIZE_PRESETS: dict[str, ModelSizeSettings] = {
    "compact": ModelSizeSettings(
        preset_key="compact",
        sphere_scale=0.25,
        stick_radius=0.15,
        space_filling_scale=0.92,
        wireframe_line_width=1.8,
    ),
    "standard": ModelSizeSettings(
        preset_key="standard",
        sphere_scale=0.30,
        stick_radius=0.20,
        space_filling_scale=1.00,
        wireframe_line_width=2.2,
    ),
    "presentation": ModelSizeSettings(
        preset_key="presentation",
        sphere_scale=0.33,
        stick_radius=0.22,
        space_filling_scale=1.08,
        wireframe_line_width=2.6,
    ),
}


def model_size_preset(key: str) -> ModelSizeSettings:
    return MODEL_SIZE_PRESETS.get(key, MODEL_SIZE_PRESETS["standard"])


def clamp_model_size_settings(settings: ModelSizeSettings) -> ModelSizeSettings:
    return ModelSizeSettings(
        preset_key=settings.preset_key,
        sphere_scale=min(max(settings.sphere_scale, 0.15), 0.50),
        stick_radius=min(max(settings.stick_radius, 0.08), 0.35),
        space_filling_scale=min(max(settings.space_filling_scale, 0.70), 1.35),
        wireframe_line_width=min(max(settings.wireframe_line_width, 0.8), 4.5),
    )


def base_layout(*, visual_style_key: str | None = None) -> dict[str, Any]:
    style = resolve_visual_style(visual_style_key)
    palette = style.palette
    return {
        "template": style.plotly_template,
        "paper_bgcolor": palette["paper_bg"],
        "plot_bgcolor": palette["plot_bg"],
        "font": {"family": style.font_family, "size": style.font_size, "color": palette["text_primary"]},
        "title": {
            "font": {"family": style.font_family, "size": style.title_size, "color": palette["text_primary"]},
            "x": 0.01,
            "xanchor": "left",
            "y": 0.98,
            "yanchor": "top",
        },
        "margin": {"l": 72, "r": 28, "t": 62, "b": 60},
        "hoverlabel": {
            "bgcolor": palette["hover_bg"],
            "bordercolor": palette["hover_border"],
            "font": {"family": style.font_family, "size": max(style.font_size - 1, 12), "color": palette["text_primary"]},
        },
        "legend": {
            "orientation": "h",
            "y": 1.04,
            "x": 1,
            "xanchor": "right",
            "bgcolor": palette["legend_bg"],
            "bordercolor": palette["border"],
            "borderwidth": 1,
            "font": {"size": max(style.font_size - 2, 11), "color": palette["text_primary"]},
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
    visual_style_key: str | None = None,
    **layout_overrides: Any,
) -> go.Figure:
    style = resolve_visual_style(visual_style_key)
    palette = style.palette
    register_figure_visual_style(figure, style.key)
    layout = base_layout(visual_style_key=style.key)
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
        linewidth=1.6 * style.line_scale,
        linecolor=palette["axis"],
        mirror=False,
        ticks="outside",
        tickcolor=palette["axis"],
        tickwidth=1.2 * style.line_scale,
        ticklen=6,
        showgrid=True,
        gridcolor=palette["grid"],
        zeroline=False,
        title_font={"size": style.font_size + 1, "color": palette["text_primary"]},
        tickfont={"size": max(style.font_size - 1, 11), "color": palette["text_muted"]},
    )
    figure.update_yaxes(
        title_text=yaxis_title,
        showline=True,
        linewidth=1.6 * style.line_scale,
        linecolor=palette["axis"],
        mirror=False,
        ticks="outside",
        tickcolor=palette["axis"],
        tickwidth=1.2 * style.line_scale,
        ticklen=6,
        showgrid=True,
        gridcolor=palette["grid"],
        zeroline=zeroline,
        zerolinecolor=palette["grid"],
        title_font={"size": style.font_size + 1, "color": palette["text_primary"]},
        tickfont={"size": max(style.font_size - 1, 11), "color": palette["text_muted"]},
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
    visual_style_key: str | None = None,
) -> go.Figure:
    style = resolve_visual_style(visual_style_key)
    palette = style.palette
    register_figure_visual_style(figure, style.key)
    layout = base_layout(visual_style_key=style.key)
    if title is not None:
        layout["title"]["text"] = title
    if height is not None:
        layout["height"] = height
    if showlegend is not None:
        layout["showlegend"] = showlegend
    layout["margin"] = margin or {"l": 0, "r": 0, "t": 56, "b": 0}
    layout["scene"] = {
        "aspectmode": "data",
        "bgcolor": palette["scene_bg"],
        "xaxis": standard_3d_axis_layout(show_axes=style.scene_axis_visible, visual_style_key=style.key)["xaxis"],
        "yaxis": standard_3d_axis_layout(show_axes=style.scene_axis_visible, visual_style_key=style.key)["yaxis"],
        "zaxis": standard_3d_axis_layout(show_axes=style.scene_axis_visible, visual_style_key=style.key)["zaxis"],
        "camera": camera or style.cameras["structure"],
    }
    figure.update_layout(**layout)
    return figure


def standard_3d_axis_layout(
    *,
    show_axes: bool = True,
    background_color: str | None = None,
    visual_style_key: str | None = None,
) -> dict[str, Any]:
    style = resolve_visual_style(visual_style_key)
    palette = style.palette
    axis_visibility = bool(show_axes)
    bg_color = background_color or palette["scene_bg"]
    axis_template = {
        "visible": axis_visibility,
        "title": {"text": None, "font": {"size": style.font_size, "color": palette["text_primary"]}},
        "backgroundcolor": bg_color,
        "showbackground": False,
        "showgrid": axis_visibility,
        "gridcolor": palette["grid"],
        "linecolor": palette["axis"],
        "zeroline": False,
        "zerolinecolor": palette["grid"],
        "showticklabels": axis_visibility,
        "tickfont": {"size": max(style.font_size - 2, 10), "color": palette["text_muted"]},
    }
    return {
        "xaxis": dict(axis_template),
        "yaxis": dict(axis_template),
        "zaxis": dict(axis_template),
    }


def standard_export_margin(
    *,
    is_3d: bool,
    crop_mode: str = "balanced",
    visual_style_key: str | None = None,
) -> dict[str, int]:
    style = resolve_visual_style(visual_style_key)
    normalized = crop_mode.strip().lower()
    if is_3d:
        if normalized == "tight":
            return {"l": 0, "r": 0, "t": max(style.title_size + 8, 34), "b": 0}
        return {"l": 0, "r": 0, "t": max(style.title_size + 20, 50), "b": 0}
    if normalized == "tight":
        return {"l": 42, "r": 18, "t": max(style.title_size + 12, 50), "b": 42}
    return {"l": 72, "r": 28, "t": max(style.title_size + 16, 58), "b": 60}


# Backward-compatible aliases for modules that still import the old names.
_DEFAULT_STYLE = resolve_visual_style("scientific_standard")
SCIENTIFIC_FONT_FAMILY = _DEFAULT_STYLE.font_family
CHART_SURFACE_BG = _DEFAULT_STYLE.palette["plot_bg"]
CHART_PAPER_BG = _DEFAULT_STYLE.palette["paper_bg"]
TEXT_PRIMARY = _DEFAULT_STYLE.palette["text_primary"]
TEXT_MUTED = _DEFAULT_STYLE.palette["text_muted"]
GRID_COLOR = _DEFAULT_STYLE.palette["grid"]
AXIS_COLOR = _DEFAULT_STYLE.palette["axis"]
BORDER_COLOR = _DEFAULT_STYLE.palette["border"]
ACCENT_TEAL = _DEFAULT_STYLE.palette["accent_secondary"]
ACCENT_TEAL_DARK = _DEFAULT_STYLE.palette["accent_secondary_dark"]
ACCENT_RED = _DEFAULT_STYLE.palette["accent_positive"]
ACCENT_RED_DARK = _DEFAULT_STYLE.palette["accent_positive"]
ACCENT_BLUE = _DEFAULT_STYLE.palette["accent_primary"]
ACCENT_BLUE_LIGHT = _DEFAULT_STYLE.palette["accent_primary_light"]
ACCENT_GOLD = _DEFAULT_STYLE.palette["accent_warning"]
ACCENT_VIOLET = _DEFAULT_STYLE.palette["accent_emphasis"]
ACCENT_SLATE = _DEFAULT_STYLE.palette["accent_neutral"]
ACCENT_ORANGE = _DEFAULT_STYLE.palette["measure_selection"]
PAPER_CAMERA = _DEFAULT_STYLE.cameras["paper"]
CUBE_CAMERA = _DEFAULT_STYLE.cameras["cube"]
STRUCTURE_CAMERA = _DEFAULT_STYLE.cameras["structure"]
