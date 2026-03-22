from __future__ import annotations

from pathlib import Path
import json
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from ..i18n import tr
from ..pathway import PathwayResult, analyze_pathway, build_xyz_trajectory_text
from ..parser import OrcaParseResult
from ..visualization import (
    atom_reference_dataframe,
    build_pathway_animation_html,
    build_vibration_mode_html,
    charge_extrema_dataframe,
    create_charge_3d_figure,
    create_charge_figure,
    create_energy_figure,
    create_frequency_figure,
    create_mode_magnitude_figure,
    create_path_figure,
    create_uv_vis_figure,
    create_vibrational_density_figure,
    structure_summary,
    top_mode_atoms,
)
from .common import (
    format_float,
    get_structure_view_settings,
    render_page_visual_style_override,
    render_page_model_size_override,
    render_page_note,
    render_pathway_animation_component,
    render_plotly_chart,
    render_structure_viewer_component,
    resolve_visual_style_key,
    slug_key,
)
from .data import download_dataframe, path_display_dataframe
from .export_controls import render_figure_export_controls, render_pathway_animation_export_controls
from .labels import ts_status_label


def render_orca_analysis(result: OrcaParseResult) -> None:
    base_key = slug_key(result.source_name)
    render_page_visual_style_override(f"{base_key}-orca")
    render_page_model_size_override(f"{base_key}-orca")
    structure_representation, show_atom_labels, model_size_settings = get_structure_view_settings(f"{base_key}-orca")
    visual_style_key = resolve_visual_style_key(f"{base_key}-orca")
    render_page_note(
        tr("ORCA 输出说明"),
        [
            tr("推荐输入完整 `.out/.log/.txt` 输出；如果只有 `.xyz`，则只能显示结构。"),
            tr("频率页需要 `VIBRATIONAL FREQUENCIES` 和 `NORMAL MODES`，谱图页需要 TDDFT/TDA 表。"),
            tr("路径、电荷和过渡态页会按文件里实际存在的模块自动显示。"),
        ],
    )
    for warning in result.warnings:
        st.warning(warning)

    frontier_gap_ev = result.metadata.get("homo_lumo_gap_ev")
    summary_cols = st.columns(7)
    summary_cols[0].metric(tr("文件"), result.source_name)
    summary_cols[1].metric(tr("原子数"), result.atom_count)
    summary_cols[2].metric(tr("总能量 (Eh)"), format_float(result.total_energy_hartree))
    summary_cols[3].metric(tr("虚频数"), len(result.imaginary_frequencies))
    summary_cols[4].metric(tr("激发态数"), len(result.excited_states))
    summary_cols[5].metric(
        tr("HOMO-LUMO gap (eV)"),
        "-" if frontier_gap_ev is None else f"{float(frontier_gap_ev):.3f}",
    )
    summary_cols[6].metric(tr("TS 状态"), ts_status_label(result.transition_state_info.get("status")))

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
            summary_fields = [tr("分子式"), tr("组成"), tr("原子数")]
            summary_values = [info["formula"], info["composition"], info["atom_count"]]
            for label, key in [
                (tr("HOMO 能量 (eV)"), "homo_energy_ev"),
                (tr("LUMO 能量 (eV)"), "lumo_energy_ev"),
                (tr("HOMO-LUMO gap (eV)"), "homo_lumo_gap_ev"),
            ]:
                value = result.metadata.get(key)
                if isinstance(value, (int, float)):
                    summary_fields.append(label)
                    summary_values.append(f"{float(value):.3f}")
            left.dataframe(
                pd.DataFrame(
                    {
                        tr("字段"): summary_fields,
                        tr("值"): summary_values,
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )
            with right:
                render_structure_viewer_component(
                    result.atoms,
                    component_id=f"{base_key}-overview-viewer",
                    representation=structure_representation,
                    show_atom_labels=show_atom_labels,
                    enable_measurement=True,
                    model_size_settings=model_size_settings,
                    visual_style_key=visual_style_key,
                    height=760,
                )
                with st.expander(tr("原子索引参考"), expanded=False):
                    st.dataframe(
                        atom_reference_dataframe(result.atoms),
                        hide_index=True,
                        use_container_width=True,
                    )
        else:
            left.info(tr("未解析到结构。"))

        if result.energies_hartree:
            render_plotly_chart(
                create_energy_figure(result.energies_hartree, visual_style_key=visual_style_key),
                key=f"{base_key}-overview-energy",
                file_name=f"{Path(result.source_name).stem}_energy_overview",
            )
        if not result.excited_states.empty:
            render_plotly_chart(
                create_uv_vis_figure(result.excited_states, visual_style_key=visual_style_key),
                key=f"{base_key}-overview-uv",
                file_name=f"{Path(result.source_name).stem}_spectrum_overview",
            )

    with tabs[1]:
        st.caption(tr("结构页需要最终笛卡尔坐标块，XYZ 输入也可以直接显示。"))
        if result.atoms is None:
            st.info(tr("当前文件未解析出结构。"))
        else:
            render_structure_viewer_component(
                result.atoms,
                component_id=f"{base_key}-structure-viewer",
                representation=structure_representation,
                show_atom_labels=show_atom_labels,
                enable_measurement=True,
                model_size_settings=model_size_settings,
                visual_style_key=visual_style_key,
                height=760,
            )
            coords = pd.DataFrame(result.atoms.get_positions(), columns=["x", "y", "z"])
            coords.insert(0, "element", result.atoms.get_chemical_symbols())
            st.dataframe(coords, hide_index=True, use_container_width=True)
            download_dataframe(tr("下载坐标 CSV"), coords, f"{Path(result.source_name).stem}_coords.csv")

    with tabs[2]:
        st.caption(tr("能量页基于 `FINAL SINGLE POINT ENERGY` 历史记录绘制优化曲线。"))
        if result.energies_hartree:
            energy_figure = create_energy_figure(result.energies_hartree, visual_style_key=visual_style_key)
            render_plotly_chart(
                energy_figure,
                key=f"{base_key}-energy-tab",
                file_name=f"{Path(result.source_name).stem}_energy_curve",
            )
            energies_df = pd.DataFrame(
                {
                    "step": list(range(1, len(result.energies_hartree) + 1)),
                    "energy_hartree": result.energies_hartree,
                }
            )
            st.dataframe(energies_df, hide_index=True, use_container_width=True)
            render_figure_export_controls(
                energy_figure,
                file_stem=f"{Path(result.source_name).stem}_energy_curve",
                key_prefix=f"{base_key}-energy-export",
            )
            download_dataframe(tr("下载能量 CSV"), energies_df, f"{Path(result.source_name).stem}_energies.csv")
        else:
            st.info(tr("当前文件未解析出能量曲线。"))

    with tabs[3]:
        st.caption(tr("频率页需要振动频率；振动动画还需要 `NORMAL MODES` 位移矩阵。"))
        left, right = st.columns(2)
        with left:
            if result.frequencies_cm1:
                frequency_figure = create_frequency_figure(result.frequencies_cm1, visual_style_key=visual_style_key)
                render_plotly_chart(
                    frequency_figure,
                    key=f"{base_key}-frequency-bar",
                    file_name=f"{Path(result.source_name).stem}_frequencies",
                )
                freq_df = pd.DataFrame(
                    {
                        tr("mode"): list(range(1, len(result.frequencies_cm1) + 1)),
                        tr("frequency_cm^-1"): result.frequencies_cm1,
                    }
                )
                st.dataframe(freq_df, hide_index=True, use_container_width=True)
                render_figure_export_controls(
                    frequency_figure,
                    file_stem=f"{Path(result.source_name).stem}_frequency_bar",
                    key_prefix=f"{base_key}-freq-export",
                )
                download_dataframe(
                    tr("下载频率 CSV"), freq_df, f"{Path(result.source_name).stem}_frequencies.csv"
                )
            else:
                st.info(tr("当前文件未解析出频率数据。"))
        with right:
            if result.frequencies_cm1:
                vibrational_figure = create_vibrational_density_figure(
                    result.frequencies_cm1,
                    visual_style_key=visual_style_key,
                )
                render_plotly_chart(
                    vibrational_figure,
                    key=f"{base_key}-frequency-density",
                    file_name=f"{Path(result.source_name).stem}_frequency_density",
                )
                render_figure_export_controls(
                    vibrational_figure,
                    file_stem=f"{Path(result.source_name).stem}_frequency_density",
                    key_prefix=f"{base_key}-freq-density-export",
                )
                render_vibration_mode_panel(
                    result,
                    base_key,
                    structure_representation=structure_representation,
                    model_size_settings=model_size_settings,
                    visual_style_key=visual_style_key,
                )
            else:
                st.info(tr("没有可展宽的频率谱。"))

    with tabs[4]:
        st.caption(tr("谱图页需要 TDDFT/TDA 激发态表，支持棒谱和展宽曲线。"))
        if result.excited_states.empty:
            st.info(tr("当前文件未解析出 TDDFT 吸收光谱。"))
        else:
            settings_col, summary_col = st.columns([1, 2])
            with settings_col:
                st.caption(tr("谱图设置"))
                sigma_ev = st.slider(
                    tr("展宽参数 sigma (eV)"),
                    min_value=0.03,
                    max_value=0.40,
                    value=0.12,
                    step=0.01,
                    key=f"{base_key}-uv-sigma",
                )
            strongest_state = result.excited_states.loc[result.excited_states["oscillator_strength"].idxmax()]
            with summary_col:
                metric_cols = st.columns(4)
                metric_cols[0].metric(
                    tr("最低激发能 (eV)"),
                    f"{result.excited_states['energy_eV'].min():.3f}",
                )
                metric_cols[1].metric(tr("最强振子强度"), f"{strongest_state['oscillator_strength']:.4f}")
                metric_cols[2].metric(tr("最强跃迁波长 (nm)"), f"{strongest_state['wavelength_nm']:.1f}")
                metric_cols[3].metric(tr("最强跃迁态"), f"S{int(strongest_state['state'])}")
            uv_figure = create_uv_vis_figure(
                result.excited_states,
                sigma_ev=sigma_ev,
                visual_style_key=visual_style_key,
            )
            render_plotly_chart(
                uv_figure,
                key=f"{base_key}-uv-tab",
                file_name=f"{Path(result.source_name).stem}_tddft_spectrum",
            )
            render_figure_export_controls(
                uv_figure,
                file_stem=f"{Path(result.source_name).stem}_tddft_spectrum",
                key_prefix=f"{base_key}-uv-export",
            )
            st.dataframe(result.excited_states, hide_index=True, use_container_width=True)
            download_dataframe(
                tr("下载 TDDFT 光谱 CSV"),
                result.excited_states,
                f"{Path(result.source_name).stem}_tddft.csv",
            )

    with tabs[5]:
        st.caption(tr("路径页会自动识别 IRC、NEB 或 Scan 数据，并默认显示相对能量。"))
        st.caption(tr("路径数据表会同时保留绝对能量和相对能量。"))
        pathway_energy_modes = {
            tr("相对最低点"): "minimum",
            tr("相对第一个点"): "first",
            tr("相对最后一个点"): "last",
            tr("相对指定点"): "selected",
            tr("绝对能量 (Hartree)"): "absolute",
        }
        selected_energy_mode = st.selectbox(
            tr("路径能量参考"),
            list(pathway_energy_modes),
            key=f"{base_key}-path-energy-mode",
        )
        pathway_map = _pathways_for_result(result)
        for kind, title, empty_message, download_label, file_name, key_prefix in [
            ("irc", tr("IRC 路径能量"), tr("当前文件未解析出 IRC 路径。"), tr("下载 IRC CSV"), f"{Path(result.source_name).stem}_irc.csv", f"{base_key}-irc-path"),
            ("neb", tr("NEB 路径能量"), tr("当前文件未解析出 NEB 路径。"), tr("下载 NEB CSV"), f"{Path(result.source_name).stem}_neb.csv", f"{base_key}-neb-path"),
            ("scan", tr("Scan 路径能量"), tr("当前文件未解析出 Scan 路径。"), tr("下载 Scan CSV"), f"{Path(result.source_name).stem}_scan.csv", f"{base_key}-scan-path"),
        ]:
            _render_pathway_section(
                pathway_map.get(kind),
                title=title,
                empty_message=empty_message,
                download_label=download_label,
                file_name=file_name,
                key_prefix=key_prefix,
                reference_mode=pathway_energy_modes[selected_energy_mode],
                structure_representation=structure_representation,
                show_atom_labels=show_atom_labels,
                model_size_settings=model_size_settings,
                visual_style_key=visual_style_key,
            )

    with tabs[6]:
        st.caption(tr("电荷页需要 Mulliken 或 Loewdin 原子电荷块。"))
        left, right = st.columns(2)
        with left:
            if result.mulliken_charges.empty:
                st.info(tr("未解析到 Mulliken 电荷。"))
            else:
                mulliken_bar = create_charge_figure(
                    result.mulliken_charges,
                    tr("Mulliken 原子电荷"),
                    visual_style_key=visual_style_key,
                )
                render_plotly_chart(
                    mulliken_bar,
                    key=f"{base_key}-mulliken-charge",
                    file_name=f"{Path(result.source_name).stem}_mulliken_bar",
                )
                if result.atoms is not None:
                    mulliken_3d = create_charge_3d_figure(
                        result.atoms,
                        result.mulliken_charges,
                        tr("Mulliken 3D 电荷分布"),
                        show_charge_labels=show_atom_labels,
                        representation=structure_representation,
                        model_size_settings=model_size_settings,
                        visual_style_key=visual_style_key,
                    )
                    render_plotly_chart(
                        mulliken_3d,
                        key=f"{base_key}-mulliken-charge-3d",
                        enable_scroll_zoom=True,
                        file_name=f"{Path(result.source_name).stem}_mulliken_charge_3d",
                    )
                    st.caption(tr("3D 图里红色偏正、蓝色偏负，球越大表示电荷绝对值越大。"))
                    st.dataframe(
                        charge_extrema_dataframe(result.atoms, result.mulliken_charges),
                        hide_index=True,
                        use_container_width=True,
                    )
                    render_figure_export_controls(
                        mulliken_3d,
                        file_stem=f"{Path(result.source_name).stem}_mulliken_charge_3d",
                        key_prefix=f"{base_key}-mulliken-3d-export",
                        note=tr("3D WebGL 图推荐优先导出高分辨率 PNG；SVG/PDF 中 3D 图层通常会栅格化。"),
                    )
                st.dataframe(result.mulliken_charges, hide_index=True, use_container_width=True)
                render_figure_export_controls(
                    mulliken_bar,
                    file_stem=f"{Path(result.source_name).stem}_mulliken_charge_bar",
                    key_prefix=f"{base_key}-mulliken-bar-export",
                )
                download_dataframe(
                    tr("下载 Mulliken CSV"),
                    result.mulliken_charges,
                    f"{Path(result.source_name).stem}_mulliken.csv",
                )
        with right:
            if result.loewdin_charges.empty:
                st.info(tr("未解析到 Loewdin 电荷。"))
            else:
                loewdin_bar = create_charge_figure(
                    result.loewdin_charges,
                    tr("Loewdin 原子电荷"),
                    visual_style_key=visual_style_key,
                )
                render_plotly_chart(
                    loewdin_bar,
                    key=f"{base_key}-loewdin-charge",
                    file_name=f"{Path(result.source_name).stem}_loewdin_bar",
                )
                if result.atoms is not None:
                    loewdin_3d = create_charge_3d_figure(
                        result.atoms,
                        result.loewdin_charges,
                        tr("Loewdin 3D 电荷分布"),
                        show_charge_labels=show_atom_labels,
                        representation=structure_representation,
                        model_size_settings=model_size_settings,
                        visual_style_key=visual_style_key,
                    )
                    render_plotly_chart(
                        loewdin_3d,
                        key=f"{base_key}-loewdin-charge-3d",
                        enable_scroll_zoom=True,
                        file_name=f"{Path(result.source_name).stem}_loewdin_charge_3d",
                    )
                    st.caption(tr("3D 图里颜色和球大小都直接反映原子电荷分布。"))
                    st.dataframe(
                        charge_extrema_dataframe(result.atoms, result.loewdin_charges),
                        hide_index=True,
                        use_container_width=True,
                    )
                    render_figure_export_controls(
                        loewdin_3d,
                        file_stem=f"{Path(result.source_name).stem}_loewdin_charge_3d",
                        key_prefix=f"{base_key}-loewdin-3d-export",
                        note=tr("3D WebGL 图推荐优先导出高分辨率 PNG；SVG/PDF 中 3D 图层通常会栅格化。"),
                    )
                st.dataframe(result.loewdin_charges, hide_index=True, use_container_width=True)
                render_figure_export_controls(
                    loewdin_bar,
                    file_stem=f"{Path(result.source_name).stem}_loewdin_charge_bar",
                    key_prefix=f"{base_key}-loewdin-bar-export",
                )
                download_dataframe(
                    tr("下载 Loewdin CSV"),
                    result.loewdin_charges,
                    f"{Path(result.source_name).stem}_loewdin.csv",
                )

    with tabs[7]:
        st.caption(tr("过渡态页会汇总虚频、TS 模号、热化学项和 Hessian 诊断。"))
        render_transition_state_analysis(result)

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


def render_transition_state_analysis(result: OrcaParseResult) -> None:
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
        metrics[0].metric(tr("TS 诊断"), ts_status_label(status))
        metrics[1].metric(tr("最低虚频 (cm^-1)"), format_float(ts_info.get("lowest_imaginary_frequency_cm^-1")))
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
            ts_table_rows.append((tr("后续 TS 模号"), str(ts_info["following_ts_mode_number"])))
        if "ts_active_atoms" in ts_info:
            ts_table_rows.append(
                (tr("TS 活性原子"), ", ".join(str(value) for value in ts_info["ts_active_atoms"]))
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
                thermo_rows.append((label, format_float(thermo[key])))
        if thermo_rows:
            thermo_df = pd.DataFrame(thermo_rows, columns=[tr("字段"), tr("值")])
            st.dataframe(thermo_df, hide_index=True, use_container_width=True)
            download_dataframe(
                tr("下载热化学 CSV"),
                thermo_df,
                f"{Path(result.source_name).stem}_thermochemistry.csv",
            )


def render_vibration_mode_panel(
    result: OrcaParseResult,
    base_key: str,
    *,
    structure_representation: str,
    model_size_settings: Any,
    visual_style_key: str,
) -> None:
    if result.atoms is None or not result.normal_modes:
        st.info(tr("当前文件未解析出可视化所需的 NORMAL MODES 位移矩阵。"))
        return

    st.subheader(tr("振动模式可视化"))
    mode_options = []
    for mode_index in sorted(result.normal_modes):
        frequency = result.frequencies_cm1[mode_index] if mode_index < len(result.frequencies_cm1) else None
        if frequency is None:
            label = tr("模态 {index}", index=mode_index)
        else:
            suffix = f" ({tr('虚频')})" if frequency < 0 else ""
            label = f"{tr('模态 {index}', index=mode_index)}: {frequency:.2f} cm^-1{suffix}"
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
            representation=structure_representation,
            model_size_settings=model_size_settings,
            visual_style_key=visual_style_key,
        ),
        height=640,
        scrolling=False,
    )
    magnitude_figure = create_mode_magnitude_figure(
        result.atoms,
        mode_displacements,
        visual_style_key=visual_style_key,
    )
    render_plotly_chart(
        magnitude_figure,
        key=f"{base_key}-mode-magnitude-{selected_mode}",
        file_name=f"{Path(result.source_name).stem}_mode_{selected_mode}_magnitude",
    )
    render_figure_export_controls(
        magnitude_figure,
        file_stem=f"{Path(result.source_name).stem}_mode_{selected_mode}_magnitude",
        key_prefix=f"{base_key}-mode-{selected_mode}-export",
    )
    st.dataframe(
        top_mode_atoms(result.atoms, mode_displacements),
        hide_index=True,
        use_container_width=True,
    )


def _render_pathway_section(
    pathway: PathwayResult | None,
    *,
    title: str,
    empty_message: str,
    download_label: str,
    file_name: str,
    key_prefix: str,
    reference_mode: str,
    structure_representation: str,
    show_atom_labels: bool,
    model_size_settings: Any,
    visual_style_key: str,
) -> None:
    st.subheader(title)
    if pathway is None or (not pathway.has_points and not pathway.has_frames):
        st.info(empty_message)
        return

    for warning in pathway.warnings:
        st.warning(warning)

    reference_selector = None
    x_col = pathway.x_column
    x_label = _pathway_x_label(pathway, x_col)
    if pathway.has_points and reference_mode == "selected":
        selector_options = _path_reference_options(pathway)
        if selector_options:
            reference_selector = st.selectbox(
                tr("参考点"),
                selector_options,
                key=f"{key_prefix}-reference-selector",
            )

    display_df = (
        path_display_dataframe(
            pathway.points_df,
            x_col=x_col,
            y_col="energy_hartree",
            kind=pathway.kind,
            reference_mode=reference_mode,
            reference_selector=reference_selector,
        )
        if pathway.has_points
        else pd.DataFrame()
    )
    analysis = analyze_pathway(pathway)
    _render_pathway_metrics(display_df, analysis, key_prefix=key_prefix)
    plot_y_col, plot_y_label, hover_format, hover_suffix = _resolve_path_energy_axis(reference_mode)

    if pathway.has_points and not display_df.empty:
        path_figure = create_path_figure(
            display_df,
            x_col,
            plot_y_col,
            title,
            x_label,
            y_label=plot_y_label,
            y_hover_format=hover_format,
            y_suffix=hover_suffix,
            visual_style_key=visual_style_key,
        )
        render_plotly_chart(
            path_figure,
            key=key_prefix,
            file_name=f"{Path(file_name).stem}_path",
        )
        render_figure_export_controls(
            path_figure,
            file_stem=f"{Path(file_name).stem}_path",
            key_prefix=f"{key_prefix}-export",
        )
        anomalies = analysis.get("anomalies", [])
        if anomalies:
            st.caption(tr("路径异常检查：{issues}", issues=", ".join(anomalies)))
        st.dataframe(display_df, hide_index=True, use_container_width=True)
        download_dataframe(download_label, display_df, file_name)
    else:
        st.info(tr("当前路径只有几何帧，没有可绘制的能量表。"))

    if pathway.has_frames:
        _render_pathway_animation(
            pathway,
            key_prefix=key_prefix,
            display_df=display_df,
            x_col=x_col,
            plot_y_col=plot_y_col,
            path_title=title,
            path_x_label=x_label,
            path_y_label=plot_y_label,
            hover_format=hover_format,
            hover_suffix=hover_suffix,
            representation=structure_representation,
            show_atom_labels=show_atom_labels,
            model_size_settings=model_size_settings,
            visual_style_key=visual_style_key,
            file_stem=f"{Path(file_name).stem}_{pathway.kind}",
        )
    elif pathway.has_points:
        st.info(tr("当前路径缺少结构帧，无法播放动画。"))


def _render_pathway_metrics(display_df: pd.DataFrame, analysis: dict[str, Any], *, key_prefix: str) -> None:
    metric_cols = st.columns(6)
    metric_cols[0].metric(tr("路径点数"), analysis.get("point_count", 0))
    metric_cols[1].metric(tr("帧数"), analysis.get("frame_count", 0))
    metric_cols[2].metric(
        tr("最高能点"),
        str(analysis.get("highest_point_label", "-")),
    )
    metric_cols[3].metric(
        tr("最高相对能量 (kcal/mol)"),
        format_float(analysis.get("highest_relative_energy_kcal_mol")),
    )
    metric_cols[4].metric(
        tr("前向能垒 (kcal/mol)"),
        format_float(analysis.get("forward_barrier_kcal_mol")),
    )
    metric_cols[5].metric(
        tr("后向能垒 (kcal/mol)"),
        format_float(analysis.get("reverse_barrier_kcal_mol")),
    )


def _render_pathway_animation(
    pathway: PathwayResult,
    *,
    key_prefix: str,
    display_df: pd.DataFrame,
    x_col: str,
    plot_y_col: str,
    path_title: str,
    path_x_label: str,
    path_y_label: str,
    hover_format: str,
    hover_suffix: str,
    representation: str,
    show_atom_labels: bool,
    model_size_settings: Any,
    visual_style_key: str,
    file_stem: str,
) -> None:
    st.subheader(tr("路径结构动画"))
    frame_df = pathway.frame_dataframe()
    if frame_df.empty:
        st.info(tr("当前路径缺少结构帧，无法播放动画。"))
        return
    st.caption(
        tr("支持播放 / 暂停、逐帧切换、进度拖动、速度调节和路径点联动。默认推荐固定视角，便于论文和汇报截图。")
    )
    animation_html = build_pathway_animation_html(
        pathway,
        display_df=display_df,
        path_x_col=x_col,
        path_y_col=plot_y_col,
        path_title=path_title,
        path_x_label=path_x_label,
        path_y_label=path_y_label,
        y_hover_format=hover_format,
        y_suffix=hover_suffix,
        representation=representation,
        show_atom_labels=show_atom_labels,
        model_size_settings=model_size_settings,
        show_axes=False,
        default_camera_mode="fixed_all_frames",
        component_id=f"{key_prefix}-pathway-player",
        visual_style_key=visual_style_key,
    )
    render_pathway_animation_component(html=animation_html, height=860)
    render_pathway_animation_export_controls(
        pathway,
        display_df=display_df,
        path_x_col=x_col,
        path_y_col=plot_y_col,
        path_title=path_title,
        path_x_label=path_x_label,
        path_y_label=path_y_label,
        y_hover_format=hover_format,
        y_suffix=hover_suffix,
        representation=representation,
        show_atom_labels=show_atom_labels,
        model_size_settings=model_size_settings,
        visual_style_key=visual_style_key,
        file_stem=file_stem,
        key_prefix=f"{key_prefix}-path-animation-export",
        default_show_path_plot=not display_df.empty,
    )

    with st.expander(tr("路径帧明细"), expanded=False):
        left, right = st.columns([2, 1])
        options = [
            f"{int(row.frame_index) if pd.notna(row.frame_index) else 0}: {row.label}" for row in frame_df.itertuples()
        ]
        selected_option = st.selectbox(
            tr("选择路径帧"),
            options,
            key=f"{key_prefix}-frame-selector",
        )
        selected_index = int(selected_option.split(":", 1)[0])
        selected_frame = pathway.frames[selected_index]
        with left:
            render_structure_viewer_component(
                selected_frame.atoms,
                component_id=f"{key_prefix}-frame-viewer-{selected_frame.index}",
                representation=representation,
                show_atom_labels=show_atom_labels,
                enable_measurement=True,
                model_size_settings=model_size_settings,
                visual_style_key=visual_style_key,
                height=640,
            )
        with right:
            st.dataframe(frame_df, hide_index=True, use_container_width=True)
            st.download_button(
                tr("下载路径轨迹 XYZ"),
                data=build_xyz_trajectory_text(pathway),
                file_name=f"{file_stem}_trajectory.xyz",
                mime="chemical/x-xyz",
                key=f"{key_prefix}-download-xyz",
            )


def _pathways_for_result(result: OrcaParseResult) -> dict[str, PathwayResult]:
    if result.pathways:
        return result.pathways
    pathway_map: dict[str, PathwayResult] = {}
    if not result.irc_points.empty:
        pathway_map["irc"] = PathwayResult(kind="irc", points_df=result.irc_points)
    if not result.neb_points.empty:
        pathway_map["neb"] = PathwayResult(kind="neb", points_df=result.neb_points)
    if not result.scan_points.empty:
        pathway_map["scan"] = PathwayResult(kind="scan", points_df=result.scan_points)
    return pathway_map


def _pathway_x_label(pathway: PathwayResult, x_col: str) -> str:
    if x_col == "distance_ang":
        return tr("路径距离 (Å)")
    if x_col == "distance_bohr":
        return tr("路径距离 (Bohr)")
    if x_col == "progress":
        return tr("路径进度")
    if x_col == "coordinate":
        return tr("扫描坐标") if pathway.kind == "scan" else tr("反应坐标")
    if x_col == "frame_index":
        return tr("帧索引")
    return tr("图像编号") if x_col == "image" else x_col


def _resolve_path_energy_axis(reference_mode: str) -> tuple[str, str, str, str]:
    if reference_mode == "absolute":
        return "absolute_energy_hartree", tr("绝对能量 (Hartree)"), ".8f", " Eh"
    return "relative_energy_kcal_mol", tr("相对能量 (kcal/mol)"), ".2f", " kcal/mol"


def _path_reference_options(pathway: PathwayResult) -> list[str]:
    if pathway.points_df.empty:
        return []
    if "label" in pathway.points_df.columns:
        return [str(value) for value in pathway.points_df["label"].dropna().astype(str).tolist()]
    selector_column = "image" if "image" in pathway.points_df.columns else "step"
    if selector_column in pathway.points_df.columns:
        return [str(value) for value in pathway.points_df[selector_column].dropna().tolist()]
    return []
