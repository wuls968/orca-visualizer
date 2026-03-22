from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd
from ase import Atoms
from ase.data import chemical_symbols

from .i18n import tr


BOHR_TO_ANGSTROM = 0.529177210903


@dataclass
class CubeData:
    source_name: str
    atoms: Atoms
    origin_angstrom: np.ndarray
    axis_vectors_angstrom: np.ndarray
    grid_shape: tuple[int, int, int]
    values: np.ndarray
    comments: tuple[str, str] = ("", "")
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def atom_count(self) -> int:
        return len(self.atoms)

    @property
    def voxel_count(self) -> int:
        return int(np.prod(self.grid_shape))

    @property
    def value_range(self) -> tuple[float, float]:
        return float(np.min(self.values)), float(np.max(self.values))


def parse_cube_file(path: str | Path) -> CubeData:
    file_path = Path(path)
    with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
        lines = handle.readlines()

    if len(lines) < 6:
        raise ValueError(tr("Cube 文件内容不完整。"))

    comment_1 = lines[0].rstrip("\n")
    comment_2 = lines[1].rstrip("\n")

    origin_tokens = lines[2].split()
    natoms_raw = int(origin_tokens[0])
    natoms = abs(natoms_raw)
    origin = np.array([float(value) for value in origin_tokens[1:4]], dtype=float)

    axis_counts: list[int] = []
    axis_vectors: list[list[float]] = []
    for axis_line in lines[3:6]:
        parts = axis_line.split()
        axis_counts.append(abs(int(parts[0])))
        axis_vectors.append([float(value) for value in parts[1:4]])

    atom_lines = lines[6 : 6 + natoms]
    symbols: list[str] = []
    positions: list[list[float]] = []
    atomic_numbers: list[int] = []
    for atom_line in atom_lines:
        parts = atom_line.split()
        atomic_number = int(float(parts[0]))
        x, y, z = [float(value) for value in parts[2:5]]
        atomic_numbers.append(atomic_number)
        symbols.append(_atomic_symbol(atomic_number))
        positions.append([x, y, z])

    value_start = 6 + natoms
    if natoms_raw < 0:
        value_start += 1

    scalar_values: list[float] = []
    for line in lines[value_start:]:
        scalar_values.extend(float(value) for value in line.split())

    grid_shape = tuple(axis_counts)
    expected_values = int(np.prod(grid_shape))
    values = np.array(scalar_values[:expected_values], dtype=float)
    if values.size != expected_values:
        raise ValueError(tr("Cube 标量场数量与网格维度不匹配。"))

    atoms = Atoms(
        symbols=symbols,
        positions=np.array(positions, dtype=float) * BOHR_TO_ANGSTROM,
    )
    axis_vectors_angstrom = np.array(axis_vectors, dtype=float) * BOHR_TO_ANGSTROM
    origin_angstrom = origin * BOHR_TO_ANGSTROM

    cube = CubeData(
        source_name=file_path.name,
        atoms=atoms,
        origin_angstrom=origin_angstrom,
        axis_vectors_angstrom=axis_vectors_angstrom,
        grid_shape=grid_shape,
        values=values.reshape(grid_shape),
        comments=(comment_1, comment_2),
        metadata={
            "path": str(file_path.resolve()),
            "atomic_numbers": atomic_numbers,
            "natoms_raw": natoms_raw,
            "cube_kind": infer_cube_kind(
                file_path.name,
                comments=(comment_1, comment_2),
                natoms_raw=natoms_raw,
            ),
            "cube_kind_label": cube_kind_label(
                infer_cube_kind(
                    file_path.name,
                    comments=(comment_1, comment_2),
                    natoms_raw=natoms_raw,
                )
            ),
        },
    )

    if cube.voxel_count > 250_000:
        cube.warnings.append(tr("Cube 网格较大，3D 等值面会自动降采样显示。"))

    return cube


def infer_cube_kind(
    source_name: str,
    comments: tuple[str, str] = ("", ""),
    natoms_raw: int | None = None,
) -> str:
    haystack = " ".join([source_name, comments[0], comments[1]]).lower()
    if "electrostatic potential" in haystack or source_name.lower().endswith(".esp.cube"):
        return "esp"
    if "molecular orbital" in haystack or re.search(r"\.mo\d+[ab]?\.cube$", source_name.lower()):
        return "orbital"
    if "spin density" in haystack or ".spindens.cube" in source_name.lower():
        return "spin_density"
    if "electron density" in haystack or ".eldens.cube" in source_name.lower():
        return "electron_density"
    if natoms_raw is not None and natoms_raw < 0:
        return "orbital"
    if "density" in haystack:
        return "density"
    return "generic"


def cube_kind_label(kind: str) -> str:
    labels = {
        "esp": tr("ESP 静电势"),
        "orbital": tr("分子轨道"),
        "electron_density": tr("电子密度"),
        "spin_density": tr("自旋密度"),
        "density": tr("密度"),
        "generic": tr("通用体数据"),
    }
    return labels.get(kind, tr("通用体数据"))


def suggest_cube_isovalue(cube: CubeData) -> float:
    kind = cube.metadata.get("cube_kind", "generic")
    values, abs_values = _cube_value_arrays(cube)
    if abs_values.size == 0:
        return 0.03

    max_abs = float(np.max(abs_values))
    if kind == "orbital":
        suggested = float(np.quantile(abs_values, 0.78))
        lower = max(float(np.quantile(abs_values, 0.55)) * 0.55, max_abs * 0.004, 5e-4)
        upper = max(max_abs * 0.12, lower * 1.5)
        return min(max(suggested, lower), upper)
    if kind == "esp":
        positive = values[values > 1e-9]
        negative = np.abs(values[values < -1e-9])
        if positive.size and negative.size:
            suggested = min(
                float(np.quantile(positive, 0.84)),
                float(np.quantile(negative, 0.84)),
            )
            upper = max(
                float(np.quantile(positive, 0.97)),
                float(np.quantile(negative, 0.97)),
            )
            return min(max(suggested, 0.001), max(upper * 0.82, 0.02))
        suggested = float(np.quantile(abs_values, 0.82))
        return min(max(suggested, max_abs * 0.002), max_abs * 0.22)
    if kind == "electron_density":
        positive = values[values > 1e-12]
        if positive.size == 0:
            return 0.002
        suggested = float(np.quantile(positive, 0.90))
        lower = max(float(np.quantile(positive, 0.80)) * 0.7, 2e-4)
        upper = max(float(np.quantile(positive, 0.965)), lower * 1.6, 0.003)
        return min(max(suggested, lower), upper)
    if kind == "spin_density":
        positive = values[values > 1e-9]
        negative = np.abs(values[values < -1e-9])
        phase_samples = [sample for sample in (positive, negative) if sample.size]
        if phase_samples:
            suggested = min(float(np.quantile(sample, 0.80)) for sample in phase_samples)
            lower = max(min(float(np.quantile(sample, 0.62)) for sample in phase_samples) * 0.7, 5e-4)
            upper = max(max(float(np.quantile(sample, 0.97)) for sample in phase_samples), lower * 1.8)
            return min(max(suggested, lower), upper)
        suggested = float(np.quantile(abs_values, 0.82))
        return min(max(suggested, max_abs * 0.01), max_abs * 0.22)
    if kind == "density":
        positive = abs_values[abs_values > 0]
        suggested = float(np.quantile(positive, 0.88))
        return max(suggested, 5e-4)
    suggested = float(np.quantile(abs_values, 0.85))
    return min(max(suggested, max_abs * 0.002), max_abs * 0.25)


def suggest_cube_level_min(cube: CubeData) -> float:
    kind = cube.metadata.get("cube_kind", "generic")
    default_level = suggest_cube_isovalue(cube)
    max_level = suggest_cube_level_max(cube)
    if max_level <= 0:
        return 1e-4
    if kind == "electron_density":
        return max(min(default_level * 0.35, max_level * 0.25), 5e-5)
    if kind == "spin_density":
        return max(min(default_level * 0.3, max_level * 0.25), 1e-4)
    return max(min(default_level * 0.25, max_level * 0.4), 1e-5)


def suggest_cube_level_max(cube: CubeData) -> float:
    kind = cube.metadata.get("cube_kind", "generic")
    values, abs_values = _cube_value_arrays(cube)
    if abs_values.size == 0:
        return 0.2

    max_abs = float(np.max(abs_values))
    if kind == "esp":
        positive = values[values > 1e-9]
        negative = np.abs(values[values < -1e-9])
        candidates: list[float] = []
        if positive.size:
            candidates.append(float(np.quantile(positive, 0.98)))
        if negative.size:
            candidates.append(float(np.quantile(negative, 0.98)))
        if candidates:
            return max(max(candidates), suggest_cube_isovalue(cube) * 2.5, 0.05)
        return max(min(max_abs, 0.5), 0.05)
    if kind == "orbital":
        return max(float(np.quantile(abs_values, 0.995)), suggest_cube_isovalue(cube) * 1.8, 0.03)
    if kind == "electron_density":
        positive = values[values > 1e-12]
        if positive.size == 0:
            return 0.02
        return max(float(np.quantile(positive, 0.985)), suggest_cube_isovalue(cube) * 2.8, 0.01)
    if kind == "spin_density":
        return max(float(np.quantile(abs_values, 0.992)), suggest_cube_isovalue(cube) * 2.4, 0.01)
    if kind == "density":
        return max(float(np.quantile(abs_values, 0.99)), suggest_cube_isovalue(cube) * 2.0, 0.01)
    return max(min(max_abs, float(np.quantile(abs_values, 0.995))), suggest_cube_isovalue(cube) * 2.0, 0.05)


def esp_signed_surface_levels(cube: CubeData, base_level: float) -> dict[str, float]:
    values, _ = _cube_value_arrays(cube)
    positive = values[values > 1e-9]
    negative = np.abs(values[values < -1e-9])
    levels = {
        "positive_level": abs(base_level),
        "negative_level": abs(base_level),
        "positive_cap": abs(base_level),
        "negative_cap": abs(base_level),
    }
    if positive.size:
        levels["positive_level"] = min(abs(base_level), float(np.quantile(positive, 0.94)))
        levels["positive_cap"] = max(
            levels["positive_level"] * 1.02,
            float(np.quantile(positive, 0.985)),
        )
    if negative.size:
        levels["negative_level"] = min(abs(base_level), float(np.quantile(negative, 0.94)))
        levels["negative_cap"] = max(
            levels["negative_level"] * 1.02,
            float(np.quantile(negative, 0.985)),
        )
    return levels


def cube_phase_visibility(cube: CubeData, level: float) -> dict[str, bool]:
    values, _ = _cube_value_arrays(cube)
    if values.size == 0:
        return {"positive": False, "negative": False, "single_phase": False, "empty": True}

    threshold = abs(level)
    positive_visible = bool(np.max(values) >= threshold)
    negative_visible = bool(np.min(values) <= -threshold)
    return {
        "positive": positive_visible,
        "negative": negative_visible,
        "single_phase": positive_visible ^ negative_visible,
        "empty": not positive_visible and not negative_visible,
    }


def cube_grid_is_compatible(left: CubeData, right: CubeData, tolerance: float = 1e-6) -> bool:
    return (
        left.grid_shape == right.grid_shape
        and np.allclose(left.origin_angstrom, right.origin_angstrom, atol=tolerance, rtol=0.0)
        and np.allclose(left.axis_vectors_angstrom, right.axis_vectors_angstrom, atol=tolerance, rtol=0.0)
    )


def find_companion_density_cube_path(cube: CubeData) -> Path | None:
    path_text = cube.metadata.get("path")
    if not path_text:
        return None
    cube_path = Path(path_text)
    if not cube_path.exists():
        return None

    candidates: list[Path] = []
    if cube.metadata.get("cube_kind") == "esp":
        name = cube_path.name
        if name.lower().endswith(".esp.cube"):
            prefix = name[: -len(".esp.cube")]
            candidates.append(cube_path.with_name(f"{prefix}.eldens.cube"))
            if "." in prefix:
                base_prefix = prefix.split(".", 1)[0]
                candidates.append(cube_path.with_name(f"{base_prefix}.eldens.cube"))
        candidates.extend(sorted(cube_path.parent.glob("*.eldens.cube")))

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen or not candidate.exists():
            continue
        seen.add(candidate)
        return candidate
    return None


def _cube_value_arrays(cube: CubeData) -> tuple[np.ndarray, np.ndarray]:
    values = cube.values.ravel()
    values = values[np.isfinite(values)]
    abs_values = np.abs(values)
    abs_values = abs_values[abs_values > 1e-9]
    return values, abs_values


def cube_summary_dataframe(cube: CubeData) -> pd.DataFrame:
    min_value, max_value = cube.value_range
    return pd.DataFrame(
        {
            tr("字段"): [
                tr("文件"),
                tr("原子数"),
                tr("网格"),
                tr("体素数"),
                tr("最小值"),
                tr("最大值"),
                tr("注释 1"),
                tr("注释 2"),
            ],
            tr("值"): [
                cube.source_name,
                cube.atom_count,
                f"{cube.grid_shape[0]} x {cube.grid_shape[1]} x {cube.grid_shape[2]}",
                cube.voxel_count,
                f"{min_value:.6f}",
                f"{max_value:.6f}",
                cube.comments[0],
                cube.comments[1],
            ],
        }
    )


def cube_sample_dataframe(cube: CubeData, stride: int = 2) -> pd.DataFrame:
    xs, ys, zs, values = sample_cube_grid(cube, stride=stride)
    return pd.DataFrame(
        {
            "x": xs,
            "y": ys,
            "z": zs,
            "value": values,
        }
    )


def sample_cube_grid(
    cube: CubeData, stride: int = 1
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    slices = tuple(slice(None, None, stride) for _ in range(3))
    sampled_values = cube.values[slices]
    nx, ny, nz = sampled_values.shape

    i, j, k = np.indices((nx, ny, nz))
    transform = cube.axis_vectors_angstrom * stride
    coords = (
        cube.origin_angstrom
        + i[..., None] * transform[0]
        + j[..., None] * transform[1]
        + k[..., None] * transform[2]
    )
    return (
        coords[..., 0].ravel(),
        coords[..., 1].ravel(),
        coords[..., 2].ravel(),
        sampled_values.ravel(),
    )


def _atomic_symbol(atomic_number: int) -> str:
    if 0 < atomic_number < len(chemical_symbols):
        return chemical_symbols[atomic_number]
    return f"Z{atomic_number}"
