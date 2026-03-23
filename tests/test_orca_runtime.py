from pathlib import Path
import platform
import tempfile
import unittest
from unittest import mock

import orca_viz.orca_runtime as runtime
from orca_viz.orca_runtime import (
    detect_orca_version,
    detect_orca_environment,
    orca_environment_dataframe,
    orca_environment_recommendations,
    python_environment_dataframe,
    report_as_dict,
    resolve_orca_executable,
    resolve_orca_executable_details,
    resolve_orca_tool_details,
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

            with mock.patch.dict("os.environ", {"ORCA_HOME": "", "PATH": ""}, clear=False), mock.patch(
                "orca_viz.orca_runtime.shutil.which",
                return_value=None,
            ), mock.patch(
                "orca_viz.orca_runtime._load_login_shell_orca_env",
                return_value={},
            ), mock.patch(
                "orca_viz.orca_runtime._shell_lookup_candidates",
                return_value=[],
            ), mock.patch("orca_viz.orca_runtime._common_orca_directories", return_value=[]):
                report = detect_orca_environment(path_hint=str(install_dir))

            tool_map = {tool.key: tool for tool in report.tools}
            self.assertEqual(report.detected_orca_version, "6.1.0")
            self.assertTrue(tool_map["orca"].available)
            self.assertTrue(tool_map["orca_plot"].available)
            self.assertTrue(tool_map["orca_2json"].available)
            self.assertFalse(tool_map["orca_2mkl"].available)
            self.assertEqual(tool_map["orca_plot"].resolved_via, "path_hint_dir")
            self.assertEqual(report.available_required_tool_count, report.required_tool_count)
            self.assertEqual(report.path_hint, str(install_dir))
            self.assertIsNotNone(report.process_path)

            report_dict = report_as_dict(report)
            self.assertEqual(report_dict["available_required_tool_count"], report.required_tool_count)

            tool_df = orca_environment_dataframe(report)
            self.assertIn("tool", tool_df.columns)
            self.assertIn("available", tool_df.columns)
            self.assertIn("resolved_via", tool_df.columns)
            self.assertIn("failure_reason", tool_df.columns)

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

            with mock.patch.dict("os.environ", {"ORCA_HOME": "", "PATH": ""}, clear=False), mock.patch(
                "orca_viz.orca_runtime.shutil.which",
                return_value=None,
            ), mock.patch(
                "orca_viz.orca_runtime._load_login_shell_orca_env",
                return_value={},
            ), mock.patch(
                "orca_viz.orca_runtime._shell_lookup_candidates",
                return_value=[],
            ), mock.patch("orca_viz.orca_runtime._common_orca_directories", return_value=[]):
                resolved = resolve_orca_executable("orca_plot", path_hint=str(executable))

            self.assertEqual(resolved, executable.resolve())

    def test_resolve_orca_tool_details_from_shell_lookup_when_process_path_misses(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            shell_dir = Path(temp_dir) / "shell-only"
            shell_dir.mkdir()
            executable = shell_dir / _tool_file_name("orca_plot")
            _write_executable(executable)

            with mock.patch.dict("os.environ", {"ORCA_HOME": "", "PATH": ""}, clear=False), mock.patch(
                "orca_viz.orca_runtime.shutil.which",
                return_value=None,
            ), mock.patch(
                "orca_viz.orca_runtime._load_login_shell_orca_env",
                return_value={"SHELL": "/bin/bash", "PATH": str(shell_dir)},
            ), mock.patch(
                "orca_viz.orca_runtime._shell_lookup_candidates",
                return_value=[runtime._DiscoveryCandidate(executable, "shell_command_v")],
            ), mock.patch("orca_viz.orca_runtime._common_orca_directories", return_value=[]):
                resolution = resolve_orca_tool_details("orca_plot")

            self.assertEqual(resolution.path, str(executable.resolve()))
            self.assertEqual(resolution.resolved_via, "shell_command_v")
            self.assertIsNone(resolution.failure_reason)

    def test_load_shell_env_merges_login_and_interactive_paths(self) -> None:
        def fake_run(command: list[str], **_: object) -> object:
            shell_mode = command[1]
            if shell_mode == "-lc":
                return mock.Mock(
                    returncode=0,
                    stdout="SHELL=/bin/bash\nPATH=/usr/local/bin\nORCA_HOME=\nORCA_ROOT=\nORCA_DIR=\nORCA_BIN=\n",
                    stderr="",
                )
            return mock.Mock(
                returncode=0,
                stdout="SHELL=/bin/bash\nPATH=/home/wls/orca_6_1_0:/usr/local/bin\nORCA_HOME=/home/wls/orca_6_1_0\nORCA_ROOT=\nORCA_DIR=\nORCA_BIN=\n",
                stderr="",
            )

        with mock.patch("orca_viz.orca_runtime.subprocess.run", side_effect=fake_run):
            shell_env = runtime._load_login_shell_orca_env()

        self.assertEqual(shell_env["SHELL"], "/bin/bash")
        self.assertEqual(shell_env["LOGIN_SHELL_PATH"], "/usr/local/bin")
        self.assertEqual(shell_env["INTERACTIVE_SHELL_PATH"], "/home/wls/orca_6_1_0:/usr/local/bin")
        self.assertTrue(shell_env["PATH"].startswith("/home/wls/orca_6_1_0"))
        self.assertEqual(shell_env["ORCA_HOME"], "/home/wls/orca_6_1_0")

    def test_resolve_orca_executable_can_find_sibling_tools_from_orca_binary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            install_dir = Path(temp_dir) / "orca_install" / "bin"
            install_dir.mkdir(parents=True)
            orca = install_dir / _tool_file_name("orca")
            orca_plot = install_dir / _tool_file_name("orca_plot")
            _write_executable(orca)
            _write_executable(orca_plot)

            def fake_which(name: str) -> str | None:
                if name in {"orca", "orca.exe", "orca.bat", "orca.cmd"}:
                    return str(orca)
                return None

            with mock.patch.dict("os.environ", {"ORCA_HOME": "", "ORCA_ROOT": str(install_dir.parent), "PATH": ""}, clear=False), mock.patch(
                "orca_viz.orca_runtime.shutil.which",
                side_effect=fake_which,
            ), mock.patch(
                "orca_viz.orca_runtime._load_login_shell_orca_env",
                return_value={"ORCA_ROOT": str(install_dir.parent)},
            ), mock.patch(
                "orca_viz.orca_runtime._shell_lookup_candidates",
                return_value=[],
            ), mock.patch("orca_viz.orca_runtime._common_orca_directories", return_value=[]):
                resolved = resolve_orca_executable("orca_plot")

            self.assertEqual(resolved, orca_plot.resolve())

    def test_orca_anchor_sibling_lookup_prefers_tool_next_to_detected_orca(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            install_dir = Path(temp_dir) / "orca_6_1_0"
            install_dir.mkdir()
            orca = install_dir / _tool_file_name("orca")
            orca_plot = install_dir / _tool_file_name("orca_plot")
            _write_executable(orca)
            _write_executable(orca_plot)

            def fake_which(name: str) -> str | None:
                if name in {"orca", "orca.exe", "orca.bat", "orca.cmd"}:
                    return str(orca)
                return None

            with mock.patch.dict("os.environ", {"ORCA_HOME": "", "PATH": ""}, clear=False), mock.patch(
                "orca_viz.orca_runtime.shutil.which",
                side_effect=fake_which,
            ), mock.patch(
                "orca_viz.orca_runtime._load_login_shell_orca_env",
                return_value={},
            ), mock.patch(
                "orca_viz.orca_runtime._shell_lookup_candidates",
                return_value=[],
            ), mock.patch("orca_viz.orca_runtime._common_orca_directories", return_value=[]):
                resolution = resolve_orca_tool_details("orca_plot")

            self.assertEqual(resolution.path, str(orca_plot.resolve()))
            self.assertEqual(resolution.resolved_via, "orca_anchor_sibling")

    @unittest.skipIf(platform.system() == "Windows", "Windows CI symlink creation is not reliable here")
    def test_resolve_orca_executable_realpath_normalizes_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            real_dir = Path(temp_dir) / "real"
            link_dir = Path(temp_dir) / "links"
            real_dir.mkdir()
            link_dir.mkdir()
            real_executable = real_dir / _tool_file_name("orca_plot")
            symlink_executable = link_dir / _tool_file_name("orca_plot")
            _write_executable(real_executable)
            symlink_executable.symlink_to(real_executable)

            with mock.patch.dict("os.environ", {"ORCA_HOME": "", "PATH": ""}, clear=False), mock.patch(
                "orca_viz.orca_runtime.shutil.which",
                return_value=str(symlink_executable),
            ), mock.patch(
                "orca_viz.orca_runtime._load_login_shell_orca_env",
                return_value={},
            ), mock.patch(
                "orca_viz.orca_runtime._shell_lookup_candidates",
                return_value=[],
            ), mock.patch("orca_viz.orca_runtime._common_orca_directories", return_value=[]):
                resolution = resolve_orca_executable_details("orca_plot")

            self.assertEqual(resolution.path, str(real_executable.resolve()))
            self.assertEqual(resolution.real_path, str(real_executable.resolve()))
            self.assertEqual(resolution.resolved_via, "process_which")

    def test_file_hint_for_orca_binary_does_not_alias_other_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            install_dir = Path(temp_dir) / "orca_install"
            install_dir.mkdir()
            orca = install_dir / _tool_file_name("orca")
            orca_plot = install_dir / _tool_file_name("orca_plot")
            _write_executable(orca)
            _write_executable(orca_plot)

            with mock.patch.dict("os.environ", {"ORCA_HOME": "", "PATH": ""}, clear=False), mock.patch(
                "orca_viz.orca_runtime.shutil.which",
                return_value=None,
            ), mock.patch(
                "orca_viz.orca_runtime._load_login_shell_orca_env",
                return_value={},
            ), mock.patch(
                "orca_viz.orca_runtime._shell_lookup_candidates",
                return_value=[],
            ), mock.patch("orca_viz.orca_runtime._common_orca_directories", return_value=[]):
                resolved = resolve_orca_executable("orca_plot", path_hint=str(orca))

            self.assertEqual(resolved, orca_plot.resolve())

    def test_tool_lookup_can_succeed_when_orca_and_orca_plot_are_in_different_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            orca_dir = Path(temp_dir) / "orca_only"
            plot_dir = Path(temp_dir) / "plot_only"
            orca_dir.mkdir()
            plot_dir.mkdir()
            orca = orca_dir / _tool_file_name("orca")
            orca_plot = plot_dir / _tool_file_name("orca_plot")
            _write_executable(orca)
            _write_executable(orca_plot)

            def fake_which(name: str) -> str | None:
                if name in {"orca", "orca.exe", "orca.bat", "orca.cmd"}:
                    return str(orca)
                return None

            def fake_shell_lookup(name: str, _login_env: dict[str, str]) -> list[object]:
                if name in {"orca_plot", "orca_plot.exe", "orca_plot.bat", "orca_plot.cmd"}:
                    return [runtime._DiscoveryCandidate(orca_plot, "shell_command_v")]
                return []

            with mock.patch.dict("os.environ", {"ORCA_HOME": "", "PATH": ""}, clear=False), mock.patch(
                "orca_viz.orca_runtime.shutil.which",
                side_effect=fake_which,
            ), mock.patch(
                "orca_viz.orca_runtime._load_login_shell_orca_env",
                return_value={"SHELL": "/bin/bash", "PATH": str(plot_dir)},
            ), mock.patch(
                "orca_viz.orca_runtime._shell_lookup_candidates",
                side_effect=fake_shell_lookup,
            ), mock.patch("orca_viz.orca_runtime._common_orca_directories", return_value=[]):
                resolution = resolve_orca_tool_details("orca_plot")

            self.assertEqual(resolution.path, str(orca_plot.resolve()))
            self.assertEqual(resolution.resolved_via, "shell_command_v")

    def test_common_directory_scan_can_find_install_directly_under_home(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_home = Path(temp_dir)
            install_dir = fake_home / "orca_6_1_0"
            install_dir.mkdir()
            orca = install_dir / _tool_file_name("orca")
            orca_plot = install_dir / _tool_file_name("orca_plot")
            _write_executable(orca)
            _write_executable(orca_plot)

            with mock.patch.dict("os.environ", {"ORCA_HOME": "", "PATH": ""}, clear=False), mock.patch(
                "orca_viz.orca_runtime.shutil.which",
                return_value=None,
            ), mock.patch(
                "orca_viz.orca_runtime._load_login_shell_orca_env",
                return_value={},
            ), mock.patch(
                "orca_viz.orca_runtime._shell_lookup_candidates",
                return_value=[],
            ), mock.patch(
                "orca_viz.orca_runtime.Path.home",
                return_value=fake_home,
            ):
                resolution = resolve_orca_tool_details("orca_plot")

            self.assertEqual(resolution.path, str(orca_plot.resolve()))
            self.assertIn(resolution.resolved_via, {"common_dir_scan", "orca_anchor_sibling"})

    def test_path_hint_takes_priority_and_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            hinted_dir = Path(temp_dir) / "hinted"
            path_dir = Path(temp_dir) / "path"
            hinted_dir.mkdir()
            path_dir.mkdir()
            hinted_plot = hinted_dir / _tool_file_name("orca_plot")
            path_plot = path_dir / _tool_file_name("orca_plot")
            _write_executable(hinted_plot)
            _write_executable(path_plot)

            with mock.patch.dict("os.environ", {"ORCA_HOME": "", "PATH": str(path_dir)}, clear=False), mock.patch(
                "orca_viz.orca_runtime.shutil.which",
                return_value=str(path_plot),
            ), mock.patch(
                "orca_viz.orca_runtime._load_login_shell_orca_env",
                return_value={"SHELL": "/bin/bash", "PATH": str(path_dir)},
            ), mock.patch(
                "orca_viz.orca_runtime._shell_lookup_candidates",
                return_value=[],
            ), mock.patch("orca_viz.orca_runtime._common_orca_directories", return_value=[]):
                resolution = resolve_orca_tool_details("orca_plot", path_hint=str(hinted_dir))

            self.assertEqual(resolution.path, str(hinted_plot.resolve()))
            self.assertEqual(resolution.resolved_via, "path_hint_dir")

    def test_missing_tool_reports_failure_reason_and_debug_paths(self) -> None:
        with mock.patch.dict("os.environ", {"ORCA_HOME": "", "PATH": "/usr/local/bin"}, clear=False), mock.patch(
            "orca_viz.orca_runtime.shutil.which",
            return_value=None,
        ), mock.patch(
            "orca_viz.orca_runtime._load_login_shell_orca_env",
            return_value={
                "SHELL": "/bin/bash",
                "PATH": "/home/wls/orca_6_1_0:/opt/orca/bin",
                "LOGIN_SHELL_PATH": "/opt/orca/bin",
                "INTERACTIVE_SHELL_PATH": "/home/wls/orca_6_1_0:/opt/orca/bin",
            },
        ), mock.patch(
            "orca_viz.orca_runtime._shell_lookup_candidates",
            return_value=[],
        ), mock.patch("orca_viz.orca_runtime._common_orca_directories", return_value=[]):
            report = detect_orca_environment(
                tool_specs=[runtime.OrcaToolSpec("orca_plot", "orca_plot", "gbw_cube", "plot", required=True)]
            )

        tool = report.tools[0]
        self.assertFalse(tool.available)
        self.assertIsNotNone(tool.failure_reason)
        self.assertEqual(report.process_path, "/usr/local/bin")
        self.assertEqual(report.shell_path, "/home/wls/orca_6_1_0:/opt/orca/bin")
        self.assertEqual(report.shell_executable, "/bin/bash")
        self.assertEqual(report.login_shell_path, "/opt/orca/bin")
        self.assertEqual(report.interactive_shell_path, "/home/wls/orca_6_1_0:/opt/orca/bin")

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
