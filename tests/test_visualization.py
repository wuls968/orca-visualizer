from pathlib import Path
import unittest

import pandas as pd
from ase import Atoms

from orca_viz.i18n import set_language
from orca_viz.visualization import (
    STATIC_IMAGE_EXPORT_AVAILABLE,
    charge_extrema_dataframe,
    create_charge_3d_figure,
    create_charge_figure,
    create_structure_figure,
    export_plotly_figure,
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
        space_filling = create_structure_figure(self.atoms, representation="space_filling")
        wireframe = create_structure_figure(self.atoms, representation="wireframe", show_atom_labels=True)

        self.assertEqual(len(ball_stick.data), 2)
        self.assertEqual(len(space_filling.data), 1)
        self.assertEqual(len(wireframe.data), 2)
        self.assertEqual(wireframe.data[-1].mode, "markers+text")

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
