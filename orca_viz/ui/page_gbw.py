from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from ..cube import parse_cube_file
from ..gbw import (
    GbwData,
    generate_cube_from_gbw,
    list_available_densities,
    resolve_property_orbital_index,
)
from ..i18n import tr
from ..orca_runtime import resolve_orca_tool
from .common import render_page_note, render_task_state, set_task_state, slug_key
from .page_cube import render_cube_analysis


def render_gbw_analysis(gbw_data: GbwData) -> None:
    base_key = slug_key(gbw_data.source_name)
    task_key = f"{base_key}-gbw-task-state"
    render_page_note(
        tr("GBW 页面说明"),
        [
            tr("最少需要 `.gbw`；生成电子密度、自旋密度和 ESP 通常还需要同名 `.densities` 与 `.densitiesinfo`。"),
            tr("如果有 `.property.json` 或 `.property.txt`，软件会自动给出电子数、HOMO/LUMO 建议和收敛信息。"),
            tr("如果有 `.xyz`，生成出的 cube 会自动叠加参考结构；上传 sidecar 时建议使用同 stem 文件名。"),
        ],
    )
    for warning in gbw_data.warnings:
        st.warning(warning)

    render_task_state(task_key)

    detected_orca_plot = resolve_orca_tool("orca_plot")
    property_summary = gbw_data.metadata.get("property_summary", {})
    property_sources = gbw_data.metadata.get("property_summary_sources", [])
    summary_cols = st.columns(7)
    yes_no = lambda flag: tr("是") if flag else tr("否")
    summary_cols[0].metric(tr("文件"), gbw_data.source_name)
    summary_cols[1].metric(tr("有 .densities"), yes_no("densities" in gbw_data.sidecars))
    summary_cols[2].metric(tr("有 .densitiesinfo"), yes_no("densitiesinfo" in gbw_data.sidecars))
    summary_cols[3].metric(tr("有 property.json"), yes_no("property_json" in gbw_data.sidecars))
    summary_cols[4].metric(tr("有 property.txt"), yes_no("property_txt" in gbw_data.sidecars))
    summary_cols[5].metric(tr("有 .xyz"), yes_no("xyz" in gbw_data.sidecars))
    summary_cols[6].metric(tr("检测到 orca_plot"), yes_no(bool(detected_orca_plot)))
    if not detected_orca_plot:
        st.info(tr("如果这里没有检测到 `orca_plot`，可切到“环境检测”页查看 ORCA 工具可用性与安装建议。"))

    with st.expander(tr("GBW 资源信息"), expanded=False):
        st.json(
            {
                "gbw_path": str(gbw_data.file_path),
                "sidecars": {key: str(value) for key, value in gbw_data.sidecars.items()},
                "detected_orca_plot": str(detected_orca_plot) if detected_orca_plot else None,
                "property_summary": property_summary or None,
                "property_summary_sources": property_sources or None,
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
            set_task_state(
                task_key,
                title=tr("GBW 运行状态"),
                state="running",
                detail=tr("正在扫描可用 density 列表。"),
                steps=[tr("定位 orca_plot"), tr("检查 sidecar 文件"), tr("读取 density 列表")],
            )
            st.session_state[available_density_key] = list_available_densities(
                gbw_data, orca_plot_hint=orca_plot_hint
            )
            st.session_state[density_error_key] = ""
            st.session_state[density_signature_key] = scan_signature
            set_task_state(
                task_key,
                title=tr("GBW 运行状态"),
                state="done",
                detail=tr("density 列表扫描完成。"),
                steps=[tr("定位 orca_plot"), tr("检查 sidecar 文件"), tr("读取 density 列表")],
            )
        except Exception as exc:
            st.session_state[available_density_key] = []
            st.session_state[density_error_key] = str(exc)
            st.session_state[density_signature_key] = scan_signature
            set_task_state(
                task_key,
                title=tr("GBW 运行状态"),
                state="failed",
                detail=str(exc),
                steps=[tr("定位 orca_plot"), tr("检查 sidecar 文件"), tr("读取 density 列表")],
            )

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
            (tr("HOMO 能量 (Eh)"), "homo_energy_hartree"),
            (tr("HOMO 能量 (eV)"), "homo_energy_ev"),
            (tr("LUMO 能量 (Eh)"), "lumo_energy_hartree"),
            (tr("LUMO 能量 (eV)"), "lumo_energy_ev"),
            (tr("HOMO-LUMO gap (Eh)"), "homo_lumo_gap_hartree"),
            (tr("HOMO-LUMO gap (eV)"), "homo_lumo_gap_ev"),
        ]:
            if key in property_summary:
                value = property_summary[key]
                if isinstance(value, float):
                    value = f"{value:.8f}" if "hartree" in key or key.endswith("_eh") else f"{value:.4f}"
                property_rows.append((label, value))
        if property_rows:
            st.subheader(tr("Property 摘要"))
            if property_sources:
                st.caption(
                    tr(
                        "Property 数据来源：{sources}",
                        sources=", ".join(property_sources),
                    )
                )
            frontier_metrics = []
            for label, key, digits in [
                (tr("HOMO 能量 (eV)"), "homo_energy_ev", 3),
                (tr("LUMO 能量 (eV)"), "lumo_energy_ev", 3),
                (tr("HOMO-LUMO gap (eV)"), "homo_lumo_gap_ev", 3),
            ]:
                value = property_summary.get(key)
                if isinstance(value, (int, float)):
                    frontier_metrics.append((label, f"{float(value):.{digits}f}"))
            if frontier_metrics:
                metric_cols = st.columns(len(frontier_metrics))
                for column, (label, value) in zip(metric_cols, frontier_metrics, strict=False):
                    column.metric(label, value)
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
    generate_density_surface_companion = False

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
        elif plot_kind == "spin_density" and property_summary.get("closed_shell") is True:
            st.info(tr("当前 property 信息显示为 closed-shell；自旋密度通常会接近零，但仍可继续生成检查。"))

        if plot_kind == "electrostatic_potential":
            default_density = next(
                (name for name in available_densities if name.lower().endswith(".scfp")),
                f"{gbw_data.stem}.scfp",
            )
            if available_densities:
                density_name = st.selectbox(
                    tr("ESP 所用状态 density"),
                    available_densities,
                    index=available_densities.index(default_density) if default_density in available_densities else 0,
                    key=f"{base_key}-gbw-density-name-select",
                )
            else:
                density_name = st.text_input(
                    tr("ESP 所用状态 density"),
                    value=default_density,
                    key=f"{base_key}-gbw-density-name",
                )
            generate_density_surface_companion = st.checkbox(
                tr("同时生成电子密度表面（用于 ESP 着色图）"),
                value=True,
                key=f"{base_key}-gbw-generate-esp-density-surface",
            )
    else:
        st.caption(tr("轨道模式只需要 `.gbw`；HOMO/LUMO 建议值优先来自 `.property.json` / `.property.txt`，前线轨道建议 120-160 网格。"))
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
                [tr("alpha / closed shell"), tr("beta")],
                key=f"{base_key}-gbw-operator",
            )
            operator = 0 if operator_label == tr("alpha / closed shell") else 1

        requested_orbital = orbital_mode_options[orbital_mode]
        resolved_orbital_index: int | None = None
        if requested_orbital in {"HOMO", "LUMO"}:
            resolved_orbital_index = resolve_property_orbital_index(
                property_summary,
                requested_orbital,
                operator=operator,
            )
            if not disabled_reason and resolved_orbital_index is None:
                disabled_reason = tr(
                    "当前无法从 `.property.json` / `.property.txt` 解析出 {requested_orbital} 编号，请切换到“自定义”后手动输入。",
                    requested_orbital=requested_orbital,
                )
        else:
            custom_index_raw = st.text_input(
                tr("轨道编号"),
                value="",
                placeholder=tr("请输入非负轨道编号"),
                key=f"{base_key}-gbw-orbital-index",
            ).strip()
            if not custom_index_raw:
                if not disabled_reason:
                    disabled_reason = tr("请先手动输入要生成的轨道编号。")
            else:
                try:
                    parsed_custom_index = int(custom_index_raw)
                except ValueError:
                    if not disabled_reason:
                        disabled_reason = tr("轨道编号必须是非负整数。")
                else:
                    if parsed_custom_index < 0:
                        if not disabled_reason:
                            disabled_reason = tr("轨道编号必须是非负整数。")
                    else:
                        resolved_orbital_index = parsed_custom_index

        orbital_index = resolved_orbital_index
        display_cols = st.columns(3)
        display_cols[0].metric(tr("Requested orbital"), requested_orbital)
        display_cols[1].metric(
            tr("Resolved orbital index"),
            tr("未解析到") if resolved_orbital_index is None else str(resolved_orbital_index),
        )
        display_cols[2].metric(
            tr("Operator"),
            tr("alpha / closed shell") if operator == 0 else tr("beta"),
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
            set_task_state(
                task_key,
                title=tr("GBW 运行状态"),
                state="running",
                detail=tr("正在调用 orca_plot 生成 cube，请等待任务完成。"),
                steps=[
                    tr("定位 orca_plot"),
                    tr("写入交互输入"),
                    tr("执行 cube 生成"),
                    tr("加载结果并可视化"),
                ],
            )
            cube, run_info = generate_cube_from_gbw(
                gbw_data,
                plot_kind=plot_kind,
                orca_plot_hint=orca_plot_hint,
                grid_intervals=grid_intervals,
                density_name=density_name,
                orbital_index=int(orbital_index) if orbital_index is not None else None,
                operator=operator,
            )
            companion_density_path = ""
            if plot_kind == "electrostatic_potential" and generate_density_surface_companion:
                density_cube, density_run_info = generate_cube_from_gbw(
                    gbw_data,
                    plot_kind="electron_density",
                    orca_plot_hint=orca_plot_hint,
                    grid_intervals=grid_intervals,
                )
                companion_density_path = density_cube.metadata.get("path", "")
                if companion_density_path:
                    cube.metadata["esp_surface_density_path"] = companion_density_path
                run_info["density_surface_cube"] = density_run_info.get("generated_cube")
            if plot_kind == "molecular_orbital":
                run_info["requested_orbital"] = requested_orbital
                run_info["resolved_orbital_index"] = orbital_index
            st.session_state[f"{base_key}-gbw-cube-path"] = cube.metadata.get("path")
            st.session_state[f"{base_key}-gbw-esp-surface-density-path"] = companion_density_path
            st.session_state[f"{base_key}-gbw-run-info"] = run_info
            set_task_state(
                task_key,
                title=tr("GBW 运行状态"),
                state="done",
                detail=tr("cube 生成完成，可以继续检查 2D/3D 图和导出。"),
                steps=[
                    tr("定位 orca_plot"),
                    tr("写入交互输入"),
                    tr("执行 cube 生成"),
                    tr("加载结果并可视化"),
                ],
            )
            st.success(tr("cube 生成完成。"))
        except Exception as exc:
            set_task_state(
                task_key,
                title=tr("GBW 运行状态"),
                state="failed",
                detail=str(exc),
                steps=[
                    tr("定位 orca_plot"),
                    tr("写入交互输入"),
                    tr("执行 cube 生成"),
                    tr("加载结果并可视化"),
                ],
            )
            st.error(str(exc))

    render_task_state(task_key)

    run_info = st.session_state.get(f"{base_key}-gbw-run-info")
    if run_info:
        with st.expander(tr("orca_plot 运行信息"), expanded=False):
            st.json(run_info)

    cube_path = st.session_state.get(f"{base_key}-gbw-cube-path")
    if cube_path:
        cube = parse_cube_file(cube_path)
        cube.source_name = Path(cube_path).name
        companion_density_path = st.session_state.get(f"{base_key}-gbw-esp-surface-density-path", "")
        if companion_density_path:
            cube.metadata["esp_surface_density_path"] = companion_density_path
        render_cube_analysis(cube, show_page_note=False)
