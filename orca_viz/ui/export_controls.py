from __future__ import annotations

from typing import Any

import streamlit as st

from ..exporting import EXPORT_PRESETS, export_plotly_figure, normalized_export_file_name
from ..i18n import tr
from ..visualization import STATIC_IMAGE_EXPORT_AVAILABLE
from .common import image_mime_type


def render_figure_export_controls(
    figure: Any,
    *,
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

        preset_options = {
            tr("论文图"): "paper",
            tr("汇报图"): "presentation",
            tr("网页预览图"): "web",
        }
        row1 = st.columns(5)
        selected_preset_label = row1[0].selectbox(
            tr("导出预设"),
            list(preset_options),
            index=0,
            key=f"{key_prefix}-preset",
        )
        preset_key = preset_options[selected_preset_label]
        preset = EXPORT_PRESETS[preset_key]
        image_format = row1[1].selectbox(
            tr("格式"),
            ["png", "svg", "pdf"],
            index=0,
            key=f"{key_prefix}-format",
        )
        scale = row1[2].selectbox(
            tr("倍数"),
            [1, 2, 3, 4],
            index=max(0, min([1, 2, 3, 4].index(preset.scale), 3)),
            key=f"{key_prefix}-scale",
        )
        width = row1[3].number_input(
            tr("宽度(px)"),
            min_value=800,
            max_value=6000,
            value=preset.width,
            step=100,
            key=f"{key_prefix}-width",
        )
        height = row1[4].number_input(
            tr("高度(px)"),
            min_value=600,
            max_value=5000,
            value=preset.height,
            step=100,
            key=f"{key_prefix}-height",
        )

        row2 = st.columns(4)
        font_size = row2[0].number_input(
            tr("字体大小"),
            min_value=10,
            max_value=40,
            value=preset.font_size,
            step=1,
            key=f"{key_prefix}-font-size",
        )
        title_size = row2[1].number_input(
            tr("标题大小"),
            min_value=12,
            max_value=48,
            value=preset.title_size,
            step=1,
            key=f"{key_prefix}-title-size",
        )
        transparent_background = row2[2].checkbox(
            tr("透明背景"),
            value=preset.transparent_background,
            key=f"{key_prefix}-transparent-bg",
        )
        row2[3].markdown(
            f"**{tr('文件名')}**  \n`{normalized_export_file_name(file_stem, preset_key, image_format)}`"
        )

        generated_key = f"{key_prefix}-image-bytes"
        filename_key = f"{key_prefix}-image-name"
        error_key = f"{key_prefix}-image-error"

        if st.button(tr("生成静态图片"), key=f"{key_prefix}-generate"):
            try:
                image_bytes = export_plotly_figure(
                    figure,
                    image_format=image_format,
                    preset_key=preset_key,
                    width=int(width),
                    height=int(height),
                    scale=int(scale),
                    font_size=int(font_size),
                    title_size=int(title_size),
                    transparent_background=bool(transparent_background),
                )
                st.session_state[generated_key] = image_bytes
                st.session_state[filename_key] = normalized_export_file_name(
                    file_stem, preset_key, image_format
                )
                st.session_state[error_key] = ""
            except Exception as exc:
                st.session_state[generated_key] = None
                st.session_state[filename_key] = ""
                st.session_state[error_key] = str(exc)

        export_error = st.session_state.get(error_key, "")
        if export_error:
            st.error(export_error)

        image_bytes = st.session_state.get(generated_key)
        file_name = st.session_state.get(
            filename_key, normalized_export_file_name(file_stem, preset_key, image_format)
        )
        if image_bytes:
            st.download_button(
                tr("下载静态图片"),
                data=image_bytes,
                file_name=file_name,
                mime=image_mime_type(file_name),
                key=f"{key_prefix}-download",
            )
