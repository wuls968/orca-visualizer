from __future__ import annotations

import importlib.util
import subprocess
import sys

from .exporting import create_publication_ready_figure, export_plotly_figure
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


def _detect_static_export_support() -> bool:
    if importlib.util.find_spec("kaleido") is None:
        return False

    probe_code = (
        "import plotly.graph_objects as go, plotly.io as pio;"
        "fig = go.Figure(data=[go.Scatter(x=[0,1], y=[0,1])]);"
        "pio.to_image(fig, format='png', width=32, height=32, scale=1);"
        "print('ok')"
    )
    try:
        completed = subprocess.run(
            [sys.executable, "-c", probe_code],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except Exception:
        return False
    return completed.returncode == 0 and "ok" in completed.stdout


STATIC_IMAGE_EXPORT_AVAILABLE = _detect_static_export_support()

__all__ = [
    'STATIC_IMAGE_EXPORT_AVAILABLE',
    '_cube_render_budget',
    'atom_reference_dataframe',
    'build_structure_viewer_html',
    'build_vibration_mode_html',
    'charge_extrema_dataframe',
    'create_batch_energy_figure',
    'create_batch_excited_state_figure',
    'create_charge_3d_figure',
    'create_charge_figure',
    'create_cube_isosurface_figure',
    'create_cube_slice_figure',
    'create_energy_figure',
    'create_frequency_figure',
    'create_mode_magnitude_figure',
    'create_path_figure',
    'create_publication_ready_figure',
    'create_structure_figure',
    'create_uv_vis_figure',
    'create_vibration_mode_figure',
    'create_vibrational_density_figure',
    'export_plotly_figure',
    'measure_atom_angle',
    'measure_atom_dihedral',
    'measure_atom_distance',
    'structure_summary',
    'top_mode_atoms',
]
