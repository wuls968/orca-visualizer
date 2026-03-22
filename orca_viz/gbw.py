from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any

from .cube import CubeData, parse_cube_file
from .i18n import tr
from .orca_runtime import resolve_orca_tool


DENSITY_LINE_RE = re.compile(r"^\s*\d+:\s+(\S+)\s*$", re.MULTILINE)


@dataclass
class GbwData:
    source_name: str
    file_path: Path
    sidecars: dict[str, Path] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def stem(self) -> str:
        return self.file_path.stem


def load_gbw_file(path: str | Path, source_name: str | None = None) -> GbwData:
    file_path = Path(path).expanduser().resolve()
    sidecars = discover_gbw_sidecars(file_path)
    warnings: list[str] = []
    if "densities" not in sidecars:
        warnings.append(tr("未找到同名 .densities 文件，电子密度/自旋密度/ESP 可能无法生成。"))
    if "densities" in sidecars and "densitiesinfo" not in sidecars:
        warnings.append(tr("已找到 .densities，但缺少 .densitiesinfo；密度或 ESP 生成通常会失败。"))
    property_summary, property_sources = _extract_property_summary(
        property_txt_path=sidecars.get("property_txt"),
        property_json_path=sidecars.get("property_json"),
    )
    return GbwData(
        source_name=source_name or file_path.name,
        file_path=file_path,
        sidecars=sidecars,
        metadata={
            "path": str(file_path),
            "property_summary": property_summary,
            "property_summary_sources": property_sources,
        },
        warnings=warnings,
    )


def discover_gbw_sidecars(path: str | Path) -> dict[str, Path]:
    file_path = Path(path).expanduser().resolve()
    stem = file_path.stem
    parent = file_path.parent
    candidates = {
        "densities": parent / f"{stem}.densities",
        "densitiesinfo": parent / f"{stem}.densitiesinfo",
        "out": parent / f"{stem}.out",
        "log": parent / f"{stem}.log",
        "property_json": parent / f"{stem}.property.json",
        "property_txt": parent / f"{stem}.property.txt",
        "xyz": parent / f"{stem}.xyz",
    }
    return {key: candidate for key, candidate in candidates.items() if candidate.exists()}
def resolve_property_orbital_index(
    property_summary: dict[str, Any],
    requested_orbital: str,
    *,
    operator: int = 0,
) -> int | None:
    derived_summary = dict(property_summary)
    _derive_property_summary(derived_summary)
    orbital_key = requested_orbital.strip().upper()
    if orbital_key not in {"HOMO", "LUMO"}:
        raise ValueError(tr("只支持解析 HOMO 或 LUMO 请求。"))

    specific_key_map = {
        ("HOMO", 0): "alpha_homo_index",
        ("LUMO", 0): "alpha_lumo_index",
        ("HOMO", 1): "beta_homo_index",
        ("LUMO", 1): "beta_lumo_index",
    }
    generic_key_map = {
        "HOMO": "homo_index",
        "LUMO": "lumo_index",
    }
    candidate_keys = [specific_key_map[(orbital_key, operator)]]
    if operator == 0:
        candidate_keys.append(generic_key_map[orbital_key])

    for key in candidate_keys:
        value = derived_summary.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, float) and float(value).is_integer():
            return int(value)
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                continue
    return None


def build_orca_plot_input(
    plot_kind: str,
    grid_intervals: int = 80,
    density_name: str = "",
    orbital_index: int | None = None,
    operator: int = 0,
) -> str:
    if plot_kind == "electron_density":
        return "\n".join(
            [
                "1",
                "2",
                "y",
                "4",
                str(grid_intervals),
                "11",
                "12",
                "",
            ]
        )
    if plot_kind == "spin_density":
        return "\n".join(
            [
                "1",
                "3",
                "y",
                "4",
                str(grid_intervals),
                "11",
                "12",
                "",
            ]
        )
    if plot_kind == "electrostatic_potential":
        if not density_name.strip():
            raise ValueError(tr("ESP 生成需要指定状态密度名，例如 basename.scfp。"))
        return "\n".join(
            [
                "1",
                "43",
                density_name.strip(),
                "4",
                str(grid_intervals),
                "11",
                "12",
                "",
            ]
        )
    if plot_kind == "molecular_orbital":
        if orbital_index is None or orbital_index < 0:
            raise ValueError(tr("分子轨道 cube 生成需要指定非负轨道编号。"))
        if operator not in {0, 1}:
            raise ValueError(tr("operator 只支持 0(alpha/closed shell) 或 1(beta)。"))
        return "\n".join(
            [
                "2",
                str(orbital_index),
                "3",
                str(operator),
                "4",
                str(grid_intervals),
                "11",
                "12",
                "",
            ]
        )
    raise ValueError(tr("不支持的 gbw 绘图类型: {plot_kind}", plot_kind=plot_kind))


def list_available_densities(
    gbw_data: GbwData,
    orca_plot_hint: str = "",
    timeout_seconds: int = 120,
) -> list[str]:
    orca_plot = resolve_orca_tool("orca_plot", path_hint=orca_plot_hint)
    if orca_plot is None:
        raise FileNotFoundError(tr("未找到 orca_plot。"))
    _ensure_density_sidecars(gbw_data)

    with tempfile.TemporaryDirectory(prefix="orca_viz_gbw_scan_") as temp_dir:
        staged_dir = Path(temp_dir)
        staged_gbw = _copy_gbw_bundle(gbw_data, staged_dir)
        completed = subprocess.run(
            [str(orca_plot), staged_gbw.name, "-i"],
            input="9\n12\n",
            capture_output=True,
            text=True,
            cwd=staged_dir,
            timeout=timeout_seconds,
            check=False,
        )
        density_names = DENSITY_LINE_RE.findall(completed.stdout)
        if density_names:
            return density_names
        raise RuntimeError(
            tr(
                "未能从 orca_plot 输出中解析可用 density 列表。\nstdout:\n{stdout}\n\nstderr:\n{stderr}",
                stdout=completed.stdout[-2000:],
                stderr=completed.stderr[-2000:],
            )
        )


def generate_cube_from_gbw(
    gbw_data: GbwData,
    plot_kind: str,
    orca_plot_hint: str = "",
    grid_intervals: int = 80,
    density_name: str = "",
    orbital_index: int | None = None,
    operator: int = 0,
    timeout_seconds: int = 300,
) -> tuple[CubeData, dict[str, Any]]:
    orca_plot = resolve_orca_tool("orca_plot", path_hint=orca_plot_hint)
    if orca_plot is None:
        raise FileNotFoundError(
            tr("未找到 orca_plot。请在软件中填写 ORCA 安装目录或 orca_plot 可执行文件路径。")
        )

    if plot_kind in {"electron_density", "spin_density", "electrostatic_potential"}:
        _ensure_density_sidecars(gbw_data)

    staged_dir = Path(tempfile.mkdtemp(prefix="orca_viz_gbw_"))
    staged_gbw = _copy_gbw_bundle(gbw_data, staged_dir)

    input_text = build_orca_plot_input(
        plot_kind,
        grid_intervals=grid_intervals,
        density_name=density_name,
        orbital_index=orbital_index,
        operator=operator,
    )

    started = __import__("time").time()
    completed = subprocess.run(
        [str(orca_plot), staged_gbw.name, "-i"],
        input=input_text,
        capture_output=True,
        text=True,
        cwd=staged_dir,
        timeout=timeout_seconds,
        check=False,
    )

    cube_path = _find_generated_cube(
        staged_dir,
        gbw_data.stem,
        plot_kind=plot_kind,
        density_name=density_name,
        orbital_index=orbital_index,
        operator=operator,
        started_timestamp=started,
    )
    if cube_path is None:
        raise RuntimeError(
            tr(
                "orca_plot 已运行，但未找到生成的 cube 文件。请检查 ORCA 输出信息。\nstdout:\n{stdout}\n\nstderr:\n{stderr}",
                stdout=completed.stdout[-2000:],
                stderr=completed.stderr[-2000:],
            )
        )

    cube = parse_cube_file(cube_path)
    cube.source_name = cube_path.name
    run_info = {
        "orca_plot": str(orca_plot),
        "workdir": str(staged_dir),
        "gbw_file": staged_gbw.name,
        "generated_cube": str(cube_path),
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
        "plot_kind": plot_kind,
        "grid_intervals": grid_intervals,
        "density_name": density_name,
        "orbital_index": orbital_index,
        "operator": operator,
    }
    return cube, run_info


def _find_generated_cube(
    workdir: Path,
    stem: str,
    plot_kind: str,
    density_name: str,
    orbital_index: int | None,
    operator: int,
    started_timestamp: float,
) -> Path | None:
    expected: list[Path] = []
    if plot_kind == "electron_density":
        expected.append(workdir / f"{stem}.eldens.cube")
    elif plot_kind == "spin_density":
        expected.append(workdir / f"{stem}.spindens.cube")
    elif plot_kind == "electrostatic_potential" and density_name.strip():
        expected.append(workdir / f"{density_name.strip()}.esp.cube")
    elif plot_kind == "molecular_orbital" and orbital_index is not None:
        spin_label = "a" if operator == 0 else "b"
        expected.append(workdir / f"{stem}.mo{orbital_index}{spin_label}.cube")

    for candidate in expected:
        if candidate.exists():
            return candidate

    generated = sorted(
        [
            path
            for path in workdir.glob("*.cube")
            if path.stat().st_mtime >= started_timestamp - 1
        ],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    return generated[0] if generated else None


def _copy_gbw_bundle(gbw_data: GbwData, target_dir: Path) -> Path:
    staged_gbw = target_dir / gbw_data.file_path.name
    shutil.copy2(gbw_data.file_path, staged_gbw)
    for sidecar in gbw_data.sidecars.values():
        shutil.copy2(sidecar, target_dir / sidecar.name)
    return staged_gbw


def _ensure_density_sidecars(gbw_data: GbwData) -> None:
    if "densities" not in gbw_data.sidecars:
        raise FileNotFoundError(
            tr("当前 gbw 缺少同名 .densities 文件，无法生成电子密度、自旋密度或 ESP cube。")
        )
    if "densitiesinfo" not in gbw_data.sidecars:
        raise FileNotFoundError(
            tr("当前 gbw 缺少同名 .densitiesinfo 文件；orca_plot 在生成密度或 ESP cube 时通常需要它。")
        )


def _extract_property_summary(
    *,
    property_txt_path: Path | None,
    property_json_path: Path | None,
) -> tuple[dict[str, Any], list[str]]:
    summary: dict[str, Any] = {}
    sources: list[str] = []
    if property_json_path is not None and property_json_path.exists():
        json_summary = _extract_property_json_summary(property_json_path)
        if json_summary:
            summary.update(json_summary)
            sources.append("property.json")
    if property_txt_path is not None and property_txt_path.exists():
        text_summary = _extract_property_text_summary(property_txt_path)
        for key, value in text_summary.items():
            summary.setdefault(key, value)
        if text_summary:
            sources.append("property.txt")

    _derive_property_summary(summary)
    return summary, sources


def _extract_property_text_summary(path: Path) -> dict[str, Any]:
    raw_text = path.read_text(encoding="utf-8", errors="ignore")
    summary: dict[str, Any] = {}
    if version := _last_regex_match(raw_text, r'&version \[.*?\]\s+"([^"]+)"'):
        summary["version"] = version
    if atom_count := _last_int_match(raw_text, r"&NAtoms \[.*?\]\s+(\d+)"):
        summary["atom_count"] = atom_count
    n_alpha = _last_int_match(raw_text, r"&nAlphaEl \[.*?\]\s+(\d+)")
    n_beta = _last_int_match(raw_text, r"&nBetaEl \[.*?\]\s+(\d+)")
    n_total = _last_int_match(raw_text, r"&nTotalEl \[.*?\]\s+(\d+)")
    final_energy = _last_float_match(raw_text, r"&FinalEnergy \[.*?\]\s+([-\d.Ee+]+)")
    converged = _last_regex_match(raw_text, r"&Converged \[.*?\]\s+(true|false)")

    if n_alpha is not None:
        summary["n_alpha"] = n_alpha
    if n_beta is not None:
        summary["n_beta"] = n_beta
    if n_total is not None:
        summary["n_total"] = n_total
    if final_energy is not None:
        summary["final_energy_hartree"] = final_energy
    if converged is not None:
        summary["converged"] = converged.lower() == "true"
    return summary


def _extract_property_json_summary(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return {}

    summary: dict[str, Any] = {}
    scalar_index = _json_scalar_index(payload)

    field_candidates = {
        "version": ["version", "orca_version"],
        "atom_count": ["natoms", "atom_count"],
        "n_alpha": ["nalphael", "n_alpha", "nalpha"],
        "n_beta": ["nbetael", "n_beta", "nbeta"],
        "n_total": ["ntotalel", "n_total", "ntotal", "nelectrons", "total_electrons"],
        "final_energy_hartree": ["finalenergy", "final_energy", "final_single_point_energy"],
        "converged": ["converged", "is_converged", "calculation_converged"],
        "homo_index": ["homoindex", "homo_index"],
        "lumo_index": ["lumoindex", "lumo_index"],
        "alpha_homo_index": ["alphahomoindex", "alpha_homo_index"],
        "alpha_lumo_index": ["alphalumoindex", "alpha_lumo_index"],
        "beta_homo_index": ["betahomoindex", "beta_homo_index"],
        "beta_lumo_index": ["betalumoindex", "beta_lumo_index"],
        "multiplicity": ["multiplicity", "spin_multiplicity"],
    }
    coercers = {
        "version": _coerce_string,
        "atom_count": _coerce_int,
        "n_alpha": _coerce_int,
        "n_beta": _coerce_int,
        "n_total": _coerce_int,
        "final_energy_hartree": _coerce_float,
        "converged": _coerce_bool,
        "homo_index": _coerce_int,
        "lumo_index": _coerce_int,
        "alpha_homo_index": _coerce_int,
        "alpha_lumo_index": _coerce_int,
        "beta_homo_index": _coerce_int,
        "beta_lumo_index": _coerce_int,
        "multiplicity": _coerce_int,
    }

    for target_key, candidates in field_candidates.items():
        raw_value = _lookup_json_scalar(scalar_index, candidates)
        if raw_value is None:
            continue
        coerced = coercers[target_key](raw_value)
        if coerced is not None:
            summary[target_key] = coerced
    return summary


def _derive_property_summary(summary: dict[str, Any]) -> None:
    n_alpha = _coerce_int(summary.get("n_alpha"))
    n_beta = _coerce_int(summary.get("n_beta"))
    n_total = _coerce_int(summary.get("n_total"))

    if n_alpha is not None:
        summary["n_alpha"] = n_alpha
    if n_beta is not None:
        summary["n_beta"] = n_beta
    if n_total is not None:
        summary["n_total"] = n_total

    if n_alpha is not None and n_beta is not None:
        summary["multiplicity"] = abs(n_alpha - n_beta) + 1
        summary["closed_shell"] = n_alpha == n_beta
        summary.setdefault("alpha_homo_index", n_alpha - 1)
        summary.setdefault("alpha_lumo_index", n_alpha)
        summary.setdefault("beta_homo_index", n_beta - 1)
        summary.setdefault("beta_lumo_index", n_beta)
        if n_alpha == n_beta:
            summary.setdefault("homo_index", n_alpha - 1)
            summary.setdefault("lumo_index", n_alpha)


def _json_scalar_index(payload: Any) -> dict[str, list[Any]]:
    collected: dict[str, list[Any]] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                normalized = _normalize_json_key(key)
                if not isinstance(value, (dict, list)):
                    collected.setdefault(normalized, []).append(value)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return collected


def _lookup_json_scalar(index: dict[str, list[Any]], candidates: list[str]) -> Any | None:
    for candidate in candidates:
        values = index.get(_normalize_json_key(candidate))
        if values:
            return values[-1]
    return None


def _normalize_json_key(raw_key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", raw_key.lower())


def _coerce_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def _coerce_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if float(value).is_integer() else None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(stripped)
        except ValueError:
            try:
                numeric = float(stripped)
            except ValueError:
                return None
            return int(numeric) if numeric.is_integer() else None
    return None


def _coerce_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    return None


def _last_regex_match(raw_text: str, pattern: str) -> str | None:
    matches = re.findall(pattern, raw_text)
    if not matches:
        return None
    return matches[-1]


def _last_int_match(raw_text: str, pattern: str) -> int | None:
    match = _last_regex_match(raw_text, pattern)
    return None if match is None else int(match)


def _last_float_match(raw_text: str, pattern: str) -> float | None:
    match = _last_regex_match(raw_text, pattern)
    return None if match is None else float(match)
