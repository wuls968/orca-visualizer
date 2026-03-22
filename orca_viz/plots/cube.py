from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from ase import Atoms
from ase.data import covalent_radii
from scipy.interpolate import RegularGridInterpolator

try:
    from skimage.measure import marching_cubes
except ImportError:  # pragma: no cover - dependency is declared, but keep a safe fallback
    marching_cubes = None

from ..cube import CubeData, cube_grid_is_compatible, cube_kind_label, esp_signed_surface_levels
from ..i18n import tr
from ..plot_theme import (
    ModelSizeSettings,
    apply_standard_2d_style,
    apply_standard_3d_style,
    resolve_visual_style,
)
from .structure import (
    _build_bond_pairs,
    _combined_bond_trace,
    _representation_bond_traces,
    _resolved_model_size_settings,
    _structure_atom_sizes,
)


def _rgba(hex_color: str, alpha: float) -> str:
    stripped = hex_color.lstrip("#")
    if len(stripped) != 6:
        return hex_color
    red = int(stripped[0:2], 16)
    green = int(stripped[2:4], 16)
    blue = int(stripped[4:6], 16)
    return f"rgba({red}, {green}, {blue}, {alpha:.3f})"

def create_cube_slice_figure(
    cube: CubeData,
    axis: str = "z",
    index: int | None = None,
    *,
    visual_style_key: str | None = None,
) -> go.Figure:
    visual_style = resolve_visual_style(visual_style_key)
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

    colorscale = _cube_slice_colorscale(cube_kind, visual_style_key=visual_style.key)
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
        visual_style_key=visual_style.key,
    )
    return figure


def create_cube_isosurface_figure(
    cube: CubeData,
    level: float = 0.03,
    quality: str = "精细",
    show_structure: bool = True,
    opacity: float | None = None,
    surface_mode: str = "default",
    surface_cube: CubeData | None = None,
    structure_representation: str = "ball_stick",
    model_size_settings: ModelSizeSettings | None = None,
    visual_style_key: str | None = None,
) -> go.Figure:
    visual_style = resolve_visual_style(visual_style_key)
    palette = visual_style.palette
    cube_kind = cube.metadata.get("cube_kind", "generic")
    stride = _cube_stride(cube, max_points=_cube_render_budget(cube_kind, quality))
    sampled_values, sampled_origin, sampled_axes = _sampled_cube_volume(cube, stride=stride)
    xs, ys, zs = _sampled_cube_coordinates(sampled_values.shape, sampled_origin, sampled_axes)
    value_flat = sampled_values.ravel()
    positive_extent = float(np.max(value_flat)) if value_flat.size else 0.0
    negative_extent = float(np.max(-value_flat)) if value_flat.size else 0.0
    use_mesh = _use_mesh_render(quality)

    figure = go.Figure()
    focus_sets: list[np.ndarray] = []

    if cube_kind == "esp" and surface_mode == "density_surface" and surface_cube is not None:
        density_stride = _cube_stride(surface_cube, max_points=_cube_render_budget("electron_density", quality))
        density_values, density_origin, density_axes = _sampled_cube_volume(surface_cube, stride=density_stride)
        if cube_grid_is_compatible(cube, surface_cube):
            density_mesh = _extract_isosurface_mesh(
                density_values,
                level=abs(level),
                origin=density_origin,
                axes=density_axes,
            )
            if density_mesh is not None:
                vertices, faces = density_mesh
                vertex_index_space = _transform_coordinates_to_grid(
                    vertices,
                    density_origin,
                    density_axes,
                )
                esp_sampled, _, _ = _sampled_cube_volume(cube, stride=density_stride)
                esp_vertex_values = _interpolate_grid_values(esp_sampled, vertex_index_space)
                color_scale = _esp_surface_color_limits(esp_vertex_values)
                figure.add_trace(
                    _mesh_trace(
                        vertices,
                        faces,
                        name=tr("ESP on electron density surface"),
                        opacity=opacity if opacity is not None else 0.78,
                        intensity=esp_vertex_values,
                        colorscale=_cube_slice_colorscale("esp", visual_style_key=visual_style.key),
                        cmin=-color_scale,
                        cmax=color_scale,
                        colorbar_title="ESP",
                    )
                )
                focus_sets.append(vertices)
            else:
                surface_mode = "default"
        else:
            surface_mode = "default"

    if surface_mode == "default":
        if cube_kind == "esp":
            esp_opacity = opacity if opacity is not None else 0.20
            esp_levels = esp_signed_surface_levels(cube, abs(level))
            positive_level = esp_levels["positive_level"]
            negative_level = esp_levels["negative_level"]
            positive_cap = esp_levels["positive_cap"]
            negative_cap = esp_levels["negative_cap"]
            positive_focus = sampled_values >= positive_level
            negative_focus = sampled_values <= -negative_level
            if positive_extent > positive_level:
                if use_mesh:
                    positive_mesh = _extract_isosurface_mesh(
                        sampled_values,
                        level=positive_level,
                        origin=sampled_origin,
                        axes=sampled_axes,
                    )
                    if positive_mesh is not None:
                        figure.add_trace(
                            _mesh_trace(
                                positive_mesh[0],
                                positive_mesh[1],
                                name=tr("ESP > 0"),
                                opacity=esp_opacity,
                                color=palette["cube_esp_positive"],
                            )
                        )
                        focus_sets.append(positive_mesh[0])
                else:
                    figure.add_trace(
                        _single_signed_isosurface(
                            xs,
                            ys,
                            zs,
                            value_flat,
                            level=positive_level,
                            max_extent=min(positive_extent, positive_cap),
                            color=palette["cube_esp_positive"],
                            name=tr("ESP > 0"),
                            opacity=esp_opacity,
                        )
                    )
                    focus_sets.append(_masked_points(positive_focus, xs, ys, zs))
            if negative_extent > negative_level:
                if use_mesh:
                    negative_mesh = _extract_isosurface_mesh(
                        -sampled_values,
                        level=negative_level,
                        origin=sampled_origin,
                        axes=sampled_axes,
                    )
                    if negative_mesh is not None:
                        figure.add_trace(
                            _mesh_trace(
                                negative_mesh[0],
                                negative_mesh[1],
                                name=tr("ESP < 0"),
                                opacity=esp_opacity,
                                color=palette["cube_esp_negative"],
                            )
                        )
                        focus_sets.append(negative_mesh[0])
                else:
                    figure.add_trace(
                        _single_signed_isosurface(
                            xs,
                            ys,
                            zs,
                            -value_flat,
                            level=negative_level,
                            max_extent=min(negative_extent, negative_cap),
                            color=palette["cube_esp_negative"],
                            name=tr("ESP < 0"),
                            opacity=esp_opacity,
                        )
                    )
                    focus_sets.append(_masked_points(negative_focus, xs, ys, zs))
        elif cube_kind == "orbital":
            orbital_opacity = opacity if opacity is not None else 0.82
            focus_sets.extend(
                _render_signed_cube_surfaces(
                    figure,
                    sampled_values=sampled_values,
                    sampled_origin=sampled_origin,
                    sampled_axes=sampled_axes,
                    xs=xs,
                    ys=ys,
                    zs=zs,
                    level=abs(level),
                    positive_color=palette["cube_orbital_positive"],
                    negative_color=palette["cube_orbital_negative"],
                    positive_name=tr("phase +"),
                    negative_name=tr("phase -"),
                    opacity=orbital_opacity,
                    use_mesh=use_mesh,
                )
            )
        elif cube_kind == "spin_density":
            spin_opacity = opacity if opacity is not None else 0.70
            focus_sets.extend(
                _render_signed_cube_surfaces(
                    figure,
                    sampled_values=sampled_values,
                    sampled_origin=sampled_origin,
                    sampled_axes=sampled_axes,
                    xs=xs,
                    ys=ys,
                    zs=zs,
                    level=abs(level),
                    positive_color=palette["cube_spin_positive"],
                    negative_color=palette["cube_spin_negative"],
                    positive_name=tr("spin +"),
                    negative_name=tr("spin -"),
                    opacity=spin_opacity,
                    use_mesh=use_mesh,
                )
            )
        else:
            default_opacity = opacity if opacity is not None else 0.42 if cube_kind == "electron_density" else 0.55
            if use_mesh:
                source_values = sampled_values if np.max(sampled_values) > abs(level) else np.abs(sampled_values)
                mesh = _extract_isosurface_mesh(
                    source_values,
                    level=abs(level),
                    origin=sampled_origin,
                    axes=sampled_axes,
                )
                if mesh is not None:
                    figure.add_trace(
                        _mesh_trace(
                            mesh[0],
                            mesh[1],
                            name=_cube_colorbar_title(cube_kind),
                            opacity=default_opacity,
                            color=palette["cube_density_surface"],
                        )
                    )
                    focus_sets.append(mesh[0])
            else:
                extent = float(np.max(np.abs(value_flat))) if value_flat.size else abs(level)
                figure.add_trace(
                    _single_signed_isosurface(
                        xs,
                        ys,
                        zs,
                        np.abs(value_flat),
                        level=abs(level),
                        max_extent=extent,
                        color=palette["cube_density_surface"],
                        name=_cube_colorbar_title(cube_kind),
                        opacity=default_opacity,
                    )
                )
                focus_sets.append(_masked_points(np.abs(sampled_values) >= abs(level), xs, ys, zs))

    if show_structure and cube.atoms is not None and len(cube.atoms) > 0:
        for trace in _subtle_structure_traces(
            cube.atoms,
            cube_kind,
            representation=structure_representation,
            model_size_settings=model_size_settings,
            visual_style_key=visual_style.key,
        ):
            figure.add_trace(trace)

    title = _cube_isosurface_title(cube_kind, level, surface_mode=surface_mode)
    apply_standard_3d_style(
        figure,
        title=title,
        camera=_cube_camera(focus_sets, cube.atoms),
        showlegend=cube_kind in {"esp", "orbital", "spin_density"},
        margin={"l": 0, "r": 0, "t": 56, "b": 0},
        visual_style_key=visual_style.key,
    )
    scene_layout = figure.layout.scene.to_plotly_json()
    for axis_name, axis_payload in _cube_scene_ranges(focus_sets, cube.atoms).items():
        merged_axis = scene_layout.get(axis_name, {})
        merged_axis.update(axis_payload)
        scene_layout[axis_name] = merged_axis
    figure.update_layout(scene=scene_layout)
    figure.update_scenes(xaxis_title="X (A)", yaxis_title="Y (A)", zaxis_title="Z (A)")
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
        "standard": 90_000,
        "fine": 260_000,
        "ultra": 720_000,
    }.get(normalized_quality, 260_000)
    if cube_kind in {"orbital", "esp", "spin_density"}:
        return int(base_budget * 1.35)
    if cube_kind == "electron_density":
        return int(base_budget * 1.10)
    return base_budget


def _use_mesh_render(quality: str) -> bool:
    normalized_quality = {
        "标准": "standard",
        "Standard": "standard",
        "精细": "fine",
        "Fine": "fine",
        "极致": "ultra",
        "Ultra": "ultra",
    }.get(quality, quality)
    return normalized_quality == "ultra" and marching_cubes is not None


def _cube_slice_colorscale(
    cube_kind: str,
    *,
    visual_style_key: str | None = None,
) -> list[list[float | str]] | str:
    visual_style = resolve_visual_style(visual_style_key)
    if cube_kind == "esp":
        return [[point, color] for point, color in visual_style.esp_slice_colorscale]
    if cube_kind == "orbital":
        return [[point, color] for point, color in visual_style.orbital_slice_colorscale]
    if cube_kind in {"electron_density", "density"}:
        return "Viridis"
    if cube_kind == "spin_density":
        return visual_style.charge_colorscale
    return "RdBu"


def _cube_colorbar_title(cube_kind: str) -> str:
    return {
        "esp": "ESP",
        "orbital": "Orbital phase",
        "electron_density": "Density",
        "spin_density": "Spin density",
        "density": "Density",
    }.get(cube_kind, "Value")


def _cube_isosurface_title(cube_kind: str, level: float, *, surface_mode: str = "default") -> str:
    if cube_kind == "esp" and surface_mode == "density_surface":
        return tr("电子密度表面的 ESP 着色 |rho| = {level}", level=f"{abs(level):.4f}")
    if cube_kind == "esp":
        return tr("ESP 等势面 |V| = {level}", level=f"{abs(level):.3f}")
    if cube_kind == "orbital":
        return tr("轨道相位等值面 |psi| = {level}", level=f"{abs(level):.3f}")
    if cube_kind == "electron_density":
        return tr("电子密度等值面 rho = {level}", level=f"{abs(level):.4f}")
    if cube_kind == "spin_density":
        return tr("自旋密度等值面 |rho_s| = {level}", level=f"{abs(level):.4f}")
    return tr("Cube 等值面 |value| = {level}", level=f"{abs(level):.4f}")


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
            "ambient": 0.62,
            "diffuse": 0.96,
            "specular": 0.28,
            "roughness": 0.18,
            "fresnel": 0.10,
        },
        lightposition={"x": 115, "y": 145, "z": 105},
        showscale=False,
        name=name,
        hovertemplate=f"{name}<br>{tr('阈值')}={level:.4f}<extra></extra>",
    )


def _mesh_trace(
    vertices: np.ndarray,
    faces: np.ndarray,
    *,
    name: str,
    opacity: float,
    color: str | None = None,
    intensity: np.ndarray | None = None,
    colorscale: list[list[float | str]] | str | None = None,
    cmin: float | None = None,
    cmax: float | None = None,
    colorbar_title: str | None = None,
) -> go.Mesh3d:
    trace_kwargs: dict[str, object] = {
        "x": vertices[:, 0],
        "y": vertices[:, 1],
        "z": vertices[:, 2],
        "i": faces[:, 0],
        "j": faces[:, 1],
        "k": faces[:, 2],
        "opacity": opacity,
        "flatshading": False,
        "lighting": {
            "ambient": 0.65,
            "diffuse": 0.96,
            "specular": 0.20,
            "roughness": 0.14,
            "fresnel": 0.06,
        },
        "lightposition": {"x": 120, "y": 150, "z": 110},
        "hovertemplate": f"{name}<extra></extra>",
        "name": name,
        "showscale": bool(intensity is not None),
    }
    if intensity is not None:
        trace_kwargs.update(
            {
                "intensity": intensity,
                "intensitymode": "vertex",
                "colorscale": colorscale,
                "cmin": cmin,
                "cmax": cmax,
                "colorbar": {"title": colorbar_title} if colorbar_title else None,
            }
        )
    else:
        trace_kwargs["color"] = color
    return go.Mesh3d(**trace_kwargs)


def _render_signed_cube_surfaces(
    figure: go.Figure,
    *,
    sampled_values: np.ndarray,
    sampled_origin: np.ndarray,
    sampled_axes: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
    zs: np.ndarray,
    level: float,
    positive_color: str,
    negative_color: str,
    positive_name: str,
    negative_name: str,
    opacity: float,
    use_mesh: bool,
) -> list[np.ndarray]:
    focus_sets: list[np.ndarray] = []
    value_flat = sampled_values.ravel()
    positive_extent = float(np.max(value_flat)) if value_flat.size else 0.0
    negative_extent = float(np.max(-value_flat)) if value_flat.size else 0.0
    positive_mask = sampled_values >= level
    negative_mask = sampled_values <= -level
    if positive_extent > level:
        if use_mesh:
            positive_mesh = _extract_isosurface_mesh(
                sampled_values,
                level=level,
                origin=sampled_origin,
                axes=sampled_axes,
            )
            if positive_mesh is not None:
                figure.add_trace(
                    _mesh_trace(
                        positive_mesh[0],
                        positive_mesh[1],
                        name=positive_name,
                        opacity=opacity,
                        color=positive_color,
                    )
                )
                focus_sets.append(positive_mesh[0])
        else:
            figure.add_trace(
                _single_signed_isosurface(
                    xs,
                    ys,
                    zs,
                    value_flat,
                    level=level,
                    max_extent=positive_extent,
                    color=positive_color,
                    name=positive_name,
                    opacity=opacity,
                )
            )
            focus_sets.append(_masked_points(positive_mask, xs, ys, zs))
    if negative_extent > level:
        if use_mesh:
            negative_mesh = _extract_isosurface_mesh(
                -sampled_values,
                level=level,
                origin=sampled_origin,
                axes=sampled_axes,
            )
            if negative_mesh is not None:
                figure.add_trace(
                    _mesh_trace(
                        negative_mesh[0],
                        negative_mesh[1],
                        name=negative_name,
                        opacity=opacity,
                        color=negative_color,
                    )
                )
                focus_sets.append(negative_mesh[0])
        else:
            figure.add_trace(
                _single_signed_isosurface(
                    xs,
                    ys,
                    zs,
                    -value_flat,
                    level=level,
                    max_extent=negative_extent,
                    color=negative_color,
                    name=negative_name,
                    opacity=opacity,
                )
            )
            focus_sets.append(_masked_points(negative_mask, xs, ys, zs))
    return focus_sets


def _sampled_cube_volume(
    cube: CubeData,
    *,
    stride: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    slices = tuple(slice(None, None, stride) for _ in range(3))
    sampled_values = cube.values[slices]
    sampled_axes = cube.axis_vectors_angstrom * stride
    return sampled_values, cube.origin_angstrom, sampled_axes


def _sampled_cube_coordinates(
    shape: tuple[int, int, int],
    origin: np.ndarray,
    axes: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    i, j, k = np.indices(shape)
    coords = origin + i[..., None] * axes[0] + j[..., None] * axes[1] + k[..., None] * axes[2]
    return coords[..., 0].ravel(), coords[..., 1].ravel(), coords[..., 2].ravel()


def _extract_isosurface_mesh(
    values: np.ndarray,
    *,
    level: float,
    origin: np.ndarray,
    axes: np.ndarray,
) -> tuple[np.ndarray, np.ndarray] | None:
    if marching_cubes is None:
        return None
    finite_values = values[np.isfinite(values)]
    if finite_values.size == 0:
        return None
    if float(np.max(finite_values)) <= level or float(np.min(finite_values)) >= level:
        return None
    try:
        vertices, faces, _, _ = marching_cubes(values.astype(float), level=level, allow_degenerate=False)
    except (RuntimeError, ValueError):
        return None
    cartesian_vertices = origin + vertices[:, 0:1] * axes[0] + vertices[:, 1:2] * axes[1] + vertices[:, 2:3] * axes[2]
    return cartesian_vertices, faces.astype(int)


def _transform_coordinates_to_grid(
    coordinates: np.ndarray,
    origin: np.ndarray,
    axes: np.ndarray,
) -> np.ndarray:
    relative = coordinates - origin
    transform = np.column_stack([axes[0], axes[1], axes[2]])
    return np.linalg.solve(transform, relative.T).T


def _interpolate_grid_values(values: np.ndarray, coordinates: np.ndarray) -> np.ndarray:
    interpolator = RegularGridInterpolator(
        (np.arange(values.shape[0]), np.arange(values.shape[1]), np.arange(values.shape[2])),
        values,
        bounds_error=False,
        fill_value=np.nan,
    )
    sampled = interpolator(coordinates)
    sampled = np.where(np.isfinite(sampled), sampled, 0.0)
    return sampled.astype(float)


def _esp_surface_color_limits(values: np.ndarray) -> float:
    finite_values = values[np.isfinite(values)]
    if finite_values.size == 0:
        return 0.05
    positive = finite_values[finite_values > 1e-9]
    negative = np.abs(finite_values[finite_values < -1e-9])
    candidates: list[float] = []
    if positive.size:
        candidates.append(float(np.quantile(positive, 0.96)))
    if negative.size:
        candidates.append(float(np.quantile(negative, 0.96)))
    if candidates:
        return max(max(candidates), 0.01)
    return max(float(np.quantile(np.abs(finite_values), 0.96)), 0.01)


def _masked_points(mask: np.ndarray, xs: np.ndarray, ys: np.ndarray, zs: np.ndarray) -> np.ndarray:
    if not np.any(mask):
        return np.empty((0, 3))
    return np.column_stack([xs[mask.ravel()], ys[mask.ravel()], zs[mask.ravel()]])


def _subtle_structure_traces(
    atoms: Atoms,
    cube_kind: str,
    *,
    representation: str = "ball_stick",
    model_size_settings: ModelSizeSettings | None = None,
    visual_style_key: str | None = None,
) -> list[go.Scatter3d]:
    visual_style = resolve_visual_style(visual_style_key)
    style = _resolved_model_size_settings(model_size_settings)
    positions = atoms.get_positions()
    atom_sizes = _structure_atom_sizes(
        atoms.get_atomic_numbers(),
        representation,
        model_size_settings=style,
    )
    overlay_base = visual_style.palette["structure_overlay"]
    atom_color = _rgba(overlay_base, 0.38 if cube_kind in {"esp", "electron_density"} else 0.54)
    bond_color = _rgba(overlay_base, 0.34 if cube_kind in {"esp", "electron_density"} else 0.52)
    traces: list[go.Scatter3d] = []
    for bond_trace in _representation_bond_traces(
        atoms,
        representation=representation,
        bond_pairs=_build_bond_pairs(atoms),
        model_size_settings=style,
        visual_style_key=visual_style.key,
    ):
        traces.append(
            go.Scatter3d(
                x=bond_trace.x,
                y=bond_trace.y,
                z=bond_trace.z,
                mode="lines",
                line={"color": bond_color, "width": max(1.8, float(bond_trace.line.width) * 0.76)},
                hoverinfo="skip",
                showlegend=False,
            )
        )
    traces.append(
        go.Scatter3d(
            x=positions[:, 0],
            y=positions[:, 1],
            z=positions[:, 2],
            mode="markers",
            marker={
                "size": atom_sizes,
                "color": atom_color,
                "line": {"color": _rgba(visual_style.palette["text_primary"], 0.28), "width": 0.8},
                "opacity": 0.55 if representation == "space_filling" else 0.78,
            },
            hoverinfo="skip",
            showlegend=False,
        )
    )
    return traces


def _cube_scene_ranges(surface_sets: list[np.ndarray], atoms: Atoms | None) -> dict[str, dict[str, list[float]]]:
    points = _cube_focus_points(surface_sets, atoms)
    mins = np.min(points, axis=0)
    maxs = np.max(points, axis=0)
    spans = np.maximum(maxs - mins, 0.2)
    max_span = float(np.max(spans))
    padding = max(max_span * 0.14, 0.45)
    ranges = []
    for axis_min, axis_max in zip(mins, maxs):
        center = float((axis_min + axis_max) / 2.0)
        half_span = float(max(axis_max - axis_min, 0.2) / 2.0 + padding)
        ranges.append([center - half_span, center + half_span])
    return {
        "xaxis": {"range": ranges[0]},
        "yaxis": {"range": ranges[1]},
        "zaxis": {"range": ranges[2]},
    }


def _cube_camera(surface_sets: list[np.ndarray], atoms: Atoms | None) -> dict[str, dict[str, float]]:
    points = _cube_focus_points(surface_sets, atoms)
    mins = np.min(points, axis=0)
    maxs = np.max(points, axis=0)
    spans = np.maximum(maxs - mins, 0.2)
    max_span = float(np.max(spans))
    normalized = spans / max_span if max_span > 0 else np.ones(3)
    scale = 1.06 if max_span < 6.0 else 1.12
    return {
        "eye": {
            "x": scale * (1.00 + 0.24 * float(normalized[0])),
            "y": scale * (0.92 + 0.24 * float(normalized[1])),
            "z": scale * (0.82 + 0.22 * float(normalized[2])),
        }
    }


def _cube_focus_points(surface_sets: list[np.ndarray], atoms: Atoms | None) -> np.ndarray:
    selected_points: list[np.ndarray] = [points for points in surface_sets if points.size]
    if atoms is not None and len(atoms) > 0:
        selected_points.append(atoms.get_positions())
    if selected_points:
        return np.vstack(selected_points)
    if atoms is not None and len(atoms) > 0:
        return atoms.get_positions()
    return np.zeros((1, 3))
