from __future__ import annotations

import streamlit as st

from ..i18n import tr


def render_home_header() -> None:
    st.markdown(
        f"""
        <div class="orca-hero">
          <div class="orca-hero-kicker">{tr("科研生产模式")}</div>
          <h1>{tr("ORCA Visualizer")}</h1>
          <p>{tr("面向 ORCA 输出、GBW 和 cube 数据的科研可视化工作台。默认提供结构、频率、光谱、电荷、路径和论文级导出，不需要再去 Origin 或 PPT 做大幅二次美化。")}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_single_mode_empty_state(intent: str = "") -> None:
    render_home_header()
    if intent == "gbw":
        st.info(tr("已切换到 GBW 工作流，请在左侧上传 `.gbw` 文件，并尽量同时提供 `.densities`、`.densitiesinfo`、`.property.txt`。"))
    elif intent == "single":
        st.info(tr("已切换到单文件工作流，请在左侧上传一个 ORCA / XYZ / cube / GBW 文件，或直接输入本地路径。"))

    st.subheader(tr("快速进入"))
    cards = [
        {
            "meta": tr("主入口"),
            "title": tr("单文件解析"),
            "body": tr("上传 `.out/.log/.txt/.xyz/.cube/.gbw` 或直接填路径，优先用于单个任务的结构、频率、TDDFT、路径和 cube 深入分析。"),
            "button": tr("进入单文件模式"),
            "mode": "single",
            "intent": "single",
            "primary": True,
        },
        {
            "meta": tr("高频任务"),
            "title": tr("GBW → cube"),
            "body": tr("把 gbw 波函数转换成电子密度、自旋密度、ESP、HOMO/LUMO 或指定轨道 cube，并直接进入高质量 2D/3D 可视化。"),
            "button": tr("进入 GBW 工作流"),
            "mode": "single",
            "intent": "gbw",
            "primary": False,
        },
        {
            "meta": tr("比较分析"),
            "title": tr("批量对比"),
            "body": tr("扫描整个文件夹，统一比较能量、虚频、激发态和路径信息，适合筛选构型、路线和候选产物。"),
            "button": tr("进入批量比较"),
            "mode": "batch",
            "intent": "",
            "primary": False,
        },
        {
            "meta": tr("生产安全"),
            "title": tr("后台监控"),
            "body": tr("检查 ORCA、Python/Streamlit 和长期驻留高占用任务，避免计算资源被不必要地持续占用。"),
            "button": tr("进入后台监控"),
            "mode": "monitor",
            "intent": "",
            "primary": False,
        },
        {
            "meta": tr("安装与诊断"),
            "title": tr("环境检测"),
            "body": tr("检查 ORCA 主程序、orca_plot、orca_2json 等工具可用性，并提供普通用户安装与开发安装指引。"),
            "button": tr("进入环境检测"),
            "mode": "environment",
            "intent": "",
            "primary": False,
        },
    ]

    for row in [cards[:3], cards[3:]]:
        columns = st.columns(len(row))
        for card, column in zip(row, columns):
            with column:
                st.markdown(
                    f"""
                    <div class="orca-card">
                      <div class="orca-card-meta">{card["meta"]}</div>
                      <h3>{card["title"]}</h3>
                      <p>{card["body"]}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(
                    card["button"],
                    key=f"landing-action-{card['mode']}-{card['intent'] or 'default'}",
                    use_container_width=True,
                    type="primary" if card["primary"] else "secondary",
                ):
                    st.session_state["app-mode-radio"] = card["mode"]
                    if card["intent"]:
                        st.session_state["single-landing-intent"] = card["intent"]
                    else:
                        st.session_state.pop("single-landing-intent", None)
                    st.rerun()

    left, right = st.columns([1.15, 0.85])
    with left:
        st.markdown(
            f"""
            <div class="orca-section-card">
              <h3>{tr("建议工作流")}</h3>
              <p>{tr("1. 在左侧选择分析模式并导入文件。 2. 上传后先看总览与运行信息。 3. 再切到结构、频率、谱图、路径和电荷页。 4. 需要汇报或论文时直接用导出预设输出图片。")}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            f"""
            <div class="orca-section-card">
              <h3>{tr("支持数据")}</h3>
              <p>{tr("ORCA 输出、XYZ、cube、GBW；单文件模式支持 sidecar 自动发现，批量模式支持递归扫描。")}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
