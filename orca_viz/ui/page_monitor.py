from __future__ import annotations

import streamlit as st

from ..i18n import tr
from ..process_monitor import process_dataframe, snapshot_processes
from .common import render_page_note
from .data import download_dataframe, localize_process_dataframe


def render_process_monitor() -> None:
    render_page_note(
        tr("后台监控说明"),
        [
            tr("扫描当前用户的后台进程，重点标记 ORCA、Python/Streamlit 和长时间高占用任务。"),
            tr("不会主动结束任何进程；默认只做检测与提示，避免误杀正常任务。"),
            tr("如果发现旧的 Streamlit、ORCA 或未知高占用进程长期驻留，再决定是否手动结束。"),
        ],
    )
    with st.sidebar:
        st.subheader(tr("监控设置"))
        hide_self_related = st.checkbox(
            tr("隐藏本软件相关进程"),
            value=True,
            key="process-monitor-hide-self",
        )
        hide_system_services = st.checkbox(
            tr("隐藏系统服务"),
            value=True,
            key="process-monitor-hide-system",
        )
        only_suspicious = st.checkbox(
            tr("仅显示中高风险进程"),
            value=True,
            key="process-monitor-only-suspicious",
        )
        st.button(tr("刷新后台检测"), key="process-monitor-refresh")

    try:
        snapshot = snapshot_processes()
    except Exception as exc:
        st.error(str(exc))
        return
    summary = snapshot["summary"]
    st.caption(f"{tr('检测时间')}: {snapshot['captured_at']}")

    summary_cols = st.columns(6)
    summary_cols[0].metric(tr("总进程数"), summary["total_processes"])
    summary_cols[1].metric(tr("可疑进程数"), summary["suspicious_processes"])
    summary_cols[2].metric(tr("ORCA 相关数"), summary["orca_related_processes"])
    summary_cols[3].metric(tr("驻留进程数"), summary["resident_processes"])
    summary_cols[4].metric(tr("可疑 CPU 合计 (%)"), f"{summary['suspicious_cpu_percent']:.1f}")
    summary_cols[5].metric(tr("最高内存占用 (%)"), f"{summary['max_memory_percent']:.1f}")

    suspicious_df = localize_process_dataframe(
        process_dataframe(
            snapshot["records"],
            include_command=True,
            hide_self_related=hide_self_related,
            hide_system_services=hide_system_services,
            only_suspicious=True,
        )
    )
    if not suspicious_df.empty:
        st.warning(tr("检测到可能长期驻留或高占用的后台进程，请检查是否需要保留。"))
        st.subheader(tr("可疑进程"))
        st.dataframe(suspicious_df, hide_index=True, use_container_width=True)
    else:
        st.success(tr("当前没有检测到明显可疑的后台驻留进程。"))

    current_view_df = localize_process_dataframe(
        process_dataframe(
            snapshot["records"],
            include_command=True,
            hide_self_related=hide_self_related,
            hide_system_services=hide_system_services,
            only_suspicious=only_suspicious,
        )
    )
    if not current_view_df.empty:
        download_dataframe(
            tr("下载进程快照 CSV"),
            current_view_df,
            "background_process_snapshot.csv",
        )

    left, right = st.columns(2)
    with left:
        st.subheader(tr("CPU 排名前 10"))
        st.dataframe(
            localize_process_dataframe(
                process_dataframe(
                    snapshot["top_cpu"],
                    include_command=False,
                    hide_self_related=hide_self_related,
                    hide_system_services=hide_system_services,
                    only_suspicious=False,
                )
            ),
            hide_index=True,
            use_container_width=True,
        )
    with right:
        st.subheader(tr("内存排名前 10"))
        st.dataframe(
            localize_process_dataframe(
                process_dataframe(
                    snapshot["top_memory"],
                    include_command=False,
                    hide_self_related=hide_self_related,
                    hide_system_services=hide_system_services,
                    only_suspicious=False,
                )
            ),
            hide_index=True,
            use_container_width=True,
        )

    with st.expander(tr("进程类别说明"), expanded=False):
        st.markdown(
            "\n".join(
                [
                    f"- {tr('orca: ORCA 或 MPI 相关计算任务')}",
                    f"- {tr('python: Python、Streamlit、Jupyter 等脚本型任务')}",
                    f"- {tr('system: 当前用户空间下的系统服务或 launch agent')}",
                    f"- {tr('other: 其他普通用户进程')}",
                ]
            )
        )

    if not current_view_df.empty:
        with st.expander(tr("后台监控"), expanded=False):
            st.dataframe(current_view_df, hide_index=True, use_container_width=True)
