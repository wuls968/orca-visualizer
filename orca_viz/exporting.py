from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import plotly.graph_objects as go
import plotly.io as pio

from .plot_theme import (
    CHART_PAPER_BG,
    SCIENTIFIC_FONT_FAMILY,
    TEXT_PRIMARY,
    apply_standard_3d_style,
    apply_standard_2d_style,
)


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


EXPORT_PRESETS: dict[str, ExportPreset] = {
    "paper": ExportPreset(
        key="paper",
        label="Paper",
        width=2200,
        height=1400,
        scale=3,
        font_size=18,
        title_size=24,
    ),
    "presentation": ExportPreset(
        key="presentation",
        label="Presentation",
        width=1920,
        height=1080,
        scale=2,
        font_size=22,
        title_size=30,
    ),
    "web": ExportPreset(
        key="web",
        label="Web Preview",
        width=1600,
        height=1000,
        scale=2,
        font_size=16,
        title_size=22,
    ),
}


def export_preset(key: str) -> ExportPreset:
    return EXPORT_PRESETS.get(key, EXPORT_PRESETS["paper"])


def normalized_export_file_name(file_stem: str, preset_key: str, image_format: str) -> str:
    suffix = image_format.lower().lstrip(".")
    return f"{file_stem}_{preset_key}.{suffix}"


def apply_export_preset(
    figure: go.Figure,
    *,
    preset_key: str = "paper",
    width: int | None = None,
    height: int | None = None,
    font_size: int | None = None,
    title_size: int | None = None,
    transparent_background: bool | None = None,
) -> go.Figure:
    preset = export_preset(preset_key)
    export_figure = go.Figure(figure)
    if export_figure.layout.scene is not None:
        apply_standard_3d_style(export_figure)
    else:
        apply_standard_2d_style(export_figure)
    export_figure.update_layout(
        font={
            "family": SCIENTIFIC_FONT_FAMILY,
            "size": font_size or preset.font_size,
            "color": TEXT_PRIMARY,
        },
        title={
            "font": {
                "family": SCIENTIFIC_FONT_FAMILY,
                "size": title_size or preset.title_size,
                "color": TEXT_PRIMARY,
            }
        },
        paper_bgcolor="rgba(0,0,0,0)"
        if (transparent_background if transparent_background is not None else preset.transparent_background)
        else CHART_PAPER_BG,
        plot_bgcolor="rgba(0,0,0,0)"
        if (transparent_background if transparent_background is not None else preset.transparent_background)
        else CHART_PAPER_BG,
        width=width or preset.width,
        height=height or preset.height,
    )
    export_figure.update_xaxes(title_font={"size": (font_size or preset.font_size) + 1})
    export_figure.update_yaxes(title_font={"size": (font_size or preset.font_size) + 1})
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
) -> bytes:
    preset = export_preset(preset_key)
    export_figure = apply_export_preset(
        figure,
        preset_key=preset_key,
        width=width,
        height=height,
        font_size=font_size,
        title_size=title_size,
        transparent_background=transparent_background,
    )
    return pio.to_image(
        export_figure,
        format=image_format,
        width=width or preset.width,
        height=height or preset.height,
        scale=scale or preset.scale,
    )


def create_publication_ready_figure(figure: go.Figure) -> go.Figure:
    return apply_export_preset(figure, preset_key="paper")
