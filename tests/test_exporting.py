import unittest

import plotly.graph_objects as go

from orca_viz.exporting import (
    EXPORT_PRESETS_2D,
    EXPORT_PRESETS_3D,
    apply_export_preset,
    export_presets_for_figure,
    normalized_export_file_name,
)


class ExportingTests(unittest.TestCase):
    def test_normalized_export_file_name_includes_profile_and_view_when_requested(self) -> None:
        self.assertEqual(
            normalized_export_file_name(
                "spectrum",
                "paper",
                "png",
                profile_key="paper",
                view_key="fit_surface",
            ),
            "spectrum_paper_fit_surface.png",
        )

    def test_export_presets_split_between_2d_and_3d(self) -> None:
        two_d = go.Figure(data=[go.Scatter(x=[0, 1], y=[0, 1])])
        three_d = go.Figure(data=[go.Scatter3d(x=[0, 1], y=[0, 1], z=[0, 1])])

        self.assertEqual(export_presets_for_figure(two_d), EXPORT_PRESETS_2D)
        self.assertEqual(export_presets_for_figure(three_d), EXPORT_PRESETS_3D)

    def test_apply_export_preset_preserves_existing_3d_camera_and_ranges_by_default(self) -> None:
        figure = go.Figure(data=[go.Scatter3d(x=[0, 1], y=[0, 1], z=[0, 1])])
        figure.update_layout(
            scene={
                "camera": {"eye": {"x": 2.0, "y": 1.1, "z": 0.9}},
                "xaxis": {"range": [-1, 3]},
                "yaxis": {"range": [-2, 2]},
                "zaxis": {"range": [0, 4]},
            }
        )

        exported = apply_export_preset(
            figure,
            preset_key="paper",
            profile_key="paper",
            width=1800,
            height=1800,
            hide_axes=False,
        )

        self.assertEqual(exported.layout.width, 1800)
        self.assertEqual(exported.layout.height, 1800)
        self.assertEqual(exported.layout.scene.camera.eye.x, 2.0)
        self.assertEqual(tuple(exported.layout.scene.xaxis.range), (-1, 3))
        self.assertEqual(tuple(exported.layout.scene.yaxis.range), (-2, 2))
        self.assertEqual(tuple(exported.layout.scene.zaxis.range), (0, 4))

    def test_apply_export_preset_can_fit_3d_figure_to_scatter_points(self) -> None:
        figure = go.Figure(
            data=[
                go.Scatter3d(
                    x=[0.0, 4.0],
                    y=[0.0, 1.0],
                    z=[0.0, 1.5],
                    mode="markers",
                    name="_structure_atoms",
                )
            ]
        )

        exported = apply_export_preset(
            figure,
            preset_key="paper",
            profile_key="faithful",
            view_mode="fit_molecule",
        )

        self.assertIsNotNone(exported.layout.scene.xaxis.range)
        self.assertGreater(exported.layout.scene.xaxis.range[1], 4.0)
        self.assertIsNotNone(exported.layout.scene.camera)

    def test_apply_export_preset_hides_axes_and_colorbar_when_requested(self) -> None:
        figure = go.Figure(
            data=[
                go.Scatter3d(
                    x=[0.0, 1.0],
                    y=[0.0, 1.0],
                    z=[0.0, 1.0],
                    mode="markers",
                    marker={"color": [0.1, 0.2], "colorscale": "Viridis", "showscale": True},
                )
            ]
        )

        exported = apply_export_preset(
            figure,
            preset_key="paper",
            hide_axes=True,
            hide_colorbar=True,
        )

        self.assertFalse(exported.layout.scene.xaxis.visible)
        self.assertFalse(exported.data[0].marker.showscale)


if __name__ == "__main__":
    unittest.main()
