from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from .orca_runtime import detect_orca_environment, orca_environment_recommendations, report_as_dict


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="orca-viz")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Launch the Streamlit application")
    run_parser.add_argument("streamlit_args", nargs=argparse.REMAINDER)

    doctor_parser = subparsers.add_parser("doctor", help="Inspect the ORCA/Python runtime")
    doctor_parser.add_argument("--path-hint", default="", help="ORCA installation directory or executable path")
    doctor_parser.add_argument("--orca-home", default="", help="Explicit ORCA_HOME hint")
    doctor_parser.add_argument("--json", action="store_true", help="Print the full report as JSON")

    args = parser.parse_args(argv)
    if args.command in {None, "run"}:
        return run_main(getattr(args, "streamlit_args", None))
    return doctor_main(
        [
            *([f"--path-hint={args.path_hint}"] if args.path_hint else []),
            *([f"--orca-home={args.orca_home}"] if args.orca_home else []),
            *(["--json"] if args.json else []),
        ]
    )


def run_main(streamlit_args: list[str] | None = None) -> int:
    script_path = Path(__file__).resolve().with_name("streamlit_app.py")
    cmd = [sys.executable, "-m", "streamlit", "run", str(script_path)]
    if streamlit_args:
        if streamlit_args and streamlit_args[0] == "--":
            streamlit_args = streamlit_args[1:]
        cmd.extend(streamlit_args)
    return subprocess.call(cmd)


def doctor_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="orca-viz-doctor")
    parser.add_argument("--path-hint", default="", help="ORCA installation directory or executable path")
    parser.add_argument("--orca-home", default="", help="Explicit ORCA_HOME hint")
    parser.add_argument("--json", action="store_true", help="Print the full report as JSON")
    args = parser.parse_args(argv)

    report = detect_orca_environment(path_hint=args.path_hint, orca_home_hint=args.orca_home)
    if args.json:
        print(json.dumps(report_as_dict(report), indent=2, ensure_ascii=False))
        return 0

    print(_format_text_report(report))
    return 0


def _format_text_report(report: object) -> str:
    payload = report_as_dict(report)
    lines = [
        "ORCA Visualizer Environment Doctor",
        f"Platform: {payload['platform']}",
        f"Python: {payload['python_version']} ({payload['python_executable']})",
        f"ORCA home: {payload['orca_home'] or 'not detected'}",
        f"ORCA version: {payload['detected_orca_version'] or 'unknown'}",
        f"Required tools: {payload['available_required_tool_count']}/{payload['required_tool_count']}",
        "",
        "Detected ORCA utilities:",
    ]
    for tool in payload["tools"]:
        status = "OK" if tool["available"] else "MISS"
        required = "required" if tool["required"] else "optional"
        path = tool["path"] or "-"
        lines.append(f"  [{status}] {tool['key']} ({required}) -> {path}")

    recommendations = orca_environment_recommendations(report)
    if recommendations:
        lines.extend(["", "Recommendations:"])
        lines.extend([f"  - {item}" for item in recommendations])

    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
