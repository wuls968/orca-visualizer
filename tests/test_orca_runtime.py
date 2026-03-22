from pathlib import Path
import platform
import tempfile
import unittest
from unittest import mock

from orca_viz.orca_runtime import (
    detect_orca_version,
    detect_orca_environment,
    orca_environment_dataframe,
    orca_environment_recommendations,
    python_environment_dataframe,
    report_as_dict,
    resolve_orca_executable,
)


def _tool_file_name(name: str) -> str:
    if platform.system() == "Windows":
        return f"{name}.exe"
    return name


def _write_executable(path: Path) -> None:
    path.write_text("echo test\n", encoding="utf-8")
    path.chmod(0o755)


class OrcaRuntimeTests(unittest.TestCase):
    def test_detect_orca_environment_from_hint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            install_dir = Path(temp_dir) / "orca_6_1_0"
            install_dir.mkdir()
            _write_executable(install_dir / _tool_file_name("orca"))
            _write_executable(install_dir / _tool_file_name("orca_plot"))
            _write_executable(install_dir / _tool_file_name("orca_2json"))

            with mock.patch.dict("os.environ", {"ORCA_HOME": ""}, clear=False), mock.patch(
                "orca_viz.orca_runtime.shutil.which",
                return_value=None,
            ), mock.patch(
                "orca_viz.orca_runtime._load_login_shell_orca_env",
                return_value={},
            ), mock.patch("orca_viz.orca_runtime._common_orca_directories", return_value=[]):
                report = detect_orca_environment(path_hint=str(install_dir))

            tool_map = {tool.key: tool for tool in report.tools}
            self.assertEqual(report.detected_orca_version, "6.1.0")
            self.assertTrue(tool_map["orca"].available)
            self.assertTrue(tool_map["orca_plot"].available)
            self.assertTrue(tool_map["orca_2json"].available)
            self.assertFalse(tool_map["orca_2mkl"].available)
            self.assertEqual(report.available_required_tool_count, report.required_tool_count)

            report_dict = report_as_dict(report)
            self.assertEqual(report_dict["available_required_tool_count"], report.required_tool_count)

            tool_df = orca_environment_dataframe(report)
            self.assertIn("tool", tool_df.columns)
            self.assertIn("available", tool_df.columns)

            package_df = python_environment_dataframe(report)
            self.assertIn("package", package_df.columns)
            self.assertIn("version", package_df.columns)

            recommendations = orca_environment_recommendations(report)
            self.assertTrue(any("orca_2mkl" in item for item in recommendations))

    def test_resolve_orca_executable_from_file_hint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            install_dir = Path(temp_dir)
            executable = install_dir / _tool_file_name("orca_plot")
            _write_executable(executable)

            with mock.patch.dict("os.environ", {"ORCA_HOME": ""}, clear=False), mock.patch(
                "orca_viz.orca_runtime.shutil.which",
                return_value=None,
            ), mock.patch(
                "orca_viz.orca_runtime._load_login_shell_orca_env",
                return_value={},
            ), mock.patch("orca_viz.orca_runtime._common_orca_directories", return_value=[]):
                resolved = resolve_orca_executable("orca_plot", path_hint=str(executable))

            self.assertEqual(resolved, executable.resolve())

    def test_detect_orca_version_prefers_executable_output_then_falls_back_to_path(self) -> None:
        with mock.patch("orca_viz.orca_runtime.subprocess.run") as mocked_run:
            mocked_run.return_value = mock.Mock(
                returncode=0,
                stdout="Program Version 6.1.2\n",
                stderr="",
            )
            detected = detect_orca_version("/tmp/orca")
        self.assertEqual(detected, "6.1.2")

        with mock.patch("orca_viz.orca_runtime.subprocess.run", side_effect=RuntimeError("boom")):
            fallback = detect_orca_version(None, fallback_source="/opt/orca_6_1_0")
        self.assertEqual(fallback, "6.1.0")


if __name__ == "__main__":
    unittest.main()
