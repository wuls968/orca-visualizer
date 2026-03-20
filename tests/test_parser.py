from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
