# Changelog

All notable changes to this project are documented here.

## [1.0.2] - 2026-03-23

### Fixed

- Extended local ORCA discovery for Ubuntu/Linux desktop sessions by combining login-shell PATH and interactive-shell PATH instead of relying on a single shell mode
- Added fallback support for installations exposed only from interactive shell startup files such as `.bashrc`
- Added lightweight home-directory root scanning so installs like `~/orca_6_1_0/orca` are discovered more reliably
- Reduced ORCA doctor / environment-page latency by delaying shell command fallback until normal PATH and directory scans fail, and by caching shell lookup results
- Expanded doctor diagnostics to show merged shell PATH, login-shell PATH, and interactive-shell PATH separately

### Validation

- Re-ran `python -m compileall -q app.py orca_viz tests`
- Re-ran `python -m unittest tests.test_orca_runtime`
- Re-ran `python -m unittest discover -s tests`
- Re-ran `python -m orca_viz.cli doctor --json`

## [1.0.1] - 2026-03-23

### Fixed

- Unified local ORCA tool discovery so the Environment Doctor, GBW page, and CLI doctor all use the same runtime backend
- Hardened local Linux / Ubuntu desktop detection for GUI-launched sessions where the Python process PATH differs from the login-shell PATH
- Added login-shell assisted lookup via `command -v`, `type -P`, and `type -a` so locally installed `orca_plot`, `orca_2json`, and sibling tools are detected more reliably
- Normalized discovered tool paths through `realpath` semantics so symlinked local installs resolve consistently
- Made user-provided ORCA path hints shared across pages so a manually supplied local install path is honored consistently in both the environment page and GBW workflows
- Added clearer local diagnostics for process PATH, shell PATH, detection source, and failure reason when a tool is missing

### Validation

- Re-ran `python -m compileall -q app.py orca_viz tests`
- Re-ran `python -m unittest tests.test_orca_runtime`
- Re-ran `python -m unittest discover -s tests`
- Re-ran `python -m orca_viz.cli doctor --json` to verify live local tool discovery output

## [1.0.0] - 2026-03-22

### Major Update

- Reworked the visualization styling direction from page-level themes into a figure-first color-scheme system focused on scientific output variety
- Added unified plotting color schemes that now propagate through 2D figures, 3D molecular views, cube rendering, animations, static exports, and video exports
- Fixed hydrogen visibility on light backgrounds by introducing explicit display colors and outlines instead of relying on pure white atom fills
- Tightened structure-viewer coloring so Plotly figures, the embedded 3D viewer, pathway animation, vibration animation, and exports inherit the same atom-color logic
- Continued hardening GBW, pathway, export, and structure workflows that were refactored in the previous release series
- Switched npm release management back to manual local publishing instead of GitHub-triggered automatic publication

### Validation

- Re-ran `python -m compileall -q app.py orca_viz tests`
- Re-ran `python -m unittest discover -s tests`
- Re-checked structure rendering and HTML viewer output for visible hydrogen atoms on light backgrounds
- Verified the package metadata version alignment for Python and npm packaging

## [0.3.1] - 2026-03-22

### Changed

- Published the first public npm package for `orca-visualizer`
- Switched the GitHub Actions npm workflow fully to Trusted Publishing mode
- Prepared the repository for token-free npm publication after package-level trusted publisher binding

### Validation

- Verified the first public `npm publish` locally for `orca-visualizer@0.3.0`
- Re-ran `npm pack --dry-run`
- Re-ran `python -m unittest discover -s tests`

## [0.3.0] - 2026-03-22

### Major Update

- Added an npm distribution wrapper so end users can install and launch ORCA Visualizer with `npm install -g orca-visualizer`
- Added a GitHub Actions workflow for automated npm publication on GitHub release publication
- Switched the npm publication workflow toward Trusted Publishing with GitHub OIDC instead of relying on a long-lived repository secret
- Updated the launcher path so packaged installs run the bundled `orca_viz/streamlit_app.py` entrypoint instead of relying on the repository-root `app.py`
- Added npm-oriented install guidance to the environment doctor and documentation while keeping the Python install path for developers
- Cleaned public-facing documentation to remove local desktop validation-bundle references and machine-specific paths

### Validation

- Verified `npm pack --dry-run` for the new npm package layout
- Re-ran `python -m unittest discover -s tests` after the packaging and launcher changes

## [0.2.0] - 2026-03-22

### Major Update

- Rebuilt the figure export system around separate 2D vs 3D export presets, preserving the current 3D camera / scene by default instead of resetting the view during export
- Added export modes for `Faithful Export` vs `Paper Export`, plus 3D view controls such as `current view`, `fit molecule`, `fit surface`, and `paper default`
- Added `HTML` export for interactive 3D delivery, alongside clearer `SVG / PDF` guidance for WebGL-backed figures
- Moved export details out of the Streamlit UI layer into a clearer backend so the export controls no longer carry rendering logic directly
- Tightened CLI and entrypoint consistency so `app.py` remains a thin compatibility wrapper while the packaged launcher uses the unified CLI path
- Consolidated ORCA executable detection around the shared runtime layer and improved ORCA version detection by probing the executable before falling back to path-name inference
- Reduced import-time side effects by making static-image export capability checks lazy instead of probing at module import
- Hardened several ORCA parser entry points against minor heading variations in frequency, charge, TDDFT, and IRC sections

### Validation

- Re-ran `python -m unittest discover -s tests` in the project virtual environment after the export/runtime cleanup
- Re-verified static PNG export, interactive HTML export, and current-view 3D export retention with local figures
- Re-verified GBW / cube workflows against local ORCA-installed test files on the desktop machine

## [0.1.1] - 2026-03-21

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
- Verified parser, path, spectrum, GBW-to-cube, and export workflows with local validation bundles

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
