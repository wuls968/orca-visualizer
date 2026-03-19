from pathlib import Path
import unittest

from orca_viz.cube import parse_cube_file
from orca_viz.parser import parse_orca_file


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


if __name__ == "__main__":
    unittest.main()
