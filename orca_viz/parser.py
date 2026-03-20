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


def parse_orca_file(path: str | Path) -> OrcaParseResult:
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix == ".xyz":
        atoms = read(file_path)
        return OrcaParseResult(
            source_name=file_path.name,
            file_type="xyz",
            atoms=atoms,
            metadata={"path": str(file_path.resolve())},
        )

    raw_text = file_path.read_text(encoding="utf-8", errors="ignore")
    return parse_orca_content(raw_text, source_name=file_path.name)


def parse_orca_content(raw_text: str, source_name: str = "uploaded_file") -> OrcaParseResult:
    result = OrcaParseResult(source_name=source_name, file_type="orca_output", raw_text=raw_text)
    lines = raw_text.splitlines()
    input_keywords = _extract_input_keywords(lines).upper()

    result.energies_hartree = [float(value) for value in ENERGY_RE.findall(raw_text)]
    if result.energies_hartree:
        result.total_energy_hartree = result.energies_hartree[-1]
    else:
        result.warnings.append(tr("未找到 FINAL SINGLE POINT ENERGY，能量曲线可能不可用。"))

    result.frequencies_cm1 = _extract_frequencies(lines)
    result.atoms = _extract_last_cartesian_block(lines)
    result.normal_modes = _extract_normal_modes(lines, result.atom_count, len(result.frequencies_cm1))
    result.mulliken_charges = _extract_charge_block(lines, "MULLIKEN ATOMIC CHARGES")
    result.loewdin_charges = _extract_charge_block(lines, "LOEWDIN ATOMIC CHARGES")
    result.excited_states = _extract_excited_states(lines)
    result.irc_points = _extract_irc_points(lines)
    result.neb_points = _extract_neb_points(lines)
    result.scan_points = _extract_scan_points(lines)
    result.thermochemistry = _extract_thermochemistry(raw_text)
    result.transition_state_info = _extract_transition_state_info(raw_text, result)
    result.metadata = _extract_metadata(raw_text, lines, result)

    if result.atoms is None:
        result.warnings.append(tr("未找到最终笛卡尔坐标，结构视图不可用。"))
    if not result.frequencies_cm1:
        result.warnings.append(tr("未检测到振动频率数据。"))
    if result.mulliken_charges.empty and result.loewdin_charges.empty:
        result.warnings.append(tr("未检测到原子电荷分布。"))
    if result.excited_states.empty and any(token in input_keywords for token in ["TDDFT", "TDA"]):
        result.warnings.append(tr("检测到 TDDFT 关键词，但未解析到吸收光谱表。"))
    if result.irc_points.empty and "IRC" in input_keywords:
        result.warnings.append(tr("检测到 IRC 相关文本，但未找到可用路径表。"))
    if result.neb_points.empty and "NEB" in input_keywords:
        result.warnings.append(tr("检测到 NEB 相关文本，但未找到可用路径表。"))
    if result.scan_points.empty and "SCAN" in input_keywords:
        result.warnings.append(tr("检测到 Scan 关键词，但未找到可用扫描路径表。"))

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
            }
        )
    return pd.DataFrame(rows)


def _extract_frequencies(lines: list[str]) -> list[float]:
    frequencies: list[float] = []
    in_block = False
    for line in lines:
        if "VIBRATIONAL FREQUENCIES" in line:
            in_block = True
            continue
        if in_block and line.strip().startswith("NORMAL MODES"):
            break
        if in_block:
            match = FREQUENCY_RE.match(line)
            if match:
                frequencies.append(float(match.group(2)))
    return frequencies


def _extract_charge_block(lines: list[str], header: str) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    in_block = False

    for line in lines:
        if header in line:
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
    start_index = next((i for i, line in enumerate(lines) if "NORMAL MODES" in line), None)
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
        if "ABSORPTION SPECTRUM VIA TRANSITION ELECTRIC DIPOLE MOMENTS" in line:
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
    records: list[dict[str, Any]] = []
    in_block = False
    for line in lines:
        if "IRC PATH SUMMARY" in line or "INTRINSIC REACTION COORDINATE" in line:
            in_block = True
            continue
        if not in_block:
            continue
        stripped = line.strip()
        if not stripped and records:
            break
        if not stripped or set(stripped) <= {"-", "."} or "Step" in stripped:
            continue
        numbers = re.findall(r"-?\d+\.\d+|-?\d+", stripped)
        if len(numbers) < 3:
            if records and re.match(r"^[A-Za-z]", stripped):
                break
            continue
        try:
            step = int(float(numbers[0]))
            coordinate = float(numbers[1])
            energy = float(numbers[2])
        except ValueError:
            continue
        records.append(
            {
                "step": step,
                "coordinate": coordinate,
                "energy_hartree": energy,
            }
        )
    return pd.DataFrame(records)


def _extract_neb_points(lines: list[str]) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    in_block = False
    for line in lines:
        upper = line.upper()
        if "FINAL NEB ENERGIES" in upper or "NEB PATH SUMMARY" in upper:
            in_block = True
            continue
        if not in_block:
            continue
        stripped = line.strip()
        if not stripped and records:
            break
        if not stripped or set(stripped) <= {"-", "."}:
            continue
        numbers = re.findall(r"-?\d+\.\d+|-?\d+", stripped)
        if len(numbers) < 2:
            if records and re.match(r"^[A-Za-z]", stripped):
                break
            continue
        image_match = re.search(r"(\d+)", stripped)
        if image_match is None:
            continue
        try:
            image_index = int(image_match.group(1))
            energy = float(numbers[-1])
        except ValueError:
            continue
        records.append({"image": image_index, "energy_hartree": energy})
    return pd.DataFrame(records)


def _extract_scan_points(lines: list[str]) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    in_block = False
    capture_surface = False
    for line in lines:
        upper = line.upper()
        stripped = line.strip()
        if "RELAXED SURFACE SCAN RESULTS" in upper:
            in_block = True
            capture_surface = False
            continue
        if not in_block:
            continue
        if stripped.startswith("The Calculated Surface using the 'Actual Energy'"):
            capture_surface = True
            continue
        if capture_surface and stripped.startswith("The Calculated Surface using the SCF energy"):
            break
        if not capture_surface:
            continue
        if not stripped or set(stripped) <= {"-", "."}:
            continue
        numbers = re.findall(r"-?\d+\.\d+|-?\d+", stripped)
        if len(numbers) < 2:
            if records and re.match(r"^[A-Za-z]", stripped):
                break
            continue
        try:
            coordinate = float(numbers[0])
            energy = float(numbers[1])
        except ValueError:
            continue
        records.append(
            {
                "step": len(records) + 1,
                "coordinate": coordinate,
                "energy_hartree": energy,
            }
        )
    return pd.DataFrame(records)


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

    metadata["has_tddft_spectrum"] = not result.excited_states.empty
    metadata["has_irc"] = not result.irc_points.empty
    metadata["has_neb"] = not result.neb_points.empty
    metadata["has_scan"] = not result.scan_points.empty
    metadata["has_thermochemistry"] = bool(result.thermochemistry)
    metadata["has_transition_state_analysis"] = bool(result.transition_state_info)

    return metadata


def _extract_input_keywords(lines: list[str]) -> str:
    for line in lines:
        if line.strip().startswith("!"):
            return line.strip()
    return ""
