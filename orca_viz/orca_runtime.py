from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib.metadata
import os
from pathlib import Path
import platform
import re
import shlex
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
    real_path: str | None
    resolved_via: str | None
    failure_reason: str | None
    searched_locations: list[str]


@dataclass(frozen=True)
class OrcaToolResolution:
    executable: str
    path: str | None
    real_path: str | None
    resolved_via: str | None
    failure_reason: str | None
    searched_locations: list[str]


@dataclass(frozen=True)
class OrcaEnvironmentReport:
    platform: str
    python_executable: str
    python_version: str
    orca_home: str | None
    detected_orca_version: str | None
    env_orca_home: str | None
    shell_orca_home: str | None
    path_hint: str | None
    orca_home_hint: str | None
    process_path: str
    shell_path: str | None
    shell_executable: str | None
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
    "scikit-image",
]

ORCA_HOME_ENV_VARS = [
    "ORCA_HOME",
    "ORCA_ROOT",
    "ORCA_DIR",
    "ORCA_BIN",
]

ORCA_SEED_EXECUTABLES = [
    "orca",
    "orca_plot",
    "orca_2json",
    "orca_2mkl",
]

DISCOVERY_METHOD_LABELS = {
    "path_hint_file": "user path hint (file)",
    "path_hint_dir": "user path hint (directory)",
    "orca_home_hint_file": "ORCA_HOME hint (file)",
    "orca_home_hint_dir": "ORCA_HOME hint (directory)",
    "process_which": "current process PATH / shutil.which",
    "shell_command_v": "login shell command -v",
    "shell_type_p": "login shell type -P",
    "shell_type_a": "login shell type -a",
    "process_seed": "current process PATH via sibling ORCA tool",
    "shell_seed": "login shell via sibling ORCA tool",
    "env_hint_file": "ORCA_HOME-like env var (file)",
    "env_hint_dir": "ORCA_HOME-like env var (directory)",
    "process_path_scan": "current process PATH directory scan",
    "login_shell_path_scan": "login shell PATH directory scan",
    "common_dir_scan": "common local installation scan",
}


@dataclass(frozen=True)
class _DiscoveryCandidate:
    path: Path
    method: str


def detect_orca_environment(
    *,
    path_hint: str = "",
    orca_home_hint: str = "",
    tool_specs: list[OrcaToolSpec] | None = None,
) -> OrcaEnvironmentReport:
    specs = tool_specs or ORCA_TOOL_SPECS
    statuses: list[OrcaToolStatus] = []
    login_env = _load_login_shell_orca_env()
    process_path = os.environ.get("PATH", "")
    detected_home = _normalize_orca_home_hint(orca_home_hint) or _normalize_orca_home_hint(path_hint)

    for spec in specs:
        resolution = resolve_orca_executable_details(
            spec.executable,
            path_hint=path_hint,
            orca_home_hint=orca_home_hint,
            login_env=login_env,
        )
        if detected_home is None and resolution.path is not None:
            detected_home = str(_candidate_roots_from_executable(Path(resolution.path))[-1].resolve())
        statuses.append(
            OrcaToolStatus(
                key=spec.key,
                executable=spec.executable,
                category=spec.category,
                purpose=spec.purpose,
                required=spec.required,
                available=resolution.path is not None,
                path=resolution.path,
                real_path=resolution.real_path,
                resolved_via=resolution.resolved_via,
                failure_reason=resolution.failure_reason,
                searched_locations=resolution.searched_locations,
            )
        )

    orca_executable_path = next((tool.path for tool in statuses if tool.key == "orca" and tool.path), None)
    return OrcaEnvironmentReport(
        platform=platform.platform(),
        python_executable=os.path.realpath(os.sys.executable),
        python_version=platform.python_version(),
        orca_home=detected_home,
        detected_orca_version=detect_orca_version(
            executable_path=orca_executable_path,
            fallback_source=detected_home,
        ),
        env_orca_home=os.environ.get("ORCA_HOME", "").strip() or None,
        shell_orca_home=_first_non_empty(login_env.get(env_name, "").strip() for env_name in ORCA_HOME_ENV_VARS),
        path_hint=path_hint.strip() or None,
        orca_home_hint=orca_home_hint.strip() or None,
        process_path=process_path,
        shell_path=login_env.get("PATH", "").strip() or None,
        shell_executable=login_env.get("SHELL", "").strip() or None,
        tools=statuses,
        python_packages=_python_package_versions(),
    )


def resolve_orca_executable_details(
    executable: str,
    *,
    path_hint: str = "",
    orca_home_hint: str = "",
    login_env: dict[str, str] | None = None,
) -> OrcaToolResolution:
    executable_names = _executable_names(executable)
    login_env = login_env if login_env is not None else _load_login_shell_orca_env()
    candidates = _candidate_paths(
        executable_names,
        path_hint=path_hint,
        orca_home_hint=orca_home_hint,
        login_env=login_env,
    )
    searched_locations = [f"{_method_label(candidate.method)} -> {candidate.path}" for candidate in candidates[:20]]

    for candidate in candidates:
        if candidate.path.exists() and candidate.path.is_file() and os.access(candidate.path, os.X_OK):
            resolved = candidate.path.resolve()
            return OrcaToolResolution(
                executable=executable,
                path=str(resolved),
                real_path=str(resolved),
                resolved_via=candidate.method,
                failure_reason=None,
                searched_locations=searched_locations,
            )

    if searched_locations:
        failure_reason = (
            "Candidate paths were discovered, but none were executable files that the current process can run."
        )
    else:
        failure_reason = (
            "No candidate path was discovered from the path hint, ORCA_HOME-like variables, current PATH, "
            "login shell lookup, or common local installation directories."
        )

    return OrcaToolResolution(
        executable=executable,
        path=None,
        real_path=None,
        resolved_via=None,
        failure_reason=failure_reason,
        searched_locations=searched_locations,
    )


def resolve_orca_executable(
    executable: str,
    *,
    path_hint: str = "",
    orca_home_hint: str = "",
    login_env: dict[str, str] | None = None,
) -> Path | None:
    resolution = resolve_orca_executable_details(
        executable,
        path_hint=path_hint,
        orca_home_hint=orca_home_hint,
        login_env=login_env,
    )
    return Path(resolution.path) if resolution.path else None


def resolve_orca_tool(
    tool_key_or_executable: str,
    *,
    path_hint: str = "",
    orca_home_hint: str = "",
    login_env: dict[str, str] | None = None,
) -> Path | None:
    normalized_key = tool_key_or_executable.strip()
    if not normalized_key:
        return None
    executable = next(
        (spec.executable for spec in ORCA_TOOL_SPECS if spec.key == normalized_key),
        normalized_key,
    )
    return resolve_orca_executable(
        executable,
        path_hint=path_hint,
        orca_home_hint=orca_home_hint,
        login_env=login_env,
    )


def resolve_orca_tool_details(
    tool_key_or_executable: str,
    *,
    path_hint: str = "",
    orca_home_hint: str = "",
    login_env: dict[str, str] | None = None,
) -> OrcaToolResolution:
    normalized_key = tool_key_or_executable.strip()
    if not normalized_key:
        return OrcaToolResolution(
            executable="",
            path=None,
            real_path=None,
            resolved_via=None,
            failure_reason="No ORCA tool name was provided.",
            searched_locations=[],
        )
    executable = next(
        (spec.executable for spec in ORCA_TOOL_SPECS if spec.key == normalized_key),
        normalized_key,
    )
    return resolve_orca_executable_details(
        executable,
        path_hint=path_hint,
        orca_home_hint=orca_home_hint,
        login_env=login_env,
    )


def orca_discovery_method_label(method: str | None) -> str | None:
    return _method_label(method)


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
                "resolved_via": _method_label(tool.resolved_via),
                "failure_reason": tool.failure_reason or "",
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


def detect_orca_version(
    executable_path: str | None,
    *,
    fallback_source: str | None = None,
) -> str | None:
    if executable_path:
        queried = _query_orca_version(executable_path)
        if queried:
            return queried
        inferred = _infer_orca_version(executable_path)
        if inferred:
            return inferred
    return _infer_orca_version(fallback_source)


def _infer_orca_version(source: str | None) -> str | None:
    if not source:
        return None
    match = re.search(r"orca[_-]?(\d+(?:[._]\d+)+)", source, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1).replace("_", ".")


def _query_orca_version(executable_path: str) -> str | None:
    executable = Path(executable_path)
    commands = [
        [str(executable), "--version"],
        [str(executable), "-v"],
        [str(executable), "-h"],
    ]
    for command in commands:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=6,
                check=False,
            )
        except Exception:
            continue
        version = _version_from_text("\n".join([completed.stdout, completed.stderr]))
        if version:
            return version
    return None


def _version_from_text(raw_text: str) -> str | None:
    patterns = [
        r"Program Version\s+([0-9]+(?:\.[0-9]+)+)",
        r"\bORCA\s+version\s+([0-9]+(?:\.[0-9]+)+)",
        r"\bVersion\s*[:=]?\s*([0-9]+(?:\.[0-9]+)+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


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
) -> list[_DiscoveryCandidate]:
    candidates: list[_DiscoveryCandidate] = []
    candidate_roots: list[tuple[Path, str]] = []

    for raw_hint, source_method_file, source_method_dir in [
        (path_hint.strip(), "path_hint_file", "path_hint_dir"),
        (orca_home_hint.strip(), "orca_home_hint_file", "orca_home_hint_dir"),
    ]:
        if not raw_hint:
            continue
        hinted = Path(raw_hint).expanduser()
        if hinted.is_file():
            if hinted.name in executable_names:
                candidates.append(_DiscoveryCandidate(hinted, source_method_file))
            roots = _candidate_roots_from_executable(hinted)
            candidate_roots.extend((root, source_method_file) for root in roots)
            for root in roots:
                candidates.extend(_executable_candidates_from_root(root, executable_names, source_method_file))
        elif hinted.is_dir():
            candidate_roots.append((hinted, source_method_dir))
            candidates.extend(_executable_candidates_from_root(hinted, executable_names, source_method_dir))
            scanned_roots = _scan_orca_roots(hinted)
            candidate_roots.extend((root, source_method_dir) for root in scanned_roots)
            for root in scanned_roots:
                candidates.extend(_executable_candidates_from_root(root, executable_names, source_method_dir))

    for executable_name in executable_names:
        which_result = shutil.which(executable_name)
        if which_result:
            which_path = Path(which_result)
            candidates.append(_DiscoveryCandidate(which_path, "process_which"))
            candidate_roots.extend((root, "process_which") for root in _candidate_roots_from_executable(which_path))
        candidates.extend(_shell_lookup_candidates(executable_name, login_env))

    for seed_executable in ORCA_SEED_EXECUTABLES:
        which_result = shutil.which(seed_executable)
        if which_result:
            candidate_roots.extend((root, "process_seed") for root in _candidate_roots_from_executable(Path(which_result)))
        for shell_candidate in _shell_lookup_candidates(seed_executable, login_env):
            candidate_roots.extend((root, "shell_seed") for root in _candidate_roots_from_executable(shell_candidate.path))

    for env_home in _orca_env_hints(login_env):
        env_path = Path(env_home).expanduser()
        if env_path.is_file():
            roots = _candidate_roots_from_executable(env_path)
            candidate_roots.extend((root, "env_hint_file") for root in roots)
            for root in roots:
                candidates.extend(_executable_candidates_from_root(root, executable_names, "env_hint_file"))
        elif env_path.is_dir():
            candidate_roots.append((env_path, "env_hint_dir"))
            candidates.extend(_executable_candidates_from_root(env_path, executable_names, "env_hint_dir"))
            scanned_roots = _scan_orca_roots(env_path)
            candidate_roots.extend((root, "env_hint_dir") for root in scanned_roots)
            for root in scanned_roots:
                candidates.extend(_executable_candidates_from_root(root, executable_names, "env_hint_dir"))

    for path_entry in _split_path_entries(os.environ.get("PATH", "")):
        path_dir = Path(path_entry)
        candidate_roots.append((path_dir, "process_path_scan"))
        candidate_roots.extend((root, "process_path_scan") for root in _scan_orca_roots(path_dir))

    for path_entry in _split_path_entries(login_env.get("PATH", "")):
        path_dir = Path(path_entry)
        candidate_roots.append((path_dir, "login_shell_path_scan"))
        candidate_roots.extend((root, "login_shell_path_scan") for root in _scan_orca_roots(path_dir))

    for base_dir in _common_orca_directories():
        if not base_dir.exists():
            continue
        candidate_roots.append((base_dir, "common_dir_scan"))
        candidate_roots.extend((root, "common_dir_scan") for root in _scan_orca_roots(base_dir))

    for root, method in candidate_roots:
        candidates.extend(_executable_candidates_from_root(root, executable_names, method))

    deduped: list[_DiscoveryCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.path.expanduser())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _load_login_shell_orca_env() -> dict[str, str]:
    if os.name == "nt":
        return {}

    shell = os.environ.get("SHELL", "").strip() or shutil.which("bash") or "/bin/bash"
    probe_parts = ['printf "SHELL=%s\\nPATH=%s\\n" "$SHELL" "$PATH"']
    for env_name in ORCA_HOME_ENV_VARS:
        probe_parts.append(f'printf "{env_name}=%s\\n" "${env_name}"')
    completed = subprocess.run(
        [shell, "-lc", "; ".join(probe_parts)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return {"SHELL": shell}

    env_data: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        env_data[key.strip()] = value.strip()
    env_data.setdefault("SHELL", shell)
    return env_data


def _executable_names(executable: str) -> list[str]:
    raw = executable.strip()
    if not raw:
        return []
    if platform.system() == "Windows":
        if raw.lower().endswith((".exe", ".bat", ".cmd")):
            return [raw]
        return [f"{raw}.exe", f"{raw}.bat", f"{raw}.cmd", raw]
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


def _scan_orca_roots(base_dir: Path) -> list[Path]:
    roots: list[Path] = []
    if not base_dir.exists() or not base_dir.is_dir():
        return roots

    patterns = ["orca*", "ORCA*", "*orca*"]
    for pattern in patterns:
        for path in base_dir.glob(pattern):
            if path.is_dir():
                roots.append(path)
    return roots


def _executable_candidates_from_root(
    root: Path,
    executable_names: list[str],
    method: str,
) -> list[_DiscoveryCandidate]:
    candidates: list[_DiscoveryCandidate] = []
    for executable_name in executable_names:
        candidates.append(_DiscoveryCandidate(root / executable_name, method))
        candidates.append(_DiscoveryCandidate(root / "bin" / executable_name, method))
    return candidates


def _candidate_roots_from_executable(executable_path: Path) -> list[Path]:
    roots = [executable_path.parent]
    if executable_path.parent.name.lower() == "bin":
        roots.append(executable_path.parent.parent)
    return roots


def _orca_env_hints(login_env: dict[str, str]) -> list[str]:
    hints: list[str] = []
    for env_name in ORCA_HOME_ENV_VARS:
        for env_source in (os.environ, login_env):
            raw_value = env_source.get(env_name, "").strip()
            if raw_value:
                hints.append(raw_value)
    return hints


def _shell_lookup_candidates(executable_name: str, login_env: dict[str, str]) -> list[_DiscoveryCandidate]:
    if os.name == "nt":
        return []
    shell = login_env.get("SHELL", "").strip() or os.environ.get("SHELL", "").strip() or shutil.which("bash")
    if not shell:
        return []
    candidates: list[_DiscoveryCandidate] = []
    for method, command in [
        ("shell_command_v", f"command -v {shlex.quote(executable_name)} 2>/dev/null || true"),
        ("shell_type_p", f"type -P {shlex.quote(executable_name)} 2>/dev/null || true"),
        ("shell_type_a", f"type -a {shlex.quote(executable_name)} 2>/dev/null || true"),
    ]:
        try:
            completed = subprocess.run(
                [shell, "-lc", command],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except Exception:
            continue
        candidates.extend(_parse_shell_lookup_output(completed.stdout, method))
    return candidates


def _parse_shell_lookup_output(stdout: str, method: str) -> list[_DiscoveryCandidate]:
    candidates: list[_DiscoveryCandidate] = []
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parsed_path: Path | None = None
        if line.startswith("/"):
            parsed_path = Path(line)
        elif " is " in line:
            possible_path = line.rsplit(" is ", 1)[-1].strip()
            if possible_path.startswith("/"):
                parsed_path = Path(possible_path)
        if parsed_path is not None:
            candidates.append(_DiscoveryCandidate(parsed_path.expanduser(), method))
    return candidates


def _split_path_entries(raw_path: str) -> list[str]:
    path_separator = ";" if os.name == "nt" else ":"
    return [entry.strip() for entry in raw_path.split(path_separator) if entry.strip()]


def _first_non_empty(values: Any) -> str | None:
    for value in values:
        if value:
            return value
    return None


def _method_label(method: str | None) -> str | None:
    if method is None:
        return None
    return DISCOVERY_METHOD_LABELS.get(method, method)
