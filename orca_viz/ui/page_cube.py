from __future__ import annotations

from pathlib import Path
import json

import streamlit as st

from ..cube import (
    CubeData,
    cube_kind_label,
    cube_sample_dataframe,
    cube_summary_dataframe,
    suggest_cube_isovalue,
    suggest_cube_level_max,
)
from ..i18n import tr
from ..visualization import (
    create_cube_isosurface_figure,
    create_cube_slice_figure,
    create_structure_figure,
)
from .common import get_structure_view_settings, render_page_note, render_plotly_chart, slug_key
from .data import download_dataframe
from .export_controls import render_figure_export_controls


def render_cube_analysis(cube: CubeData, *, show_page_note: bool = True) -> None:
    base_key = slug_key(cube.source_name)
    structure_representation, show_atom_labels = get_structure_view_settings()
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
        slice_figure = create_cube_slice_figure(cube, axis=axis, index=index)
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
