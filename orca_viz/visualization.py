from __future__ import annotations

from .exporting import (
    create_publication_ready_figure,
    export_plotly_figure,
    static_image_export_available,
)
from .plots.charges import charge_extrema_dataframe, create_charge_3d_figure, create_charge_figure
from .plots.cube import _cube_render_budget, create_cube_isosurface_figure, create_cube_slice_figure
from .plots.pathways import create_path_figure
from .plots.spectra import (
    create_batch_energy_figure,
    create_batch_excited_state_figure,
    create_energy_figure,
    create_frequency_figure,
    create_uv_vis_figure,
    create_vibrational_density_figure,
)
from .plots.structure import (
    atom_reference_dataframe,
    build_structure_viewer_html,
    build_vibration_mode_html,
    create_mode_magnitude_figure,
    create_structure_figure,
    create_vibration_mode_figure,
    measure_atom_angle,
    measure_atom_dihedral,
    measure_atom_distance,
    structure_summary,
    top_mode_atoms,
)


class _LazyBooleanProxy:
    def __bool__(self) -> bool:
        return static_image_export_available()

    def __repr__(self) -> str:
        return str(bool(self))


STATIC_IMAGE_EXPORT_AVAILABLE = _LazyBooleanProxy()

__all__ = [
    "STATIC_IMAGE_EXPORT_AVAILABLE",
    "_cube_render_budget",
    "atom_reference_dataframe",
    "build_structure_viewer_html",
    "build_vibration_mode_html",
    "charge_extrema_dataframe",
    "create_batch_energy_figure",
    "create_batch_excited_state_figure",
    "create_charge_3d_figure",
    "create_charge_figure",
    "create_cube_isosurface_figure",
    "create_cube_slice_figure",
    "create_energy_figure",
    "create_frequency_figure",
    "create_mode_magnitude_figure",
    "create_path_figure",
    "create_publication_ready_figure",
    "create_structure_figure",
    "create_uv_vis_figure",
    "create_vibration_mode_figure",
    "create_vibrational_density_figure",
    "export_plotly_figure",
    "measure_atom_angle",
    "measure_atom_dihedral",
    "measure_atom_distance",
    "static_image_export_available",
    "structure_summary",
    "top_mode_atoms",
]
