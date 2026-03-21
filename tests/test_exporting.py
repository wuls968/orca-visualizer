import unittest

import plotly.graph_objects as go

from orca_viz.exporting import apply_export_preset, normalized_export_file_name


class ExportingTests(unittest.TestCase):
    def test_normalized_export_file_name_includes_preset(self) -> None:
        self.assertEqual(
            normalized_export_file_name("spectrum", "paper", "png"),
            "spectrum_paper.png",
        )

    def test_apply_export_preset_applies_dimensions_and_fonts(self) -> None:
        figure = go.Figure(data=[go.Scatter(x=[0, 1], y=[0, 1])])
        exported = apply_export_preset(
            figure,
            preset_key="presentation",
            width=1800,
            height=1000,
            font_size=20,
            title_size=28,
        )
        self.assertEqual(exported.layout.width, 1800)
        self.assertEqual(exported.layout.height, 1000)
        self.assertEqual(exported.layout.font.size, 20)
        self.assertEqual(exported.layout.title.font.size, 28)


if __name__ == "__main__":
    unittest.main()
