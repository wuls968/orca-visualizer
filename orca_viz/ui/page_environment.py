from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from ..i18n import tr
from ..orca_runtime import (
    detect_orca_environment,
    orca_environment_dataframe,
    python_environment_dataframe,
    report_as_dict,
)
from .common import render_page_note


TOOL_CATEGORY_LABELS = {
    "core": "核心",
    "gbw_cube": "GBW / Cube",
    "json": "JSON",
    "wavefunction": "波函数",
    "spectra": "谱图",
    "vibration": "振动",
    "workflow": "工作流",
    "localization": "局域化",
    "optional": "可选",
}


def render_environment_doctor() -> None:
    render_page_note(
        tr("环境检测说明"),
        [
            tr("用于检查 Python 运行环境、ORCA 主程序以及常用 ORCA 工具是否可用。"),
            tr("普通用户优先使用一键安装脚本；开发者可使用可编辑安装。"),
            tr("检测页会列出当前可用的 ORCA 工具/插件能力，并给出缺失项建议。"),
        ],
    )

    with st.sidebar:
        st.subheader(tr("环境检测"))
        path_hint = st.text_input(
            tr("ORCA 安装目录、ORCA_HOME 或任意 ORCA 工具路径"),
            key="environment-doctor-path-hint",
        )
        st.checkbox(tr("显示可选工具"), value=True, key="environment-doctor-show-optional")
        st.button(tr("刷新环境检测"), key="environment-doctor-refresh")

    report = detect_orca_environment(path_hint=path_hint, orca_home_hint=path_hint)
    show_optional = st.session_state.get("environment-doctor-show-optional", True)

    summary_cols = st.columns(5)
    summary_cols[0].metric(tr("平台"), report.platform)
    summary_cols[1].metric(tr("Python 版本"), report.python_version)
    summary_cols[2].metric(tr("ORCA 版本"), report.detected_orca_version or tr("未知"))
    summary_cols[3].metric(
        tr("必要工具就绪"),
        f"{report.available_required_tool_count}/{report.required_tool_count}",
    )
    summary_cols[4].metric(tr("已检测工具"), f"{report.available_tool_count}/{len(report.tools)}")

    if report.available_required_tool_count == report.required_tool_count:
        st.success(tr("当前环境已经具备本软件核心工作流所需的 ORCA 工具。"))
    else:
        st.warning(tr("当前环境缺少部分核心 ORCA 工具，GBW/cube 或本地 ORCA 测试可能不可用。"))

    left, right = st.columns([1.2, 0.8])
    with left:
        st.markdown(f"**{tr('已检测到 ORCA Home')}**")
        st.code(report.orca_home or tr("未检测到 ORCA Home"), language="text")
    with right:
        st.markdown(f"**{tr('Python 解释器')}**")
        st.code(report.python_executable, language="text")

    for recommendation in _localized_recommendations(report):
        if recommendation == tr("当前核心 ORCA 工具已经就绪。"):
            st.success(recommendation)
        else:
            st.info(recommendation)

    tabs = st.tabs(
        [
            tr("ORCA 工具 / 插件检测"),
            tr("Python 环境"),
            tr("安装方式"),
        ]
    )

    with tabs[0]:
        tool_df = _tool_dataframe(report, show_optional=show_optional)
        st.dataframe(tool_df, hide_index=True, use_container_width=True)
        st.caption(tr("未提供路径提示时，程序会自动扫描 PATH、ORCA_HOME、登录 shell 环境和常见安装目录。"))

    with tabs[1]:
        package_df = python_environment_dataframe(report).rename(
            columns={
                "package": tr("工具"),
                "version": tr("版本"),
            }
        )
        st.dataframe(package_df, hide_index=True, use_container_width=True)
        st.caption(tr("可导出当前环境检测结果，便于远程排查安装问题。"))
        st.download_button(
            label=tr("下载环境报告 JSON"),
            data=json.dumps(report_as_dict(report), indent=2, ensure_ascii=False),
            file_name="orca_visualizer_environment_report.json",
            mime="application/json",
        )

    with tabs[2]:
        st.markdown(f"**{tr('推荐给普通用户的安装方式')}**")
        st.caption(tr("如果你已经装好 Node.js 和 Python 3.10 / 3.11 / 3.12，最省事的是直接用 npm 全局安装："))
        st.code(
            "\n".join(
                [
                    "npm install -g orca-visualizer",
                    "orca-visualizer",
                    "orca-visualizer doctor",
                ]
            ),
            language="bash",
        )
        st.caption(tr("npm 包不会自带 ORCA；如果要从 GBW 生成 cube，请先在本机安装好 ORCA，并让 `orca` / `orca_plot` 可被检测到。"))
        st.divider()
        st.markdown(f"**{tr('用户安装')}**")
        st.caption(tr("如果你只想直接使用软件，优先运行下面的一键安装脚本。"))
        install_tabs = st.tabs(["macOS", "Ubuntu / Linux", "Windows", tr("开发者安装")])
        with install_tabs[0]:
            st.markdown(f"**{tr('一键安装脚本')}**")
            st.code("./install_app.command\n./run_app.command", language="bash")
        with install_tabs[1]:
            st.markdown(f"**{tr('一键安装脚本')}**")
            st.code("bash install_app.sh\nbash run_app.sh", language="bash")
        with install_tabs[2]:
            st.markdown(f"**{tr('一键安装脚本')}**")
            st.code(".\\install_app.ps1\n.\\run_app.ps1\n\ninstall_app.bat\nrun_app.bat", language="powershell")
        with install_tabs[3]:
            st.caption(tr("开发者推荐使用可编辑安装，方便你直接修改代码并立即生效："))
            st.code(
                "\n".join(
                    [
                        "python -m venv .venv",
                        "source .venv/bin/activate  # Windows 使用 .\\.venv\\Scripts\\Activate.ps1",
                        "python -m pip install --upgrade pip setuptools wheel",
                        "python -m pip install -r requirements-dev.txt",
                        "python -m orca_viz.cli run",
                    ]
                ),
                language="bash",
            )
            st.caption(tr("环境诊断命令："))
            st.code("python -m orca_viz.cli doctor --json", language="bash")

    with st.expander(tr("原始环境报告"), expanded=False):
        st.json(report_as_dict(report))


def _tool_dataframe(report: object, *, show_optional: bool) -> pd.DataFrame:
    dataframe = orca_environment_dataframe(report)
    if not show_optional:
        dataframe = dataframe[dataframe["required"]]

    if dataframe.empty:
        return dataframe

    localized = dataframe.copy()
    localized["category"] = localized["category"].map(
        lambda value: tr(TOOL_CATEGORY_LABELS.get(value, value))
    )
    localized["required"] = localized["required"].map(lambda value: tr("是") if value else tr("否"))
    localized["available"] = localized["available"].map(lambda value: tr("是") if value else tr("否"))
    localized = localized.rename(
        columns={
            "category": tr("类别"),
            "tool": tr("工具"),
            "executable": "Executable",
            "purpose": tr("用途"),
            "required": tr("必要"),
            "available": tr("可用"),
            "path": tr("路径"),
        }
    )
    return localized


def _localized_recommendations(report: object) -> list[str]:
    available = {tool.key: tool.available for tool in report.tools}
    recommendations: list[str] = []
    if not available.get("orca", False):
        recommendations.append(tr("请安装 ORCA 主程序或配置 ORCA_HOME，这样软件才能运行本地计算与结果验证。"))
    if not available.get("orca_plot", False):
        recommendations.append(tr("请安装或暴露 `orca_plot`，这样才能启用 GBW 到电子密度、轨道和 ESP cube 的生成。"))
    if not available.get("orca_2json", False):
        recommendations.append(tr("如果你计划使用 JSON/property 导出工作流，建议同时安装 `orca_2json`。"))
    if not available.get("orca_mapspc", False):
        recommendations.append(tr("如果你想使用 ORCA 原生谱图后处理，建议同时安装 `orca_mapspc`。"))
    if not available.get("orca_2mkl", False):
        recommendations.append(tr("如果你想把波函数导出到 Molden/MKL 等外部查看器，建议同时安装 `orca_2mkl`。"))
    if not recommendations:
        recommendations.append(tr("当前核心 ORCA 工具已经就绪。"))
    return recommendations
