# Changelog

All notable changes to this project are documented here.

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
