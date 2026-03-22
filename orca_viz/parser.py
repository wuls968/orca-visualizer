from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd
from ase import Atoms
from ase.io import read

from .i18n import tr
from .pathway import PathFrame, PathwayResult


ENERGY_RE = re.compile(r"FINAL SINGLE POINT ENERGY\s+(-?\d+\.\d+)")
FREQUENCY_RE = re.compile(r"^\s*(\d+)\s*:\s*(-?\d+\.\d+)\s*cm\*\*-1")
CHARGE_LINE_RE = re.compile(
    r"^\s*(\d+)\s+([A-Za-z]{1,2})\s*(?::)?\s+(-?\d+\.\d+)\s*$"
)
ABSORPTION_STATE_RE = re.compile(
    r"^\s*(\d+)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)"
)
ABSORPTION_TRANSITION_RE = re.compile(
    r"^\s*\S+\s*->\s*\S+\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)"
)
ORBITAL_ENERGY_ROW_RE = re.compile(
    r"^\s*(\d+)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s*$"
)
ORBITAL_ENERGY_HEADERS = (
    "ORBITAL ENERGIES",
    "SPIN UP ORBITALS",
    "SPIN DOWN ORBITALS",
    "ALPHA ORBITAL ENERGIES",
    "BETA ORBITAL ENERGIES",
)
EV_PER_HARTREE = 27.211386245988
FREQUENCY_BLOCK_MARKERS = ("VIBRATIONAL FREQUENCIES",)
NORMAL_MODE_BLOCK_MARKERS = ("NORMAL MODES",)
MULLIKEN_HEADERS = (
    "MULLIKEN ATOMIC CHARGES",
    "MULLIKEN ATOMIC CHARGES AND SPIN POPULATIONS",
)
LOEWDIN_HEADERS = (
    "LOEWDIN ATOMIC CHARGES",
    "LOEWDIN ATOMIC CHARGES AND SPIN POPULATIONS",
)
ABSORPTION_HEADERS = (
    "ABSORPTION SPECTRUM VIA TRANSITION ELECTRIC DIPOLE MOMENTS",
    "ABSORPTION SPECTRUM VIA TRANSITION VELOCITY DIPOLE MOMENTS",
    "ABSORPTION SPECTRUM",
)
IRC_HEADERS = (
    "IRC PATH SUMMARY",
    "INTRINSIC REACTION COORDINATE",
)
NEB_HEADERS = (
    "FINAL NEB ENERGIES",
    "NEB PATH SUMMARY",
    "PATH SUMMARY FOR NEB",
)
IRC_COLUMN_ALIASES = {
    "step": {"step", "point", "index"},
    "coordinate": {"coord", "coordinate", "path", "reaction_coordinate", "s"},
    "energy_hartree": {"energy", "e_eh", "eh", "actual_energy", "energy_eh"},
}
NEB_COLUMN_ALIASES = {
    "image": {"image", "img"},
    "distance_ang": {"distance_ang", "dist_ang"},
    "energy_hartree": {"energy", "e_eh", "eh", "energy_eh"},
    "delta_energy_kcal_mol": {"de_kcal_mol", "deltae_kcal_mol", "de"},
}


@dataclass
class OrcaParseResult:
    source_name: str
    file_type: str
    total_energy_hartree: float | None = None
    energies_hartree: list[float] = field(default_factory=list)
    frequencies_cm1: list[float] = field(default_factory=list)
    normal_modes: dict[int, np.ndarray] = field(default_factory=dict)
    mulliken_charges: pd.DataFrame = field(default_factory=pd.DataFrame)
    loewdin_charges: pd.DataFrame = field(default_factory=pd.DataFrame)
    excited_states: pd.DataFrame = field(default_factory=pd.DataFrame)
    irc_points: pd.DataFrame = field(default_factory=pd.DataFrame)
    neb_points: pd.DataFrame = field(default_factory=pd.DataFrame)
    scan_points: pd.DataFrame = field(default_factory=pd.DataFrame)
    pathways: dict[str, PathwayResult] = field(default_factory=dict)
    thermochemistry: dict[str, float] = field(default_factory=dict)
    transition_state_info: dict[str, Any] = field(default_factory=dict)
    atoms: Atoms | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    raw_text: str = ""

    @property
    def imaginary_frequencies(self) -> list[float]:
        return [value for value in self.frequencies_cm1 if value < 0]

    @property
    def chemical_formula(self) -> str | None:
        return None if self.atoms is None else self.atoms.get_chemical_formula()

    @property
    def atom_count(self) -> int:
        return 0 if self.atoms is None else len(self.atoms)

    def get_pathway(self, kind: str) -> PathwayResult | None:
        return self.pathways.get(kind)


def parse_orca_file(path: str | Path) -> OrcaParseResult:
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    name_lower = file_path.name.lower()
    if suffix == ".xyz":
        raw_text = file_path.read_text(encoding="utf-8", errors="ignore")
        trajectory_result = _parse_xyz_path_file(file_path, raw_text, source_name=file_path.name)
        if trajectory_result is not None:
            return trajectory_result
        atoms = read(file_path)
        return OrcaParseResult(
            source_name=file_path.name,
            file_type="xyz",
            atoms=atoms,
            metadata={"path": str(file_path.resolve())},
        )

    raw_text = file_path.read_text(encoding="utf-8", errors="ignore")
    if name_lower.endswith(".neb.log"):
        return _parse_neb_log_content(raw_text, source_name=file_path.name)
    if suffix == ".interp":
        return _parse_neb_interp_content(raw_text, source_name=file_path.name)

    result = parse_orca_content(raw_text, source_name=file_path.name)
    return _augment_with_path_sidecars(file_path, result)


def parse_orca_content(raw_text: str, source_name: str = "uploaded_file") -> OrcaParseResult:
    result = OrcaParseResult(source_name=source_name, file_type="orca_output", raw_text=raw_text)
    lines = raw_text.splitlines()
    input_keywords = _extract_input_keywords(lines).upper()
    job_markers = _extract_job_markers(raw_text, input_keywords)

    result.energies_hartree = [float(value) for value in ENERGY_RE.findall(raw_text)]
    if result.energies_hartree:
        result.total_energy_hartree = result.energies_hartree[-1]
    else:
        result.warnings.append(tr("未找到 FINAL SINGLE POINT ENERGY，能量曲线可能不可用。"))

    result.frequencies_cm1 = _extract_frequencies(lines)
    result.atoms = _extract_last_cartesian_block(lines)
    result.normal_modes = _extract_normal_modes(lines, result.atom_count, len(result.frequencies_cm1))
    result.mulliken_charges = _extract_charge_block(lines, MULLIKEN_HEADERS)
    result.loewdin_charges = _extract_charge_block(lines, LOEWDIN_HEADERS)
    result.excited_states = _extract_excited_states(lines)
    result.pathways = _extract_pathway_results(lines)
    _sync_legacy_pathway_fields(result)
    result.thermochemistry = _extract_thermochemistry(raw_text)
    result.transition_state_info = _extract_transition_state_info(raw_text, result)
    result.metadata = _extract_metadata(raw_text, lines, result)

    if result.atoms is None:
        result.warnings.append(tr("未找到最终笛卡尔坐标，结构视图不可用。"))
    if not result.frequencies_cm1:
        result.warnings.append(tr("未检测到振动频率数据。"))
    if result.mulliken_charges.empty and result.loewdin_charges.empty:
        result.warnings.append(tr("未检测到原子电荷分布。"))
    if result.excited_states.empty and any(token in job_markers for token in ["TDDFT", "TDA"]):
        result.warnings.append(tr("检测到 TDDFT 关键词，但未解析到吸收光谱表。"))
    for pathway in result.pathways.values():
        result.warnings.extend(pathway.warnings)
    _append_pathway_parse_warnings(result, job_markers)

    return result


def summarize_results(results: list[OrcaParseResult]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for result in results:
        rows.append(
            {
                "file": result.source_name,
                "file_type": result.file_type,
                "formula": result.chemical_formula or "-",
                "atoms": result.atom_count,
                "total_energy_hartree": result.total_energy_hartree,
                "min_frequency_cm^-1": (
                    min(result.frequencies_cm1) if result.frequencies_cm1 else None
                ),
                "imaginary_modes": len(result.imaginary_frequencies),
                "excited_states": len(result.excited_states),
                "irc_points": len(result.irc_points),
                "neb_points": len(result.neb_points),
                "scan_points": len(result.scan_points),
                "charge": result.metadata.get("charge"),
                "multiplicity": result.metadata.get("multiplicity"),
                "termination": result.metadata.get("termination"),
                "is_transition_state": result.transition_state_info.get("is_transition_state"),
                "ts_status": result.transition_state_info.get("status"),
                "lowest_imaginary_cm^-1": result.transition_state_info.get(
                    "lowest_imaginary_frequency_cm^-1"
                ),
                "gibbs_free_energy_hartree": result.thermochemistry.get(
                    "gibbs_free_energy_hartree"
                ),
                "homo_lumo_gap_ev": result.metadata.get("homo_lumo_gap_ev"),
            }
        )
    return pd.DataFrame(rows)


def extract_frontier_orbital_summary(raw_text: str) -> dict[str, Any]:
    return _extract_frontier_orbital_summary_from_lines(raw_text.splitlines())


def _extract_frequencies(lines: list[str]) -> list[float]:
    frequencies: list[float] = []
    in_block = False
    for line in lines:
        if _contains_any_marker(line, FREQUENCY_BLOCK_MARKERS):
            in_block = True
            continue
        if in_block and _contains_any_marker(line, NORMAL_MODE_BLOCK_MARKERS):
            break
        if in_block:
            match = FREQUENCY_RE.match(line)
            if match:
                frequencies.append(float(match.group(2)))
    return frequencies


def _extract_charge_block(lines: list[str], headers: str | tuple[str, ...]) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    in_block = False
    header_values = (headers,) if isinstance(headers, str) else headers

    for line in lines:
        if _contains_any_marker(line, header_values):
            records = []
            in_block = True
            continue
        if not in_block:
            continue
        stripped = line.strip()
        if not stripped:
            if records:
                break
            continue
        if stripped.startswith("Sum of atomic charges"):
            break
        if set(stripped) <= {"-", "."}:
            continue
        match = CHARGE_LINE_RE.match(line)
        if match:
            records.append(
                {
                    "index": int(match.group(1)),
                    "element": match.group(2),
                    "charge": float(match.group(3)),
                }
            )

    return pd.DataFrame(records)


def _extract_normal_modes(
    lines: list[str], atom_count: int, frequency_count: int
) -> dict[int, np.ndarray]:
    start_index = next(
        (i for i, line in enumerate(lines) if _contains_any_marker(line, NORMAL_MODE_BLOCK_MARKERS)),
        None,
    )
    if start_index is None or atom_count <= 0:
        return {}

    expected_rows = atom_count * 3
    if expected_rows <= 0:
        return {}

    mode_columns: dict[int, list[float]] = {}
    current_modes: list[int] = []
    in_matrix = False

    for line in lines[start_index + 1 :]:
        if any(marker in line for marker in ["IR SPECTRUM", "RAMAN SPECTRUM", "THERMOCHEMISTRY"]):
            break
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("These modes") or stripped.startswith("M(") or stripped.startswith("Thus"):
            continue
        if in_matrix and re.match(r"^[A-Za-z]", stripped):
            break

        parts = stripped.split()
        if len(parts) >= 2 and all(re.fullmatch(r"\d+", part) for part in parts):
            current_modes = [int(part) for part in parts]
            for mode in current_modes:
                mode_columns.setdefault(mode, [])
            in_matrix = True
            continue

        if not in_matrix or not current_modes:
            continue

        if len(parts) >= 2 and re.fullmatch(r"\d+", parts[0]):
            try:
                values = [float(part) for part in parts[1:]]
            except ValueError:
                continue
            if len(values) != len(current_modes):
                continue
            for mode, value in zip(current_modes, values):
                mode_columns[mode].append(value)

    parsed_modes: dict[int, np.ndarray] = {}
    max_mode_index = frequency_count - 1 if frequency_count > 0 else None
    for mode, values in mode_columns.items():
        if max_mode_index is not None and mode > max_mode_index:
            continue
        if len(values) != expected_rows:
            continue
        parsed_modes[mode] = np.array(values, dtype=float).reshape(atom_count, 3)

    return parsed_modes


def _extract_excited_states(lines: list[str]) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    in_block = False
    for line in lines:
        if _contains_any_marker(line, ABSORPTION_HEADERS):
            records = []
            in_block = True
            continue
        if not in_block:
            continue
        stripped = line.strip()
        if not stripped and records:
            break
        if not stripped or set(stripped) <= {"-", "."}:
            continue
        match = ABSORPTION_STATE_RE.match(line)
        transition_match = ABSORPTION_TRANSITION_RE.match(line)
        if match:
            state = int(match.group(1))
            energy_cm1 = float(match.group(2))
            wavelength_nm = float(match.group(3))
            oscillator_strength = float(match.group(4))
            energy_ev = energy_cm1 / 8065.54429
        elif transition_match:
            state = len(records) + 1
            energy_ev = float(transition_match.group(1))
            energy_cm1 = float(transition_match.group(2))
            wavelength_nm = float(transition_match.group(3))
            oscillator_strength = float(transition_match.group(4))
        else:
            if records and re.match(r"^[A-Za-z]", stripped):
                break
            continue
        records.append(
            {
                "state": state,
                "energy_cm^-1": energy_cm1,
                "energy_eV": energy_ev,
                "wavelength_nm": wavelength_nm,
                "oscillator_strength": oscillator_strength,
            }
        )
    return pd.DataFrame(records)


def _extract_irc_points(lines: list[str]) -> pd.DataFrame:
    return _extract_irc_pathway(lines).points_df


def _extract_neb_points(lines: list[str]) -> pd.DataFrame:
    return _extract_neb_pathway(lines).points_df


def _extract_scan_points(lines: list[str]) -> pd.DataFrame:
    return _extract_scan_pathway(lines).points_df


def _extract_pathway_results(lines: list[str]) -> dict[str, PathwayResult]:
    candidates = {
        "irc": _extract_irc_pathway(lines),
        "neb": _extract_neb_pathway(lines),
        "scan": _extract_scan_pathway(lines),
    }
    return {
        kind: pathway
        for kind, pathway in candidates.items()
        if pathway.has_points or pathway.has_frames or pathway.warnings or pathway.metadata.get("section_found")
    }


def _extract_irc_pathway(lines: list[str]) -> PathwayResult:
    candidate_blocks = _collect_marked_sections(lines, IRC_HEADERS)
    best_points = pd.DataFrame()
    best_metadata: dict[str, Any] = {"section_found": False}
    warnings: list[str] = []

    for block in candidate_blocks:
        points_df, metadata = _parse_path_table_block(
            block,
            column_aliases=IRC_COLUMN_ALIASES,
            required_fields={"coordinate", "energy_hartree"},
            row_parser=_parse_generic_numeric_row,
        )
        metadata["section_found"] = True
        if len(points_df) > len(best_points):
            best_points = points_df
            best_metadata = metadata

    if best_metadata.get("section_found") and best_points.empty:
        warnings.append(tr("检测到 IRC 路径区块，但未成功解析出有效数据行。"))
    elif best_metadata.get("skipped_rows", 0) > 0:
        warnings.append(
            tr(
                "IRC 路径表部分行未成功解析，已跳过 {count} 行。",
                count=best_metadata["skipped_rows"],
            )
        )

    return PathwayResult(
        kind="irc",
        points_df=best_points,
        metadata=best_metadata,
        warnings=warnings,
    )


def _extract_neb_pathway(lines: list[str]) -> PathwayResult:
    candidate_blocks = _collect_neb_sections(lines)
    best_points = pd.DataFrame()
    best_metadata: dict[str, Any] = {"section_found": False}
    warnings: list[str] = []
    distance_reference_rows: list[dict[str, Any]] = []

    for block in candidate_blocks:
        points_df, metadata = _parse_path_table_block(
            block,
            column_aliases=NEB_COLUMN_ALIASES,
            required_fields={"image", "energy_hartree"},
            row_parser=_parse_neb_table_row,
        )
        metadata["section_found"] = True
        if "distance_ang" in points_df.columns and points_df["distance_ang"].notna().any():
            distance_reference_rows = points_df.to_dict("records")
        if len(points_df) > len(best_points) or (
            len(points_df) == len(best_points)
            and "point_type" in points_df.columns
            and (points_df["point_type"] == "transition_state").any()
        ):
            best_points = points_df
            best_metadata = metadata

    if not best_points.empty and distance_reference_rows:
        merged_rows = best_points.to_dict("records")
        _merge_neb_distance_reference(merged_rows, distance_reference_rows)
        best_points = pd.DataFrame(merged_rows)

    if best_metadata.get("section_found") and best_points.empty:
        warnings.append(tr("检测到 NEB 路径区块，但未成功解析出有效数据行。"))
    elif best_metadata.get("skipped_rows", 0) > 0:
        warnings.append(
            tr(
                "NEB 路径表部分行未成功解析，已跳过 {count} 行。",
                count=best_metadata["skipped_rows"],
            )
        )

    return PathwayResult(
        kind="neb",
        points_df=best_points,
        metadata=best_metadata,
        warnings=warnings,
    )


def _extract_scan_pathway(lines: list[str]) -> PathwayResult:
    section_indices = [
        index
        for index, line in enumerate(lines)
        if "RELAXED SURFACE SCAN RESULTS" in line.upper()
    ]
    best_points = pd.DataFrame()
    metadata: dict[str, Any] = {"section_found": bool(section_indices)}
    warnings: list[str] = []

    for index in section_indices:
        points_df, block_metadata = _parse_scan_surface_block(lines, index)
        if len(points_df) > len(best_points):
            best_points = points_df
            metadata = block_metadata

    if metadata.get("section_found") and best_points.empty:
        warnings.append(tr("检测到 Scan 路径区块，但未成功解析出有效数据行。"))
    elif metadata.get("skipped_rows", 0) > 0:
        warnings.append(
            tr(
                "Scan 路径表部分行未成功解析，已跳过 {count} 行。",
                count=metadata["skipped_rows"],
            )
        )

    return PathwayResult(
        kind="scan",
        points_df=best_points,
        metadata=metadata,
        warnings=warnings,
    )


def _collect_marked_sections(lines: list[str], markers: tuple[str, ...], *, max_lines: int = 80) -> list[list[str]]:
    sections: list[list[str]] = []
    for index, line in enumerate(lines):
        if _contains_any_marker(line, markers):
            sections.append(lines[index + 1 : index + 1 + max_lines])
    return sections


def _collect_neb_sections(lines: list[str]) -> list[list[str]]:
    sections: list[list[str]] = []
    for index, line in enumerate(lines):
        if _is_neb_path_summary_start(lines, index):
            sections.append(lines[index + 1 : index + 1 + 120])
    return sections


def _parse_path_table_block(
    section_lines: list[str],
    *,
    column_aliases: dict[str, set[str]],
    required_fields: set[str],
    row_parser,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    header_mapping: dict[str, int] | None = None
    header_tokens: list[str] = []
    records: list[dict[str, Any]] = []
    skipped_rows = 0
    header_found = False

    for line in section_lines:
        stripped = line.strip()
        if not stripped:
            if records:
                break
            continue
        if _is_visual_separator(stripped):
            continue
        if header_mapping is None:
            for candidate_tokens in _header_token_candidates(stripped):
                candidate_mapping = _map_header_fields(candidate_tokens, column_aliases)
                if required_fields.issubset(candidate_mapping):
                    header_tokens = candidate_tokens
                    header_mapping = candidate_mapping
                    header_found = True
                    break
            continue

        if _looks_like_section_break(stripped):
            if records:
                break
            continue
        if _is_header_repeat(stripped, header_tokens):
            continue

        parsed_row = row_parser(stripped, header_mapping, header_tokens, records)
        if parsed_row is None:
            if _looks_like_data_row(stripped):
                skipped_rows += 1
            if records and _looks_like_section_break(stripped):
                break
            continue
        records.append(parsed_row)

    return pd.DataFrame(records), {
        "header_found": header_found,
        "skipped_rows": skipped_rows,
        "parsed_rows": len(records),
    }


def _parse_generic_numeric_row(
    stripped: str,
    header_mapping: dict[str, int],
    header_tokens: list[str],
    records: list[dict[str, Any]],
) -> dict[str, Any] | None:
    tokens = _split_table_tokens(stripped)
    if len(tokens) < max(header_mapping.values()) + 1:
        return None
    record: dict[str, Any] = {}
    for semantic, column_index in header_mapping.items():
        parsed = _coerce_float_token(tokens[column_index])
        if parsed is None:
            return None
        if semantic in {"step", "image"} and float(parsed).is_integer():
            record[semantic] = int(parsed)
        else:
            record[semantic] = float(parsed)
    return record


def _parse_neb_table_row(
    stripped: str,
    header_mapping: dict[str, int],
    header_tokens: list[str],
    records: list[dict[str, Any]],
) -> dict[str, Any] | None:
    tokens = _split_table_tokens(stripped)
    if not tokens:
        return None

    first_token = tokens[0].upper()
    record: dict[str, Any] = {
        "label": tokens[0],
        "point_type": "transition_state" if first_token == "TS" else "image",
    }

    image_index = header_mapping.get("image")
    if image_index is not None:
        if image_index >= len(tokens):
            return None
        if first_token == "TS":
            previous_image = records[-1].get("image") if records else None
            record["image"] = float(previous_image) + 0.5 if previous_image is not None else 0.5
        else:
            parsed_image = _coerce_float_token(tokens[image_index])
            if parsed_image is None:
                return None
            record["image"] = int(parsed_image) if float(parsed_image).is_integer() else float(parsed_image)

    for semantic, column_index in header_mapping.items():
        if semantic == "image":
            continue
        if column_index >= len(tokens):
            continue
        parsed_value = _coerce_float_token(tokens[column_index])
        if parsed_value is None:
            if semantic == "delta_energy_kcal_mol":
                continue
            return None
        record[semantic] = float(parsed_value)
    if "energy_hartree" not in record:
        return None
    return record


def _parse_scan_surface_block(lines: list[str], start_index: int) -> tuple[pd.DataFrame, dict[str, Any]]:
    records: list[dict[str, Any]] = []
    capture_surface = False
    skipped_rows = 0
    for line in lines[start_index + 1 : start_index + 120]:
        stripped = line.strip()
        upper = stripped.upper()
        if "THE CALCULATED SURFACE USING THE 'ACTUAL ENERGY'" in upper:
            capture_surface = True
            continue
        if capture_surface and "THE CALCULATED SURFACE USING THE SCF ENERGY" in upper:
            break
        if not capture_surface:
            continue
        if not stripped or _is_visual_separator(stripped):
            continue
        numeric_tokens = [_coerce_float_token(token) for token in _split_table_tokens(stripped)]
        numeric_values = [value for value in numeric_tokens if value is not None]
        if len(numeric_values) < 2:
            if _looks_like_data_row(stripped):
                skipped_rows += 1
            if records and _looks_like_section_break(stripped):
                break
            continue
        record: dict[str, Any] = {
            "step": len(records) + 1,
            "coordinate": float(numeric_values[0]),
            "energy_hartree": float(numeric_values[1]),
        }
        if len(numeric_values) >= 3:
            record["surface_value"] = float(numeric_values[2])
        records.append(record)

    return pd.DataFrame(records), {
        "section_found": True,
        "header_found": capture_surface,
        "skipped_rows": skipped_rows,
        "parsed_rows": len(records),
    }


def _map_header_fields(
    header_tokens: list[str],
    column_aliases: dict[str, set[str]],
) -> dict[str, int]:
    mapping: dict[str, int] = {}
    normalized_tokens = [_normalize_header_token(token) for token in header_tokens]
    for semantic, aliases in column_aliases.items():
        for index, token in enumerate(normalized_tokens):
            if token in aliases:
                mapping[semantic] = index
                break
    return mapping


def _split_table_tokens(raw_text: str) -> list[str]:
    compact = raw_text.replace("<= ", "<=")
    if "  " in compact:
        tokens = [token for token in re.split(r"\s{2,}|\t+", compact.strip()) if token]
        if len(tokens) > 1:
            return tokens
    return compact.split()


def _header_token_candidates(raw_text: str) -> list[list[str]]:
    candidates = [_split_table_tokens(raw_text)]
    whitespace_tokens = raw_text.split()
    if whitespace_tokens != candidates[0]:
        candidates.append(whitespace_tokens)
    return candidates


def _normalize_header_token(token: str) -> str:
    cleaned = token.strip().lower()
    cleaned = cleaned.replace("(", "_").replace(")", "")
    cleaned = cleaned.replace("/", "_").replace("-", "_")
    cleaned = cleaned.replace(".", "").replace(":", "")
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned


def _is_visual_separator(stripped: str) -> bool:
    return set(stripped) <= {"-", ".", "*", "="}


def _looks_like_section_break(stripped: str) -> bool:
    upper = stripped.upper()
    if stripped.startswith("The Calculated Surface using the SCF energy"):
        return True
    if any(token in upper for token in ["STATISTICS", "INFORMATION ABOUT", "THERMOCHEMISTRY", "MULLIKEN", "LOEWDIN"]):
        return True
    if _looks_like_data_row(stripped):
        return False
    return bool(re.match(r"^[A-Z][A-Z0-9 /().:-]{6,}$", stripped))


def _is_header_repeat(stripped: str, header_tokens: list[str]) -> bool:
    candidate = _split_table_tokens(stripped)
    if len(candidate) != len(header_tokens):
        return False
    return [_normalize_header_token(token) for token in candidate] == [
        _normalize_header_token(token) for token in header_tokens
    ]


def _looks_like_data_row(stripped: str) -> bool:
    return bool(re.search(r"\d", stripped))


def _coerce_float_token(token: str) -> float | None:
    if token.upper() == "TS":
        return None
    try:
        return float(token)
    except ValueError:
        return None


def _extract_neb_log_points(lines: list[str]) -> pd.DataFrame:
    blocks: list[dict[str, Any]] = []
    current_block: dict[str, Any] = {}

    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()
        if lower.startswith("iteration"):
            if current_block.get("distance") and current_block.get("energy"):
                blocks.append(current_block)
            numbers = re.findall(r"-?\d+", stripped)
            current_block = {
                "iteration": int(numbers[-1]) if numbers else None,
            }
            continue
        if lower.startswith("distance"):
            current_block["distance"] = _extract_float_values(stripped)
            continue
        if lower.startswith("energy"):
            current_block["energy"] = _extract_float_values(stripped)
            continue

    if current_block.get("distance") and current_block.get("energy"):
        blocks.append(current_block)

    if not blocks:
        return pd.DataFrame()

    final_block = blocks[-1]
    distances = final_block.get("distance", [])
    energies = final_block.get("energy", [])
    point_count = min(len(distances), len(energies))
    records = [
        {
            "image": index,
            "distance_bohr": float(distances[index]),
            "energy_hartree": float(energies[index]),
            "label": str(index),
            "point_type": "image",
        }
        for index in range(point_count)
    ]
    return pd.DataFrame(records)


def _extract_neb_interp_points(lines: list[str]) -> tuple[pd.DataFrame, str | None]:
    sections: dict[str, list[tuple[float, float, float]]] = {"images": [], "interp": []}
    current_section: str | None = None

    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()
        if lower.startswith("images:"):
            current_section = "images"
            continue
        if lower.startswith("interp.:"):
            current_section = "interp"
            continue
        if not stripped:
            continue
        if current_section is None:
            continue
        numbers = _extract_float_values(stripped)
        if len(numbers) < 3:
            if sections[current_section] and re.match(r"^[A-Za-z]", stripped):
                current_section = None
            continue
        sections[current_section].append((numbers[0], numbers[1], numbers[2]))

    preferred_section = "interp" if sections["interp"] else "images"
    records = sections[preferred_section]
    if not records:
        return pd.DataFrame(), None

    dataframe = pd.DataFrame(
        [
            {
                "image": index,
                "progress": progress,
                "distance_bohr": distance_bohr,
                "energy_hartree": energy_hartree,
                "label": str(index),
                "point_type": preferred_section,
            }
            for index, (progress, distance_bohr, energy_hartree) in enumerate(records)
        ]
    )
    return dataframe, preferred_section


def _extract_thermochemistry(raw_text: str) -> dict[str, float]:
    patterns = {
        "temperature_k": r"THERMOCHEMISTRY AT\s+(\d+(?:\.\d+)?)K",
        "zero_point_energy_hartree": r"Zero point energy\s+\.\.\.\s+(-?\d+\.\d+)\s+Eh",
        "thermal_energy_hartree": r"Total thermal energy\s+\.\.\.\s+(-?\d+\.\d+)\s+Eh",
        "enthalpy_hartree": r"Total Enthalpy\s+\.\.\.\s+(-?\d+\.\d+)\s+Eh",
        "entropy_term_hartree": r"Final entropy term\s+\.\.\.\s+(-?\d+\.\d+)\s+Eh",
        "entropy_correction_hartree": r"Total entropy correction\s+\.\.\.\s+(-?\d+\.\d+)\s+Eh",
        "gibbs_free_energy_hartree": r"Final Gibbs free energy\s+\.\.\.\s+(-?\d+\.\d+)\s+Eh",
        "g_minus_e_el_hartree": r"G-E\(el\)\s+\.\.\.\s+(-?\d+\.\d+)\s+Eh",
    }
    data: dict[str, float] = {}
    for key, pattern in patterns.items():
        matches = re.findall(pattern, raw_text)
        if matches:
            data[key] = float(matches[-1])
    return data


def _extract_transition_state_info(
    raw_text: str, result: OrcaParseResult
) -> dict[str, Any]:
    info: dict[str, Any] = {}
    input_upper = _extract_input_keywords(raw_text.splitlines()).upper()
    raw_upper = raw_text.upper()

    mode_matches = re.findall(
        r"TS mode is mode number\s+(\d+)\s+with eigenvalue\s+(-?\d+\.\d+)",
        raw_text,
    )
    if mode_matches:
        info["ts_mode_number"] = int(mode_matches[-1][0])
        info["ts_mode_eigenvalue"] = float(mode_matches[-1][1])

    following_mode_match = re.search(r"Following TS mode number\s+\.\.\.\s+(\d+)", raw_text)
    if following_mode_match:
        info["following_ts_mode_number"] = int(following_mode_match.group(1))

    active_atoms_match = re.search(
        r"TS-active-atoms for coordinate setup\.\.\.\s+([0-9 ]+)", raw_text
    )
    if active_atoms_match:
        info["ts_active_atoms"] = [int(value) for value in active_atoms_match.group(1).split()]

    hessian_matches = re.findall(r"Hessian has\s+(\d+)\s+negative eigenvalues", raw_text)
    if hessian_matches:
        info["negative_hessian_eigenvalues"] = int(hessian_matches[-1])

    if result.imaginary_frequencies:
        sorted_imag = sorted(result.imaginary_frequencies)
        info["imaginary_frequency_count"] = len(sorted_imag)
        info["lowest_imaginary_frequency_cm^-1"] = sorted_imag[0]
        info["all_imaginary_frequencies_cm^-1"] = sorted_imag
    else:
        info["imaginary_frequency_count"] = 0

    input_suggests_ts = any(
        token in raw_upper for token in ["TS OPTIMIZATION", "NEB-TS", "TRANSITION STATE"]
    ) or any(token in input_upper for token in ["TS", "NEB-TS"])
    info["input_suggests_ts"] = input_suggests_ts

    imag_count = info["imaginary_frequency_count"]
    if imag_count == 1:
        status = "confirmed_ts"
        diagnosis = tr("检测到且仅检测到一个虚频，符合过渡态的常见判据。")
    elif imag_count > 1:
        status = "multiple_imaginaries"
        diagnosis = tr("检测到多个虚频，这通常说明结构未完全收敛到一阶鞍点。")
    elif input_suggests_ts:
        status = "ts_search_without_imaginary"
        diagnosis = tr("输入或优化过程显示这是 TS 搜索，但频率结果没有给出虚频。")
    else:
        status = "not_ts"
        diagnosis = tr("未检测到明确的过渡态特征。")

    info["is_transition_state"] = input_suggests_ts or imag_count > 0
    info["status"] = status
    info["diagnosis"] = diagnosis
    return info


def _extract_last_cartesian_block(lines: list[str]) -> Atoms | None:
    blocks: list[list[tuple[str, float, float, float]]] = []
    line_count = len(lines)
    i = 0

    while i < line_count:
        if "CARTESIAN COORDINATES (ANGSTROEM)" not in lines[i]:
            i += 1
            continue
        i += 1
        while i < line_count and (
            not lines[i].strip() or set(lines[i].strip()) <= {"-", "."}
        ):
            i += 1

        block: list[tuple[str, float, float, float]] = []
        while i < line_count:
            stripped = lines[i].strip()
            if not stripped:
                break
            parts = stripped.split()
            if len(parts) < 4:
                break
            element = parts[0]
            if not re.fullmatch(r"[A-Za-z]{1,2}", element):
                break
            try:
                x, y, z = map(float, parts[1:4])
            except ValueError:
                break
            block.append((element, x, y, z))
            i += 1

        if block:
            blocks.append(block)
        i += 1

    if not blocks:
        return None

    final_block = blocks[-1]
    symbols = [item[0] for item in final_block]
    positions = [(item[1], item[2], item[3]) for item in final_block]
    return Atoms(symbols=symbols, positions=positions)


def _extract_metadata(
    raw_text: str, lines: list[str], result: OrcaParseResult
) -> dict[str, Any]:
    metadata: dict[str, Any] = {}

    version_match = re.search(r"Program Version\s+([^\s]+)", raw_text)
    if version_match:
        metadata["orca_version"] = version_match.group(1)

    timing_match = re.search(
        r"TOTAL RUN TIME:\s+(\d+)\s+days\s+(\d+)\s+hours\s+(\d+)\s+minutes\s+(\d+)\s+seconds",
        raw_text,
    )
    if timing_match:
        metadata["run_time"] = (
            f"{timing_match.group(1)}d {timing_match.group(2)}h "
            f"{timing_match.group(3)}m {timing_match.group(4)}s"
        )

    if "ORCA TERMINATED NORMALLY" in raw_text:
        metadata["termination"] = "normal"
    elif "ORCA finished by error termination" in raw_text:
        metadata["termination"] = "error"
    else:
        metadata["termination"] = "unknown"

    charge_match = re.search(r"Total Charge\s+Charge\s+\.*\s+(-?\d+)", raw_text)
    mult_match = re.search(r"Multiplicity\s+Mult\s+\.*\s+(\d+)", raw_text)
    if charge_match:
        metadata["charge"] = int(charge_match.group(1))
    if mult_match:
        metadata["multiplicity"] = int(mult_match.group(1))

    input_keywords = _extract_input_keywords(lines)
    if input_keywords:
        metadata["input_keywords"] = input_keywords
    job_markers = sorted(_extract_job_markers(raw_text, input_keywords))
    if job_markers:
        metadata["detected_job_markers"] = job_markers

    metadata.update(_extract_frontier_orbital_summary_from_lines(lines))

    metadata["has_tddft_spectrum"] = not result.excited_states.empty
    metadata["has_irc"] = not result.irc_points.empty
    metadata["has_neb"] = not result.neb_points.empty
    metadata["has_scan"] = not result.scan_points.empty
    if result.pathways:
        metadata["pathways"] = {
            kind: {
                "point_count": pathway.point_count,
                "frame_count": pathway.frame_count,
                "source_files": pathway.source_files,
                "warnings": pathway.warnings,
            }
            for kind, pathway in result.pathways.items()
        }
    metadata["has_thermochemistry"] = bool(result.thermochemistry)
    metadata["has_transition_state_analysis"] = bool(result.transition_state_info)

    return metadata


def _extract_frontier_orbital_summary_from_lines(lines: list[str]) -> dict[str, Any]:
    blocks = _extract_orbital_energy_blocks(lines)
    if not blocks:
        return {}

    summary: dict[str, Any] = {}
    restricted_blocks = [block for block in blocks if block["spin"] == "restricted"]
    alpha_blocks = [block for block in blocks if block["spin"] == "alpha"]
    beta_blocks = [block for block in blocks if block["spin"] == "beta"]

    if restricted_blocks:
        summary.update(_summarize_orbital_block(restricted_blocks[-1]["rows"]))  # type: ignore[index]

    if alpha_blocks:
        summary.update(_prefixed_orbital_summary(_summarize_orbital_block(alpha_blocks[-1]["rows"]), "alpha"))
    if beta_blocks:
        summary.update(_prefixed_orbital_summary(_summarize_orbital_block(beta_blocks[-1]["rows"]), "beta"))

    if not restricted_blocks:
        summary.update(_combine_spin_frontier_summary(summary))

    return summary


def _extract_orbital_energy_blocks(lines: list[str]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    current_spin: str | None = None
    current_rows: list[dict[str, float | int]] = []
    header_found = False

    def flush_block() -> None:
        nonlocal current_spin, current_rows, header_found
        if current_spin is not None and current_rows:
            blocks.append({"spin": current_spin, "rows": current_rows})
        current_spin = None
        current_rows = []
        header_found = False

    for line in lines:
        stripped = line.strip()
        upper = stripped.upper()
        if upper in ORBITAL_ENERGY_HEADERS:
            flush_block()
            current_spin = _orbital_block_spin(upper)
            continue
        if current_spin is None:
            continue
        if not header_found:
            if "NO" in upper and "OCC" in upper and "E(EH)" in upper:
                header_found = True
            continue
        if not stripped:
            if current_rows:
                flush_block()
            continue
        if stripped.startswith("*Only the first"):
            flush_block()
            continue
        if set(stripped) <= {"-", "="}:
            if current_rows:
                flush_block()
            continue
        match = ORBITAL_ENERGY_ROW_RE.match(line)
        if match:
            current_rows.append(
                {
                    "index": int(match.group(1)),
                    "occupation": float(match.group(2)),
                    "energy_hartree": float(match.group(3)),
                    "energy_ev": float(match.group(4)),
                }
            )
            continue
        if current_rows and re.match(r"^[A-Z][A-Z0-9 ()/_-]+$", stripped):
            flush_block()

    flush_block()
    return blocks


def _orbital_block_spin(header: str) -> str:
    if "SPIN UP" in header or "ALPHA" in header:
        return "alpha"
    if "SPIN DOWN" in header or "BETA" in header:
        return "beta"
    return "restricted"


def _summarize_orbital_block(rows: list[dict[str, float | int]]) -> dict[str, Any]:
    occupied = [row for row in rows if float(row["occupation"]) > 1e-6]
    virtual = [row for row in rows if float(row["occupation"]) <= 1e-6]
    if not occupied or not virtual:
        return {}

    homo = occupied[-1]
    lumo = virtual[0]
    gap_hartree = float(lumo["energy_hartree"]) - float(homo["energy_hartree"])
    gap_ev = float(lumo["energy_ev"]) - float(homo["energy_ev"])
    return {
        "homo_index": int(homo["index"]),
        "lumo_index": int(lumo["index"]),
        "homo_energy_hartree": float(homo["energy_hartree"]),
        "homo_energy_ev": float(homo["energy_ev"]),
        "lumo_energy_hartree": float(lumo["energy_hartree"]),
        "lumo_energy_ev": float(lumo["energy_ev"]),
        "homo_lumo_gap_hartree": gap_hartree,
        "homo_lumo_gap_ev": gap_ev,
    }


def _prefixed_orbital_summary(summary: dict[str, Any], prefix: str) -> dict[str, Any]:
    return {f"{prefix}_{key}": value for key, value in summary.items()}


def _combine_spin_frontier_summary(summary: dict[str, Any]) -> dict[str, Any]:
    occupied_candidates: list[tuple[float, str, int, float]] = []
    virtual_candidates: list[tuple[float, str, int, float]] = []
    for spin in ("alpha", "beta"):
        homo_energy_hartree = summary.get(f"{spin}_homo_energy_hartree")
        homo_energy_ev = summary.get(f"{spin}_homo_energy_ev")
        homo_index = summary.get(f"{spin}_homo_index")
        lumo_energy_hartree = summary.get(f"{spin}_lumo_energy_hartree")
        lumo_energy_ev = summary.get(f"{spin}_lumo_energy_ev")
        lumo_index = summary.get(f"{spin}_lumo_index")
        if isinstance(homo_energy_hartree, (int, float)) and isinstance(homo_index, int):
            occupied_candidates.append((float(homo_energy_hartree), spin, homo_index, float(homo_energy_ev)))
        if isinstance(lumo_energy_hartree, (int, float)) and isinstance(lumo_index, int):
            virtual_candidates.append((float(lumo_energy_hartree), spin, lumo_index, float(lumo_energy_ev)))

    if not occupied_candidates or not virtual_candidates:
        return {}

    homo_energy_hartree, homo_spin, homo_index, homo_energy_ev = max(
        occupied_candidates, key=lambda item: item[0]
    )
    lumo_energy_hartree, lumo_spin, lumo_index, lumo_energy_ev = min(
        virtual_candidates, key=lambda item: item[0]
    )
    return {
        "homo_index": homo_index,
        "lumo_index": lumo_index,
        "homo_energy_hartree": homo_energy_hartree,
        "homo_energy_ev": homo_energy_ev,
        "lumo_energy_hartree": lumo_energy_hartree,
        "lumo_energy_ev": lumo_energy_ev,
        "homo_lumo_gap_hartree": lumo_energy_hartree - homo_energy_hartree,
        "homo_lumo_gap_ev": lumo_energy_ev - homo_energy_ev,
        "homo_spin": homo_spin,
        "lumo_spin": lumo_spin,
    }


def _extract_input_keywords(lines: list[str]) -> str:
    for line in lines:
        if line.strip().startswith("!"):
            return line.strip()
    return ""


def _extract_job_markers(raw_text: str, input_keywords: str) -> set[str]:
    search_space = raw_text.upper()
    keyword_space = input_keywords.upper()
    markers: set[str] = set()
    if "ABSORPTION SPECTRUM" in search_space or re.search(r"\bTDDFT\b", keyword_space):
        markers.add("TDDFT")
    if re.search(r"\bTDA\b", keyword_space):
        markers.add("TDA")
    if any(
        token in search_space
        for token in ["%NEB", "NEB OPTIMIZATION", "PATH SUMMARY FOR NEB", ".NEB.LOG", "FINAL NEB ENERGIES"]
    ) or re.search(r"\bNEB(?:-TS|-CI)?\b", keyword_space):
        markers.add("NEB")
    if any(token in search_space for token in ["IRC PATH SUMMARY", "INTRINSIC REACTION COORDINATE", "%IRC"]) or re.search(
        r"\bIRC\b", keyword_space
    ):
        markers.add("IRC")
    if any(token in search_space for token in ["RELAXED SURFACE SCAN", "SCAN RESULTS"]) or re.search(
        r"\bSCAN\b", keyword_space
    ):
        markers.add("SCAN")
    return markers


def _is_neb_path_summary_start(lines: list[str], index: int) -> bool:
    upper = lines[index].upper()
    if any(marker in upper for marker in NEB_HEADERS):
        return True
    if "PATH SUMMARY" not in upper:
        return False
    lookahead = "\n".join(lines[index + 1 : index + 8]).upper()
    return "IMAGE" in lookahead and "E(EH)" in lookahead


def _parse_neb_path_row(
    stripped: str,
    *,
    has_distance_column: bool,
    previous_image: float | int | None,
) -> dict[str, Any] | None:
    tokens = stripped.split()
    if not tokens:
        return None

    first_token = tokens[0].upper()
    numeric_values = _extract_float_values(" ".join(tokens[1:]))
    if first_token == "TS":
        if len(tokens) < 2 or not re.fullmatch(r"-?\d+(?:\.\d+)?", tokens[1]):
            return None
        if len(numeric_values) < 2:
            return None
        image_value = float(previous_image) + 0.5 if previous_image is not None else 0.5
        record: dict[str, Any] = {
            "image": image_value,
            "label": "TS",
            "point_type": "transition_state",
        }
        if has_distance_column and len(numeric_values) >= 3:
            record["distance_ang"] = numeric_values[0]
            record["energy_hartree"] = numeric_values[1]
            record["delta_energy_kcal_mol"] = numeric_values[2]
        else:
            record["energy_hartree"] = numeric_values[0]
            if len(numeric_values) >= 2:
                record["delta_energy_kcal_mol"] = numeric_values[1]
        return record

    if not re.fullmatch(r"-?\d+(?:\.\d+)?", tokens[0]):
        return None
    if has_distance_column and len(numeric_values) < 2:
        return None
    if not has_distance_column and len(numeric_values) < 1:
        return None

    image_value = float(tokens[0]) if "." in tokens[0] else int(tokens[0])
    record = {
        "image": image_value,
        "label": tokens[0],
        "point_type": "image",
    }
    if has_distance_column:
        record["distance_ang"] = numeric_values[0]
        record["energy_hartree"] = numeric_values[1]
        if len(numeric_values) >= 3:
            record["delta_energy_kcal_mol"] = numeric_values[2]
    else:
        record["energy_hartree"] = numeric_values[0]
        if len(numeric_values) >= 2:
            record["delta_energy_kcal_mol"] = numeric_values[1]
    return record


def _extract_float_values(raw_text: str) -> list[float]:
    return [float(value) for value in re.findall(r"-?\d+\.\d+|-?\d+", raw_text)]


def _merge_neb_distance_reference(
    records: list[dict[str, Any]],
    distance_reference_records: list[dict[str, Any]],
) -> None:
    if not records or not distance_reference_records:
        return
    if any("distance_ang" in row for row in records):
        return

    distance_by_label = {
        str(row.get("label")): row.get("distance_ang")
        for row in distance_reference_records
        if "distance_ang" in row and row.get("distance_ang") is not None
    }
    for row in records:
        label = str(row.get("label", ""))
        if label in distance_by_label:
            row["distance_ang"] = distance_by_label[label]

    for index, row in enumerate(records):
        if row.get("point_type") != "transition_state" or row.get("distance_ang") is not None:
            continue
        previous_distance = None
        next_distance = None
        for previous_row in reversed(records[:index]):
            if previous_row.get("distance_ang") is not None:
                previous_distance = float(previous_row["distance_ang"])
                break
        for next_row in records[index + 1 :]:
            if next_row.get("distance_ang") is not None:
                next_distance = float(next_row["distance_ang"])
                break
        if previous_distance is not None and next_distance is not None:
            row["distance_ang"] = (previous_distance + next_distance) / 2.0


def _parse_neb_log_content(raw_text: str, source_name: str) -> OrcaParseResult:
    neb_points = _extract_neb_log_points(raw_text.splitlines())
    warnings: list[str] = []
    if neb_points.empty:
        warnings.append(tr("未能从 `.NEB.log` 文件中解析路径能量。"))
    pathway = PathwayResult(
        kind="neb",
        points_df=neb_points,
        source_files=[source_name],
        metadata={"path_source": "neb_log", "section_found": True},
        warnings=list(warnings),
    )
    result = OrcaParseResult(
        source_name=source_name,
        file_type="neb_log",
        warnings=warnings,
        raw_text=raw_text,
        pathways={"neb": pathway},
        metadata={
            "termination": "unknown",
            "has_neb": not neb_points.empty,
            "detected_job_markers": ["NEB"],
            "path_source": "neb_log",
        },
    )
    _sync_legacy_pathway_fields(result)
    return result


def _parse_neb_interp_content(raw_text: str, source_name: str) -> OrcaParseResult:
    neb_points, interpolation_kind = _extract_neb_interp_points(raw_text.splitlines())
    warnings: list[str] = []
    if neb_points.empty:
        warnings.append(tr("未能从 `.interp` 文件中解析插值路径。"))
    else:
        warnings.append(tr("当前 `.interp` 文件中的能量通常是沿路径的相对能量，不是绝对总能量。"))
    pathway = PathwayResult(
        kind="neb",
        points_df=neb_points,
        source_files=[source_name],
        metadata={
            "path_source": interpolation_kind or "interp",
            "energy_reference": "relative_to_first_image" if not neb_points.empty else None,
            "section_found": True,
        },
        warnings=list(warnings),
    )
    result = OrcaParseResult(
        source_name=source_name,
        file_type="neb_interp",
        warnings=warnings,
        raw_text=raw_text,
        pathways={"neb": pathway},
        metadata={
            "termination": "unknown",
            "has_neb": not neb_points.empty,
            "detected_job_markers": ["NEB"],
            "path_source": interpolation_kind or "interp",
            "energy_reference": "relative_to_first_image" if not neb_points.empty else None,
        },
    )
    _sync_legacy_pathway_fields(result)
    return result


def _augment_with_path_sidecars(file_path: Path, result: OrcaParseResult) -> OrcaParseResult:
    if not result.raw_text:
        return result

    for candidate in _discover_path_sidecar_candidates(file_path, result.raw_text):
        sidecar_pathway = _load_pathway_sidecar(candidate)
        if sidecar_pathway is None:
            continue
        target_kind = sidecar_pathway.kind
        if target_kind == "trajectory" and len(result.pathways) == 1:
            target_kind = next(iter(result.pathways))
            sidecar_pathway = PathwayResult(
                kind=target_kind,
                points_df=sidecar_pathway.points_df,
                frames=sidecar_pathway.frames,
                source_files=sidecar_pathway.source_files,
                metadata=sidecar_pathway.metadata,
                reference_energy_hartree=sidecar_pathway.reference_energy_hartree,
                warnings=sidecar_pathway.warnings,
            )
        existing = result.pathways.get(target_kind)
        if existing is None:
            result.pathways[target_kind] = sidecar_pathway
        else:
            result.pathways[target_kind] = _merge_pathway_result(existing, sidecar_pathway)

    _sync_legacy_pathway_fields(result)
    result.metadata["has_irc"] = not result.irc_points.empty
    result.metadata["has_neb"] = not result.neb_points.empty
    result.metadata["has_scan"] = not result.scan_points.empty
    if result.pathways:
        result.metadata["pathway_sources"] = {
            kind: pathway.source_files for kind, pathway in result.pathways.items()
        }
    return result


def _discover_path_sidecar_candidates(file_path: Path, raw_text: str) -> list[Path]:
    parent = file_path.parent
    candidates: list[Path] = []
    log_matches = re.findall(r"([A-Za-z0-9_.-]+\.NEB\.log)", raw_text, flags=re.IGNORECASE)
    interp_matches = re.findall(r"([A-Za-z0-9_.-]+(?:\.final)?\.interp)", raw_text, flags=re.IGNORECASE)
    xyz_matches = re.findall(r"([A-Za-z0-9_.-]+(?:trj|path|mep|irc|scan|neb)[A-Za-z0-9_.-]*\.xyz)", raw_text, flags=re.IGNORECASE)

    for match in log_matches + interp_matches + xyz_matches:
        candidates.append(parent / match)

    xyz_prefixes: set[str] = {file_path.stem}
    for log_match in log_matches:
        stem = re.sub(r"\.NEB\.log$", "", log_match, flags=re.IGNORECASE)
        xyz_prefixes.add(stem)
        candidates.append(parent / f"{stem}.final.interp")
        candidates.append(parent / f"{stem}.interp")
        candidates.extend(sorted(parent.glob(f"{stem}*.xyz")))

    for xyz_match in xyz_matches:
        xyz_prefixes.add(Path(xyz_match).stem.split(".")[0])

    keyword_patterns = ["*trj*.xyz", "*path*.xyz", "*mep*.xyz", "*irc*.xyz", "*scan*.xyz", "*neb*.xyz"]
    for prefix in xyz_prefixes:
        candidates.extend(sorted(parent.glob(f"{prefix}*.xyz")))
    for pattern in keyword_patterns:
        candidates.extend(sorted(parent.glob(pattern)))

    if not candidates:
        neb_logs = sorted(parent.glob("*.NEB.log"))
        if len(neb_logs) == 1:
            log_path = neb_logs[0]
            prefix = log_path.stem[:-4]
            candidates.extend([log_path, parent / f"{prefix}.final.interp", parent / f"{prefix}.interp"])
            candidates.extend(sorted(parent.glob(f"{prefix}*.xyz")))

    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _parse_xyz_path_file(
    file_path: Path,
    raw_text: str,
    *,
    source_name: str,
) -> OrcaParseResult | None:
    frames = _read_xyz_path_frames(file_path, raw_text)
    if len(frames) <= 1:
        return None
    kind = _infer_path_kind_from_name(file_path.name)
    pathway = _build_pathway_from_frames(
        kind,
        frames,
        source_files=[str(file_path.resolve())],
        metadata={"path_source": "xyz_trajectory", "section_found": True},
    )
    result = OrcaParseResult(
        source_name=source_name,
        file_type="xyz_trajectory",
        atoms=frames[-1].atoms,
        pathways={kind: pathway},
        metadata={
            "path": str(file_path.resolve()),
            "path_source": "xyz_trajectory",
            "frame_count": len(frames),
            "detected_job_markers": [kind.upper()] if kind != "trajectory" else [],
        },
        raw_text=raw_text,
    )
    _sync_legacy_pathway_fields(result)
    return result


def _load_pathway_sidecar(path: Path) -> PathwayResult | None:
    if not path.exists():
        return None
    name_lower = path.name.lower()
    raw_text = path.read_text(encoding="utf-8", errors="ignore")
    if name_lower.endswith(".neb.log"):
        return _parse_neb_log_content(raw_text, source_name=path.name).get_pathway("neb")
    if path.suffix.lower() == ".interp":
        return _parse_neb_interp_content(raw_text, source_name=path.name).get_pathway("neb")
    if path.suffix.lower() == ".xyz":
        frames = _read_xyz_path_frames(path, raw_text)
        if len(frames) <= 1:
            return None
        kind = _infer_path_kind_from_name(path.name)
        return _build_pathway_from_frames(
            kind,
            frames,
            source_files=[str(path.resolve())],
            metadata={"path_source": "xyz_trajectory", "section_found": True},
        )
    return None


def _merge_pathway_result(primary: PathwayResult, supplemental: PathwayResult) -> PathwayResult:
    merged_points = _merge_pathway_points(primary.points_df, supplemental.points_df)
    merged_frames = primary.frames
    if supplemental.has_frames and (
        not primary.has_frames or supplemental.frame_count > primary.frame_count
    ):
        merged_frames = supplemental.frames
    merged = PathwayResult(
        kind=primary.kind,
        points_df=merged_points,
        frames=merged_frames,
        source_files=list(dict.fromkeys(primary.source_files + supplemental.source_files)),
        metadata={**supplemental.metadata, **primary.metadata},
        reference_energy_hartree=(
            primary.reference_energy_hartree
            if primary.reference_energy_hartree is not None
            else supplemental.reference_energy_hartree
        ),
        warnings=list(dict.fromkeys(primary.warnings + supplemental.warnings)),
    )
    return merged


def _merge_pathway_points(primary_df: pd.DataFrame, supplemental_df: pd.DataFrame) -> pd.DataFrame:
    if primary_df.empty:
        return supplemental_df.copy()
    if supplemental_df.empty:
        return primary_df.copy()

    key_columns = [
        column
        for column in ["label", "image", "step", "frame_index", "coordinate", "distance_ang"]
        if column in primary_df.columns and column in supplemental_df.columns
    ]
    if not key_columns:
        return primary_df.copy()

    key_column = key_columns[0]
    primary_indexed = primary_df.copy().set_index(key_column, drop=False)
    supplemental_indexed = supplemental_df.copy().set_index(key_column, drop=False)
    supplemental_indexed = supplemental_indexed.loc[
        supplemental_indexed.index.isin(primary_indexed.index)
    ]
    if supplemental_indexed.empty:
        return primary_df.copy()
    merged = primary_indexed.copy()

    for column in supplemental_indexed.columns:
        if column not in merged.columns:
            merged[column] = supplemental_indexed[column]
        else:
            merged[column] = merged[column].combine_first(supplemental_indexed[column])
    return merged.reset_index(drop=True)


def _read_xyz_path_frames(file_path: Path, raw_text: str) -> list[PathFrame]:
    ase_frames = read(file_path, index=":")
    if isinstance(ase_frames, Atoms):
        ase_frame_list = [ase_frames]
    else:
        ase_frame_list = list(ase_frames)

    comments = _extract_xyz_comments(raw_text)
    frames: list[PathFrame] = []
    total_frames = max(len(ase_frame_list) - 1, 1)
    for index, atoms in enumerate(ase_frame_list):
        comment = comments[index] if index < len(comments) else ""
        energy_match = re.search(r"\bE(?:nergy)?\s*[=:]?\s*(-?\d+\.\d+)", comment, flags=re.IGNORECASE)
        coordinate_match = re.search(
            r"\b(?:coord(?:inate)?|s)\s*[=:]?\s*(-?\d+\.\d+)",
            comment,
            flags=re.IGNORECASE,
        )
        frames.append(
            PathFrame(
                index=index,
                atoms=atoms,
                label=str(index),
                source_file=str(file_path.resolve()),
                energy_hartree=float(energy_match.group(1)) if energy_match else None,
                coordinate=float(coordinate_match.group(1)) if coordinate_match else None,
                progress=index / total_frames if len(ase_frame_list) > 1 else 0.0,
                comment=comment,
            )
        )
    return frames


def _extract_xyz_comments(raw_text: str) -> list[str]:
    comments: list[str] = []
    lines = raw_text.splitlines()
    cursor = 0
    while cursor < len(lines):
        stripped = lines[cursor].strip()
        if not stripped:
            cursor += 1
            continue
        try:
            atom_count = int(stripped)
        except ValueError:
            break
        comment_index = cursor + 1
        comments.append(lines[comment_index] if comment_index < len(lines) else "")
        cursor += atom_count + 2
    return comments


def _build_pathway_from_frames(
    kind: str,
    frames: list[PathFrame],
    *,
    source_files: list[str],
    metadata: dict[str, Any] | None = None,
) -> PathwayResult:
    records: list[dict[str, Any]] = []
    total_frames = max(len(frames) - 1, 1)
    for frame in frames:
        if kind == "neb":
            frame.image = float(frame.index)
        elif kind in {"irc", "scan"}:
            frame.step = frame.index
        if frame.progress is None:
            frame.progress = frame.index / total_frames if len(frames) > 1 else 0.0
        record: dict[str, Any] = {
            "frame_index": frame.index,
            "label": frame.label or str(frame.index),
            "point_type": "frame",
        }
        if kind == "neb":
            record["image"] = frame.index
        elif kind in {"irc", "scan"}:
            record["step"] = frame.index
        if frame.progress is not None:
            record["progress"] = frame.progress
        if frame.energy_hartree is not None:
            record["energy_hartree"] = frame.energy_hartree
        if frame.coordinate is not None:
            record["coordinate"] = frame.coordinate
        records.append(record)
    return PathwayResult(
        kind=kind if kind in {"irc", "neb", "scan"} else "trajectory",
        points_df=pd.DataFrame(records),
        frames=frames,
        source_files=source_files,
        metadata=metadata or {},
    )


def _infer_path_kind_from_name(name: str) -> str:
    lowered = name.lower()
    if "irc" in lowered:
        return "irc"
    if any(token in lowered for token in ["neb", "mep"]):
        return "neb"
    if "scan" in lowered:
        return "scan"
    return "trajectory"


def _sync_legacy_pathway_fields(result: OrcaParseResult) -> None:
    result.irc_points = result.pathways.get("irc", PathwayResult("irc")).points_df.copy()
    result.neb_points = result.pathways.get("neb", PathwayResult("neb")).points_df.copy()
    result.scan_points = result.pathways.get("scan", PathwayResult("scan")).points_df.copy()
    if result.atoms is None:
        for kind in ["irc", "neb", "scan", "trajectory"]:
            pathway = result.pathways.get(kind)
            if pathway and pathway.frames:
                result.atoms = pathway.frames[-1].atoms
                break


def _append_pathway_parse_warnings(result: OrcaParseResult, job_markers: set[str]) -> None:
    kind_labels = {"irc": "IRC", "neb": "NEB", "scan": "Scan"}
    for kind, label in kind_labels.items():
        pathway = result.pathways.get(kind)
        if pathway and pathway.has_points:
            continue
        if label.upper() not in {marker.upper() for marker in job_markers}:
            continue
        if pathway and pathway.metadata.get("section_found") and not pathway.metadata.get("header_found", True):
            result.warnings.append(tr("检测到 {label} 路径区块，但未识别到可用表头。", label=label))
        elif pathway and pathway.metadata.get("section_found"):
            result.warnings.append(tr("检测到 {label} 路径区块，但未成功解析出有效数据行。", label=label))
        else:
            result.warnings.append(tr("检测到 {label} 相关文本，但未找到可解析的路径区块。", label=label))


def _contains_any_marker(line: str, markers: tuple[str, ...]) -> bool:
    upper = line.upper()
    return any(marker in upper for marker in markers)
