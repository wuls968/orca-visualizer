from __future__ import annotations

import streamlit as st

from orca_viz.i18n import set_language, tr
from orca_viz.ui import (
    inject_app_styles,
    inject_plotly_modebar_localizer,
    load_single_input,
    render_batch_mode,
    render_cube_analysis,
    render_environment_doctor,
    render_gbw_analysis,
    render_orca_analysis,
    render_process_monitor,
    render_single_mode_empty_state,
)


st.set_page_config(page_title="ORCA Visualizer", layout="wide")


def main() -> None:
    _configure_language()
    inject_app_styles()
    inject_plotly_modebar_localizer(st.session_state["ui_language"])
    selected_mode = _render_sidebar()

    if selected_mode == "single":
        _render_single_mode()
    elif selected_mode == "batch":
        render_batch_mode()
    elif selected_mode == "environment":
        render_environment_doctor()
    else:
        render_process_monitor()


def _configure_language() -> None:
    with st.sidebar:
        language_enabled = st.toggle(
            "English / 中文",
            value=st.session_state.get("ui_language", "zh") == "en",
            help=tr("一键切换界面中英文。"),
        )
    language = "en" if language_enabled else "zh"
    st.session_state["ui_language"] = language
    set_language(language)


def _render_sidebar() -> str:
    _apply_pending_mode_navigation()
    with st.sidebar:
        mode_labels = {
            "single": tr("单文件分析"),
            "batch": tr("批量比较"),
            "environment": tr("环境检测"),
            "monitor": tr("后台监控"),
        }
        if st.session_state.get("app-mode-radio") not in mode_labels:
            st.session_state["app-mode-radio"] = "single"
        selected_mode = st.radio(
            tr("分析模式"),
            options=list(mode_labels),
            format_func=lambda value: mode_labels[value],
            key="app-mode-radio",
        )

        st.divider()
        if selected_mode in {"single", "batch"}:
            st.markdown(
                tr(
                    "支持文件：`out` `log` `txt` `xyz` `cube`\n\n单文件模式额外支持 `gbw`。\n\n批量模式可直接读取整个文件夹。"
                )
            )
        elif selected_mode == "environment":
            st.markdown(
                tr("检查 ORCA 主程序、orca_plot、orca_2json 等工具可用性，并提供普通用户安装与开发安装指引。")
            )
        else:
            st.markdown(tr("重点查看后台驻留与高占用任务，避免本机资源被旧任务长期占用。"))

        if selected_mode == "single":
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

    return selected_mode


def _apply_pending_mode_navigation() -> None:
    pending_mode = st.session_state.pop("app-mode-radio-pending", None)
    if pending_mode:
        st.session_state["app-mode-radio"] = pending_mode


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

    loaded = load_single_input(uploaded_file, local_path, gbw_sidecar_uploads)
    if loaded is None:
        render_single_mode_empty_state(st.session_state.get("single-landing-intent", ""))
        return

    st.session_state.pop("single-landing-intent", None)
    data, data_type = loaded
    if data_type == "cube":
        render_cube_analysis(data)
    elif data_type == "gbw":
        render_gbw_analysis(data)
    else:
        render_orca_analysis(data)


if __name__ == "__main__":
    main()
