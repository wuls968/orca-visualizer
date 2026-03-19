from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any

from .cube import CubeData, parse_cube_file
from .i18n import tr


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
    property_summary = _extract_property_summary(sidecars.get("property_txt"))
    return GbwData(
        source_name=source_name or file_path.name,
        file_path=file_path,
        sidecars=sidecars,
        metadata={
            "path": str(file_path),
            "property_summary": property_summary,
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
        "property_txt": parent / f"{stem}.property.txt",
        "xyz": parent / f"{stem}.xyz",
    }
    return {key: candidate for key, candidate in candidates.items() if candidate.exists()}


def resolve_orca_plot(path_hint: str = "") -> Path | None:
    hint = path_hint.strip()
    candidates: list[Path] = []

    if hint:
        raw_path = Path(hint).expanduser()
        if raw_path.is_file():
            candidates.append(raw_path)
            candidates.append(raw_path.parent / "orca_plot")
        elif raw_path.is_dir():
            candidates.append(raw_path / "orca_plot")

    which_result = shutil.which("orca_plot")
    if which_result:
        candidates.append(Path(which_result))

    env_orca_home = os.environ.get("ORCA_HOME", "").strip()
    if env_orca_home:
        candidates.append(Path(env_orca_home) / "orca_plot")

    login_env = _load_login_shell_orca_env()
    login_orca_home = login_env.get("ORCA_HOME", "").strip()
    if login_orca_home:
        candidates.append(Path(login_orca_home) / "orca_plot")

    for path_entry in login_env.get("PATH", "").split(":"):
        path_entry = path_entry.strip()
        if path_entry:
            candidates.append(Path(path_entry) / "orca_plot")

    common_dirs = [
        Path.home() / "Library",
        Path.home() / "Applications",
        Path("/Applications"),
        Path("/opt"),
        Path("/usr/local"),
    ]
    for base_dir in common_dirs:
        if not base_dir.exists():
            continue
        for pattern in ["orca*/orca_plot", "orca_*/orca_plot", "*/orca_plot"]:
            candidates.extend(base_dir.glob(pattern))

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    return None


def _load_login_shell_orca_env() -> dict[str, str]:
    command = (
        "zsh -lic 'printf \"ORCA_HOME=%s\\nPATH=%s\\n\" \"$ORCA_HOME\" \"$PATH\"'"
    )
    completed = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return {}

    env_data: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        env_data[key.strip()] = value.strip()
    return env_data


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
    orca_plot = resolve_orca_plot(orca_plot_hint)
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
    orca_plot = resolve_orca_plot(orca_plot_hint)
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


def _extract_property_summary(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}

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

    if n_alpha is not None and n_beta is not None:
        summary["multiplicity"] = abs(n_alpha - n_beta) + 1
        summary["closed_shell"] = n_alpha == n_beta
        summary["alpha_homo_index"] = n_alpha - 1
        summary["alpha_lumo_index"] = n_alpha
        summary["beta_homo_index"] = n_beta - 1
        summary["beta_lumo_index"] = n_beta
        if n_alpha == n_beta:
            summary["homo_index"] = n_alpha - 1
            summary["lumo_index"] = n_alpha

    return summary


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
