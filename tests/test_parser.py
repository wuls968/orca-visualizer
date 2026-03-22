from pathlib import Path
import tempfile
import unittest

from orca_viz.cube import parse_cube_file
from orca_viz.parser import parse_orca_content, parse_orca_file


class ParserTests(unittest.TestCase):
    def test_sample_output_can_be_parsed(self) -> None:
        sample = Path(__file__).resolve().parents[1] / "sample_data" / "orca_sample.out"
        result = parse_orca_file(sample)

        self.assertEqual(result.metadata.get("termination"), "normal")
        self.assertAlmostEqual(result.total_energy_hartree, -76.34567890)
        self.assertEqual(len(result.energies_hartree), 2)
        self.assertEqual(len(result.frequencies_cm1), 3)
        self.assertEqual(len(result.imaginary_frequencies), 1)
        self.assertEqual(result.atom_count, 3)
        self.assertEqual(len(result.normal_modes), 3)
        self.assertEqual(result.normal_modes[0].shape, (3, 3))
        self.assertAlmostEqual(result.normal_modes[0][0, 0], -0.1)
        self.assertFalse(result.mulliken_charges.empty)
        self.assertFalse(result.loewdin_charges.empty)
        self.assertEqual(len(result.excited_states), 3)
        self.assertEqual(len(result.irc_points), 3)
        self.assertEqual(len(result.neb_points), 4)
        self.assertEqual(result.transition_state_info.get("status"), "confirmed_ts")
        self.assertAlmostEqual(
            result.transition_state_info.get("lowest_imaginary_frequency_cm^-1"), -123.45
        )
        self.assertEqual(result.transition_state_info.get("ts_mode_number"), 0)
        self.assertEqual(result.transition_state_info.get("ts_active_atoms"), [1, 2, 3])
        self.assertAlmostEqual(
            result.thermochemistry.get("gibbs_free_energy_hartree"), -76.10900000
        )
        self.assertAlmostEqual(result.thermochemistry.get("temperature_k"), 298.15)

    def test_sample_cube_can_be_parsed(self) -> None:
        sample = Path(__file__).resolve().parents[1] / "sample_data" / "orbital_sample.cube"
        cube = parse_cube_file(sample)

        self.assertEqual(cube.atom_count, 2)
        self.assertEqual(cube.grid_shape, (2, 2, 2))
        self.assertEqual(cube.voxel_count, 8)
        self.assertAlmostEqual(cube.values[0, 0, 0], -0.1)
        self.assertAlmostEqual(cube.value_range[1], 0.12)

    def test_relaxed_surface_scan_summary_can_be_parsed(self) -> None:
        raw_text = """
! RHF STO-3G TightSCF Opt
-------------------------   --------------------
FINAL SINGLE POINT ENERGY        -1.005106704791
-------------------------   --------------------
                   **** RELAXED SURFACE SCAN DONE ***

                    SUMMARY OF THE CALCULATED SURFACE

----------------------------
RELAXED SURFACE SCAN RESULTS
----------------------------

Column   1: NONAME

The Calculated Surface using the 'Actual Energy'
   0.60000000  -1.10112824
   0.80000000  -1.11085040
   1.00000000  -1.06610865
   1.20000000  -1.00510670

The Calculated Surface using the SCF energy
   0.60000000  -1.10112824
   0.80000000  -1.11085040
   1.00000000  -1.06610865
   1.20000000  -1.00510670

                             ****ORCA TERMINATED NORMALLY****
""".strip()
        result = parse_orca_content(raw_text, source_name="scan_test.out")

        self.assertEqual(len(result.scan_points), 4)
        self.assertEqual(list(result.scan_points["step"]), [1, 2, 3, 4])
        self.assertAlmostEqual(result.scan_points.iloc[1]["coordinate"], 0.8)
        self.assertAlmostEqual(result.scan_points.iloc[1]["energy_hartree"], -1.11085040)
        self.assertTrue(result.metadata.get("has_scan"))
        self.assertEqual(result.metadata.get("termination"), "normal")

    def test_irc_summary_with_extra_columns_and_repeated_header_can_be_parsed(self) -> None:
        raw_text = """
! B3LYP IRC
-----------------
IRC PATH SUMMARY
-----------------
 Step   Coord.     E(Eh)    dE(kcal/mol)
   0    -0.50   -76.200000     0.00
   1    -0.10   -76.230000   -18.83
 Step   Coord.     E(Eh)    dE(kcal/mol)
   2     0.00   -76.240000   -25.10
 Note: branch switches near the TS
   3     0.60   -76.210000    -6.27
""".strip()
        result = parse_orca_content(raw_text, source_name="irc_extra_cols.out")

        self.assertEqual(len(result.irc_points), 4)
        self.assertIn("branch_id", result.irc_points.columns)
        self.assertEqual(result.pathways["irc"].metadata.get("header_found"), True)
        self.assertAlmostEqual(result.irc_points.iloc[2]["coordinate"], 0.0)

    def test_transition_dipole_absorption_table_can_be_parsed(self) -> None:
        raw_text = """
                     ABSORPTION SPECTRUM VIA TRANSITION ELECTRIC DIPOLE MOMENTS
----------------------------------------------------------------------------------------------------
     Transition      Energy     Energy  Wavelength fosc(D2)      D2        DX        DY        DZ
                      (eV)      (cm-1)    (nm)                 (au**2)    (au)      (au)      (au)
----------------------------------------------------------------------------------------------------
  0-1A  ->  1-1A    8.000598   64529.2   155.0   0.021521974   0.10980   0.00000  -0.33136  -0.00000
  0-1A  ->  2-1A    9.819031   79195.8   126.3   0.069613546   0.28938   0.00000  -0.00000   0.53794
""".strip()
        result = parse_orca_content(raw_text, source_name="tddft_real_format.out")

        self.assertEqual(len(result.excited_states), 2)
        self.assertEqual(list(result.excited_states["state"]), [1, 2])
        self.assertAlmostEqual(result.excited_states.iloc[0]["energy_eV"], 8.000598)
        self.assertAlmostEqual(result.excited_states.iloc[1]["oscillator_strength"], 0.069613546)

    def test_orbital_energies_frontier_gap_can_be_parsed(self) -> None:
        raw_text = """
Program Version 6.1.0
----------------
ORBITAL ENERGIES
----------------

  NO   OCC          E(Eh)            E(eV)
   0   2.0000      -0.800000       -21.7691
   1   2.0000      -0.300000        -8.1634
   2   0.0000       0.050000         1.3606
   3   0.0000       0.100000         2.7211
""".strip()
        result = parse_orca_content(raw_text, source_name="orbital_gap.out")

        self.assertEqual(result.metadata.get("homo_index"), 1)
        self.assertEqual(result.metadata.get("lumo_index"), 2)
        self.assertAlmostEqual(result.metadata.get("homo_energy_hartree"), -0.3)
        self.assertAlmostEqual(result.metadata.get("lumo_energy_hartree"), 0.05)
        self.assertAlmostEqual(result.metadata.get("homo_lumo_gap_hartree"), 0.35)
        self.assertAlmostEqual(result.metadata.get("homo_lumo_gap_ev"), 9.5240, places=3)

    def test_real_style_neb_path_summary_is_detected_without_bang_input_line(self) -> None:
        raw_text = """
Program Version 6.1.0
%NEB
  Product "Product.xyz"
END

---------------------------------------------------------------
                         PATH SUMMARY
---------------------------------------------------------------
All forces in Eh/Bohr.

Image Dist.(Ang.)    E(Eh)   dE(kcal/mol)  max(|Fp|)  RMS(Fp)
  0     0.000    -425.22884      0.00       0.00024   0.00006
  1     1.518    -425.22528      2.23       0.00142   0.00041
  5     3.721    -425.19791     19.41       0.00199   0.00053 <= CI

---------------------------------------------------------------
                      PATH SUMMARY FOR NEB-TS
---------------------------------------------------------------
Image     E(Eh)   dE(kcal/mol)  max(|Fp|)  RMS(Fp)
  5    -425.19791    19.41       0.00199   0.00053 <= CI
 TS    -425.20678    13.85       0.00038   0.00007 <= TS
  6    -425.20519    14.84       0.00135   0.00049

                             ****ORCA TERMINATED NORMALLY****
""".strip()
        result = parse_orca_content(raw_text, source_name="real_neb_ts.out")

        self.assertFalse(result.neb_points.empty)
        self.assertTrue(result.metadata.get("has_neb"))
        self.assertIn("NEB", result.metadata.get("detected_job_markers", []))
        self.assertIn("distance_ang", result.neb_points.columns)
        self.assertIn("delta_energy_kcal_mol", result.neb_points.columns)
        self.assertIn("transition_state", set(result.neb_points["point_type"]))
        ts_row = result.neb_points[result.neb_points["point_type"] == "transition_state"].iloc[0]
        self.assertAlmostEqual(ts_row["energy_hartree"], -425.20678)

    def test_neb_log_and_interp_files_can_be_parsed_directly(self) -> None:
        neb_log = """
NEB log file generated by ORCA
iteration       : 0
distance        :   0.00000000    1.15903834    2.32101025
energy          : -425.22884470  -425.22158414  -425.20513895
>
iteration       : 1
distance        :   0.00000000    1.20349499    2.37503062
energy          : -425.22884470  -425.22284220  -425.20995663
""".strip()
        interp_text = """
Iteration: -1
Images: Distance  (Bohr), Energy (Eh)
0.0000   0.00000000      0.00000000
1.0000   2.00000000      0.01000000

Interp.: Distance  (Bohr), Energy (Eh)
0.0000   0.00000000      0.00000000
0.5000   1.00000000      0.00600000
1.0000   2.00000000      0.01000000
""".strip()

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            neb_log_path = root / "demo.NEB.log"
            interp_path = root / "demo.interp"
            neb_log_path.write_text(neb_log, encoding="utf-8")
            interp_path.write_text(interp_text, encoding="utf-8")

            neb_log_result = parse_orca_file(neb_log_path)
            interp_result = parse_orca_file(interp_path)

        self.assertEqual(neb_log_result.file_type, "neb_log")
        self.assertEqual(len(neb_log_result.neb_points), 3)
        self.assertIn("distance_bohr", neb_log_result.neb_points.columns)
        self.assertEqual(interp_result.file_type, "neb_interp")
        self.assertEqual(len(interp_result.neb_points), 3)
        self.assertEqual(interp_result.metadata.get("path_source"), "interp")
        self.assertEqual(interp_result.neb_points.iloc[1]["progress"], 0.5)

    def test_scan_block_with_extra_columns_and_notes_can_be_parsed(self) -> None:
        raw_text = """
! PBEh-3c Scan
RELAXED SURFACE SCAN RESULTS
Column   1: B(1,2)
The Calculated Surface using the 'Actual Energy'
 0.90   -113.550000   0.0008
 comment line that should be ignored
 1.10   -113.520000   0.0011
 1.30   -113.470000   0.0024
The Calculated Surface using the SCF energy
""".strip()
        result = parse_orca_content(raw_text, source_name="scan_notes.out")

        self.assertEqual(len(result.scan_points), 3)
        self.assertIn("surface_value", result.scan_points.columns)
        self.assertAlmostEqual(result.scan_points.iloc[0]["surface_value"], 0.0008)

    def test_keywords_without_valid_path_table_produce_specific_warning(self) -> None:
        raw_text = """
! B3LYP NEB
PATH SUMMARY FOR NEB-TS
Image   E(Eh)   dE(kcal/mol)
   bad   data   row
ORCA TERMINATED NORMALLY
""".strip()
        result = parse_orca_content(raw_text, source_name="broken_neb.out")

        self.assertTrue(result.neb_points.empty)
        self.assertTrue(any("NEB" in warning for warning in result.warnings))

    def test_multiframe_xyz_is_loaded_as_pathway(self) -> None:
        xyz_text = """
3
Frame 0 E = -76.100000
H 0.0 0.0 0.0
H 0.0 0.0 0.7
O 0.0 0.0 1.4
3
Frame 1 E = -76.050000
H 0.0 0.0 0.0
H 0.0 0.0 0.8
O 0.0 0.0 1.6
""".strip()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "demo_neb_trj.xyz"
            path.write_text(xyz_text, encoding="utf-8")
            result = parse_orca_file(path)

        self.assertEqual(result.file_type, "xyz_trajectory")
        self.assertIn("neb", result.pathways)
        self.assertEqual(result.pathways["neb"].frame_count, 2)
        self.assertEqual(len(result.neb_points), 2)
        self.assertAlmostEqual(result.neb_points.iloc[0]["energy_hartree"], -76.1)

    def test_output_and_trajectory_sidecar_are_merged(self) -> None:
        out_text = """
! wB97X-D4 NEB-TS
Optimization log-file .... demo.NEB.log
PATH SUMMARY FOR NEB-TS
Image     E(Eh)   dE(kcal/mol)
  0    -425.22884     0.00
 TS    -425.20678    13.85
  1    -425.20519    14.84
""".strip()
        xyz_text = """
2
Frame 0 E = -425.228840
H 0.0 0.0 0.0
H 0.0 0.0 0.7
2
Frame 1 E = -425.206780
H 0.0 0.0 0.0
H 0.0 0.0 0.8
""".strip()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            out_path = root / "ts.out"
            xyz_path = root / "demo_trj.xyz"
            out_path.write_text(out_text, encoding="utf-8")
            xyz_path.write_text(xyz_text, encoding="utf-8")

            result = parse_orca_file(out_path)

        self.assertIn("neb", result.pathways)
        self.assertTrue(result.pathways["neb"].has_frames)
        self.assertEqual(result.pathways["neb"].frame_count, 2)
        self.assertEqual(len(result.neb_points), 3)


if __name__ == "__main__":
    unittest.main()
