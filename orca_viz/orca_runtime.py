from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib.metadata
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class OrcaToolSpec:
    key: str
    executable: str
    category: str
    purpose: str
    required: bool = False


@dataclass(frozen=True)
class OrcaToolStatus:
    key: str
    executable: str
    category: str
    purpose: str
    required: bool
    available: bool
    path: str | None


@dataclass(frozen=True)
class OrcaEnvironmentReport:
    platform: str
    python_executable: str
    python_version: str
    orca_home: str | None
    detected_orca_version: str | None
    env_orca_home: str | None
    path_hint: str | None
    tools: list[OrcaToolStatus]
    python_packages: dict[str, str]

    @property
    def available_tool_count(self) -> int:
        return sum(1 for tool in self.tools if tool.available)

    @property
    def required_tool_count(self) -> int:
        return sum(1 for tool in self.tools if tool.required)

    @property
    def available_required_tool_count(self) -> int:
        return sum(1 for tool in self.tools if tool.required and tool.available)


ORCA_TOOL_SPECS: list[OrcaToolSpec] = [
    OrcaToolSpec("orca", "orca", "core", "Main ORCA engine", required=True),
    OrcaToolSpec("orca_plot", "orca_plot", "gbw_cube", "GBW to density/orbital/ESP cube", required=True),
    OrcaToolSpec("orca_2json", "orca_2json", "json", "property.json / JSON export"),
    OrcaToolSpec("orca_2mkl", "orca_2mkl", "wavefunction", "Molden / MKL style wavefunction export"),
    OrcaToolSpec("orca_mapspc", "orca_mapspc", "spectra", "Spectrum broadening and post-processing"),
    OrcaToolSpec("orca_vib", "orca_vib", "vibration", "Vibrational post-processing"),
    OrcaToolSpec("orca_pltvib", "orca_pltvib", "vibration", "Vibrational plotting helper"),
    OrcaToolSpec("orca_nmrspectrum", "orca_nmrspectrum", "spectra", "NMR spectrum post-processing"),
    OrcaToolSpec("orca_mergefrag", "orca_mergefrag", "workflow", "Fragment and job merge utility"),
    OrcaToolSpec("orca_loc", "orca_loc", "localization", "Orbital localization utility"),
    OrcaToolSpec("orca_plot_mpi", "orca_plot_mpi", "gbw_cube", "MPI variant of orca_plot"),
    OrcaToolSpec("otool_gcp", "otool_gcp", "optional", "gCP correction helper"),
]

PYTHON_PACKAGE_NAMES = [
    "streamlit",
    "ase",
    "plotly",
    "pandas",
    "numpy",
    "psutil",
    "kaleido",
]


def detect_orca_environment(
    *,
    path_hint: str = "",
    orca_home_hint: str = "",
    tool_specs: list[OrcaToolSpec] | None = None,
) -> OrcaEnvironmentReport:
    specs = tool_specs or ORCA_TOOL_SPECS
    statuses: list[OrcaToolStatus] = []
    login_env = _load_login_shell_orca_env()
    detected_home = _normalize_orca_home_hint(orca_home_hint) or _normalize_orca_home_hint(path_hint)

    for spec in specs:
        resolved = resolve_orca_executable(
            spec.executable,
            path_hint=path_hint,
            orca_home_hint=orca_home_hint,
            login_env=login_env,
        )
        if detected_home is None and resolved is not None:
            detected_home = str(resolved.parent)
        statuses.append(
            OrcaToolStatus(
                key=spec.key,
                executable=spec.executable,
                category=spec.category,
                purpose=spec.purpose,
                required=spec.required,
                available=resolved is not None,
                path=str(resolved) if resolved else None,
            )
        )

    version_source = next((tool.path for tool in statuses if tool.key == "orca" and tool.path), detected_home)
    return OrcaEnvironmentReport(
        platform=platform.platform(),
        python_executable=os.path.realpath(os.sys.executable),
        python_version=platform.python_version(),
        orca_home=detected_home,
        detected_orca_version=_infer_orca_version(version_source),
        env_orca_home=os.environ.get("ORCA_HOME", "").strip() or None,
        path_hint=path_hint.strip() or None,
        tools=statuses,
        python_packages=_python_package_versions(),
    )


def resolve_orca_executable(
    executable: str,
    *,
    path_hint: str = "",
    orca_home_hint: str = "",
    login_env: dict[str, str] | None = None,
) -> Path | None:
    executable_names = _executable_names(executable)
    login_env = login_env if login_env is not None else _load_login_shell_orca_env()
    candidates = _candidate_paths(
        executable_names,
        path_hint=path_hint,
        orca_home_hint=orca_home_hint,
        login_env=login_env,
    )

    for candidate in candidates:
        if candidate.exists() and candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    return None


def orca_environment_dataframe(report: OrcaEnvironmentReport) -> pd.DataFrame:
    rows = []
    for tool in report.tools:
        rows.append(
            {
                "category": tool.category,
                "tool": tool.key,
                "executable": tool.executable,
                "purpose": tool.purpose,
                "required": tool.required,
                "available": tool.available,
                "path": tool.path or "",
            }
        )
    return pd.DataFrame(rows)


def orca_environment_recommendations(report: OrcaEnvironmentReport) -> list[str]:
    available = {tool.key: tool.available for tool in report.tools}
    recommendations: list[str] = []
    if not available.get("orca", False):
        recommendations.append("Install ORCA or set ORCA_HOME so the app can run local calculations and validate outputs.")
    if not available.get("orca_plot", False):
        recommendations.append("Install or expose `orca_plot` to enable GBW -> density/orbital/ESP cube generation.")
    if not available.get("orca_2json", False):
        recommendations.append("Add `orca_2json` if you plan to use future JSON/property export workflows.")
    if not available.get("orca_mapspc", False):
        recommendations.append("Add `orca_mapspc` if you want native ORCA spectrum post-processing workflows.")
    if not available.get("orca_2mkl", False):
        recommendations.append("Add `orca_2mkl` if you want Molden/MKL style wavefunction export for external viewers.")
    if not recommendations:
        recommendations.append("Core ORCA utilities needed by the current app are available.")
    return recommendations


def python_environment_dataframe(report: OrcaEnvironmentReport) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "package": list(report.python_packages.keys()),
            "version": list(report.python_packages.values()),
        }
    )


def report_as_dict(report: OrcaEnvironmentReport) -> dict[str, Any]:
    payload = asdict(report)
    payload["available_tool_count"] = report.available_tool_count
    payload["required_tool_count"] = report.required_tool_count
    payload["available_required_tool_count"] = report.available_required_tool_count
    return payload


def _python_package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for package_name in PYTHON_PACKAGE_NAMES:
        try:
            versions[package_name] = importlib.metadata.version(package_name)
        except importlib.metadata.PackageNotFoundError:
            versions[package_name] = "missing"
    return versions


def _infer_orca_version(source: str | None) -> str | None:
    if not source:
        return None
    match = re.search(r"orca[_-]?(\d+(?:[._]\d+)+)", source, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1).replace("_", ".")


def _normalize_orca_home_hint(raw_hint: str) -> str | None:
    hint = raw_hint.strip()
    if not hint:
        return None
    path = Path(hint).expanduser()
    if path.is_file():
        return str(path.parent.resolve())
    if path.is_dir():
        return str(path.resolve())
    return None


def _candidate_paths(
    executable_names: list[str],
    *,
    path_hint: str,
    orca_home_hint: str,
    login_env: dict[str, str],
) -> list[Path]:
    candidates: list[Path] = []

    for raw_hint in [path_hint.strip(), orca_home_hint.strip()]:
        if not raw_hint:
            continue
        hinted = Path(raw_hint).expanduser()
        if hinted.is_file():
            candidates.append(hinted)
            candidates.extend(hinted.parent / name for name in executable_names)
        elif hinted.is_dir():
            candidates.extend(hinted / name for name in executable_names)

    for executable_name in executable_names:
        which_result = shutil.which(executable_name)
        if which_result:
            candidates.append(Path(which_result))

    for env_home in filter(
        None,
        [
            os.environ.get("ORCA_HOME", "").strip(),
            login_env.get("ORCA_HOME", "").strip(),
        ],
    ):
        candidates.extend(Path(env_home) / name for name in executable_names)

    path_separator = ";" if os.name == "nt" else ":"
    for path_entry in login_env.get("PATH", "").split(path_separator):
        path_entry = path_entry.strip()
        if path_entry:
            candidates.extend(Path(path_entry) / name for name in executable_names)

    for base_dir in _common_orca_directories():
        if not base_dir.exists():
            continue
        candidates.extend(_scan_orca_candidates(base_dir, executable_names))

    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.expanduser())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _load_login_shell_orca_env() -> dict[str, str]:
    if os.name == "nt":
        return {}

    shell = os.environ.get("SHELL", "").strip() or "/bin/bash"
    completed = subprocess.run(
        [shell, "-lc", 'printf "ORCA_HOME=%s\\nPATH=%s\\n" "$ORCA_HOME" "$PATH"'],
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


def _executable_names(executable: str) -> list[str]:
    raw = executable.strip()
    if not raw:
        return []
    if platform.system() == "Windows":
        if raw.lower().endswith((".exe", ".bat")):
            return [raw]
        return [f"{raw}.exe", f"{raw}.bat", raw]
    return [raw]


def _common_orca_directories() -> list[Path]:
    if platform.system() == "Windows":
        roots = [
            os.environ.get("ProgramFiles", ""),
            os.environ.get("ProgramFiles(x86)", ""),
            os.environ.get("LOCALAPPDATA", ""),
            str(Path.home() / "AppData" / "Local"),
        ]
        return [Path(root) for root in roots if root]
    return [
        Path.home() / "orca",
        Path.home() / "opt",
        Path.home() / "Library",
        Path("/opt"),
        Path("/usr/local"),
        Path("/usr/local/bin"),
    ]


def _scan_orca_candidates(base_dir: Path, executable_names: list[str]) -> list[Path]:
    candidates: list[Path] = []
    for executable_name in executable_names:
        direct_candidate = base_dir / executable_name
        if direct_candidate.exists():
            candidates.append(direct_candidate)

    patterns = ["orca*", "ORCA*", "orca_*", "*orca*"]
    for pattern in patterns:
        for path in base_dir.glob(pattern):
            if not path.is_dir():
                continue
            for executable_name in executable_names:
                candidates.append(path / executable_name)
                candidates.append(path / "bin" / executable_name)
    return candidates
