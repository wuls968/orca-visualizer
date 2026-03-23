import sys
import unittest
from unittest import mock

import plotly.graph_objects as go
import pandas as pd
from ase import Atoms

import orca_viz.exporting as exporting_module
from orca_viz.exporting import (
    EXPORT_PRESETS_2D,
    EXPORT_PRESETS_3D,
    apply_export_preset,
    export_pathway_animation,
    export_plotly_figure,
    export_presets_for_figure,
    available_video_formats,
    normalized_animation_file_name,
    normalized_export_file_name,
    static_image_export_available,
)
from orca_viz.pathway import PathFrame, PathwayResult
from orca_viz.plot_theme import model_size_preset
from orca_viz.plot_theme import resolve_visual_style


class ExportingTests(unittest.TestCase):
    def test_normalized_animation_file_name_is_consistent(self) -> None:
        self.assertEqual(
            normalized_animation_file_name("neb_ts", "paper", "mp4"),
            "neb_ts_path_paper.mp4",
        )

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

    def test_apply_export_preset_inherits_visual_style_from_figure_meta(self) -> None:
        figure = go.Figure(data=[go.Scatter(x=[0, 1], y=[0, 1])])
        figure.update_layout(meta={"orca_viz": {"visual_style_key": "monochrome_accent"}})
        expected = resolve_visual_style("monochrome_accent")

        exported = apply_export_preset(
            figure,
            preset_key="paper",
            profile_key="paper",
            width=1200,
            height=800,
        )

        self.assertEqual(exported.layout.paper_bgcolor, expected.palette["paper_bg"])
        self.assertEqual(exported.layout.font.color, expected.palette["text_primary"])

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

    def test_available_video_formats_includes_gif_when_static_export_is_available(self) -> None:
        formats = available_video_formats()
        if static_image_export_available():
            self.assertIn("gif", formats)
        else:
            self.assertEqual(formats, [])

    @unittest.skipIf(sys.platform.startswith("win"), "Windows CI skips backend animation export integration tests")
    def test_export_pathway_animation_can_render_gif(self) -> None:
        if not static_image_export_available():
            self.skipTest("Static export backend unavailable")
        if "gif" not in available_video_formats():
            self.skipTest("GIF animation export backend unavailable")

        frame_a = Atoms("H2", positions=[(0.0, 0.0, 0.0), (0.0, 0.0, 0.74)])
        frame_b = Atoms("H2", positions=[(0.0, 0.0, 0.0), (0.0, 0.08, 0.86)])
        pathway = PathwayResult(
            kind="trajectory",
            points_df=pd.DataFrame(
                {
                    "frame_index": [0, 1],
                    "label": ["0", "1"],
                    "energy_hartree": [-1.0000, -0.9965],
                }
            ),
            frames=[
                PathFrame(index=0, atoms=frame_a, label="0"),
                PathFrame(index=1, atoms=frame_b, label="1"),
            ],
        )

        gif_bytes = export_pathway_animation(
            pathway,
            display_df=pathway.points_df,
            path_x_col="frame_index",
            path_y_col="energy_hartree",
            path_title="Demo Path",
            path_x_label="Frame",
            path_y_label="Energy",
            y_hover_format=".4f",
            y_suffix=" Eh",
            video_format="gif",
            preset_key="web",
            width=960,
            height=720,
            fps=6,
            scale=1,
            model_size_settings=model_size_preset("presentation"),
        )

        self.assertIn(gif_bytes[:6], {b"GIF87a", b"GIF89a"})
        self.assertGreater(len(gif_bytes), 2000)

    def test_windows_static_export_requests_kaleido_shutdown(self) -> None:
        figure = go.Figure(data=[go.Scatter(x=[0, 1], y=[0, 1])])

        with mock.patch.object(exporting_module, "_plotly_to_image", return_value=b"png-bytes") as mocked_export:
            export_plotly_figure(figure, image_format="png", width=640, height=480, scale=1, _shutdown_kaleido=True)

        self.assertTrue(mocked_export.called)
        self.assertTrue(mocked_export.call_args.kwargs["shutdown_after"])


if __name__ == "__main__":
    unittest.main()
