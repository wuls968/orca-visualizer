from __future__ import annotations

import pandas as pd
import streamlit as st

from ..cube import CubeData
from ..i18n import tr
from ..parser import OrcaParseResult, summarize_results
from ..visualization import create_batch_energy_figure, create_batch_excited_state_figure
from .common import render_page_note, render_page_visual_style_override, render_plotly_chart, resolve_visual_style_key
from .data import download_dataframe, load_batch_inputs


def render_batch_mode() -> None:
    render_page_visual_style_override("batch-page")
    visual_style_key = resolve_visual_style_key("batch-page")
    render_page_note(
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

    loaded_items = load_batch_inputs(uploaded_files, folder_path)
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
            render_plotly_chart(
                create_batch_energy_figure(summary_df, visual_style_key=visual_style_key),
                key="batch-energy-chart",
                file_name="orca_batch_energy",
            )
        with right:
            render_plotly_chart(
                create_batch_excited_state_figure(summary_df, visual_style_key=visual_style_key),
                key="batch-excited-state-chart",
                file_name="orca_batch_excited_states",
            )
        download_dataframe(tr("下载 ORCA 汇总 CSV"), summary_df, "orca_batch_summary.csv")
    else:
        st.info(tr("当前批量输入中没有可比较的 ORCA 输出文件。"))

    if cube_results:
        st.subheader(tr("Cube 文件汇总"))
        cube_summary = pd.DataFrame(
            {
                "file": [cube.source_name for cube in cube_results],
                "atoms": [cube.atom_count for cube in cube_results],
                "grid": [
                    f"{cube.grid_shape[0]}x{cube.grid_shape[1]}x{cube.grid_shape[2]}"
                    for cube in cube_results
                ],
                "voxels": [cube.voxel_count for cube in cube_results],
                "min_value": [cube.value_range[0] for cube in cube_results],
                "max_value": [cube.value_range[1] for cube in cube_results],
            }
        )
        st.dataframe(cube_summary, hide_index=True, use_container_width=True)
        download_dataframe(tr("下载 cube 汇总 CSV"), cube_summary, "cube_batch_summary.csv")
