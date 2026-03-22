from __future__ import annotations

from typing import Any

import streamlit as st

from ..exporting import (
    animation_export_preset,
    available_video_formats,
    export_pathway_animation,
    export_plotly_figure,
    export_presets_for_figure,
    is_3d_figure,
    is_webgl_figure,
    normalized_animation_file_name,
    normalized_export_file_name,
    static_image_export_available,
)
from ..i18n import tr
from ..plot_theme import figure_visual_style_key, visual_style_display_map
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

        three_d = is_3d_figure(figure)
        webgl = is_webgl_figure(figure)
        preset_map = export_presets_for_figure(figure)
        style_labels = visual_style_display_map()
        active_style_key = figure_visual_style_key(figure)
        st.caption(tr("当前配色方案：{style}", style=tr(style_labels.get(active_style_key, active_style_key))))

        profile_options = {
            tr("忠实导出"): "faithful",
            tr("论文导出"): "paper",
        }
        preset_options = {
            tr("论文图"): "paper",
            tr("汇报图"): "presentation",
            tr("网页预览图"): "web",
        }
        format_options = ["png", "svg", "pdf", "html"]

        row1 = st.columns(5)
        selected_profile_label = row1[0].selectbox(
            tr("导出模式"),
            list(profile_options),
            index=1,
            key=f"{key_prefix}-profile",
        )
        profile_key = profile_options[selected_profile_label]
        selected_preset_label = row1[1].selectbox(
            tr("导出预设"),
            list(preset_options),
            index=0,
            key=f"{key_prefix}-preset",
        )
        preset_key = preset_options[selected_preset_label]
        preset = preset_map[preset_key]
        image_format = row1[2].selectbox(
            tr("格式"),
            format_options,
            index=0,
            key=f"{key_prefix}-format",
        )
        scale = row1[3].selectbox(
            tr("倍数"),
            [1, 2, 3, 4],
            index=max(0, min([1, 2, 3, 4].index(preset.scale), 3)),
            key=f"{key_prefix}-scale",
            disabled=image_format == "html",
        )
        margin_mode_options = {
            tr("平衡留白"): "balanced",
            tr("紧凑裁切"): "tight",
        }
        selected_margin_label = row1[4].selectbox(
            tr("留白策略"),
            list(margin_mode_options),
            index=0,
            key=f"{key_prefix}-margin-mode",
        )
        margin_mode = margin_mode_options[selected_margin_label]

        row2 = st.columns(4)
        width = row2[0].number_input(
            tr("宽度(px)"),
            min_value=800,
            max_value=6000,
            value=preset.width,
            step=100,
            key=f"{key_prefix}-width",
        )
        height = row2[1].number_input(
            tr("高度(px)"),
            min_value=600,
            max_value=6000,
            value=preset.height,
            step=100,
            key=f"{key_prefix}-height",
        )
        font_size = row2[2].number_input(
            tr("字体大小"),
            min_value=10,
            max_value=40,
            value=preset.font_size,
            step=1,
            key=f"{key_prefix}-font-size",
            disabled=profile_key == "faithful",
        )
        title_size = row2[3].number_input(
            tr("标题大小"),
            min_value=12,
            max_value=48,
            value=preset.title_size,
            step=1,
            key=f"{key_prefix}-title-size",
            disabled=profile_key == "faithful",
        )

        view_mode = "current"
        if three_d:
            view_mode_options = {
                tr("当前视角"): "current",
                tr("适配分子"): "fit_molecule",
                tr("适配表面"): "fit_surface",
                tr("论文默认视角"): "paper_default",
            }
            selected_view_label = st.selectbox(
                tr("3D 导出视角"),
                list(view_mode_options),
                index=0,
                key=f"{key_prefix}-view-mode",
            )
            view_mode = view_mode_options[selected_view_label]
            st.caption(tr("3D 图导出默认保留当前 camera / scene；若要重新构图，请使用上面的视角选项。"))

        row3 = st.columns(4)
        hide_axes = row3[0].checkbox(
            tr("隐藏坐标轴"),
            value=three_d,
            key=f"{key_prefix}-hide-axes",
        )
        hide_legend = row3[1].checkbox(
            tr("隐藏图例"),
            value=False,
            key=f"{key_prefix}-hide-legend",
        )
        hide_colorbar = row3[2].checkbox(
            tr("隐藏色条"),
            value=False,
            key=f"{key_prefix}-hide-colorbar",
        )
        transparent_background = row3[3].checkbox(
            tr("透明背景"),
            value=preset.transparent_background,
            key=f"{key_prefix}-transparent-bg",
        )

        file_name = normalized_export_file_name(
            file_stem,
            preset_key,
            image_format,
            profile_key=profile_key,
            view_key=view_mode if three_d else None,
        )
        st.markdown(f"**{tr('文件名')}**  \n`{file_name}`")

        if image_format in {"svg", "pdf"} and three_d and webgl:
            st.info(
                tr(
                    "3D WebGL 图在 SVG / PDF 中通常仍会栅格化，若需要保留交互视角与画面请优先导出 HTML 或高分辨率 PNG。"
                )
            )
        if image_format == "html":
            st.info(tr("HTML 会保留交互视图，适合高质量 3D 分享和存档。"))
        elif not static_image_export_available():
            st.info(tr("当前环境未安装 `kaleido`，暂时不能导出高分辨率静态图，但仍可导出 HTML 交互图。"))

        generated_key = f"{key_prefix}-export-bytes"
        filename_key = f"{key_prefix}-export-name"
        error_key = f"{key_prefix}-export-error"

        can_generate = image_format == "html" or static_image_export_available()
        button_label = tr("生成 HTML 导出") if image_format == "html" else tr("生成静态图片")
        if st.button(button_label, key=f"{key_prefix}-generate", disabled=not can_generate):
            try:
                exported_bytes = export_plotly_figure(
                    figure,
                    image_format=image_format,
                    preset_key=preset_key,
                    width=int(width),
                    height=int(height),
                    scale=int(scale),
                    font_size=int(font_size),
                    title_size=int(title_size),
                    transparent_background=bool(transparent_background),
                    profile_key=profile_key,
                    view_mode=view_mode,
                    hide_axes=bool(hide_axes),
                    hide_legend=bool(hide_legend),
                    hide_colorbar=bool(hide_colorbar),
                    margin_mode=margin_mode,
                )
                st.session_state[generated_key] = exported_bytes
                st.session_state[filename_key] = file_name
                st.session_state[error_key] = ""
            except Exception as exc:
                st.session_state[generated_key] = None
                st.session_state[filename_key] = ""
                st.session_state[error_key] = str(exc)

        export_error = st.session_state.get(error_key, "")
        if export_error:
            st.error(export_error)

        exported_bytes = st.session_state.get(generated_key)
        resolved_file_name = st.session_state.get(filename_key, file_name)
        if exported_bytes:
            st.download_button(
                tr("下载 HTML 交互图") if image_format == "html" else tr("下载静态图片"),
                data=exported_bytes,
                file_name=resolved_file_name,
                mime=image_mime_type(resolved_file_name),
                key=f"{key_prefix}-download",
            )


def render_pathway_animation_export_controls(
    pathway: Any,
    *,
    display_df: Any,
    path_x_col: str,
    path_y_col: str,
    path_title: str,
    path_x_label: str,
    path_y_label: str,
    y_hover_format: str,
    y_suffix: str,
    representation: str,
    show_atom_labels: bool,
    model_size_settings: Any,
    visual_style_key: str,
    file_stem: str,
    key_prefix: str,
    default_show_path_plot: bool = True,
) -> None:
    with st.expander(tr("论文级视频导出"), expanded=False):
        if not getattr(pathway, "frames", None):
            st.info(tr("当前路径缺少结构帧，无法导出动画视频。"))
            return

        formats = available_video_formats()
        if not formats:
            st.info(tr("当前环境缺少路径视频导出后端。GIF 需要 `kaleido`，MP4 还需要 `imageio-ffmpeg`。"))
            return

        preset_options = {
            tr("论文图"): "paper",
            tr("汇报图"): "presentation",
            tr("网页预览图"): "web",
        }
        style_labels = visual_style_display_map()
        st.caption(tr("当前配色方案：{style}", style=tr(style_labels.get(visual_style_key, visual_style_key))))
        format_labels = {
            "gif": "GIF",
            "mp4": "MP4",
        }
        background_options = {
            tr("白底"): "white",
            tr("透明"): "transparent",
        }
        camera_mode_options = {
            tr("固定视角（全路径）"): "fixed_all_frames",
            tr("逐帧适配"): "fit_current_frame",
            tr("论文默认视角"): "paper_default",
        }

        row1 = st.columns(4)
        preset_label = row1[0].selectbox(
            tr("导出预设"),
            list(preset_options),
            index=0,
            key=f"{key_prefix}-preset",
        )
        preset_key = preset_options[preset_label]
        preset = animation_export_preset(preset_key)
        format_index = 1 if "mp4" in formats else 0
        video_format = formats[min(format_index, len(formats) - 1)]
        selected_format_label = row1[1].selectbox(
            tr("格式"),
            [format_labels[value] for value in formats],
            index=min(format_index, len(formats) - 1),
            key=f"{key_prefix}-format",
        )
        video_format = next(key for key, label in format_labels.items() if label == selected_format_label)
        width = int(
            row1[2].number_input(
                tr("宽度(px)"),
                min_value=960,
                max_value=6000,
                value=preset.width,
                step=120,
                key=f"{key_prefix}-width",
            )
        )
        height = int(
            row1[3].number_input(
                tr("高度(px)"),
                min_value=720,
                max_value=6000,
                value=preset.height,
                step=120,
                key=f"{key_prefix}-height",
            )
        )

        row2 = st.columns(4)
        fps = int(
            row2[0].number_input(
                tr("帧率 (fps)"),
                min_value=4,
                max_value=60,
                value=preset.fps,
                step=1,
                key=f"{key_prefix}-fps",
            )
        )
        scale = int(
            row2[1].selectbox(
                tr("倍数"),
                [1, 2, 3],
                index=max(0, min([1, 2, 3].index(preset.scale), 2)),
                key=f"{key_prefix}-scale",
            )
        )
        camera_label = row2[2].selectbox(
            tr("视角模式"),
            list(camera_mode_options),
            index=0,
            key=f"{key_prefix}-camera-mode",
        )
        background_label = row2[3].selectbox(
            tr("背景"),
            list(background_options),
            index=0,
            key=f"{key_prefix}-background",
            disabled=video_format != "gif",
        )
        background_mode = background_options[background_label]
        if video_format != "gif":
            background_mode = "white"

        row3 = st.columns(4)
        show_axes = row3[0].checkbox(tr("显示坐标轴"), value=False, key=f"{key_prefix}-axes")
        show_labels = row3[1].checkbox(
            tr("显示原子标签"),
            value=show_atom_labels,
            key=f"{key_prefix}-labels",
        )
        show_frame_number = row3[2].checkbox(tr("显示帧编号"), value=True, key=f"{key_prefix}-frame-number")
        show_path_plot = row3[3].checkbox(
            tr("叠加路径曲线"),
            value=bool(default_show_path_plot and display_df is not None and not getattr(display_df, "empty", True)),
            key=f"{key_prefix}-path-plot",
            disabled=display_df is None or getattr(display_df, "empty", True),
        )

        estimated_duration = len(pathway.frames) / max(fps, 1)
        file_name = normalized_animation_file_name(file_stem, preset_key, video_format)
        st.markdown(f"**{tr('文件名')}**  \n`{file_name}`")
        st.caption(
            tr(
                "预计时长约 {seconds:.1f} 秒，共 {frames} 帧。MP4 适合汇报与存档，GIF 适合网页预览。",
                seconds=estimated_duration,
                frames=len(pathway.frames),
            )
        )
        st.caption(
            tr("路径视频导出采用逐帧离线渲染，不是前端录屏；默认优先保证固定视角、统一留白和科研展示构图。")
        )

        generated_key = f"{key_prefix}-bytes"
        filename_key = f"{key_prefix}-name"
        error_key = f"{key_prefix}-error"

        if st.button(tr("生成路径动画"), key=f"{key_prefix}-generate"):
            try:
                exported_bytes = export_pathway_animation(
                    pathway,
                    display_df=display_df,
                    path_x_col=path_x_col,
                    path_y_col=path_y_col,
                    path_title=path_title,
                    path_x_label=path_x_label,
                    path_y_label=path_y_label,
                    y_hover_format=y_hover_format,
                    y_suffix=y_suffix,
                    representation=representation,
                    show_atom_labels=bool(show_labels),
                    model_size_settings=model_size_settings,
                    show_axes=bool(show_axes),
                    show_frame_number=bool(show_frame_number),
                    show_path_plot=bool(show_path_plot),
                    preset_key=preset_key,
                    video_format=video_format,
                    width=width,
                    height=height,
                    fps=fps,
                    scale=scale,
                    background_mode=background_mode,
                    camera_mode=camera_mode_options[camera_label],
                    visual_style_key=visual_style_key,
                )
                st.session_state[generated_key] = exported_bytes
                st.session_state[filename_key] = file_name
                st.session_state[error_key] = ""
            except Exception as exc:
                st.session_state[generated_key] = None
                st.session_state[filename_key] = ""
                st.session_state[error_key] = str(exc)

        export_error = st.session_state.get(error_key, "")
        if export_error:
            st.error(export_error)

        exported_bytes = st.session_state.get(generated_key)
        resolved_file_name = st.session_state.get(filename_key, file_name)
        if exported_bytes:
            st.download_button(
                tr("下载路径动画"),
                data=exported_bytes,
                file_name=resolved_file_name,
                mime=image_mime_type(resolved_file_name),
                key=f"{key_prefix}-download",
            )
