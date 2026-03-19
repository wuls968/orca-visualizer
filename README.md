# ORCA 数据处理与可视化

本项目是一个基于 `Python + Streamlit + ASE + Plotly` 的本地可视化工具，用来分析 ORCA 计算输出，并显示结构、频率、光谱、过渡态、cube 网格和 gbw 派生密度信息。

项目目录：

- `app.py`
  Streamlit 主界面。
- `orca_viz/parser.py`
  ORCA 输出解析，包括能量、频率、过渡态、热化学、TDDFT、IRC、NEB、NORMAL MODES。
- `orca_viz/cube.py`
  cube 文件读取与网格采样。
- `orca_viz/gbw.py`
  gbw 工作流，负责 sidecar 检测、`orca_plot` 路径解析和 cube 生成。
- `orca_viz/visualization.py`
  Plotly 结构图、光谱图、路径图、振动模式 HTML 播放器等。
- `sample_data/`
  示例 ORCA 输出和 cube 文件。
- `tests/`
  单元测试。

## 当前功能

- 读取 `.out`、`.log`、`.txt`、`.xyz`、`.cube`、`.gbw`
- 解析总能量和优化过程能量曲线
- 显示最终结构 3D 视图
- 解析振动频率、虚频和 NORMAL MODES
- 播放振动模式动画，并支持拖动视角
- 解析 Mulliken / Loewdin 电荷
- 显示 Mulliken / Loewdin 的 3D 原子电荷分布
- 3D 结构支持球棍、空间填充、棒状和线框模型切换
- 解析 TDDFT 吸收光谱
- 解析 IRC / NEB 路径
- 识别过渡态并提取热化学量
- 批量比较多个 ORCA 文件
- 可视化 cube 等值面和切片
- 自动检测 `orca_plot`
- 扫描 gbw 可用 density 列表
- 使用 gbw + `orca_plot` 生成电子密度 / 自旋密度 / ESP cube
- 使用 gbw + `orca_plot` 生成 HOMO / LUMO / 指定分子轨道 cube
- 从 `.property.txt` 自动提取电子数、收敛状态和 HOMO/LUMO 建议值
- 主要图表支持高分辨率 PNG / SVG / PDF 导出
- ESP 与前线轨道采用专用 3D 渲染：ESP 红/蓝半透明分离，轨道正负相位独立显示

## 环境要求

- macOS / Linux
- Python 3.12 左右
- 建议使用项目自带虚拟环境 `.venv`

如果你要使用 gbw 生成功能，还需要：

- 已安装 ORCA
- 能访问 `orca_plot`，程序会优先自动检测
- 对电子密度 / 自旋密度 / ESP，通常还需要同名 `.densities` 和 `.densitiesinfo`
- 如果想自动推荐 HOMO / LUMO，建议同时提供同名 `.property.txt`

## 启动方法

```bash
cd /Users/a0000/Desktop/orca_visualizer
source .venv/bin/activate
streamlit run app.py
```

如果已经给 `run_app.command` 可执行权限，也可以直接双击它启动。

## 使用说明

### 单文件分析

支持上传或输入本地路径：

- ORCA 输出：`.out` `.log` `.txt`
- 结构文件：`.xyz`
- 网格文件：`.cube`
- 波函数文件：`.gbw`

侧边栏的“3D 视图”设置会同时影响：

- ORCA 结构总览
- 结构页 3D 分子
- cube 总览里的参考结构
- 电荷页 3D 电荷分布

### 频率与振动模式

- 在“频率”页可以查看频率柱状图和振动模式动画
- 可以选择不同模态和放大倍数
- 默认不显示红色位移方向线
- 现在支持播放时调整视角，松手后自动继续播放

### 电荷分布与图片导出

- 在“电荷”页除了柱状图，还会显示按原子电荷着色的 3D 结构图
- 红色偏正、蓝色偏负，球大小会随电荷绝对值增大
- 每个主要电荷图下方都带“论文级图片导出”折叠区
- 2D 图推荐导出 `SVG` 或高分辨率 `PNG`
- 3D WebGL 图推荐优先导出高分辨率 `PNG`

### 过渡态分析

如果输出是过渡态计算，程序会尽量提取：

- 最低虚频
- 虚频个数
- TS 模号
- Hessian 负本征值数
- TS-active-atoms
- ZPE、热能、焓、熵项、Gibbs 自由能

### GBW 分析

对于 `.gbw` 文件，软件会先检测同目录 sidecar：

- `.densities`
- `.densitiesinfo`
- `.property.txt`
- `.xyz`
- `.out` / `.log`

然后你可以在界面里填写：

- ORCA 安装目录，或 `orca_plot` 可执行文件路径
- 想生成的内容：电子密度 / 自旋密度 / ESP / HOMO / LUMO / 自定义 MO
- 网格分辨率

GBW 页面还会：

- 自动扫描可用 density 名称，例如 `basename.scfp`
- 在有 `.property.txt` 时显示 `n_alpha / n_beta / n_total / multiplicity / HOMO / LUMO`
- 在缺少 `.densitiesinfo` 时提前给出提示，避免直接跑进 ORCA 报错

生成的 cube 会自动进入现有 cube 可视化页面。

### Cube / ESP / 前线轨道

- 软件会自动识别当前 cube 是 `ESP / 分子轨道 / 电子密度 / 自旋密度`
- `ESP` 视图采用化学里更常见的约定：负静电势偏红，正静电势偏蓝，并使用半透明分离等势面
- `HOMO/LUMO` 这类轨道采用正负相位分离的双表面，减少颜色混杂
- 等值面页提供 `渲染质量 / 透明度 / 结构骨架` 控件，可以细调图像精细度

### 页面说明

当前界面里的主要页面都带有“说明”折叠块，里面会写清楚：

- 这个页面适合看什么
- 需要哪些输入文件或模块
- 没有对应数据时为什么会是空白

## 测试

运行测试：

```bash
cd /Users/a0000/Desktop/orca_visualizer
PYTHONPATH=/Users/a0000/Desktop/orca_visualizer .venv/bin/python -m unittest discover -s tests -v
```

## 备注

- 当前解析器优先支持常见 ORCA 输出格式，不同版本或特殊模板可能需要补规则
- `.densitiesinfo` 不是文本文件，不适合直接阅读
- gbw 不是通用文本格式，通常需要借助 ORCA 官方工具转换成 cube
- 如果页面启动报错，先检查 `.venv` 是否正常、`app.py` 是否能通过 `py_compile`
