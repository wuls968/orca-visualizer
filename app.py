from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
import tempfile
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from orca_viz import load_gbw_file, parse_cube_file, parse_orca_content, parse_orca_file
from orca_viz.cube import (
    CubeData,
    cube_kind_label,
    cube_sample_dataframe,
    suggest_cube_level_max,
    cube_summary_dataframe,
    suggest_cube_isovalue,
)
from orca_viz.gbw import (
    GbwData,
    generate_cube_from_gbw,
    list_available_densities,
    resolve_orca_plot,
)
from orca_viz.i18n import set_language, tr
from orca_viz.parser import OrcaParseResult, summarize_results
from orca_viz.visualization import (
    STATIC_IMAGE_EXPORT_AVAILABLE,
    build_vibration_mode_html,
    charge_extrema_dataframe,
    create_batch_energy_figure,
    create_batch_excited_state_figure,
    create_charge_figure,
    create_charge_3d_figure,
    create_cube_isosurface_figure,
    create_cube_slice_figure,
    create_energy_figure,
    create_frequency_figure,
    create_mode_magnitude_figure,
    create_path_figure,
    create_structure_figure,
    create_uv_vis_figure,
    create_vibrational_density_figure,
    export_plotly_figure,
    structure_summary,
    top_mode_atoms,
)


st.set_page_config(page_title="ORCA Visualizer", layout="wide")


def main() -> None:
    with st.sidebar:
        language_enabled = st.toggle(
            "English / 中文",
            value=st.session_state.get("ui_language", "zh") == "en",
            help=tr("一键切换界面中英文。"),
        )
    language = "en" if language_enabled else "zh"
    st.session_state["ui_language"] = language
    set_language(language)

    st.title(tr("ORCA 数据处理与可视化"))
    st.caption(tr("支持 ORCA 输出、TDDFT 光谱、IRC/NEB 路径、批量比较和 cube 轨道可视化"))

    with st.sidebar:
        mode_options = {
            tr("单文件分析"): "single",
            tr("批量比较"): "batch",
        }
        mode = st.radio(tr("分析模式"), list(mode_options), index=0)
        st.divider()
        st.markdown(
            tr(
                "支持文件：`out` `log` `txt` `xyz` `cube`\n\n单文件模式额外支持 `gbw`。\n\n批量模式可直接读取整个文件夹。"
            )
        )
        st.divider()
        st.subheader(tr("3D 视图"))
        representation_options = [
            tr("球棍"),
            tr("空间填充"),
            tr("棒状"),
            tr("线框"),
        ]
        st.selectbox(
            tr("分子模型"),
            representation_options,
            index=0,
            key="global-structure-representation",
        )
        st.checkbox(tr("显示原子标签"), value=False, key="global-structure-labels")

    if mode_options[mode] == "single":
        _render_single_mode()
    else:
        _render_batch_mode()


def _render_single_mode() -> None:
    with st.sidebar:
        st.subheader(tr("单文件输入"))
        uploaded_file = st.file_uploader(
            tr("上传单个文件"),
            type=["out", "log", "xyz", "txt", "cube", "gbw"],
            accept_multiple_files=False,
            key="single_file",
        )
        local_path = st.text_input(tr("或输入本地文件路径"), key="single_path")
        gbw_sidecar_uploads = st.file_uploader(
            tr("GBW 可选：上传 sidecar 文件"),
            type=["densities", "densitiesinfo", "xyz", "out", "log", "txt"],
            accept_multiple_files=True,
            key="single_gbw_sidecars",
        )

    loaded = _load_single_input(uploaded_file, local_path, gbw_sidecar_uploads)
    if loaded is None:
        st.info(tr("请先上传一个 ORCA 输出、XYZ、cube 或 gbw 文件。"))
        _render_feature_preview()
        return

    data, data_type = loaded
    if data_type == "cube":
        _render_cube_analysis(data)
    elif data_type == "gbw":
        _render_gbw_analysis(data)
    else:
        _render_orca_analysis(data)


def _render_batch_mode() -> None:
    _render_page_note(
        tr("批量比较说明"),
        [
            tr("适合比较多个 `.out/.log/.txt/.xyz/.cube` 文件的能量、频率和激发态信息。"),
            tr("如果输入文件夹，程序会递归扫描常见 ORCA 和 cube 文件。"),
        ],
    )
    with st.sidebar:
        st.subheader(tr("批量输入"))
        uploaded_files = st.file_uploader(
            tr("上传多个文件"),
            type=["out", "log", "xyz", "txt", "cube"],
            accept_multiple_files=True,
            key="batch_files",
        )
        folder_path = st.text_input(tr("或输入本地文件夹路径"), key="batch_folder")

    loaded_items = _load_batch_inputs(uploaded_files, folder_path)
    if not loaded_items:
        st.info(tr("请上传多个文件，或输入一个包含 ORCA/cube 文件的文件夹。"))
        return

    orca_results = [item for item in loaded_items if isinstance(item, OrcaParseResult)]
    cube_results = [item for item in loaded_items if isinstance(item, CubeData)]

    if orca_results:
        summary_df = summarize_results(orca_results)
        st.subheader(tr("ORCA 批量比较"))
        st.dataframe(summary_df, hide_index=True, use_container_width=True)
        left, right = st.columns(2)
        with left:
            st.plotly_chart(
                create_batch_energy_figure(summary_df),
                use_container_width=True,
                key="batch-energy-chart",
            )
        with right:
            st.plotly_chart(
                create_batch_excited_state_figure(summary_df),
                use_container_width=True,
                key="batch-excited-state-chart",
            )
        _download_dataframe(tr("下载 ORCA 汇总 CSV"), summary_df, "orca_batch_summary.csv")
    else:
        st.info(tr("当前批量输入中没有可比较的 ORCA 输出文件。"))

    if cube_results:
        st.subheader(tr("Cube 文件汇总"))
        cube_summary = pd.DataFrame(
            {
                "file": [cube.source_name for cube in cube_results],
                "atoms": [cube.atom_count for cube in cube_results],
                "grid": [f"{cube.grid_shape[0]}x{cube.grid_shape[1]}x{cube.grid_shape[2]}" for cube in cube_results],
                "voxels": [cube.voxel_count for cube in cube_results],
                "min_value": [cube.value_range[0] for cube in cube_results],
                "max_value": [cube.value_range[1] for cube in cube_results],
            }
        )
        st.dataframe(cube_summary, hide_index=True, use_container_width=True)
        _download_dataframe(tr("下载 cube 汇总 CSV"), cube_summary, "cube_batch_summary.csv")


def _render_orca_analysis(result: OrcaParseResult) -> None:
    base_key = _slug_key(result.source_name)
    structure_representation, show_atom_labels = _get_structure_view_settings()
    _render_page_note(
        tr("ORCA 输出说明"),
        [
            tr("推荐输入完整 `.out/.log/.txt` 输出；如果只有 `.xyz`，则只能显示结构。"),
            tr("频率页需要 `VIBRATIONAL FREQUENCIES` 和 `NORMAL MODES`，谱图页需要 TDDFT/TDA 表。"),
            tr("路径、电荷和过渡态页会按文件里实际存在的模块自动显示。"),
        ],
    )
    for warning in result.warnings:
        st.warning(warning)

    summary_cols = st.columns(6)
    summary_cols[0].metric(tr("文件"), result.source_name)
    summary_cols[1].metric(tr("原子数"), result.atom_count)
    summary_cols[2].metric(tr("总能量 (Eh)"), _format_float(result.total_energy_hartree))
    summary_cols[3].metric(tr("虚频数"), len(result.imaginary_frequencies))
    summary_cols[4].metric(tr("激发态数"), len(result.excited_states))
    summary_cols[5].metric(tr("TS 状态"), _ts_status_label(result.transition_state_info.get("status")))

    if result.metadata:
        with st.expander(tr("运行信息"), expanded=False):
            st.json(result.metadata)

    tabs = st.tabs(
        [
            tr("总览"),
            tr("结构"),
            tr("能量"),
            tr("频率"),
            tr("谱图"),
            tr("路径"),
            tr("电荷"),
            tr("过渡态"),
            tr("导出"),
            tr("原始文本"),
        ]
    )

    with tabs[0]:
        st.caption(tr("自动汇总结构、能量和吸收谱。没有对应模块时会自动跳过。"))
        left, right = st.columns([1, 2])
        if result.atoms is not None:
            info = structure_summary(result.atoms)
            left.dataframe(
                pd.DataFrame(
                    {
                        tr("字段"): [tr("分子式"), tr("组成"), tr("原子数")],
                        tr("值"): [info["formula"], info["composition"], info["atom_count"]],
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )
            right.plotly_chart(
                create_structure_figure(
                    result.atoms,
                    representation=structure_representation,
                    show_atom_labels=show_atom_labels,
                ),
                use_container_width=True,
                key=f"{base_key}-overview-structure",
            )
        else:
            left.info(tr("未解析到结构。"))

        if result.energies_hartree:
            st.plotly_chart(
                create_energy_figure(result.energies_hartree),
                use_container_width=True,
                key=f"{base_key}-overview-energy",
            )
        if not result.excited_states.empty:
            st.plotly_chart(
                create_uv_vis_figure(result.excited_states),
                use_container_width=True,
                key=f"{base_key}-overview-uv",
            )

    with tabs[1]:
        st.caption(tr("结构页需要最终笛卡尔坐标块，XYZ 输入也可以直接显示。"))
        if result.atoms is None:
            st.info(tr("当前文件未解析出结构。"))
        else:
            st.plotly_chart(
                create_structure_figure(
                    result.atoms,
                    representation=structure_representation,
                    show_atom_labels=show_atom_labels,
                ),
                use_container_width=True,
                key=f"{base_key}-structure-tab",
            )
            coords = pd.DataFrame(result.atoms.get_positions(), columns=["x", "y", "z"])
            coords.insert(0, "element", result.atoms.get_chemical_symbols())
            st.dataframe(coords, hide_index=True, use_container_width=True)
            _download_dataframe(tr("下载坐标 CSV"), coords, f"{Path(result.source_name).stem}_coords.csv")

    with tabs[2]:
        st.caption(tr("能量页基于 `FINAL SINGLE POINT ENERGY` 历史记录绘制优化曲线。"))
        if result.energies_hartree:
            st.plotly_chart(
                create_energy_figure(result.energies_hartree),
                use_container_width=True,
                key=f"{base_key}-energy-tab",
            )
            energies_df = pd.DataFrame(
                {
                    "step": list(range(1, len(result.energies_hartree) + 1)),
                    "energy_hartree": result.energies_hartree,
                }
            )
            st.dataframe(energies_df, hide_index=True, use_container_width=True)
            _download_dataframe(tr("下载能量 CSV"), energies_df, f"{Path(result.source_name).stem}_energies.csv")
        else:
            st.info(tr("当前文件未解析出能量曲线。"))

    with tabs[3]:
        st.caption(tr("频率页需要振动频率；振动动画还需要 `NORMAL MODES` 位移矩阵。"))
        left, right = st.columns(2)
        with left:
            if result.frequencies_cm1:
                st.plotly_chart(
                    create_frequency_figure(result.frequencies_cm1),
                    use_container_width=True,
                    key=f"{base_key}-frequency-bar",
                )
                freq_df = pd.DataFrame(
                    {
                        tr("mode"): list(range(1, len(result.frequencies_cm1) + 1)),
                        tr("frequency_cm^-1"): result.frequencies_cm1,
                    }
                )
                st.dataframe(freq_df, hide_index=True, use_container_width=True)
                _download_dataframe(
                    tr("下载频率 CSV"), freq_df, f"{Path(result.source_name).stem}_frequencies.csv"
                )
            else:
                st.info(tr("当前文件未解析出频率数据。"))
        with right:
            if result.frequencies_cm1:
                st.plotly_chart(
                    create_vibrational_density_figure(result.frequencies_cm1),
                    use_container_width=True,
                    key=f"{base_key}-frequency-density",
                )
                _render_vibration_mode_panel(result, base_key)
            else:
                st.info(tr("没有可展宽的频率谱。"))

    with tabs[4]:
        st.caption(tr("谱图页需要 TDDFT/TDA 激发态表，支持棒谱和展宽曲线。"))
        if result.excited_states.empty:
            st.info(tr("当前文件未解析出 TDDFT 吸收光谱。"))
        else:
            st.plotly_chart(
                create_uv_vis_figure(result.excited_states),
                use_container_width=True,
                key=f"{base_key}-uv-tab",
            )
            st.dataframe(result.excited_states, hide_index=True, use_container_width=True)
            _download_dataframe(
                tr("下载 TDDFT 光谱 CSV"),
                result.excited_states,
                f"{Path(result.source_name).stem}_tddft.csv",
            )

    with tabs[5]:
        st.caption(tr("路径页会自动识别 IRC 或 NEB 数据，并分别绘制反应路径能量。"))
        left, right = st.columns(2)
        with left:
            if result.irc_points.empty:
                st.info(tr("当前文件未解析出 IRC 路径。"))
            else:
                st.plotly_chart(
                    create_path_figure(
                        result.irc_points,
                        "coordinate",
                        "energy_hartree",
                        tr("IRC 路径能量"),
                        tr("反应坐标"),
                    ),
                    use_container_width=True,
                    key=f"{base_key}-irc-path",
                )
                st.dataframe(result.irc_points, hide_index=True, use_container_width=True)
                _download_dataframe(
                    tr("下载 IRC CSV"), result.irc_points, f"{Path(result.source_name).stem}_irc.csv"
                )
        with right:
            if result.neb_points.empty:
                st.info(tr("当前文件未解析出 NEB 路径。"))
            else:
                st.plotly_chart(
                    create_path_figure(
                        result.neb_points,
                        "image",
                        "energy_hartree",
                        tr("NEB 路径能量"),
                        "Image",
                    ),
                    use_container_width=True,
                    key=f"{base_key}-neb-path",
                )
                st.dataframe(result.neb_points, hide_index=True, use_container_width=True)
                _download_dataframe(
                    tr("下载 NEB CSV"), result.neb_points, f"{Path(result.source_name).stem}_neb.csv"
                )

    with tabs[6]:
        st.caption(tr("电荷页需要 Mulliken 或 Loewdin 原子电荷块。"))
        left, right = st.columns(2)
        with left:
            if result.mulliken_charges.empty:
                st.info(tr("未解析到 Mulliken 电荷。"))
            else:
                mulliken_bar = create_charge_figure(result.mulliken_charges, tr("Mulliken 原子电荷"))
                st.plotly_chart(
                    mulliken_bar,
                    use_container_width=True,
                    key=f"{base_key}-mulliken-charge",
                )
                if result.atoms is not None:
                    mulliken_3d = create_charge_3d_figure(
                        result.atoms,
                        result.mulliken_charges,
                        tr("Mulliken 3D 电荷分布"),
                        show_charge_labels=show_atom_labels,
                        representation=structure_representation,
                    )
                    st.plotly_chart(
                        mulliken_3d,
                        use_container_width=True,
                        key=f"{base_key}-mulliken-charge-3d",
                    )
                    st.caption(tr("3D 图里红色偏正、蓝色偏负，球越大表示电荷绝对值越大。"))
                    st.dataframe(
                        charge_extrema_dataframe(result.atoms, result.mulliken_charges),
                        hide_index=True,
                        use_container_width=True,
                    )
                    _render_figure_export_controls(
                        mulliken_3d,
                        file_stem=f"{Path(result.source_name).stem}_mulliken_charge_3d",
                        key_prefix=f"{base_key}-mulliken-3d-export",
                        note=tr("3D WebGL 图推荐优先导出高分辨率 PNG；SVG/PDF 中 3D 图层通常会栅格化。"),
                    )
                st.dataframe(result.mulliken_charges, hide_index=True, use_container_width=True)
                _render_figure_export_controls(
                    mulliken_bar,
                    file_stem=f"{Path(result.source_name).stem}_mulliken_charge_bar",
                    key_prefix=f"{base_key}-mulliken-bar-export",
                )
                _download_dataframe(
                    tr("下载 Mulliken CSV"),
                    result.mulliken_charges,
                    f"{Path(result.source_name).stem}_mulliken.csv",
                )
        with right:
            if result.loewdin_charges.empty:
                st.info(tr("未解析到 Loewdin 电荷。"))
            else:
                loewdin_bar = create_charge_figure(result.loewdin_charges, tr("Loewdin 原子电荷"))
                st.plotly_chart(
                    loewdin_bar,
                    use_container_width=True,
                    key=f"{base_key}-loewdin-charge",
                )
                if result.atoms is not None:
                    loewdin_3d = create_charge_3d_figure(
                        result.atoms,
                        result.loewdin_charges,
                        tr("Loewdin 3D 电荷分布"),
                        show_charge_labels=show_atom_labels,
                        representation=structure_representation,
                    )
                    st.plotly_chart(
                        loewdin_3d,
                        use_container_width=True,
                        key=f"{base_key}-loewdin-charge-3d",
                    )
                    st.caption(tr("3D 图里颜色和球大小都直接反映原子电荷分布。"))
                    st.dataframe(
                        charge_extrema_dataframe(result.atoms, result.loewdin_charges),
                        hide_index=True,
                        use_container_width=True,
                    )
                    _render_figure_export_controls(
                        loewdin_3d,
                        file_stem=f"{Path(result.source_name).stem}_loewdin_charge_3d",
                        key_prefix=f"{base_key}-loewdin-3d-export",
                        note=tr("3D WebGL 图推荐优先导出高分辨率 PNG；SVG/PDF 中 3D 图层通常会栅格化。"),
                    )
                st.dataframe(result.loewdin_charges, hide_index=True, use_container_width=True)
                _render_figure_export_controls(
                    loewdin_bar,
                    file_stem=f"{Path(result.source_name).stem}_loewdin_charge_bar",
                    key_prefix=f"{base_key}-loewdin-bar-export",
                )
                _download_dataframe(
                    tr("下载 Loewdin CSV"),
                    result.loewdin_charges,
                    f"{Path(result.source_name).stem}_loewdin.csv",
                )

    with tabs[7]:
        st.caption(tr("过渡态页会汇总虚频、TS 模号、热化学项和 Hessian 诊断。"))
        _render_transition_state_analysis(result)

    with tabs[8]:
        st.caption(tr("导出页提供当前解析结果的 JSON 和文本下载。"))
        export_items = {
            "metadata.json": json.dumps(result.metadata, ensure_ascii=False, indent=2),
            "warnings.txt": "\n".join(result.warnings) if result.warnings else "No warnings",
        }
        for filename, content in export_items.items():
            st.download_button(
                label=tr("下载 {filename}", filename=filename),
                data=content,
                file_name=f"{Path(result.source_name).stem}_{filename}",
            )

    with tabs[9]:
        st.caption(tr("原始文本页便于核对解析内容；XYZ 输入不会包含 ORCA 原始文本。"))
        if result.raw_text:
            st.text_area(tr("原始输出"), result.raw_text, height=600)
        else:
            st.info(tr("XYZ 输入没有原始 ORCA 文本。"))


def _render_cube_analysis(cube: CubeData, show_page_note: bool = True) -> None:
    base_key = _slug_key(cube.source_name)
    structure_representation, show_atom_labels = _get_structure_view_settings()
    cube_kind = cube.metadata.get("cube_kind", "generic")
    cube_kind_name = cube.metadata.get("cube_kind_label", cube_kind_label(cube_kind))
    if show_page_note:
        _render_page_note(
            tr("Cube 页面说明"),
            [
                tr("需要 `.cube` 文件；适合查看电子密度、轨道、ESP 等体数据。"),
                tr("切片页看二维截面，等值面页看三维空间分布，导出页可抽样为 CSV。"),
            ],
        )
    for warning in cube.warnings:
        st.warning(warning)

    min_value, max_value = cube.value_range
    summary_cols = st.columns(6)
    summary_cols[0].metric(tr("文件"), cube.source_name)
    summary_cols[1].metric(tr("原子数"), cube.atom_count)
    summary_cols[2].metric(tr("网格"), f"{cube.grid_shape[0]}x{cube.grid_shape[1]}x{cube.grid_shape[2]}")
    summary_cols[3].metric(tr("最小值"), f"{min_value:.4f}")
    summary_cols[4].metric(tr("最大值"), f"{max_value:.4f}")
    summary_cols[5].metric(tr("类型"), cube_kind_name)

    tabs = st.tabs([tr("总览"), tr("切片"), tr("等值面"), tr("导出")])

    with tabs[0]:
        st.caption(tr("总览页显示网格摘要和参考结构。当前自动识别为：{cube_kind_name}。", cube_kind_name=cube_kind_name))
        left, right = st.columns([1, 2])
        left.dataframe(cube_summary_dataframe(cube), hide_index=True, use_container_width=True)
        right.plotly_chart(
            create_structure_figure(
                cube.atoms,
                representation=structure_representation,
                show_atom_labels=show_atom_labels,
            ),
            use_container_width=True,
            key=f"{base_key}-cube-structure",
        )

    with tabs[1]:
        if cube_kind == "esp":
            st.caption(tr("ESP 切片采用化学常用配色：负静电势偏红，正静电势偏蓝，零附近接近白色。"))
        elif cube_kind == "orbital":
            st.caption(tr("轨道切片会把正负相位分开显示，白色附近表示节点区域。"))
        else:
            st.caption(tr("切片页适合快速查看某个方向上的密度分布。"))
        axis = st.selectbox(tr("切片方向"), ["x", "y", "z"], index=2, key=f"{base_key}-slice-axis")
        axis_id = {"x": 0, "y": 1, "z": 2}[axis]
        index = st.slider(
            tr("切片索引"),
            0,
            cube.grid_shape[axis_id] - 1,
            cube.grid_shape[axis_id] // 2,
            key=f"{base_key}-slice-index",
        )
        slice_figure = create_cube_slice_figure(cube, axis=axis, index=index)
        st.plotly_chart(
            slice_figure,
            use_container_width=True,
            key=f"{base_key}-cube-slice",
        )
        _render_figure_export_controls(
            slice_figure,
            file_stem=f"{Path(cube.source_name).stem}_{axis}_slice_{index}",
            key_prefix=f"{base_key}-cube-slice-export",
        )

    with tabs[2]:
        if cube_kind == "esp":
            st.caption(tr("ESP 3D 图采用负势红、正势蓝的半透明等势面，并对正负两侧分别做稳健阈值处理，避免蓝色一侧被核附近尖峰值吞掉。"))
        elif cube_kind == "orbital":
            st.caption(tr("前线轨道使用分离的正负相位表面，减少颜色混浊和表面锯齿。"))
        else:
            st.caption(tr("等值面页适合观察轨道形状、电子云范围和正负区域。"))
        max_level = max(suggest_cube_level_max(cube), 0.01)
        default_level = suggest_cube_isovalue(cube)
        controls = st.columns(3)
        render_quality = controls[0].selectbox(
            tr("渲染质量"),
            [tr("标准"), tr("精细"), tr("极致")],
            index=1 if cube_kind in {"esp", "orbital"} else 0,
            key=f"{base_key}-cube-render-quality",
        )
        surface_opacity = controls[1].slider(
            tr("表面透明度"),
            min_value=0.08,
            max_value=0.95,
            value=0.20 if cube_kind == "esp" else 0.82 if cube_kind == "orbital" else 0.55,
            step=0.02,
            key=f"{base_key}-cube-surface-opacity",
        )
        show_structure = controls[2].checkbox(
            tr("叠加结构骨架"),
            value=True,
            key=f"{base_key}-cube-show-structure",
        )
        level = st.slider(
            tr("等值面阈值"),
            min_value=0.001,
            max_value=max_level,
            value=min(max(default_level, 0.01), max_level),
            key=f"{base_key}-iso-level",
        )
        isosurface_figure = create_cube_isosurface_figure(
            cube,
            level=level,
            quality=render_quality,
            show_structure=show_structure,
            opacity=surface_opacity,
        )
        st.plotly_chart(
            isosurface_figure,
            use_container_width=True,
            key=f"{base_key}-cube-isosurface",
        )
        _render_figure_export_controls(
            isosurface_figure,
            file_stem=f"{Path(cube.source_name).stem}_isosurface",
            key_prefix=f"{base_key}-cube-isosurface-export",
            note=tr("ESP 和分子轨道的 3D 图推荐优先导出高分辨率 PNG；2D slice 更适合 SVG/PDF。"),
        )

    with tabs[3]:
        st.caption(tr("导出页提供抽样点表和 cube 元数据。"))
        sample_df = cube_sample_dataframe(cube, stride=max(1, min(cube.grid_shape) // 12))
        st.dataframe(sample_df.head(500), hide_index=True, use_container_width=True)
        _download_dataframe(
            tr("下载 cube 采样 CSV"), sample_df, f"{Path(cube.source_name).stem}_cube_sample.csv"
        )
        st.download_button(
            tr("下载 cube 元数据 JSON"),
            data=json.dumps(cube.metadata, ensure_ascii=False, indent=2),
            file_name=f"{Path(cube.source_name).stem}_cube_metadata.json",
        )


def _render_feature_preview() -> None:
    st.subheader(tr("当前版本功能"))
    st.markdown(
        """
        - {line1}
        - {line2}
        - {line3}
        - {line4}
        - {line5}
        - {line6}
        - {line7}
        - {line8}
        - {line9}
        - {line10}
        - {line11}
        """
        .format(
            line1=tr("读取 ORCA `.out/.log/.txt`、`.xyz`、`.cube`、`.gbw`"),
            line2=tr("解析总能量、最终结构、频率、电荷、TDDFT 吸收光谱"),
            line3=tr("自动识别过渡态并给出虚频与热化学摘要"),
            line4=tr("解析并绘制 IRC / NEB 路径能量"),
            line5=tr("对多个 ORCA 文件做批量比较"),
            line6=tr("对 cube 轨道文件做切片和 3D 等值面可视化"),
            line7=tr("在电荷页提供 Mulliken / Loewdin 的 3D 电荷分布图"),
            line8=tr("3D 结构支持球棍、空间填充、棒状和线框模型"),
            line9=tr("在配置 `orca_plot` 后，可由 gbw 生成电子密度、自旋密度、ESP、HOMO/LUMO 和指定 MO cube"),
            line10=tr("主要图表支持高分辨率 PNG / SVG / PDF 导出"),
            line11=tr("支持主要结果表导出为 CSV / JSON"),
        )
    )


def _render_gbw_analysis(gbw_data: GbwData) -> None:
    base_key = _slug_key(gbw_data.source_name)
    _render_page_note(
        tr("GBW 页面说明"),
        [
            tr("最少需要 `.gbw`；生成电子密度、自旋密度和 ESP 通常还需要同名 `.densities` 与 `.densitiesinfo`。"),
            tr("如果有 `.property.txt`，软件会自动给出电子数、HOMO/LUMO 建议和收敛信息。"),
            tr("如果有 `.xyz`，生成出的 cube 会自动叠加参考结构；上传 sidecar 时建议使用同 stem 文件名。"),
        ],
    )
    for warning in gbw_data.warnings:
        st.warning(warning)

    detected_orca_plot = resolve_orca_plot()
    property_summary = gbw_data.metadata.get("property_summary", {})
    summary_cols = st.columns(6)
    yes_no = lambda flag: tr("是") if flag else tr("否")
    summary_cols[0].metric(tr("文件"), gbw_data.source_name)
    summary_cols[1].metric(tr("有 .densities"), yes_no("densities" in gbw_data.sidecars))
    summary_cols[2].metric(tr("有 .densitiesinfo"), yes_no("densitiesinfo" in gbw_data.sidecars))
    summary_cols[3].metric(tr("有 property.txt"), yes_no("property_txt" in gbw_data.sidecars))
    summary_cols[4].metric(tr("有 .xyz"), yes_no("xyz" in gbw_data.sidecars))
    summary_cols[5].metric(tr("检测到 orca_plot"), yes_no(bool(detected_orca_plot)))

    with st.expander(tr("GBW 资源信息"), expanded=False):
        st.json(
            {
                "gbw_path": str(gbw_data.file_path),
                "sidecars": {key: str(value) for key, value in gbw_data.sidecars.items()},
                "detected_orca_plot": str(detected_orca_plot) if detected_orca_plot else None,
                "property_summary": property_summary or None,
            }
        )

    orca_plot_hint = st.text_input(
        tr("ORCA 安装目录或 orca_plot 路径"),
        value=str(detected_orca_plot) if detected_orca_plot else "",
        key=f"{base_key}-orca-plot-hint",
    )

    available_density_key = f"{base_key}-gbw-available-densities"
    density_error_key = f"{base_key}-gbw-density-error"
    density_signature_key = f"{base_key}-gbw-density-signature"
    scan_signature = "|".join(
        [
            str(gbw_data.file_path),
            orca_plot_hint.strip(),
            str("densities" in gbw_data.sidecars),
            str("densitiesinfo" in gbw_data.sidecars),
        ]
    )
    can_scan_densities = (
        bool(orca_plot_hint.strip())
        and "densities" in gbw_data.sidecars
        and "densitiesinfo" in gbw_data.sidecars
    )
    if can_scan_densities and st.session_state.get(density_signature_key) != scan_signature:
        try:
            with st.spinner(tr("正在扫描可用 density 列表...")):
                st.session_state[available_density_key] = list_available_densities(
                    gbw_data, orca_plot_hint=orca_plot_hint
                )
            st.session_state[density_error_key] = ""
            st.session_state[density_signature_key] = scan_signature
        except Exception as exc:
            st.session_state[available_density_key] = []
            st.session_state[density_error_key] = str(exc)
            st.session_state[density_signature_key] = scan_signature

    available_densities = st.session_state.get(available_density_key, [])
    density_error = st.session_state.get(density_error_key, "")
    if density_error:
        st.warning(tr("density 列表扫描失败：{error}", error=density_error))
    elif available_densities:
        st.caption(tr("已检测到可用 density，可直接用于 ESP 或状态密度选择。"))
        st.dataframe(
            pd.DataFrame({"density_name": available_densities}),
            hide_index=True,
            use_container_width=True,
        )

    if property_summary:
        property_rows = []
        for label, key in [
            (tr("ORCA 版本"), "version"),
            (tr("原子数"), "atom_count"),
            (tr("alpha 电子数"), "n_alpha"),
            (tr("beta 电子数"), "n_beta"),
            (tr("总电子数"), "n_total"),
            (tr("多重度"), "multiplicity"),
            (tr("收敛"), "converged"),
            (tr("最终能量 (Eh)"), "final_energy_hartree"),
            ("HOMO", "homo_index"),
            ("LUMO", "lumo_index"),
        ]:
            if key in property_summary:
                value = property_summary[key]
                if isinstance(value, float):
                    value = f"{value:.8f}"
                property_rows.append((label, value))
        if property_rows:
            st.subheader(tr("Property 摘要"))
            st.dataframe(
                pd.DataFrame(property_rows, columns=[tr("字段"), tr("值")]),
                hide_index=True,
                use_container_width=True,
            )

    st.subheader(tr("GBW 转 cube"))
    generator_family_options = {
        tr("密度 / 静电势"): "density",
        tr("分子轨道"): "orbital",
    }
    generator_family = st.radio(
        tr("生成类别"),
        list(generator_family_options),
        horizontal=True,
        key=f"{base_key}-gbw-generator-family",
    )
    grid_intervals = st.slider(
        tr("网格分辨率"),
        min_value=40,
        max_value=200,
        value=120,
        step=10,
        key=f"{base_key}-gbw-grid",
    )

    plot_kind = ""
    density_name = ""
    orbital_index: int | None = None
    operator = 0
    disabled_reason = ""
    spin_density_available = any(name.lower().endswith(".scfr") for name in available_densities)

    if not orca_plot_hint.strip():
        disabled_reason = tr("当前没有可用的 `orca_plot` 路径，无法从 gbw 生成 cube。")

    if generator_family_options[generator_family] == "density":
        st.caption(tr("ESP 建议优先使用 120-160 的网格分辨率，颜色边界会更平滑。"))
        plot_label_options = {
            tr("电子密度"): "electron_density",
            tr("自旋密度"): "spin_density",
            tr("静电势 ESP"): "electrostatic_potential",
        }
        plot_label = st.selectbox(
            tr("生成内容"),
            list(plot_label_options),
            key=f"{base_key}-gbw-plot-kind",
        )
        plot_kind = plot_label_options[plot_label]
        if not disabled_reason and (
            "densities" not in gbw_data.sidecars or "densitiesinfo" not in gbw_data.sidecars
        ):
            disabled_reason = tr("密度或 ESP 生成功能需要同名 `.densities` 与 `.densitiesinfo`。")
        elif (
            not disabled_reason
            and plot_kind == "spin_density"
            and available_densities
            and not spin_density_available
        ):
            disabled_reason = tr("当前 density 列表里没有检测到 `.scfr` 自旋密度。")

        if plot_kind == "electrostatic_potential":
            default_density = next(
                (name for name in available_densities if name.lower().endswith(".scfp")),
                f"{gbw_data.stem}.scfp",
            )
            if available_densities:
                density_name = st.selectbox(
                    tr("ESP 所用状态 density"),
                    available_densities,
                    index=available_densities.index(default_density)
                    if default_density in available_densities
                    else 0,
                    key=f"{base_key}-gbw-density-name-select",
                )
            else:
                density_name = st.text_input(
                    tr("ESP 所用状态 density"),
                    value=default_density,
                    key=f"{base_key}-gbw-density-name",
                )
    else:
        st.caption(tr("轨道模式只需要 `.gbw`；HOMO/LUMO 建议值优先来自 `.property.txt`，前线轨道建议 120-160 网格。"))
        orbital_mode_options = {
            "HOMO": "HOMO",
            "LUMO": "LUMO",
            tr("自定义"): "custom",
        }
        orbital_mode = st.radio(
            tr("轨道选择"),
            list(orbital_mode_options),
            horizontal=True,
            key=f"{base_key}-gbw-orbital-mode",
        )
        if property_summary.get("closed_shell", False):
            operator = 0
            st.caption(tr("当前 property 信息显示为 closed-shell，默认使用 alpha / closed-shell 轨道。"))
        else:
            operator_label = st.selectbox(
                tr("轨道算符"),
                ["alpha / closed shell", "beta"],
                key=f"{base_key}-gbw-operator",
            )
            operator = 0 if operator_label == "alpha / closed shell" else 1

        if orbital_mode_options[orbital_mode] == "HOMO":
            suggested_key = "homo_index" if operator == 0 else "beta_homo_index"
            orbital_index = property_summary.get(suggested_key)
        elif orbital_mode_options[orbital_mode] == "LUMO":
            suggested_key = "lumo_index" if operator == 0 else "beta_lumo_index"
            orbital_index = property_summary.get(suggested_key)

        if orbital_mode_options[orbital_mode] != "custom" and orbital_index is None:
            st.caption(tr("当前没有可用于自动推断 HOMO/LUMO 的 property 信息，请手动填写轨道编号。"))

        default_index = orbital_index if orbital_index is not None else 0
        orbital_index = st.number_input(
            tr("轨道编号"),
            min_value=0,
            step=1,
            value=int(default_index),
            key=f"{base_key}-gbw-orbital-index",
        )
        plot_kind = "molecular_orbital"

    if disabled_reason:
        st.info(disabled_reason)

    if st.button(
        tr("生成 cube 并可视化"),
        key=f"{base_key}-gbw-generate",
        disabled=bool(disabled_reason),
    ):
        try:
            with st.spinner(tr("正在调用 orca_plot 生成 cube...")):
                cube, run_info = generate_cube_from_gbw(
                    gbw_data,
                    plot_kind=plot_kind,
                    orca_plot_hint=orca_plot_hint,
                    grid_intervals=grid_intervals,
                    density_name=density_name,
                    orbital_index=int(orbital_index) if orbital_index is not None else None,
                    operator=operator,
                )
            st.session_state[f"{base_key}-gbw-cube-path"] = cube.metadata.get("path")
            st.session_state[f"{base_key}-gbw-run-info"] = run_info
            st.success(tr("cube 生成完成。"))
        except Exception as exc:
            st.error(str(exc))

    run_info = st.session_state.get(f"{base_key}-gbw-run-info")
    if run_info:
        with st.expander(tr("orca_plot 运行信息"), expanded=False):
            st.json(run_info)

    cube_path = st.session_state.get(f"{base_key}-gbw-cube-path")
    if cube_path:
        cube = parse_cube_file(cube_path)
        cube.source_name = Path(cube_path).name
        _render_cube_analysis(cube, show_page_note=False)


def _render_transition_state_analysis(result: OrcaParseResult) -> None:
    ts_info = result.transition_state_info
    thermo = result.thermochemistry
    if not ts_info and not thermo:
        st.info(tr("当前文件没有可用的过渡态或热化学分析信息。"))
        return

    if ts_info:
        status = ts_info.get("status")
        diagnosis = ts_info.get("diagnosis", "-")
        if status == "confirmed_ts":
            st.success(diagnosis)
        elif status in {"multiple_imaginaries", "ts_search_without_imaginary"}:
            st.warning(diagnosis)
        else:
            st.info(diagnosis)

        metrics = st.columns(5)
        metrics[0].metric(tr("TS 诊断"), _ts_status_label(status))
        metrics[1].metric(
            tr("最低虚频 (cm^-1)"),
            _format_float(ts_info.get("lowest_imaginary_frequency_cm^-1")),
        )
        metrics[2].metric(tr("虚频个数"), ts_info.get("imaginary_frequency_count", 0))
        metrics[3].metric(
            tr("TS 模号"),
            str(ts_info["ts_mode_number"]) if "ts_mode_number" in ts_info else "-",
        )
        metrics[4].metric(
            tr("负 Hessian 本征值"),
            str(ts_info["negative_hessian_eigenvalues"])
            if "negative_hessian_eigenvalues" in ts_info
            else "-",
        )

        ts_table_rows = []
        if "ts_mode_eigenvalue" in ts_info:
            ts_table_rows.append((tr("TS 模本征值"), f'{ts_info["ts_mode_eigenvalue"]:.8f}'))
        if "following_ts_mode_number" in ts_info:
            ts_table_rows.append(("Following TS mode", str(ts_info["following_ts_mode_number"])))
        if "ts_active_atoms" in ts_info:
            ts_table_rows.append(
                ("TS-active-atoms", ", ".join(str(value) for value in ts_info["ts_active_atoms"]))
            )
        if "all_imaginary_frequencies_cm^-1" in ts_info:
            ts_table_rows.append(
                (
                    tr("全部虚频"),
                    ", ".join(f"{value:.2f}" for value in ts_info["all_imaginary_frequencies_cm^-1"]),
                )
            )
        if ts_table_rows:
            st.dataframe(
                pd.DataFrame(ts_table_rows, columns=[tr("字段"), tr("值")]),
                hide_index=True,
                use_container_width=True,
            )

    if thermo:
        st.subheader(tr("热化学摘要"))
        thermo_rows = []
        for label, key in [
            (tr("温度 (K)"), "temperature_k"),
            (tr("零点能 ZPE (Eh)"), "zero_point_energy_hartree"),
            (tr("总热能 U (Eh)"), "thermal_energy_hartree"),
            (tr("总焓 H (Eh)"), "enthalpy_hartree"),
            (tr("最终熵项 T*S (Eh)"), "entropy_term_hartree"),
            (tr("熵校正 (Eh)"), "entropy_correction_hartree"),
            (tr("Gibbs 自由能 G (Eh)"), "gibbs_free_energy_hartree"),
            ("G-E(el) (Eh)", "g_minus_e_el_hartree"),
        ]:
            if key in thermo:
                thermo_rows.append((label, _format_float(thermo[key])))
        if thermo_rows:
            thermo_df = pd.DataFrame(thermo_rows, columns=[tr("字段"), tr("值")])
            st.dataframe(thermo_df, hide_index=True, use_container_width=True)
            _download_dataframe(
                tr("下载热化学 CSV"),
                thermo_df,
                f"{Path(result.source_name).stem}_thermochemistry.csv",
            )


def _render_vibration_mode_panel(result: OrcaParseResult, base_key: str) -> None:
    if result.atoms is None or not result.normal_modes:
        st.info(tr("当前文件未解析出可视化所需的 NORMAL MODES 位移矩阵。"))
        return

    st.subheader(tr("振动模式可视化"))
    mode_options = []
    for mode_index in sorted(result.normal_modes):
        frequency = (
            result.frequencies_cm1[mode_index]
            if mode_index < len(result.frequencies_cm1)
            else None
        )
        if frequency is None:
            label = f"Mode {mode_index}"
        else:
            suffix = tr(" imaginary") if frequency < 0 else ""
            label = f"Mode {mode_index}: {frequency:.2f} cm^-1{suffix}"
        mode_options.append((label, mode_index))

    selected_label = st.selectbox(
        tr("选择模态"),
        [label for label, _ in mode_options],
        key=f"{base_key}-mode-select",
    )
    selected_mode = dict(mode_options)[selected_label]
    amplitude = st.slider(
        tr("振动放大倍数"),
        min_value=0.1,
        max_value=2.0,
        value=0.8,
        step=0.1,
        key=f"{base_key}-mode-amplitude",
    )
    show_vectors = st.checkbox(
        tr("显示位移方向红线"),
        value=False,
        key=f"{base_key}-mode-vectors",
    )

    mode_displacements = result.normal_modes[selected_mode]
    components.html(
        build_vibration_mode_html(
            result.atoms,
            mode_displacements,
            amplitude=amplitude,
            component_id=f"{base_key}-mode-player-{selected_mode}",
            show_vectors=show_vectors,
        ),
        height=640,
        scrolling=False,
    )
    st.plotly_chart(
        create_mode_magnitude_figure(result.atoms, mode_displacements),
        use_container_width=True,
        key=f"{base_key}-mode-magnitude-{selected_mode}",
    )
    st.dataframe(
        top_mode_atoms(result.atoms, mode_displacements),
        hide_index=True,
        use_container_width=True,
    )


def _load_single_input(
    uploaded_file: Any, local_path: str, gbw_sidecar_uploads: list[Any] | None = None
) -> tuple[Any, str] | None:
    if uploaded_file is not None:
        suffix = Path(uploaded_file.name).suffix.lower()
        if suffix in {".xyz", ".cube", ".gbw"}:
            temp_dir = Path(tempfile.mkdtemp(prefix="orca_viz_input_"))
            temp_path = temp_dir / uploaded_file.name
            temp_path.write_bytes(uploaded_file.getbuffer())
            if suffix == ".gbw":
                for sidecar_upload in gbw_sidecar_uploads or []:
                    target_name = _normalize_gbw_sidecar_name(temp_path.stem, sidecar_upload.name)
                    if target_name is None:
                        continue
                    sidecar_path = temp_dir / target_name
                    sidecar_path.write_bytes(sidecar_upload.getbuffer())
            return _parse_path(temp_path, source_name=uploaded_file.name)
        raw_text = uploaded_file.getvalue().decode("utf-8", errors="ignore")
        return parse_orca_content(raw_text, source_name=uploaded_file.name), "orca"

    if local_path.strip():
        path = Path(local_path.strip()).expanduser()
        if not path.exists():
            st.error(tr("文件不存在：{path}", path=path))
            return None
        return _parse_path(path)

    return None


def _load_batch_inputs(uploaded_files: list[Any], folder_path: str) -> list[Any]:
    items: list[Any] = []
    for uploaded_file in uploaded_files or []:
        loaded = _load_single_input(uploaded_file, "")
        if loaded is not None:
            items.append(loaded[0])

    if folder_path.strip():
        folder = Path(folder_path.strip()).expanduser()
        if not folder.exists() or not folder.is_dir():
            st.error(tr("文件夹不存在：{folder}", folder=folder))
            return items
        patterns = ["*.out", "*.log", "*.txt", "*.xyz", "*.cube"]
        paths: list[Path] = []
        for pattern in patterns:
            paths.extend(folder.rglob(pattern))
        paths = sorted(set(paths))
        for path in paths:
            try:
                parsed, _ = _parse_path(path)
            except Exception as exc:
                st.warning(tr("跳过 {name}: {error}", name=path.name, error=exc))
                continue
            items.append(parsed)

    return items


def _parse_path(path: Path, source_name: str | None = None) -> tuple[Any, str]:
    suffix = path.suffix.lower()
    if suffix == ".cube":
        cube = parse_cube_file(path)
        if source_name:
            cube.source_name = source_name
        return cube, "cube"
    if suffix == ".gbw":
        gbw = load_gbw_file(path, source_name=source_name)
        return gbw, "gbw"

    result = parse_orca_file(path)
    if source_name:
        result.source_name = source_name
    return result, "orca"


def _download_dataframe(label: str, dataframe: pd.DataFrame, file_name: str) -> None:
    csv_buffer = StringIO()
    dataframe.to_csv(csv_buffer, index=False)
    st.download_button(label=label, data=csv_buffer.getvalue(), file_name=file_name)


def _render_figure_export_controls(
    figure: Any,
    file_stem: str,
    key_prefix: str,
    note: str = "",
) -> None:
    with st.expander(tr("论文级图片导出"), expanded=False):
        if note:
            st.caption(note)
        if not STATIC_IMAGE_EXPORT_AVAILABLE:
            st.info(tr("当前环境未安装 `kaleido`，暂时不能导出高分辨率静态图。"))
            return

        row1 = st.columns(4)
        image_format = row1[0].selectbox(
            tr("格式"),
            ["png", "svg", "pdf"],
            index=0,
            key=f"{key_prefix}-format",
        )
        scale = row1[1].selectbox(
            tr("倍数"),
            [1, 2, 3, 4],
            index=1,
            key=f"{key_prefix}-scale",
        )
        width = row1[2].number_input(
            tr("宽度(px)"),
            min_value=800,
            max_value=4800,
            value=1800,
            step=100,
            key=f"{key_prefix}-width",
        )
        height = row1[3].number_input(
            tr("高度(px)"),
            min_value=600,
            max_value=3600,
            value=1200,
            step=100,
            key=f"{key_prefix}-height",
        )
        publication_style = st.checkbox(
            tr("应用论文风格排版"),
            value=True,
            key=f"{key_prefix}-publication-style",
        )

        generated_key = f"{key_prefix}-image-bytes"
        filename_key = f"{key_prefix}-image-name"
        error_key = f"{key_prefix}-image-error"

        if st.button(tr("生成静态图片"), key=f"{key_prefix}-generate"):
            try:
                image_bytes = export_plotly_figure(
                    figure,
                    image_format=image_format,
                    width=int(width),
                    height=int(height),
                    scale=int(scale),
                    publication_style=publication_style,
                )
                st.session_state[generated_key] = image_bytes
                st.session_state[filename_key] = f"{file_stem}.{image_format}"
                st.session_state[error_key] = ""
            except Exception as exc:
                st.session_state[generated_key] = None
                st.session_state[filename_key] = ""
                st.session_state[error_key] = str(exc)

        export_error = st.session_state.get(error_key, "")
        if export_error:
            st.error(export_error)

        image_bytes = st.session_state.get(generated_key)
        file_name = st.session_state.get(filename_key, f"{file_stem}.{image_format}")
        if image_bytes:
            st.download_button(
                tr("下载静态图片"),
                data=image_bytes,
                file_name=file_name,
                mime=_image_mime_type(file_name),
                key=f"{key_prefix}-download",
            )


def _format_float(value: float | None) -> str:
    return "-" if value is None else f"{value:.8f}"


def _render_page_note(title: str, lines: list[str]) -> None:
    with st.expander(title, expanded=False):
        st.markdown("\n".join(f"- {line}" for line in lines))


def _normalize_gbw_sidecar_name(stem: str, upload_name: str) -> str | None:
    lowered = upload_name.lower()
    if lowered.endswith(".densitiesinfo"):
        return f"{stem}.densitiesinfo"
    if lowered.endswith(".densities"):
        return f"{stem}.densities"
    if lowered.endswith(".property.txt"):
        return f"{stem}.property.txt"
    if lowered.endswith(".xyz"):
        return f"{stem}.xyz"
    if lowered.endswith(".out"):
        return f"{stem}.out"
    if lowered.endswith(".log"):
        return f"{stem}.log"
    return None


def _image_mime_type(file_name: str) -> str:
    suffix = Path(file_name).suffix.lower()
    if suffix == ".svg":
        return "image/svg+xml"
    if suffix == ".pdf":
        return "application/pdf"
    return "image/png"


def _get_structure_view_settings() -> tuple[str, bool]:
    representation_map = {
        tr("球棍"): "ball_stick",
        tr("空间填充"): "space_filling",
        tr("棒状"): "stick",
        tr("线框"): "wireframe",
    }
    label = st.session_state.get("global-structure-representation", tr("球棍"))
    representation = representation_map.get(label, "ball_stick")
    show_labels = bool(st.session_state.get("global-structure-labels", False))
    return representation, show_labels


def _slug_key(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value.lower()).strip("-") or "item"


def _ts_status_label(status: str | None) -> str:
    mapping = {
        "confirmed_ts": tr("已确认"),
        "multiple_imaginaries": tr("多虚频"),
        "ts_search_without_imaginary": tr("TS 搜索未成"),
        "not_ts": tr("非 TS"),
    }
    return mapping.get(status, "-")


if __name__ == "__main__":
    main()
