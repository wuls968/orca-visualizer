from pathlib import Path
import json
import tempfile
import unittest

from orca_viz.gbw import (
    build_orca_plot_input,
    discover_gbw_sidecars,
    load_gbw_file,
    resolve_property_orbital_index,
)


class GbwTests(unittest.TestCase):
    def test_sidecar_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gbw = root / "demo.gbw"
            densities = root / "demo.densities"
            densitiesinfo = root / "demo.densitiesinfo"
            property_json = root / "demo.property.json"
            property_txt = root / "demo.property.txt"
            gbw.write_bytes(b"gbw")
            densities.write_bytes(b"dens")
            densitiesinfo.write_bytes(b"densinfo")
            property_json.write_text("{}")
            property_txt.write_text("properties")

            discovered = discover_gbw_sidecars(gbw)
            self.assertIn("densities", discovered)
            self.assertIn("densitiesinfo", discovered)
            self.assertIn("property_json", discovered)
            self.assertIn("property_txt", discovered)

            gbw_data = load_gbw_file(gbw)
            self.assertEqual(gbw_data.source_name, "demo.gbw")
            self.assertIn("densities", gbw_data.sidecars)
            self.assertEqual(gbw_data.warnings, [])

    def test_sidecar_discovery_can_fall_back_to_unique_out_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gbw = root / "demo.gbw"
            out_file = root / "ts.out"
            gbw.write_bytes(b"gbw")
            out_file.write_text("ORCA TERMINATED NORMALLY")

            discovered = discover_gbw_sidecars(gbw)
            self.assertEqual(discovered.get("out"), out_file.resolve())

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

    def test_property_json_takes_priority_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gbw = root / "demo.gbw"
            densities = root / "demo.densities"
            densitiesinfo = root / "demo.densitiesinfo"
            property_txt = root / "demo.property.txt"
            property_json = root / "demo.property.json"
            gbw.write_bytes(b"gbw")
            densities.write_bytes(b"dens")
            densitiesinfo.write_bytes(b"densinfo")
            property_txt.write_text(
                """
$Calculation_Status
   &version [&Type "String"] "6.0.0"
$End
$DFT_Energy
   &nAlphaEl [&Type "Integer"] 10
   &nBetaEl [&Type "Integer"] 10
$End
""".strip()
            )
            property_json.write_text(
                json.dumps(
                    {
                        "version": "6.1.1",
                        "nAlphaEl": 12,
                        "nBetaEl": 12,
                        "FinalEnergy": -123.456789,
                        "Converged": True,
                        "homo_index": 11,
                        "lumo_index": 12,
                    }
                )
            )

            gbw_data = load_gbw_file(gbw)
            property_summary = gbw_data.metadata["property_summary"]
            self.assertEqual(property_summary["version"], "6.1.1")
            self.assertEqual(property_summary["n_alpha"], 12)
            self.assertEqual(property_summary["n_beta"], 12)
            self.assertEqual(property_summary["homo_index"], 11)
            self.assertEqual(property_summary["lumo_index"], 12)
            self.assertTrue(property_summary["converged"])
            self.assertIn("property.json", gbw_data.metadata["property_summary_sources"])

    def test_property_json_frontier_energies_and_gap_are_exposed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gbw = root / "demo.gbw"
            property_json = root / "demo.property.json"
            gbw.write_bytes(b"gbw")
            property_json.write_text(
                json.dumps(
                    {
                        "n_alpha": 12,
                        "n_beta": 12,
                        "homo_index": 11,
                        "lumo_index": 12,
                        "homo_energy_ev": -5.43,
                        "lumo_energy_ev": -1.12,
                    }
                )
            )

            gbw_data = load_gbw_file(gbw)
            property_summary = gbw_data.metadata["property_summary"]
            self.assertAlmostEqual(property_summary["homo_energy_ev"], -5.43)
            self.assertAlmostEqual(property_summary["lumo_energy_ev"], -1.12)
            self.assertAlmostEqual(property_summary["homo_lumo_gap_ev"], 4.31)

    def test_out_sidecar_can_supply_frontier_gap_when_property_file_has_only_indices(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gbw = root / "demo.gbw"
            property_txt = root / "demo.property.txt"
            out_file = root / "demo.out"
            gbw.write_bytes(b"gbw")
            property_txt.write_text(
                """
$DFT_Energy
   &nAlphaEl [&Type "Integer"] 12
   &nBetaEl [&Type "Integer"] 12
$End
""".strip()
            )
            out_file.write_text(
                """
----------------
ORBITAL ENERGIES
----------------

  NO   OCC          E(Eh)            E(eV)
   0   2.0000      -0.800000       -21.7691
   1   2.0000      -0.300000        -8.1634
   2   0.0000       0.050000         1.3606
""".strip()
            )

            gbw_data = load_gbw_file(gbw)
            property_summary = gbw_data.metadata["property_summary"]
            self.assertEqual(property_summary["homo_index"], 11)
            self.assertEqual(property_summary["lumo_index"], 12)
            self.assertAlmostEqual(property_summary["homo_energy_hartree"], -0.3)
            self.assertAlmostEqual(property_summary["lumo_energy_hartree"], 0.05)
            self.assertAlmostEqual(property_summary["homo_lumo_gap_ev"], 9.5240, places=3)
            self.assertIn("out 轨道能量", gbw_data.metadata["property_summary_sources"])

    def test_resolve_property_orbital_index_returns_none_when_missing(self) -> None:
        summary = {"n_alpha": 8, "n_beta": 7}
        self.assertEqual(resolve_property_orbital_index(summary, "HOMO", operator=0), 7)
        self.assertEqual(resolve_property_orbital_index(summary, "LUMO", operator=0), 8)
        self.assertEqual(resolve_property_orbital_index(summary, "HOMO", operator=1), 6)
        self.assertEqual(resolve_property_orbital_index(summary, "LUMO", operator=1), 7)
        self.assertIsNone(resolve_property_orbital_index({}, "HOMO", operator=0))


if __name__ == "__main__":
    unittest.main()
