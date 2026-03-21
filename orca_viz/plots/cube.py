from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from ase import Atoms
from ase.data import covalent_radii

from ..cube import CubeData, cube_kind_label, esp_signed_surface_levels, sample_cube_grid
from ..i18n import tr
from ..plot_theme import ACCENT_BLUE, ACCENT_GOLD, ACCENT_RED, CUBE_CAMERA, apply_standard_2d_style, apply_standard_3d_style
from .structure import _build_bond_pairs, _combined_bond_trace

ESP_COLOR_NEGATIVE = ACCENT_RED
ESP_COLOR_POSITIVE = ACCENT_BLUE
ORBITAL_COLOR_NEGATIVE = ACCENT_BLUE
ORBITAL_COLOR_POSITIVE = ACCENT_GOLD
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
    apply_standard_2d_style(
        figure,
        title=tr(
            "{cube_kind_label} 切片 {axis} = {index}",
            cube_kind_label=cube_kind_label(cube_kind),
            axis=axis.upper(),
            index=index,
        ),
        xaxis_title=x_title,
        yaxis_title=y_title,
        showlegend=False,
        margin={"l": 76, "r": 24, "t": 60, "b": 60},
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
    apply_standard_3d_style(
        figure,
        title=title,
        camera=CUBE_CAMERA,
        showlegend=cube_kind in {"esp", "orbital"},
        margin={"l": 0, "r": 0, "t": 56, "b": 0},
    )
    figure.update_layout(
        scene={
            **figure.layout.scene.to_plotly_json(),
            "xaxis_title": "X (A)",
            "yaxis_title": "Y (A)",
            "zaxis_title": "Z (A)",
        }
    )
    return figure

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
            "ambient": 0.58,
            "diffuse": 0.92,
            "specular": 0.34,
            "roughness": 0.28,
            "fresnel": 0.18,
        },
        lightposition={"x": 110, "y": 150, "z": 95},
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
