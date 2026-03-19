from pathlib import Path
import tempfile
import unittest

from orca_viz.gbw import build_orca_plot_input, discover_gbw_sidecars, load_gbw_file


class GbwTests(unittest.TestCase):
    def test_sidecar_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gbw = root / "demo.gbw"
            densities = root / "demo.densities"
            densitiesinfo = root / "demo.densitiesinfo"
            property_txt = root / "demo.property.txt"
            gbw.write_bytes(b"gbw")
            densities.write_bytes(b"dens")
            densitiesinfo.write_bytes(b"densinfo")
            property_txt.write_text("properties")

            discovered = discover_gbw_sidecars(gbw)
            self.assertIn("densities", discovered)
            self.assertIn("densitiesinfo", discovered)
            self.assertIn("property_txt", discovered)

            gbw_data = load_gbw_file(gbw)
            self.assertEqual(gbw_data.source_name, "demo.gbw")
            self.assertIn("densities", gbw_data.sidecars)
            self.assertEqual(gbw_data.warnings, [])

    def test_orca_plot_input_builders(self) -> None:
        electron = build_orca_plot_input("electron_density", grid_intervals=90)
        self.assertIn("1\n2\ny", electron)
        self.assertIn("\n4\n90\n", electron)
        self.assertTrue(electron.endswith("12\n"))

        spin = build_orca_plot_input("spin_density", grid_intervals=70)
        self.assertIn("1\n3\ny", spin)
        self.assertIn("\n4\n70\n", spin)

        esp = build_orca_plot_input(
            "electrostatic_potential", grid_intervals=80, density_name="demo.scfp"
        )
        self.assertIn("1\n43\ndemo.scfp", esp)

        orbital = build_orca_plot_input(
            "molecular_orbital", grid_intervals=60, orbital_index=12, operator=1
        )
        self.assertIn("2\n12\n3\n1", orbital)
        self.assertIn("\n4\n60\n", orbital)

    def test_property_summary_in_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gbw = root / "demo.gbw"
            densities = root / "demo.densities"
            densitiesinfo = root / "demo.densitiesinfo"
            property_txt = root / "demo.property.txt"
            gbw.write_bytes(b"gbw")
            densities.write_bytes(b"dens")
            densitiesinfo.write_bytes(b"densinfo")
            property_txt.write_text(
                """
$Calculation_Status
   &version [&Type "String"] "6.1.0"
$End
$Geometry
   &NAtoms [&Type "Integer"] 22
$End
$DFT_Energy
   &nAlphaEl [&Type "Integer"] 37
   &nBetaEl [&Type "Integer"] 37
   &nTotalEl [&Type "Integer"] 74
$End
$Single_Point_Data
   &FinalEnergy [&Type "Double"]      -4.2519790836293106e+02  "Final single point energy"
   &Converged [&Type "Boolean"] true
$End
""".strip()
            )

            gbw_data = load_gbw_file(gbw)
            property_summary = gbw_data.metadata["property_summary"]
            self.assertEqual(property_summary["version"], "6.1.0")
            self.assertEqual(property_summary["atom_count"], 22)
            self.assertEqual(property_summary["n_alpha"], 37)
            self.assertEqual(property_summary["homo_index"], 36)
            self.assertEqual(property_summary["lumo_index"], 37)
            self.assertTrue(property_summary["converged"])


if __name__ == "__main__":
    unittest.main()
