from __future__ import annotations

from pathlib import Path
import json

import streamlit as st

from ..cube import (
    CubeData,
    cube_grid_is_compatible,
    cube_phase_visibility,
    cube_kind_label,
    cube_sample_dataframe,
    cube_summary_dataframe,
    find_companion_density_cube_path,
    parse_cube_file,
    suggest_cube_isovalue,
    suggest_cube_level_min,
    suggest_cube_level_max,
)
from ..i18n import tr
from ..visualization import (
    create_cube_isosurface_figure,
    create_cube_slice_figure,
    create_structure_figure,
)
from .common import (
    get_structure_view_settings,
    render_page_visual_style_override,
    render_page_model_size_override,
    render_page_note,
    render_plotly_chart,
    resolve_visual_style_key,
    slug_key,
)
from .data import download_dataframe
from .export_controls import render_figure_export_controls


def render_cube_analysis(cube: CubeData, *, show_page_note: bool = True) -> None:
    base_key = slug_key(cube.source_name)
    render_page_visual_style_override(f"{base_key}-cube")
    render_page_model_size_override(f"{base_key}-cube")
    structure_representation, show_atom_labels, model_size_settings = get_structure_view_settings(f"{base_key}-cube")
    visual_style_key = resolve_visual_style_key(f"{base_key}-cube")
    cube_kind = cube.metadata.get("cube_kind", "generic")
    cube_kind_name = cube.metadata.get("cube_kind_label", cube_kind_label(cube_kind))
    if show_page_note:
        render_page_note(
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
        st.caption(
            tr("总览页显示网格摘要和参考结构。当前自动识别为：{cube_kind_name}。", cube_kind_name=cube_kind_name)
        )
        left, right = st.columns([1, 2])
        left.dataframe(cube_summary_dataframe(cube), hide_index=True, use_container_width=True)
        with right:
            render_plotly_chart(
                create_structure_figure(
                    cube.atoms,
                    representation=structure_representation,
                    show_atom_labels=show_atom_labels,
                    model_size_settings=model_size_settings,
                    visual_style_key=visual_style_key,
                ),
                key=f"{base_key}-cube-structure",
                enable_scroll_zoom=True,
                file_name=f"{Path(cube.source_name).stem}_structure",
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
        slice_figure = create_cube_slice_figure(
            cube,
            axis=axis,
            index=index,
            visual_style_key=visual_style_key,
        )
        render_plotly_chart(
            slice_figure,
            key=f"{base_key}-cube-slice",
            file_name=f"{Path(cube.source_name).stem}_{axis}_slice_{index}",
        )
        render_figure_export_controls(
            slice_figure,
            file_stem=f"{Path(cube.source_name).stem}_{axis}_slice_{index}",
            key_prefix=f"{base_key}-cube-slice-export",
        )

    with tabs[2]:
        esp_surface_cube: CubeData | None = None
        esp_surface_mode = "default"
        esp_density_surface_available = False
        if cube_kind == "esp":
            companion_path = cube.metadata.get("esp_surface_density_path")
            if companion_path:
                companion_candidate = Path(companion_path)
            else:
                companion_candidate = find_companion_density_cube_path(cube)
            if companion_candidate and companion_candidate.exists():
                try:
                    parsed_surface_cube = parse_cube_file(companion_candidate)
                except Exception:
                    parsed_surface_cube = None
                if (
                    parsed_surface_cube is not None
                    and parsed_surface_cube.metadata.get("cube_kind") in {"electron_density", "density"}
                    and cube_grid_is_compatible(cube, parsed_surface_cube)
                ):
                    esp_surface_cube = parsed_surface_cube
                    esp_density_surface_available = True

        if cube_kind == "esp":
            if esp_density_surface_available:
                st.caption(
                    tr(
                        "ESP 3D 图支持两种模式：传统红/蓝等势面，以及更符合化学习惯的“电子密度表面上的 ESP 着色图”。"
                    )
                )
                esp_surface_mode = {
                    tr("ESP 等势面"): "default",
                    tr("电子密度表面的 ESP 着色"): "density_surface",
                }[
                    st.radio(
                        tr("ESP 3D 模式"),
                        [tr("ESP 等势面"), tr("电子密度表面的 ESP 着色")],
                        horizontal=True,
                        key=f"{base_key}-esp-surface-mode",
                    )
                ]
                if esp_surface_mode == "density_surface":
                    st.info(
                        tr(
                            "当前 3D 图使用电子密度等值面作为外形，并用 ESP 数值着色；这更接近科研中常见的 MEP on density surface 表达。"
                        )
                    )
                else:
                    st.caption(
                        tr(
                            "ESP 等势面模式采用负势红、正势蓝的半透明表面，并对正负两侧分别做稳健阈值处理，避免蓝色一侧被核附近尖峰值吞掉。"
                        )
                    )
            else:
                st.caption(tr("ESP 3D 图采用负势红、正势蓝的半透明等势面，并对正负两侧分别做稳健阈值处理，避免蓝色一侧被核附近尖峰值吞掉。"))
                st.info(tr("若同目录中存在匹配网格的 `.eldens.cube`，这里会自动启用“电子密度表面的 ESP 着色”模式。"))
        elif cube_kind == "orbital":
            st.caption(tr("前线轨道使用分离的正负相位表面，减少颜色混浊和表面锯齿。"))
        elif cube_kind == "spin_density":
            st.caption(tr("自旋密度会分开渲染正负两相，便于区分 alpha / beta 自旋富集区域。"))
        elif cube_kind == "electron_density":
            st.caption(tr("电子密度默认采用更接近分子外表面的低阈值，并降低表面厚重感，便于科研截图和汇报。"))
        else:
            st.caption(tr("等值面页适合观察轨道形状、电子云范围和正负区域。"))
        level_source_cube = esp_surface_cube if esp_surface_mode == "density_surface" and esp_surface_cube is not None else cube
        max_level = suggest_cube_level_max(level_source_cube)
        default_level = suggest_cube_isovalue(level_source_cube)
        min_level = suggest_cube_level_min(level_source_cube)
        if max_level <= min_level:
            max_level = min_level * 1.25
        controls = st.columns(3)
        render_quality = controls[0].selectbox(
            tr("渲染质量"),
            [tr("标准"), tr("精细"), tr("极致")],
            index=2 if cube_kind in {"esp", "orbital", "spin_density"} else 1 if cube_kind == "electron_density" else 0,
            key=f"{base_key}-cube-render-quality",
        )
        surface_opacity = controls[1].slider(
            tr("表面透明度"),
            min_value=0.08,
            max_value=0.95,
            value=(
                0.76
                if cube_kind == "esp" and esp_surface_mode == "density_surface"
                else 0.20
                if cube_kind == "esp"
                else 0.82
                if cube_kind == "orbital"
                else 0.68
                if cube_kind == "spin_density"
                else 0.42
                if cube_kind == "electron_density"
                else 0.55
            ),
            step=0.02,
            key=f"{base_key}-cube-surface-opacity",
        )
        show_structure = controls[2].checkbox(
            tr("叠加结构骨架"),
            value=True,
            key=f"{base_key}-cube-show-structure",
        )
        level = st.slider(
            tr("表面密度阈值") if cube_kind == "esp" and esp_surface_mode == "density_surface" else tr("等值面阈值"),
            min_value=min_level,
            max_value=max_level,
            value=min(max(default_level, min_level), max_level),
            key=f"{base_key}-iso-level",
        )
        phase_visibility = cube_phase_visibility(cube, level)
        if cube_kind in {"orbital", "esp", "spin_density"} and esp_surface_mode != "density_surface" and phase_visibility["single_phase"]:
            if phase_visibility["positive"]:
                st.warning(tr("当前阈值只显示正相位/正符号一侧；如果你希望同时看到两侧，请适当降低等值面阈值。"))
            elif phase_visibility["negative"]:
                st.warning(tr("当前阈值只显示负相位/负符号一侧；如果你希望同时看到两侧，请适当降低等值面阈值。"))
        elif cube_kind in {"orbital", "esp", "spin_density"} and esp_surface_mode != "density_surface" and phase_visibility["empty"]:
            st.warning(tr("当前阈值过高，正负两侧都没有可见等值面，请降低阈值。"))
        isosurface_figure = create_cube_isosurface_figure(
            cube,
            level=level,
            quality=render_quality,
            show_structure=show_structure,
            opacity=surface_opacity,
            surface_mode=esp_surface_mode,
            surface_cube=esp_surface_cube,
            structure_representation=structure_representation,
            model_size_settings=model_size_settings,
            visual_style_key=visual_style_key,
        )
        render_plotly_chart(
            isosurface_figure,
            key=f"{base_key}-cube-isosurface",
            enable_scroll_zoom=True,
            file_name=f"{Path(cube.source_name).stem}_isosurface",
        )
        render_figure_export_controls(
            isosurface_figure,
            file_stem=f"{Path(cube.source_name).stem}_isosurface",
            key_prefix=f"{base_key}-cube-isosurface-export",
            note=tr("ESP 和分子轨道的 3D 图推荐优先导出高分辨率 PNG；2D slice 更适合 SVG/PDF。"),
        )

    with tabs[3]:
        st.caption(tr("导出页提供抽样点表和 cube 元数据。"))
        sample_df = cube_sample_dataframe(cube, stride=max(1, min(cube.grid_shape) // 12))
        st.dataframe(sample_df.head(500), hide_index=True, use_container_width=True)
        download_dataframe(
            tr("下载 cube 采样 CSV"), sample_df, f"{Path(cube.source_name).stem}_cube_sample.csv"
        )
        st.download_button(
            tr("下载 cube 元数据 JSON"),
            data=json.dumps(cube.metadata, ensure_ascii=False, indent=2),
            file_name=f"{Path(cube.source_name).stem}_cube_metadata.json",
        )
