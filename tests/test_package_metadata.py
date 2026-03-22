from __future__ import annotations

import json
from pathlib import Path
import tomllib
import unittest

from orca_viz import cli


REPO_ROOT = Path(__file__).resolve().parents[1]


class PackageMetadataTests(unittest.TestCase):
    def test_python_and_npm_versions_match(self) -> None:
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        package_json = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))

        self.assertEqual(pyproject["project"]["version"], package_json["version"])

    def test_npm_package_exposes_launcher(self) -> None:
        package_json = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
        launcher_path = REPO_ROOT / package_json["bin"]["orca-visualizer"]

        self.assertTrue(launcher_path.exists())

    def test_cli_uses_packaged_streamlit_entrypoint(self) -> None:
        streamlit_entry = Path(cli.__file__).resolve().with_name("streamlit_app.py")
        self.assertTrue(streamlit_entry.exists())


if __name__ == "__main__":
    unittest.main()
