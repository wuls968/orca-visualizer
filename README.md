# ORCA Visualizer

Cross-platform ORCA post-processing and visualization software built with `Python`, `Streamlit`, `ASE`, and `Plotly`.

支持 `macOS / Ubuntu / Windows` 的 ORCA 结果处理与可视化软件，面向本地科研工作流，覆盖输出解析、结构显示、谱图、路径、cube、GBW 和后台驻留任务检测。

Important:

- For pure viewing of existing `.out / .log / .xyz / .cube` files, ORCA itself is not required.
- For `GBW -> cube`, local validation, and ORCA tool/environment checks, you should install ORCA on the same machine and make `orca` / `orca_plot` available.

## Highlights

- Parse `.out`, `.log`, `.txt`, `.xyz`, `.cube`, and `.gbw`
- Visualize structures, frequencies, vibrational modes, TDDFT spectra, IRC / NEB / Scan paths, and atomic charges
- Generate electron density, spin density, ESP, HOMO/LUMO, and custom MO cubes from `GBW + orca_plot`
- Provide transition-state diagnostics and thermochemistry summaries
- Support Chinese / English UI switching
- Include a cross-platform background-process monitor for ORCA / Python / Streamlit jobs
- Provide a card-based landing page and clearer upload-before/upload-after states
- Ship unified figure styling and export presets for `Paper / Presentation / Web`
- Provide separate 2D/3D export presets, faithful export, paper export, HTML export, and 3D view-aware export controls
- Show persistent task status for GBW density scanning and cube generation
- Offer an npm launcher so non-developer users can install and run the app more easily
- Run on `Windows`, `macOS`, and `Ubuntu/Linux` with launch scripts and CI coverage

## Platform Support

The repository is maintained for:

- `windows-latest`
- `macos-latest`
- `ubuntu-latest`
- Python `3.10`, `3.11`, `3.12`

This matrix is verified in GitHub Actions:
[.github/workflows/ci.yml](.github/workflows/ci.yml)

## Features

### ORCA Output Analysis

- Final energy and optimization energy trajectory
- Frequencies, imaginary modes, and vibrational density broadening
- Normal-mode animation
- TDDFT / TDA absorption spectra
- IRC / NEB / relaxed Scan pathway plots
- Transition-state diagnosis, TS mode, active atoms, Hessian summary, and thermochemistry
- Mulliken / Loewdin charges

### 3D Visualization

- Ball-and-stick, space-filling, stick, and wireframe structure views
- Direct atom picking for automatic `distance / angle / dihedral` measurements
- Charge-colored 3D molecular views
- Cube slice and isosurface rendering for density, ESP, and orbitals

### GBW Workflow

- Auto-detect `orca_plot` where possible
- Detect sidecar files such as `.densities`, `.densitiesinfo`, `.property.txt`, `.xyz`
- Generate:
  - electron density
  - spin density
  - electrostatic potential
  - HOMO / LUMO
  - custom molecular orbitals

### Utilities

- Background process monitor for resident ORCA / Python / Streamlit tasks
- High-resolution figure export with preset-based defaults
- Bilingual UI

### Export Presets

- `Paper`: larger canvas, tighter typography, vector-friendly defaults
- `Presentation`: 16:9 layout and larger labels for slide decks
- `Web`: lighter canvas for browser previews and screenshots

Export modes:

- `Faithful Export`: preserve the current figure as much as possible and only adjust size / scale / explicit toggles
- `Paper Export`: keep the current 2D/3D view while normalizing typography, margins, and background for publication use

3D-specific export controls:

- `current view`
- `fit molecule`
- `fit surface`
- `paper default`
- `hide axes / legend / colorbar`
- `tight crop / balanced margin`

Supported export targets:

- `PNG`
- `SVG`
- `PDF`
- `HTML` for interactive 3D delivery

## Screens and Data Types

### Single-File Mode

Supported inputs:

- `.out`
- `.log`
- `.txt`
- `.xyz`
- `.cube`
- `.gbw`

### Batch Mode

Use batch mode to compare multiple ORCA or cube files from:

- multiple uploaded files
- a local folder scanned recursively

## Quick Start

### 1. Install from npm

```bash
npm install -g orca-visualizer
orca-visualizer
orca-visualizer doctor
```

Or run without a global install:

```bash
npx orca-visualizer
```

Notes:

- The npm launcher expects local `Python 3.10 / 3.11 / 3.12`.
- The npm package does not bundle ORCA itself.
- To use `GBW -> cube`, `orca_plot`, or local ORCA validation workflows, install ORCA locally first.

### 2. Install from the Repository

If you prefer cloning the repository, or if you want a no-npm install path, use the bundled install scripts:

- macOS: double-click `install_app.command`, then `run_app.command`
- Ubuntu / Linux:

```bash
bash install_app.sh
bash run_app.sh
```

- Windows PowerShell:

```powershell
.\install_app.ps1
.\run_app.ps1
```

- Windows CMD:

```bat
install_app.bat
run_app.bat
```

The install scripts:

- create `.venv` automatically if needed
- upgrade `pip / setuptools / wheel`
- install the packaged app with `pip install .`
- keep the launch path short for non-developer users

Before using `GBW -> electron density / spin density / ESP / HOMO / LUMO` workflows, install ORCA locally first.
The app can read existing ORCA outputs without ORCA, but it cannot call `orca_plot` if ORCA is not installed on the machine.

### 3. Clone the Repository

```bash
git clone https://github.com/wuls968/orca-visualizer.git
cd orca-visualizer
```

### 4. Developer Install

For active development, use an editable install so source-code changes apply immediately.

macOS / Ubuntu:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements-dev.txt
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements-dev.txt
```

Windows CMD:

```bat
py -3 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements-dev.txt
```

Equivalent developer install command:

```bash
python -m pip install -e ".[dev]"
```

### 5. Run the App

Recommended:

```bash
orca-visualizer
orca-visualizer doctor
```

Developer-friendly:

```bash
python -m orca_viz.cli run
```

Compatibility entry:

```bash
python -m streamlit run app.py
```

The packaged launcher and npm wrapper both route through the same CLI entrypoint. `app.py` remains only as a thin compatibility wrapper.

Platform launchers:

- macOS: [run_app.command](run_app.command)
- Ubuntu / Linux: [run_app.sh](run_app.sh)
- Windows CMD: [run_app.bat](run_app.bat)
- Windows PowerShell: [run_app.ps1](run_app.ps1)

## Environment Doctor and ORCA Tool Detection

The app now includes a dedicated `Environment Doctor` mode in the sidebar.

It checks:

- Python runtime and package versions
- `ORCA_HOME`
- auto-detected ORCA version from installation paths
- version probing from the `orca` executable when possible, with path-based fallback
- whether key ORCA utilities are usable, including:
  - `orca`
  - `orca_plot`
  - `orca_2json`
  - `orca_2mkl`
  - `orca_mapspc`
  - `orca_vib`
  - `orca_pltvib`
  - `orca_nmrspectrum`

The same logic is available from the command line:

```bash
python -m orca_viz.cli doctor
python -m orca_viz.cli doctor --json

# after packaged install
orca-viz-doctor
orca-viz-doctor --json
```

When no manual path is provided, the detector searches:

- current-process `PATH`
- current-process `ORCA_HOME`
- login-shell `PATH` and `ORCA_HOME`
- common ORCA installation directories on Windows / macOS / Ubuntu

If ORCA is installed locally, this page is also the fastest way to confirm whether `orca`, `orca_plot`, and related tools are really callable by the app instead of only existing somewhere on disk.

## ORCA and GBW Notes

If you want GBW-derived density or orbital cubes, install ORCA and make sure `orca_plot` is available.

In practice this means:

- install ORCA locally on the machine where ORCA Visualizer runs
- ensure `orca` and `orca_plot` are reachable through `ORCA_HOME` or `PATH`
- then use the `Environment Doctor` page to verify detection before starting GBW workflows

Recommended GBW sidecar files:

- `.densities`
- `.densitiesinfo`
- `.property.json`
- `.property.txt`
- `.xyz`
- `.out` or `.log`

The app tries to auto-detect `orca_plot`. If detection fails, provide the ORCA installation directory or executable path in the UI.

## Export Notes

- 2D and 3D figures now use different default export sizes.
- 3D export keeps the current camera / scene by default instead of resetting to a generic view.
- `SVG` / `PDF` export is still useful for 2D figures, but Plotly WebGL-based 3D layers are typically rasterized there.
- For high-quality interactive 3D sharing or archival, prefer `HTML`.

## Structure Viewer Notes

- The structure viewer is bundled locally in the repository, so it does not depend on an external CDN to render molecules.
- Direct picking works in the `Overview` and `Structure` tabs.
- Measurement logic is automatic:
  - select 2 atoms: distance
  - select 3 atoms: angle
  - select 4 atoms: dihedral
  - click a selected atom again: unselect it

## Testing

Run local verification with:

```bash
python -m compileall -q app.py orca_viz tests
.venv/bin/python -m unittest discover -s tests
```

Current CI covers:

- Windows
- macOS
- Ubuntu
- Python 3.10 / 3.11 / 3.12

## Project Layout

- [app.py](app.py): thin compatibility wrapper for Streamlit launches from a source checkout
- [pyproject.toml](pyproject.toml): package metadata, runtime dependencies, and CLI entrypoints
- [orca_viz/parser.py](orca_viz/parser.py): ORCA output parsing
- [orca_viz/cube.py](orca_viz/cube.py): cube reading and sampling
- [orca_viz/gbw.py](orca_viz/gbw.py): GBW loading and `orca_plot` workflows
- [orca_viz/orca_runtime.py](orca_viz/orca_runtime.py): ORCA runtime and utility detection
- [orca_viz/streamlit_app.py](orca_viz/streamlit_app.py): packaged Streamlit app entrypoint used by the CLI launcher
- [orca_viz/cli.py](orca_viz/cli.py): CLI launch and environment-doctor commands
- [orca_viz/visualization.py](orca_viz/visualization.py): figures, 3D viewers, animations
- [orca_viz/plots](orca_viz/plots): split plotting modules for `structure / spectra / cube / charges / pathways`
- [orca_viz/plot_theme.py](orca_viz/plot_theme.py): shared scientific plot theme
- [orca_viz/exporting.py](orca_viz/exporting.py): preset-based export pipeline
- [orca_viz/ui](orca_viz/ui): page layer, UI components, export controls, and data-loading helpers
- [orca_viz/process_monitor.py](orca_viz/process_monitor.py): cross-platform process monitor
- [tests](tests): unit tests

## Changelog

See:

- [CHANGELOG.md](CHANGELOG.md)

## License

This project is released under the MIT License.

See:

- [LICENSE](LICENSE)

## 中文说明

### 适用平台

- Windows
- macOS
- Ubuntu / Linux
- Python 3.10 / 3.11 / 3.12

并通过 GitHub Actions 持续测试。

### 主要功能

- ORCA 输出解析：总能量、优化曲线、频率、虚频、TDDFT、IRC / NEB / Scan、过渡态、热化学
- 结构 3D 可视化：球棍、空间填充、棒状、线框
- 直接点原子自动测量：键长、键角、二面角
- 电荷 2D / 3D 分布
- cube 切片和等值面
- GBW + `orca_plot` 波函数后处理
- 环境检测：自动检查 `orca / orca_plot / orca_2json / orca_2mkl` 等工具可用性
- 后台驻留进程检测
- 中英文界面切换

### 启动方法

推荐命令：

```bash
orca-visualizer
orca-visualizer doctor
```

兼容的源码运行方式：

```bash
python -m streamlit run app.py
```

也可以直接双击或执行：

- [run_app.command](run_app.command)
- [run_app.sh](run_app.sh)
- [run_app.bat](run_app.bat)
- [run_app.ps1](run_app.ps1)

### GBW 注意事项

如果要从 `.gbw` 生成电子密度、ESP 或轨道 cube，请先在本机安装好 ORCA，并确保 `orca` / `orca_plot` 可以被软件检测到。建议同时准备同名：

- `.densities`
- `.densitiesinfo`
- `.property.txt`
- `.xyz`
- `.out/.log`

### 结构测量说明

- 选 2 个原子：显示键长
- 选 3 个原子：显示键角
- 选 4 个原子：显示二面角
- 再点一次已选原子：取消选中

### 更新记录

详见：

- [CHANGELOG.md](CHANGELOG.md)
