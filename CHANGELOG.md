# Changelog

All notable changes to this project are documented here.

## [Unreleased] - 2026-03-21

### Changed

- Added package metadata in `pyproject.toml`, CLI entrypoints, and separate end-user vs developer installation paths
- Added cross-platform install launchers `install_app.sh/.command/.ps1/.bat`
- Switched runtime launchers to install and run the packaged app instead of only raw dependency bootstrapping
- Added a dedicated Environment Doctor page for ORCA utility/plugin detection and install guidance
- Unified GBW `orca_plot` lookup with the shared ORCA runtime detection layer
- Refactored the Streamlit entrypoint into a thinner router and moved page/UI logic into `orca_viz/ui`
- Added a shared scientific figure theme in `orca_viz/plot_theme.py` and a preset-based export layer in `orca_viz/exporting.py`
- Split the former monolithic `orca_viz/visualization.py` implementation into `orca_viz/plots/structure.py`, `spectra.py`, `cube.py`, `charges.py`, and `pathways.py`, while keeping a compatibility export layer
- Reworked the single-file empty state into a clearer card-based landing page with stronger workflow guidance
- Unified the default styling of energy, frequency, vibrational, TDDFT, pathway, charge, and cube figures
- Upgraded figure export controls to `Paper / Presentation / Web` presets with normalized file names, font controls, and background controls
- Added persistent run-status panels for GBW density scanning and `orca_plot` cube generation
- Tuned 3D structure and isosurface defaults for cleaner screenshots and more stable scientific presentation

### Validation

- Re-ran local unit tests with the project virtual environment after the install/runtime refactor
- Generated new lightweight real-ORCA validation cases on `2026-03-21`
- Verified parser, path, spectrum, GBW-to-cube, and export workflows with the desktop bundle at `/Users/a0000/Desktop/orca_visualizer_test_cases/20260321_refactor_validation`

## [0.1.0] - 2026-03-20

### Added

- Cross-platform support for `Windows`, `macOS`, and `Ubuntu/Linux`
- GitHub Actions CI matrix for `windows-latest`, `macos-latest`, and `ubuntu-latest`
- Single-file and batch analysis workflows for ORCA and cube data
- ORCA parsing for:
  - energies
  - frequencies
  - TDDFT / TDA spectra
  - IRC / NEB / Scan pathways
  - transition-state diagnostics
  - thermochemistry
  - Mulliken / Loewdin charges
- GBW workflows with `orca_plot` auto-detection and cube generation
- Cube slice and isosurface visualization for density, ESP, and orbitals
- Background process monitor for resident ORCA / Python / Streamlit jobs
- Chinese / English UI toggle
- High-resolution figure export

### Improved

- ESP rendering with clearer positive/negative separation
- Frontier orbital rendering quality
- Charge-distribution 3D figures and export workflow
- Structure viewer with local bundled 3D rendering dependency
- Direct atom-picking measurements in 3D
- Automatic measurement results for distance, angle, and dihedral
- More realistic ball-and-stick rendering in the interactive structure viewer

### Documentation

- Reworked `README.md` for public GitHub use
- Added platform-specific setup and launch instructions
- Added project layout and testing instructions
- Added this `CHANGELOG.md`

### Testing

- Added and updated parser and visualization tests
- Verified with local unit tests and cross-platform CI
