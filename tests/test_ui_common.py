from __future__ import annotations

import unittest
from unittest.mock import patch

from orca_viz.ui.common import inject_app_styles


class TestUiCommon(unittest.TestCase):
    def test_inject_app_styles_renders_css_without_name_error(self) -> None:
        captured: dict[str, object] = {}

        def fake_markdown(body: str, unsafe_allow_html: bool = False) -> None:
            captured["body"] = body
            captured["unsafe"] = unsafe_allow_html

        with patch("orca_viz.ui.common.st.session_state", {"global-visual-style-preset": "scientific_standard"}):
            with patch("orca_viz.ui.common.st.markdown", side_effect=fake_markdown):
                inject_app_styles()

        body = captured.get("body", "")
        self.assertIsInstance(body, str)
        self.assertIn("<style>", body)
        self.assertIn(".stApp {", body)
        self.assertIn("background:", body)
        self.assertTrue(captured.get("unsafe"))


if __name__ == "__main__":
    unittest.main()
