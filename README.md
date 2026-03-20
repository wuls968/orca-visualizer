# ORCA Visualizer

Cross-platform ORCA post-processing and visualization software built with `Python`, `Streamlit`, `ASE`, and `Plotly`.

支持 `macOS / Ubuntu / Windows` 的 ORCA 结果处理与可视化软件，面向本地科研工作流，覆盖输出解析、结构显示、谱图、路径、cube、GBW 和后台驻留任务检测。

## Highlights

- Parse `.out`, `.log`, `.txt`, `.xyz`, `.cube`, and `.gbw`
- Visualize structures, frequencies, vibrational modes, TDDFT spectra, IRC / NEB / Scan paths, and atomic charges
- Generate electron density, spin density, ESP, HOMO/LUMO, and custom MO cubes from `GBW + orca_plot`
- Provide transition-state diagnostics and thermochemistry summaries
- Support Chinese / English UI switching
- Include a cross-platform background-process monitor for ORCA / Python / Streamlit jobs
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
- High-resolution figure export
- Bilingual UI

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

### 1. Clone the Repository

```bash
git clone https://github.com/wuls968/orca-visualizer.git
cd orca-visualizer
```

### 2. Create a Virtual Environment

macOS / Ubuntu:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Windows CMD:

```bat
py -3 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Run the App

Generic:

```bash
python -m streamlit run app.py
```

Platform launchers:

- macOS: [run_app.command](run_app.command)
- Ubuntu / Linux: [run_app.sh](run_app.sh)
- Windows CMD: [run_app.bat](run_app.bat)
- Windows PowerShell: [run_app.ps1](run_app.ps1)

## ORCA and GBW Notes

If you want GBW-derived density or orbital cubes, install ORCA and make sure `orca_plot` is available.

Recommended GBW sidecar files:

- `.densities`
- `.densitiesinfo`
- `.property.txt`
- `.xyz`
- `.out` or `.log`

The app tries to auto-detect `orca_plot`. If detection fails, provide the ORCA installation directory or executable path in the UI.

## Structure Viewer Notes

- The structure viewer is bundled locally in the repository, so it does not depend on an external CDN to render molecules.
- Direct picking works in the `Overview` and `Structure` tabs.
- Measurement logic is automatic:
  - select 2 atoms: distance
  - select 3 atoms: angle
  - select 4 atoms: dihedral
  - click a selected atom again: unselect it

## Sample Data

Built-in examples are available in:

- [sample_data](sample_data)

Additional real ORCA test cases generated during development are available on the desktop:

- `/Users/a0000/Desktop/orca_visualizer_test_cases`

## Testing

Run local verification with:

```bash
python -m compileall -q app.py orca_viz tests
python -m unittest discover -s tests
```

Current CI covers:

- Windows
- macOS
- Ubuntu
- Python 3.10 / 3.11 / 3.12

## Project Layout

- [app.py](app.py): Streamlit UI
- [orca_viz/parser.py](orca_viz/parser.py): ORCA output parsing
- [orca_viz/cube.py](orca_viz/cube.py): cube reading and sampling
- [orca_viz/gbw.py](orca_viz/gbw.py): GBW loading and `orca_plot` workflows
- [orca_viz/visualization.py](orca_viz/visualization.py): figures, 3D viewers, animations
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
- 后台驻留进程检测
- 中英文界面切换

### 启动方法

通用命令：

```bash
python -m streamlit run app.py
```

也可以直接双击或执行：

- [run_app.command](run_app.command)
- [run_app.sh](run_app.sh)
- [run_app.bat](run_app.bat)
- [run_app.ps1](run_app.ps1)

### GBW 注意事项

如果要从 `.gbw` 生成电子密度、ESP 或轨道 cube，建议准备同名：

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
