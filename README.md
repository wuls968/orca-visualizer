# ORCA Visualizer / ORCA 数据处理与可视化

Local visualization software for ORCA outputs, cube grids, and GBW-derived properties.

一个本地 ORCA 结果处理与可视化软件，基于 `Python + Streamlit + ASE + Plotly`，支持结构、频率、过渡态、光谱、cube、GBW 和后台驻留进程检测。

## Chinese

### 功能

- 读取 `.out`、`.log`、`.txt`、`.xyz`、`.cube`、`.gbw`
- 解析总能量、优化过程能量曲线、频率、虚频、TDDFT 光谱、IRC、NEB、过渡态和热化学量
- 显示结构 3D 视图，支持球棍、空间填充、棒状、线框
- 支持振动模式动画，播放时可调整视角
- 显示 Mulliken / Loewdin 电荷的 2D 和 3D 分布
- 可视化 cube 切片、等值面、ESP 和前线轨道
- 使用 GBW + `orca_plot` 生成电子密度、自旋密度、ESP、HOMO/LUMO 和指定轨道 cube
- 检测后台驻留进程，标记 ORCA / Python / Streamlit 的长时间高占用任务
- 支持中英文界面切换
- 支持主要图表导出为高分辨率 `PNG / SVG / PDF`

### 目录

- [app.py](app.py)
  Streamlit 主界面
- [orca_viz/parser.py](orca_viz/parser.py)
  ORCA 输出解析
- [orca_viz/cube.py](orca_viz/cube.py)
  cube 文件读取与网格采样
- [orca_viz/gbw.py](orca_viz/gbw.py)
  GBW sidecar 检测、`orca_plot` 查找与 cube 生成
- [orca_viz/visualization.py](orca_viz/visualization.py)
  结构、谱图、路径、振动模式和 cube 可视化
- [orca_viz/process_monitor.py](orca_viz/process_monitor.py)
  跨平台后台驻留进程检测
- [tests](tests)
  单元测试

### 环境要求

- macOS / Ubuntu / Linux / Windows 10+
- Python 3.10 及以上
- 如果使用 GBW 生成功能，需要安装 ORCA，并且能访问 `orca_plot`

### 安装

```bash
git clone <your-repo-url>
cd orca-visualizer
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 启动

通用方式:

```bash
python -m streamlit run app.py
```

也可以直接使用脚本:

- macOS: [run_app.command](run_app.command)
- Linux: [run_app.sh](run_app.sh)
- Windows CMD: [run_app.bat](run_app.bat)
- Windows PowerShell: [run_app.ps1](run_app.ps1)

### GBW 说明

对于 `.gbw` 文件，推荐同时准备这些同名 sidecar：

- `.densities`
- `.densitiesinfo`
- `.property.txt`
- `.xyz`
- `.out` 或 `.log`

程序会尽量自动寻找 `orca_plot`。如果自动检测失败，可以在界面里手动填 ORCA 安装目录或 `orca_plot` 路径。

### 后台监控

- 侧边栏新增“后台监控”模式
- 会扫描当前用户的后台进程
- 会标记 `ORCA / Python / Streamlit / 长时间高占用 / 驻留任务`
- 默认只检测，不自动结束任何进程

### 测试

```bash
python -m compileall -q app.py orca_viz tests
python -m unittest discover -s tests
```

### GitHub Actions

仓库包含跨平台 CI：

- Ubuntu
- macOS
- Windows
- Python 3.10 / 3.11 / 3.12

工作流文件在 [.github/workflows/ci.yml](.github/workflows/ci.yml)。

## English

### Features

- Reads `.out`, `.log`, `.txt`, `.xyz`, `.cube`, and `.gbw`
- Parses total energy, optimization energy trajectory, frequencies, imaginary modes, TDDFT spectra, IRC, NEB, transition states, and thermochemistry
- Displays 3D molecular structures with ball-and-stick, space-filling, stick, and wireframe models
- Plays vibrational mode animations while keeping camera interaction usable
- Shows Mulliken / Loewdin charge distributions in both 2D and 3D
- Visualizes cube slices, isosurfaces, ESP, and frontier orbitals
- Generates electron density, spin density, ESP, HOMO/LUMO, and custom orbital cubes from GBW through `orca_plot`
- Detects resident background processes and flags long-running ORCA / Python / Streamlit jobs
- Supports Chinese / English UI switching
- Exports major figures as high-resolution `PNG / SVG / PDF`

### Project Layout

- [app.py](app.py)
  Main Streamlit app
- [orca_viz/parser.py](orca_viz/parser.py)
  ORCA output parser
- [orca_viz/cube.py](orca_viz/cube.py)
  cube reader and grid sampler
- [orca_viz/gbw.py](orca_viz/gbw.py)
  GBW sidecar discovery, `orca_plot` resolution, and cube generation
- [orca_viz/visualization.py](orca_viz/visualization.py)
  Structure, spectra, path, vibration, and cube visualization
- [orca_viz/process_monitor.py](orca_viz/process_monitor.py)
  Cross-platform background-process monitor
- [tests](tests)
  Unit tests

### Requirements

- macOS / Ubuntu / Linux / Windows 10+
- Python 3.10+
- ORCA and `orca_plot` if you want GBW-derived cube generation

### Installation

```bash
git clone <your-repo-url>
cd orca-visualizer
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### Launch

Generic launch:

```bash
python -m streamlit run app.py
```

Platform-specific launchers:

- macOS: [run_app.command](run_app.command)
- Linux: [run_app.sh](run_app.sh)
- Windows CMD: [run_app.bat](run_app.bat)
- Windows PowerShell: [run_app.ps1](run_app.ps1)

### GBW Notes

For `.gbw` workflows, these same-stem sidecar files are recommended:

- `.densities`
- `.densitiesinfo`
- `.property.txt`
- `.xyz`
- `.out` or `.log`

The app will try to auto-detect `orca_plot`. If that fails, provide the ORCA installation directory or the executable path manually in the UI.

### Background Monitor

- A dedicated `Background Monitor` mode is available in the sidebar
- It scans processes belonging to the current user
- It highlights `ORCA / Python / Streamlit / long-running / resident` jobs
- It does not terminate anything automatically

### Tests

```bash
python -m compileall -q app.py orca_viz tests
python -m unittest discover -s tests
```

### GitHub Actions

The repository includes cross-platform CI for:

- Ubuntu
- macOS
- Windows
- Python 3.10 / 3.11 / 3.12

Workflow file: [.github/workflows/ci.yml](.github/workflows/ci.yml)
