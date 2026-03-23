from pathlib import Path
import sys
import unittest

import pandas as pd
from ase import Atoms

from orca_viz.i18n import set_language
from orca_viz.pathway import PathFrame, PathwayResult
from orca_viz.plot_theme import figure_visual_style_key, model_size_preset, resolve_visual_style
from orca_viz.visualization import (
    STATIC_IMAGE_EXPORT_AVAILABLE,
    atom_reference_dataframe,
    build_pathway_animation_html,
    build_structure_viewer_html,
    charge_extrema_dataframe,
    create_charge_3d_figure,
    create_charge_figure,
    create_structure_figure,
    export_plotly_figure,
    measure_atom_angle,
    measure_atom_dihedral,
    measure_atom_distance,
)


class VisualizationTests(unittest.TestCase):
    def setUp(self) -> None:
        set_language("zh")
        self.atoms = Atoms(
            symbols=["C", "O", "H"],
            positions=[
                (0.0, 0.0, 0.0),
                (1.2, 0.0, 0.0),
                (-0.6, 0.9, 0.0),
            ],
        )
        self.charges = pd.DataFrame(
            {
                "index": [0, 1, 2],
                "element": ["C", "O", "H"],
                "charge": [-0.1234, -0.4567, 0.5801],
            }
        )

    def tearDown(self) -> None:
        set_language("zh")

    def test_charge_figures_can_be_built(self) -> None:
        bar = create_charge_figure(self.charges, "Demo charge")
        spatial = create_charge_3d_figure(self.atoms, self.charges, "Demo charge 3D")
        space_filling_charge = create_charge_3d_figure(
            self.atoms,
            self.charges,
            "Demo charge 3D space filling",
            representation="space_filling",
        )

        self.assertEqual(len(bar.data), 1)
        self.assertEqual(spatial.data[1].type, "scatter3d")
        self.assertEqual(spatial.layout.title.text, "Demo charge 3D")
        self.assertEqual(len(space_filling_charge.data), 1)

    def test_structure_representations_can_be_switched(self) -> None:
        ball_stick = create_structure_figure(self.atoms, representation="ball_stick")
        stick = create_structure_figure(self.atoms, representation="stick")
        space_filling = create_structure_figure(self.atoms, representation="space_filling")
        wireframe = create_structure_figure(self.atoms, representation="wireframe", show_atom_labels=True)

        ball_stick_atom_trace = next(trace for trace in ball_stick.data if trace.name == "_structure_atoms")
        stick_atom_trace = next(trace for trace in stick.data if trace.name == "_structure_atoms")
        ball_stick_bond_trace = next(trace for trace in ball_stick.data if trace.name == "_structure_bonds")
        stick_bond_trace = next(trace for trace in stick.data if trace.name == "_structure_bonds")

        self.assertGreaterEqual(len(ball_stick.data), 2)
        self.assertEqual(len(space_filling.data), 1)
        self.assertEqual(len(wireframe.data), 2)
        self.assertEqual(wireframe.data[-1].mode, "markers+text")
        self.assertGreater(ball_stick_atom_trace.marker.size[0], stick_atom_trace.marker.size[0])
        self.assertLess(ball_stick_bond_trace.line.width, stick_bond_trace.line.width)

    def test_model_size_presets_change_structure_sizes(self) -> None:
        compact = model_size_preset("compact")
        standard = model_size_preset("standard")
        presentation = model_size_preset("presentation")

        compact_figure = create_structure_figure(
            self.atoms,
            representation="ball_stick",
            model_size_settings=compact,
        )
        presentation_figure = create_structure_figure(
            self.atoms,
            representation="ball_stick",
            model_size_settings=presentation,
        )

        compact_atoms = next(trace for trace in compact_figure.data if trace.name == "_structure_atoms")
        compact_bonds = next(trace for trace in compact_figure.data if trace.name == "_structure_bonds")
        presentation_atoms = next(trace for trace in presentation_figure.data if trace.name == "_structure_atoms")
        presentation_bonds = next(trace for trace in presentation_figure.data if trace.name == "_structure_bonds")

        self.assertAlmostEqual(standard.sphere_scale, 0.30)
        self.assertAlmostEqual(standard.stick_radius, 0.20)
        self.assertGreater(presentation_atoms.marker.size[0], compact_atoms.marker.size[0])
        self.assertGreater(presentation_bonds.line.width, compact_bonds.line.width)

    def test_structure_measurement_overlay_can_be_built(self) -> None:
        measured = create_structure_figure(
            self.atoms,
            representation="ball_stick",
            measurement_atoms={"distance": [0, 1]},
        )
        self.assertGreaterEqual(len(measured.data), 4)
        self.assertEqual(measured.layout.clickmode, "event+select")
        atom_trace = next(trace for trace in measured.data if trace.name == "_structure_atoms")
        self.assertEqual(atom_trace.customdata[0][2], 0)
        self.assertTrue(any(trace.name == "_measurement_selection" for trace in measured.data))

    def test_structure_viewer_html_contains_3dmol_measurement_ui(self) -> None:
        html = build_structure_viewer_html(
            self.atoms,
            representation="ball_stick",
            show_atom_labels=True,
            enable_measurement=True,
            component_id="demo-viewer",
            model_size_settings=model_size_preset("presentation"),
        )

        self.assertIn("$3Dmol", html)
        self.assertIn("demo-viewer-viewer", html)
        self.assertIn("连续点选 2/3/4 个原子后会自动显示距离、键角和二面角", html)
        self.assertIn("data-action='undo'", html)
        self.assertIn('"radius": 0.22', html)
        self.assertIn('"scale": 0.33', html)

    def test_structure_viewer_html_uses_visible_hydrogen_color(self) -> None:
        html = build_structure_viewer_html(
            self.atoms,
            representation="ball_stick",
            component_id="scheme-viewer",
            visual_style_key="cobalt_amber",
        )

        self.assertIn("#dce3ec", html)
        self.assertIn("atom_colors", html)

    def test_pathway_animation_html_contains_controls_and_path_linkage(self) -> None:
        pathway = PathwayResult(
            kind="trajectory",
            points_df=pd.DataFrame(
                {
                    "frame_index": [0, 1],
                    "label": ["0", "1"],
                    "energy_hartree": [-10.0, -9.8],
                }
            ),
            frames=[
                PathFrame(index=0, atoms=self.atoms.copy(), label="0"),
                PathFrame(index=1, atoms=self.atoms.copy(), label="1"),
            ],
        )

        html = build_pathway_animation_html(
            pathway,
            display_df=pathway.points_df,
            path_x_col="frame_index",
            path_y_col="energy_hartree",
            path_title="Demo path",
            path_x_label="Frame",
            path_y_label="Energy",
            y_hover_format=".2f",
            y_suffix=" Eh",
            component_id="demo-path-animation",
        )

        self.assertIn("demo-path-animation-toggle", html)
        self.assertIn("demo-path-animation-slider", html)
        self.assertIn("plotly_click", html)
        self.assertIn("点击路径点可跳转到对应帧。", html)

    def test_non_default_visual_style_is_registered_on_structure_figure(self) -> None:
        figure = create_structure_figure(self.atoms, representation="ball_stick", visual_style_key="cobalt_amber")
        palette = resolve_visual_style("cobalt_amber").palette
        atom_trace = next(trace for trace in figure.data if trace.name == "_structure_atoms")

        self.assertEqual(figure_visual_style_key(figure), "cobalt_amber")
        self.assertEqual(figure.layout.paper_bgcolor, "#ffffff")
        self.assertEqual(atom_trace.marker.color[-1], palette["hydrogen_fill"])
        self.assertEqual(atom_trace.marker.line.color, palette["atom_outline"])

    def test_legacy_theme_alias_falls_back_to_neutral_scientific_scheme(self) -> None:
        self.assertEqual(resolve_visual_style("dark_mode").key, "scientific_standard")

    def test_structure_hover_is_translated_in_english(self) -> None:
        set_language("en")
        figure = create_structure_figure(self.atoms, representation="ball_stick", show_atom_labels=True)
        hovertemplate = figure.data[-1].hovertemplate

        self.assertIn("Atom:", hovertemplate)
        self.assertIn("Element:", hovertemplate)
        self.assertNotIn("原子", hovertemplate)
        self.assertNotIn("元素", hovertemplate)

    def test_charge_extrema_table(self) -> None:
        summary = charge_extrema_dataframe(self.atoms, self.charges, top_n=2)
        self.assertEqual(list(summary.columns), ["atom_label", "charge", "x", "y", "z", "charge_sign"])
        self.assertEqual(len(summary), 2)
        self.assertEqual(summary.iloc[0]["atom_label"], "H3")

    def test_atom_reference_and_measurements(self) -> None:
        reference = atom_reference_dataframe(self.atoms)
        self.assertEqual(list(reference["atom_label"]), ["C1", "O2", "H3"])
        self.assertAlmostEqual(measure_atom_distance(self.atoms, 0, 1), 1.2)
        self.assertAlmostEqual(measure_atom_angle(self.atoms, 1, 0, 2), 123.6900675, places=5)

        atoms_4 = Atoms(
            symbols=["C", "C", "C", "C"],
            positions=[
                (0.0, 0.0, 0.0),
                (1.0, 0.0, 0.0),
                (1.0, 1.0, 0.0),
                (1.0, 1.0, 1.0),
            ],
        )
        self.assertAlmostEqual(measure_atom_dihedral(atoms_4, 0, 1, 2, 3), 90.0, places=5)
        self.assertIsNone(measure_atom_distance(self.atoms, 0, 0))

    @unittest.skipIf(sys.platform.startswith("win"), "Windows CI skips backend static export integration tests")
    def test_static_image_export_when_available(self) -> None:
        if not STATIC_IMAGE_EXPORT_AVAILABLE:
            self.skipTest("kaleido not installed")
        image_bytes = export_plotly_figure(
            create_charge_figure(self.charges, "Demo charge"),
            image_format="png",
            width=800,
            height=600,
            scale=1,
        )
        self.assertGreater(len(image_bytes), 1000)


if __name__ == "__main__":
    unittest.main()
