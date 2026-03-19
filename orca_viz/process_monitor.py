from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import getpass
import os
from pathlib import Path
import platform
import subprocess
import time
from typing import Any

import pandas as pd

try:
    import psutil
except ImportError:  # pragma: no cover - fallback path is covered separately
    psutil = None


@dataclass
class ProcessRecord:
    pid: int
    ppid: int
    cpu_percent: float
    memory_percent: float
    elapsed: str
    elapsed_seconds: int
    executable: str
    command: str
    category: str
    risk: str
    resident: bool
    system_service: bool
    self_related: bool
    reasons: list[str]


def snapshot_processes() -> dict[str, Any]:
    records = _list_user_processes()
    suspicious = [record for record in records if record.risk in {"high", "medium"}]
    orca_related = [record for record in records if record.category == "orca"]
    resident = [record for record in records if record.resident]
    top_cpu = sorted(records, key=lambda item: item.cpu_percent, reverse=True)[:10]
    top_memory = sorted(records, key=lambda item: item.memory_percent, reverse=True)[:10]

    return {
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "records": records,
        "summary": {
            "total_processes": len(records),
            "suspicious_processes": len(suspicious),
            "orca_related_processes": len(orca_related),
            "resident_processes": len(resident),
            "suspicious_cpu_percent": round(sum(item.cpu_percent for item in suspicious), 1),
            "max_memory_percent": round(max((item.memory_percent for item in records), default=0.0), 1),
        },
        "top_cpu": top_cpu,
        "top_memory": top_memory,
    }


def process_dataframe(
    records: list[ProcessRecord],
    include_command: bool = True,
    hide_self_related: bool = False,
    hide_system_services: bool = False,
    only_suspicious: bool = False,
) -> pd.DataFrame:
    filtered = records
    if hide_self_related:
        filtered = [record for record in filtered if not record.self_related]
    if hide_system_services:
        filtered = [record for record in filtered if not record.system_service]
    if only_suspicious:
        filtered = [record for record in filtered if record.risk in {"high", "medium"}]

    rows: list[dict[str, Any]] = []
    for record in filtered:
        row = {
            "pid": record.pid,
            "ppid": record.ppid,
            "process": record.executable,
            "category": record.category,
            "risk": record.risk,
            "cpu_percent": record.cpu_percent,
            "memory_percent": record.memory_percent,
            "elapsed": record.elapsed,
            "resident": record.resident,
            "reasons": "; ".join(record.reasons) if record.reasons else "",
        }
        if include_command:
            row["command"] = record.command
        rows.append(row)
    return pd.DataFrame(rows)


def _list_user_processes() -> list[ProcessRecord]:
    if psutil is not None:
        return _list_user_processes_psutil()
    return _list_user_processes_ps()


def _list_user_processes_psutil() -> list[ProcessRecord]:
    current_user = _normalized_current_user()
    processes = list(
        psutil.process_iter(
            ["pid", "ppid", "name", "exe", "cmdline", "username", "memory_percent", "create_time"]
        )
    )
    for process in processes:
        try:
            process.cpu_percent(None)
        except Exception:
            continue
    time.sleep(0.05)

    records: list[ProcessRecord] = []
    for process in processes:
        try:
            info = process.info
            username = str(info.get("username") or "")
            if current_user and not _username_matches(username, current_user):
                continue
            cmdline = [str(item) for item in (info.get("cmdline") or []) if str(item).strip()]
            executable_hint = (
                cmdline[0]
                if cmdline
                else str(info.get("exe") or info.get("name") or "unknown")
            )
            command = " ".join(cmdline) if cmdline else str(info.get("exe") or info.get("name") or "unknown")
            elapsed_seconds = max(
                0,
                int(time.time() - float(info.get("create_time") or time.time())),
            )
            record = _classify_record(
                pid=int(info.get("pid") or 0),
                ppid=int(info.get("ppid") or 0),
                cpu_percent=float(process.cpu_percent(None)),
                memory_percent=float(info.get("memory_percent") or 0.0),
                elapsed=format_elapsed_seconds(elapsed_seconds),
                command=command,
                executable_hint=executable_hint,
                elapsed_seconds_override=elapsed_seconds,
            )
            records.append(record)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return records


def _list_user_processes_ps() -> list[ProcessRecord]:
    current_user = os.environ.get("USER", "").strip()
    command = ["ps"]
    if current_user:
        command.extend(["-U", current_user])
    command.extend(["-ww", "-o", "pid=,ppid=,%cpu=,%mem=,etime=,args="])
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ps command failed")

    records: list[ProcessRecord] = []
    for line in completed.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parsed = _parse_ps_line(line)
        if parsed is None:
            continue
        records.append(_classify_record(*parsed))
    return records


def _parse_ps_line(line: str) -> tuple[int, int, float, float, str, str] | None:
    parts = line.split(None, 5)
    if len(parts) < 6:
        return None
    pid, ppid, cpu_percent, memory_percent, elapsed, command = parts
    return (
        int(pid),
        int(ppid),
        float(cpu_percent),
        float(memory_percent),
        elapsed,
        command.strip(),
    )


def _classify_record(
    pid: int,
    ppid: int,
    cpu_percent: float,
    memory_percent: float,
    elapsed: str,
    command: str,
    executable_hint: str | None = None,
    elapsed_seconds_override: int | None = None,
) -> ProcessRecord:
    elapsed_seconds = (
        elapsed_seconds_override if elapsed_seconds_override is not None else parse_elapsed_seconds(elapsed)
    )
    executable_source = executable_hint or (command.split()[0] if command else "unknown")
    executable = Path(executable_source).name if executable_source else "unknown"
    lower = command.lower()

    self_markers = [
        "orca_visualizer",
        "streamlit run app.py",
    ]
    self_related = any(marker in lower for marker in self_markers) or pid == os.getpid()
    system_prefixes = [
        "/system/",
        "/usr/libexec/",
        "/usr/sbin/",
        "c:\\windows\\system32",
        "c:\\windows\\winsxs",
    ]
    system_service = ppid in {0, 1} and any(lower.startswith(prefix) for prefix in system_prefixes)
    orca_related = any(
        token in lower
        for token in ["orca_plot", "orca.exe", "/orca", "\\orca", " orca ", " mpirun ", " mpiexec ", "orterun"]
    )
    python_related = any(token in lower for token in ["python", "streamlit", "jupyter", "ipykernel"])
    resident = ppid == 1 or elapsed_seconds >= 1800 or "nohup" in lower

    category = "other"
    if orca_related:
        category = "orca"
    elif python_related:
        category = "python"
    elif system_service:
        category = "system"

    reasons: list[str] = []
    score = 0
    if orca_related:
        reasons.append("orca_related")
        score += 2
    if resident:
        reasons.append("resident")
        score += 1
    if elapsed_seconds >= 3600:
        reasons.append("long_running")
        score += 1
    if cpu_percent >= 80:
        reasons.append("high_cpu")
        score += 3
    elif cpu_percent >= 20:
        reasons.append("moderate_cpu")
        score += 1
    if memory_percent >= 20:
        reasons.append("high_memory")
        score += 3
    elif memory_percent >= 8:
        reasons.append("moderate_memory")
        score += 1
    if python_related and resident and not self_related:
        reasons.append("python_service")
        score += 1
    if system_service:
        score -= 2
    if self_related:
        score -= 1

    risk = "low"
    if score >= 4:
        risk = "high"
    elif score >= 2:
        risk = "medium"

    return ProcessRecord(
        pid=pid,
        ppid=ppid,
        cpu_percent=cpu_percent,
        memory_percent=memory_percent,
        elapsed=elapsed,
        elapsed_seconds=elapsed_seconds,
        executable=executable,
        command=command,
        category=category,
        risk=risk,
        resident=resident,
        system_service=system_service,
        self_related=self_related,
        reasons=reasons,
    )


def parse_elapsed_seconds(value: str) -> int:
    value = value.strip()
    if not value:
        return 0
    day_part = 0
    time_part = value
    if "-" in value:
        days, time_part = value.split("-", 1)
        day_part = int(days) * 86400
    chunks = [int(chunk) for chunk in time_part.split(":")]
    if len(chunks) == 3:
        hours, minutes, seconds = chunks
    elif len(chunks) == 2:
        hours = 0
        minutes, seconds = chunks
    else:
        hours = 0
        minutes = 0
        seconds = chunks[0]
    return day_part + hours * 3600 + minutes * 60 + seconds


def format_elapsed_seconds(value: int) -> str:
    days, remainder = divmod(max(value, 0), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    if days:
        return f"{days:02d}-{hours:02d}:{minutes:02d}:{seconds:02d}"
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _normalized_current_user() -> str:
    return (
        os.environ.get("USERNAME")
        or os.environ.get("USER")
        or getpass.getuser()
        or ""
    ).strip().lower()


def _username_matches(value: str, current_user: str) -> bool:
    value = value.strip().lower()
    if not value:
        return False
    if value == current_user:
        return True
    if platform.system() == "Windows" and "\\" in value:
        return value.rsplit("\\", 1)[-1] == current_user
    return value.endswith(f"/{current_user}") or value.endswith(f"\\{current_user}")
