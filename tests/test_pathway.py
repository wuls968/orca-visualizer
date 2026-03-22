import unittest

import pandas as pd
from ase import Atoms

from orca_viz.pathway import (
    PathFrame,
    PathwayResult,
    analyze_pathway,
    build_frame_point_mapping,
    build_path_display_dataframe,
)


class PathwayTests(unittest.TestCase):
    def test_energy_reference_modes(self) -> None:
        pathway = PathwayResult(
            kind="neb",
            points_df=pd.DataFrame(
                {
                    "image": [0, 1, 2],
                    "label": ["0", "1", "2"],
                    "energy_hartree": [-10.0, -9.9, -9.95],
                }
            ),
        )

        minimum_df = build_path_display_dataframe(pathway, reference_mode="minimum")
        first_df = build_path_display_dataframe(pathway, reference_mode="first")
        last_df = build_path_display_dataframe(pathway, reference_mode="last")
        selected_df = build_path_display_dataframe(
            pathway,
            reference_mode="selected",
            reference_selector="1",
        )

        self.assertAlmostEqual(minimum_df["reference_energy_hartree"].iloc[0], -10.0)
        self.assertAlmostEqual(first_df["reference_energy_hartree"].iloc[0], -10.0)
        self.assertAlmostEqual(last_df["reference_energy_hartree"].iloc[0], -9.95)
        self.assertAlmostEqual(selected_df["reference_energy_hartree"].iloc[0], -9.9)
        self.assertAlmostEqual(selected_df.iloc[0]["relative_energy_hartree"], -0.1)

    def test_pathway_analysis_reports_barriers_and_anomalies(self) -> None:
        pathway = PathwayResult(
            kind="irc",
            points_df=pd.DataFrame(
                {
                    "step": [0, 2, 2, 4],
                    "coordinate": [-0.5, -0.1, -0.1, 0.6],
                    "energy_hartree": [-10.1, -10.0, -9.95, -10.08],
                }
            ),
        )

        analysis = analyze_pathway(pathway)

        self.assertEqual(analysis["point_count"], 4)
        self.assertIn("duplicate_x", analysis["anomalies"])
        self.assertIn("step_gap", analysis["anomalies"])
        self.assertGreater(analysis["forward_barrier_kcal_mol"], 0.0)
        self.assertEqual(sorted(analysis["branch_ids"]), ["backward", "forward"])

    def test_build_frame_point_mapping_prefers_exact_frame_indices(self) -> None:
        atoms = Atoms("H2", positions=[(0.0, 0.0, 0.0), (0.0, 0.0, 0.74)])
        pathway = PathwayResult(
            kind="neb",
            points_df=pd.DataFrame(
                {
                    "frame_index": [0, 2, 4],
                    "image": [0, 1, 2],
                    "energy_hartree": [-1.0, -0.9, -0.95],
                }
            ),
            frames=[
                PathFrame(index=0, atoms=atoms.copy()),
                PathFrame(index=1, atoms=atoms.copy()),
                PathFrame(index=2, atoms=atoms.copy()),
                PathFrame(index=3, atoms=atoms.copy()),
                PathFrame(index=4, atoms=atoms.copy()),
            ],
        )

        frame_to_point, point_to_frame = build_frame_point_mapping(pathway)

        self.assertEqual(frame_to_point, [0, 0, 1, 1, 2])
        self.assertEqual(point_to_frame, {0: 0, 1: 2, 2: 4})


if __name__ == "__main__":
    unittest.main()
