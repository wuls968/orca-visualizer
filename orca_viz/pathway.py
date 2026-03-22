from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import pandas as pd
from ase import Atoms


HARTREE_TO_KCAL_MOL = 627.509474
PathwayKind = Literal["irc", "neb", "scan", "trajectory"]
EnergyReferenceMode = Literal["absolute", "minimum", "first", "last", "selected"]


@dataclass
class PathFrame:
    index: int
    atoms: Atoms
    label: str | None = None
    source_file: str | None = None
    energy_hartree: float | None = None
    coordinate: float | None = None
    image: float | None = None
    step: int | None = None
    distance_ang: float | None = None
    distance_bohr: float | None = None
    progress: float | None = None
    branch_id: str | None = None
    comment: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "frame_index": self.index,
            "label": self.label or str(self.index),
            "energy_hartree": self.energy_hartree,
            "coordinate": self.coordinate,
            "image": self.image,
            "step": self.step,
            "distance_ang": self.distance_ang,
            "distance_bohr": self.distance_bohr,
            "progress": self.progress,
            "branch_id": self.branch_id,
            "source_file": self.source_file or "",
            "comment": self.comment,
        }


@dataclass
class PathwayResult:
    kind: PathwayKind
    points_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    frames: list[PathFrame] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    reference_energy_hartree: float | None = None
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.points_df = normalize_path_points(self.points_df, self.kind)

    @property
    def has_points(self) -> bool:
        return not self.points_df.empty

    @property
    def has_frames(self) -> bool:
        return bool(self.frames)

    @property
    def point_count(self) -> int:
        return len(self.points_df)

    @property
    def frame_count(self) -> int:
        return len(self.frames)

    @property
    def x_column(self) -> str:
        return default_path_x_column(self.kind, self.points_df)

    def frame_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([frame.to_record() for frame in self.frames])


def normalize_path_points(dataframe: pd.DataFrame, kind: str) -> pd.DataFrame:
    if dataframe.empty:
        return dataframe.copy()

    normalized = dataframe.copy()
    for column in [
        "step",
        "image",
        "frame_index",
        "coordinate",
        "distance_ang",
        "distance_bohr",
        "progress",
        "energy_hartree",
        "delta_energy_kcal_mol",
    ]:
        if column in normalized.columns:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    if "point_type" not in normalized.columns:
        normalized["point_type"] = "image" if kind == "neb" else "point"
    if "label" not in normalized.columns:
        label_source = None
        for candidate in ["image", "step", "frame_index", "coordinate"]:
            if candidate in normalized.columns:
                label_source = candidate
                break
        if label_source:
            normalized["label"] = normalized[label_source].map(_label_value)
        else:
            normalized["label"] = [str(index) for index in range(len(normalized))]

    if kind == "irc" and "coordinate" in normalized.columns and "branch_id" not in normalized.columns:
        coordinates = normalized["coordinate"].dropna()
        if not coordinates.empty and coordinates.min() < 0 < coordinates.max():
            branch_ids: list[str] = []
            for value in normalized["coordinate"]:
                if pd.isna(value):
                    branch_ids.append("unknown")
                elif value < 0:
                    branch_ids.append("backward")
                elif value > 0:
                    branch_ids.append("forward")
                else:
                    branch_ids.append("transition")
            normalized["branch_id"] = branch_ids
    return normalized


def default_path_x_column(kind: str, dataframe: pd.DataFrame) -> str:
    priorities = {
        "irc": ["coordinate", "step", "frame_index"],
        "neb": ["distance_ang", "distance_bohr", "progress", "image", "frame_index"],
        "scan": ["coordinate", "step", "frame_index"],
        "trajectory": ["frame_index", "coordinate", "progress"],
    }
    for candidate in priorities.get(kind, []):
        if candidate in dataframe.columns and dataframe[candidate].notna().any():
            return candidate
    for fallback in ["image", "step", "frame_index"]:
        if fallback in dataframe.columns:
            return fallback
    return dataframe.columns[0] if not dataframe.empty else "index"


def build_path_display_dataframe(
    pathway: PathwayResult,
    *,
    reference_mode: EnergyReferenceMode = "minimum",
    reference_selector: str | int | float | None = None,
    energy_col: str = "energy_hartree",
) -> pd.DataFrame:
    if pathway.points_df.empty:
        return pathway.points_df.copy()

    display_df = pathway.points_df.copy()
    x_col = pathway.x_column
    if x_col in display_df.columns:
        display_df = display_df.sort_values(x_col, kind="mergesort").reset_index(drop=True)
    else:
        display_df = display_df.reset_index(drop=True)

    if energy_col not in display_df.columns:
        return display_df

    display_df["absolute_energy_hartree"] = pd.to_numeric(display_df[energy_col], errors="coerce")
    reference_energy = resolve_reference_energy(
        display_df,
        energy_col=energy_col,
        reference_mode=reference_mode,
        reference_selector=reference_selector,
        selector_col=_preferred_selector_column(display_df),
    )
    display_df["reference_energy_hartree"] = reference_energy
    display_df["relative_energy_hartree"] = display_df["absolute_energy_hartree"] - reference_energy
    display_df["relative_energy_kcal_mol"] = display_df["relative_energy_hartree"] * HARTREE_TO_KCAL_MOL
    return display_df


def resolve_reference_energy(
    dataframe: pd.DataFrame,
    *,
    energy_col: str = "energy_hartree",
    reference_mode: EnergyReferenceMode = "minimum",
    reference_selector: str | int | float | None = None,
    selector_col: str | None = None,
) -> float:
    energies = pd.to_numeric(dataframe[energy_col], errors="coerce").dropna()
    if energies.empty:
        return 0.0
    if reference_mode == "first":
        return float(energies.iloc[0])
    if reference_mode == "last":
        return float(energies.iloc[-1])
    if reference_mode == "selected":
        matched = _match_reference_row(dataframe, selector_col=selector_col, selector=reference_selector, energy_col=energy_col)
        if matched is not None:
            return matched
    return float(energies.min())


def analyze_pathway(pathway: PathwayResult) -> dict[str, Any]:
    analysis: dict[str, Any] = {
        "kind": pathway.kind,
        "point_count": pathway.point_count,
        "frame_count": pathway.frame_count,
        "warnings": list(pathway.warnings),
    }
    if pathway.points_df.empty or "energy_hartree" not in pathway.points_df.columns:
        return analysis

    plot_df = build_path_display_dataframe(pathway, reference_mode="minimum")
    x_col = pathway.x_column
    energies = plot_df["absolute_energy_hartree"]
    if energies.dropna().empty:
        return analysis

    highest_idx = int(energies.idxmax())
    lowest_idx = int(energies.idxmin())
    highest_row = plot_df.loc[highest_idx]
    lowest_row = plot_df.loc[lowest_idx]
    first_row = plot_df.iloc[0]
    last_row = plot_df.iloc[-1]

    analysis.update(
        {
            "x_column": x_col,
            "minimum_energy_hartree": float(lowest_row["absolute_energy_hartree"]),
            "maximum_energy_hartree": float(highest_row["absolute_energy_hartree"]),
            "first_energy_hartree": float(first_row["absolute_energy_hartree"]),
            "last_energy_hartree": float(last_row["absolute_energy_hartree"]),
            "highest_point_label": str(highest_row.get("label", highest_idx)),
            "highest_point_position": highest_row.get(x_col),
            "highest_relative_energy_kcal_mol": float(highest_row["relative_energy_kcal_mol"]),
            "forward_barrier_kcal_mol": float(
                (highest_row["absolute_energy_hartree"] - first_row["absolute_energy_hartree"])
                * HARTREE_TO_KCAL_MOL
            ),
            "reverse_barrier_kcal_mol": float(
                (highest_row["absolute_energy_hartree"] - last_row["absolute_energy_hartree"])
                * HARTREE_TO_KCAL_MOL
            ),
            "anomalies": detect_path_anomalies(plot_df, x_col=x_col),
        }
    )
    if "branch_id" in plot_df.columns:
        analysis["branch_ids"] = [
            value for value in plot_df["branch_id"].dropna().astype(str).unique().tolist() if value
        ]
    return analysis


def detect_path_anomalies(dataframe: pd.DataFrame, *, x_col: str) -> list[str]:
    anomalies: list[str] = []
    if x_col in dataframe.columns:
        x_values = pd.to_numeric(dataframe[x_col], errors="coerce")
        if x_values.duplicated().any():
            anomalies.append("duplicate_x")
        if not x_values.dropna().is_monotonic_increasing:
            anomalies.append("x_not_monotonic")

    for candidate in ["image", "step"]:
        if candidate not in dataframe.columns:
            continue
        values = pd.to_numeric(dataframe[candidate], errors="coerce").dropna()
        integer_values = values[values.map(lambda value: float(value).is_integer())]
        if integer_values.empty:
            continue
        ordered = sorted({int(value) for value in integer_values})
        if ordered and len(ordered) > 1:
            expected = list(range(ordered[0], ordered[-1] + 1))
            if ordered != expected:
                anomalies.append(f"{candidate}_gap")
        break
    return anomalies


def build_frame_point_mapping(pathway: PathwayResult) -> tuple[list[int | None], dict[int, int]]:
    if not pathway.frames:
        return [], {}
    if pathway.points_df.empty:
        return [None] * len(pathway.frames), {}

    points_df = normalize_path_points(pathway.points_df, pathway.kind)
    point_count = len(points_df)
    frame_to_point: list[int | None] = [None] * len(pathway.frames)
    point_to_frame: dict[int, int] = {}

    exact_frame_index = _exact_frame_index_mapping(points_df)
    if exact_frame_index:
        point_positions = sorted(exact_frame_index)
        point_to_exact_frame = {point_index: frame_index for frame_index, point_index in exact_frame_index.items()}
        for frame in pathway.frames:
            nearest = min(point_positions, key=lambda value: abs(value - frame.index))
            frame_to_point[frame.index] = exact_frame_index[nearest]
        for point_index, frame_index in point_to_exact_frame.items():
            point_to_frame[int(point_index)] = int(frame_index)
        return frame_to_point, point_to_frame

    points_coordinate = pd.to_numeric(points_df["coordinate"], errors="coerce") if "coordinate" in points_df.columns else None
    frame_coordinates = [frame.coordinate for frame in pathway.frames]
    if (
        points_coordinate is not None
        and points_coordinate.notna().any()
        and all(value is not None for value in frame_coordinates)
    ):
        point_values = points_coordinate.astype(float).tolist()
        for frame in pathway.frames:
            assert frame.coordinate is not None
            frame_to_point[frame.index] = min(
                range(point_count),
                key=lambda point_index: abs(point_values[point_index] - float(frame.coordinate)),
            )
        for point_index, coordinate in enumerate(point_values):
            point_to_frame[point_index] = min(
                range(len(pathway.frames)),
                key=lambda frame_index: abs(float(frame_coordinates[frame_index]) - coordinate),  # type: ignore[arg-type]
            )
        return frame_to_point, point_to_frame

    point_progress = _point_progress_series(points_df, pathway.kind)
    if point_progress is not None:
        point_values = point_progress.tolist()
        frame_progress = _frame_progress_values(pathway)
        for frame in pathway.frames:
            progress = frame_progress[frame.index]
            frame_to_point[frame.index] = min(
                range(point_count),
                key=lambda point_index: abs(point_values[point_index] - progress),
            )
        for point_index, progress in enumerate(point_values):
            point_to_frame[point_index] = min(
                range(len(pathway.frames)),
                key=lambda frame_index: abs(frame_progress[frame_index] - progress),
            )
        return frame_to_point, point_to_frame

    if point_count == len(pathway.frames):
        mapping = list(range(point_count))
        return mapping, {index: index for index in range(point_count)}

    for frame in pathway.frames:
        point_index = _nearest_normalized_index(frame.index, len(pathway.frames), point_count)
        frame_to_point[frame.index] = point_index
    for point_index in range(point_count):
        point_to_frame[point_index] = _nearest_normalized_index(point_index, point_count, len(pathway.frames))
    return frame_to_point, point_to_frame


def build_xyz_trajectory_text(pathway: PathwayResult) -> str:
    blocks: list[str] = []
    for frame in pathway.frames:
        atoms = frame.atoms
        blocks.append(str(len(atoms)))
        comment_parts = [frame.label or f"Frame {frame.index}"]
        if frame.energy_hartree is not None:
            comment_parts.append(f"E={frame.energy_hartree:.8f}")
        if frame.coordinate is not None:
            comment_parts.append(f"coord={frame.coordinate:.6f}")
        if frame.progress is not None:
            comment_parts.append(f"progress={frame.progress:.6f}")
        blocks.append(" ".join(comment_parts))
        for symbol, position in zip(atoms.get_chemical_symbols(), atoms.get_positions(), strict=False):
            blocks.append(f"{symbol} {position[0]:.8f} {position[1]:.8f} {position[2]:.8f}")
    return "\n".join(blocks)


def _preferred_selector_column(dataframe: pd.DataFrame) -> str | None:
    for candidate in ["label", "image", "step", "frame_index"]:
        if candidate in dataframe.columns:
            return candidate
    return None


def _match_reference_row(
    dataframe: pd.DataFrame,
    *,
    selector_col: str | None,
    selector: str | int | float | None,
    energy_col: str,
) -> float | None:
    if selector_col is None or selector is None or selector_col not in dataframe.columns:
        return None
    selector_series = dataframe[selector_col].astype(str)
    matched_rows = dataframe.loc[selector_series == str(selector)]
    if matched_rows.empty:
        return None
    energy_value = pd.to_numeric(matched_rows.iloc[0][energy_col], errors="coerce")
    if pd.isna(energy_value):
        return None
    return float(energy_value)


def _label_value(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _exact_frame_index_mapping(dataframe: pd.DataFrame) -> dict[int, int]:
    if "frame_index" not in dataframe.columns:
        return {}
    mapping: dict[int, int] = {}
    frame_indices = pd.to_numeric(dataframe["frame_index"], errors="coerce")
    for point_index, value in enumerate(frame_indices):
        if pd.isna(value):
            continue
        numeric = float(value)
        if numeric.is_integer():
            mapping[int(numeric)] = point_index
    return mapping


def _point_progress_series(dataframe: pd.DataFrame, kind: str) -> pd.Series | None:
    if "progress" in dataframe.columns:
        progress = pd.to_numeric(dataframe["progress"], errors="coerce")
        if progress.notna().any():
            return progress.astype(float)
    if "distance_ang" in dataframe.columns:
        distance = pd.to_numeric(dataframe["distance_ang"], errors="coerce")
        if distance.notna().any():
            return _normalize_series(distance)
    if "distance_bohr" in dataframe.columns:
        distance = pd.to_numeric(dataframe["distance_bohr"], errors="coerce")
        if distance.notna().any():
            return _normalize_series(distance)
    if "coordinate" in dataframe.columns and kind in {"irc", "scan"}:
        coordinate = pd.to_numeric(dataframe["coordinate"], errors="coerce")
        if coordinate.notna().any():
            return _normalize_series(coordinate)
    if "image" in dataframe.columns:
        image = pd.to_numeric(dataframe["image"], errors="coerce")
        if image.notna().any():
            return _normalize_series(image)
    if "step" in dataframe.columns:
        step = pd.to_numeric(dataframe["step"], errors="coerce")
        if step.notna().any():
            return _normalize_series(step)
    return None


def _normalize_series(series: pd.Series) -> pd.Series:
    valid = series.dropna()
    if valid.empty:
        return series
    minimum = float(valid.min())
    maximum = float(valid.max())
    if maximum - minimum < 1e-12:
        return pd.Series([0.0 if pd.notna(value) else pd.NA for value in series], index=series.index, dtype="float64")
    return (series - minimum) / (maximum - minimum)


def _frame_progress_values(pathway: PathwayResult) -> list[float]:
    explicit_progress = [frame.progress for frame in pathway.frames]
    if all(value is not None for value in explicit_progress):
        return [float(value) for value in explicit_progress if value is not None]
    frame_count = max(len(pathway.frames) - 1, 1)
    return [frame.index / frame_count for frame in pathway.frames]


def _nearest_normalized_index(index: int, source_count: int, target_count: int) -> int:
    if target_count <= 1:
        return 0
    if source_count <= 1:
        return 0
    normalized = index / max(source_count - 1, 1)
    return int(round(normalized * (target_count - 1)))
