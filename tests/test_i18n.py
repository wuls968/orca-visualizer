from __future__ import annotations

import unittest

from orca_viz.cube import cube_kind_label
from orca_viz.i18n import set_language, tr


class TestI18n(unittest.TestCase):
    def tearDown(self) -> None:
        set_language("zh")

    def test_translate_core_ui_text_to_english(self) -> None:
        set_language("en")
        self.assertEqual(tr("ORCA 数据处理与可视化"), "ORCA Processing and Visualization")
        self.assertEqual(tr("球棍"), "Ball-and-Stick")

    def test_cube_kind_label_follows_language(self) -> None:
        set_language("en")
        self.assertEqual(cube_kind_label("esp"), "ESP Electrostatic Potential")
        set_language("zh")
        self.assertEqual(cube_kind_label("esp"), "ESP 静电势")


if __name__ == "__main__":
    unittest.main()
