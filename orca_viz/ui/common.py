from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from ase import Atoms
import streamlit as st
import streamlit.components.v1 as components

from ..i18n import tr
from ..visualization import build_structure_viewer_html


PLOTLY_MODEBAR_TRANSLATIONS = {
    "zh": {
        "Zoom": "缩放",
        "Pan": "平移",
        "Zoom in": "放大",
        "Zoom out": "缩小",
        "Autoscale": "自动缩放",
        "Reset axes": "重置坐标轴",
        "Download plot as a png": "下载 PNG 图片",
        "Box Select": "框选",
        "Lasso Select": "套索选择",
        "Toggle Spike Lines": "切换尖峰线",
        "Show closest data on hover": "显示最近点悬浮信息",
        "Compare data on hover": "比较悬浮信息",
        "Orbit Rotation": "环绕旋转",
        "Turntable Rotation": "转盘旋转",
        "Reset camera to default": "重置默认视角",
    },
    "en": {
        "缩放": "Zoom",
        "平移": "Pan",
        "放大": "Zoom in",
        "缩小": "Zoom out",
        "自动缩放": "Autoscale",
        "重置坐标轴": "Reset axes",
        "下载 PNG 图片": "Download plot as a png",
        "框选": "Box Select",
        "套索选择": "Lasso Select",
        "切换尖峰线": "Toggle Spike Lines",
        "显示最近点悬浮信息": "Show closest data on hover",
        "比较悬浮信息": "Compare data on hover",
        "环绕旋转": "Orbit Rotation",
        "转盘旋转": "Turntable Rotation",
        "重置默认视角": "Reset camera to default",
    },
}
PLOTLY_MODEBAR_PREFIX_TRANSLATIONS = {
    "zh": {
        "Produced with Plotly.js": "基于 Plotly.js 构建",
    },
    "en": {
        "基于 Plotly.js 构建": "Produced with Plotly.js",
    },
}


def inject_app_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
          background:
            radial-gradient(circle at top right, rgba(14, 116, 144, 0.08), transparent 34%),
            radial-gradient(circle at top left, rgba(15, 118, 110, 0.10), transparent 28%),
            linear-gradient(180deg, #f8fafc 0%, #ffffff 16%, #ffffff 100%);
        }
        .orca-hero {
          border: 1px solid rgba(148, 163, 184, 0.22);
          border-radius: 24px;
          padding: 26px 28px;
          background: linear-gradient(135deg, rgba(255,255,255,0.96) 0%, rgba(248,250,252,0.98) 100%);
          box-shadow: 0 24px 60px rgba(15, 23, 42, 0.08);
          margin-bottom: 16px;
        }
        .orca-hero-kicker {
          display: inline-block;
          margin-bottom: 12px;
          padding: 6px 12px;
          border-radius: 999px;
          background: rgba(15, 118, 110, 0.10);
          color: #115e59;
          font-size: 12px;
          font-weight: 700;
          letter-spacing: 0.06em;
          text-transform: uppercase;
        }
        .orca-hero h1 {
          margin: 0 0 10px 0;
          font-size: 32px;
          line-height: 1.16;
          color: #0f172a;
        }
        .orca-hero p {
          margin: 0;
          max-width: 900px;
          color: #334155;
          font-size: 16px;
          line-height: 1.7;
        }
        .orca-card-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
          gap: 14px;
          margin: 12px 0 8px 0;
        }
        .orca-card {
          border: 1px solid rgba(148, 163, 184, 0.20);
          border-radius: 20px;
          padding: 18px 18px 16px 18px;
          background: rgba(255, 255, 255, 0.94);
          min-height: 156px;
          box-shadow: 0 16px 40px rgba(15, 23, 42, 0.06);
        }
        .orca-card h3 {
          margin: 0 0 8px 0;
          font-size: 18px;
          color: #0f172a;
        }
        .orca-card .orca-card-meta {
          display: inline-block;
          margin-bottom: 8px;
          font-size: 12px;
          color: #0f766e;
          font-weight: 700;
          letter-spacing: 0.04em;
          text-transform: uppercase;
        }
        .orca-card p {
          margin: 0;
          color: #475569;
          font-size: 14px;
          line-height: 1.6;
        }
        .orca-section-card {
          border: 1px solid rgba(148, 163, 184, 0.18);
          border-radius: 20px;
          padding: 18px 20px;
          background: rgba(255, 255, 255, 0.96);
          box-shadow: 0 12px 28px rgba(15, 23, 42, 0.05);
          margin-bottom: 12px;
        }
        .orca-section-card h3 {
          margin: 0 0 6px 0;
          font-size: 19px;
          color: #0f172a;
        }
        .orca-section-card p {
          margin: 0;
          color: #475569;
          font-size: 14px;
          line-height: 1.7;
        }
        .orca-status-panel {
          border: 1px solid rgba(14, 165, 233, 0.18);
          border-radius: 18px;
          padding: 14px 16px;
          background: linear-gradient(180deg, rgba(248,250,252,0.98) 0%, rgba(255,255,255,0.98) 100%);
          margin: 8px 0 14px 0;
        }
        .orca-status-title {
          font-weight: 700;
          color: #0f172a;
          margin-bottom: 4px;
          font-size: 15px;
        }
        .orca-status-meta {
          color: #475569;
          font-size: 13px;
          line-height: 1.6;
        }
        .orca-status-steps {
          margin-top: 10px;
          display: grid;
          gap: 6px;
        }
        .orca-status-step {
          display: flex;
          gap: 8px;
          align-items: flex-start;
          color: #334155;
          font-size: 13px;
        }
        .orca-status-step strong {
          color: #0f172a;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def plotly_config(*, enable_scroll_zoom: bool = False, file_name: str = "orca_visualizer_plot") -> dict[str, Any]:
    language = st.session_state.get("ui_language", "zh")
    return {
        "displaylogo": False,
        "responsive": True,
        "scrollZoom": enable_scroll_zoom,
        "locale": "zh-CN" if language == "zh" else "en-US",
        "toImageButtonOptions": {
            "format": "png",
            "filename": file_name,
            "scale": 3,
        },
    }


def render_plotly_chart(
    figure: Any,
    *,
    key: str,
    use_container_width: bool = True,
    enable_scroll_zoom: bool = False,
    file_name: str = "orca_visualizer_plot",
) -> None:
    st.plotly_chart(
        figure,
        use_container_width=use_container_width,
        key=key,
        config=plotly_config(enable_scroll_zoom=enable_scroll_zoom, file_name=file_name),
    )


def inject_plotly_modebar_localizer(language: str) -> None:
    script = f"""
    <script>
    const modebarLabels = {json.dumps(PLOTLY_MODEBAR_TRANSLATIONS, ensure_ascii=False)};
    const prefixLabels = {json.dumps(PLOTLY_MODEBAR_PREFIX_TRANSLATIONS, ensure_ascii=False)};
    const currentLanguage = {json.dumps(language)};

    function translateLabel(label) {{
      if (!label) return label;
      const trimmed = label.trim();
      const direct = (modebarLabels[currentLanguage] || {{}})[trimmed];
      if (direct) return direct;
      for (const [sourcePrefix, targetPrefix] of Object.entries(prefixLabels[currentLanguage] || {{}})) {{
        if (trimmed.startsWith(sourcePrefix)) {{
          return targetPrefix + trimmed.slice(sourcePrefix.length);
        }}
      }}
      return trimmed;
    }}

    function patchModebar(documentRef) {{
      if (!documentRef) return;
      documentRef.querySelectorAll('.modebar-btn').forEach((button) => {{
        const rawLabel = button.getAttribute('data-title') || button.getAttribute('title') || button.getAttribute('aria-label');
        const translated = translateLabel(rawLabel);
        if (!translated || translated === rawLabel) return;
        button.setAttribute('data-title', translated);
        button.setAttribute('title', translated);
        button.setAttribute('aria-label', translated);
      }});
    }}

    function patchAllModebars() {{
      try {{
        patchModebar(window.parent.document);
        window.parent.document.querySelectorAll('iframe').forEach((frame) => {{
          try {{
            patchModebar(frame.contentDocument || frame.contentWindow.document);
          }} catch (innerError) {{}}
        }});
      }} catch (error) {{}}
    }}

    patchAllModebars();
    try {{
      window.parent.__orcaPlotlyModebarLanguage = currentLanguage;
      if (!window.parent.__orcaPlotlyModebarObserver) {{
        const observer = new MutationObserver(() => patchAllModebars());
        observer.observe(window.parent.document.body, {{ childList: true, subtree: true, attributes: true }});
        window.parent.__orcaPlotlyModebarObserver = observer;
        window.parent.__orcaPlotlyModebarTimer = window.parent.setInterval(patchAllModebars, 1200);
      }}
    }} catch (error) {{}}
    </script>
    """
    components.html(script, height=0, width=0)


def render_page_note(title: str, lines: list[str]) -> None:
    with st.expander(title, expanded=False):
        st.markdown("\n".join(f"- {line}" for line in lines))


def render_section_card(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="orca-section-card">
          <h3>{title}</h3>
          <p>{body}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_structure_viewer_component(
    atoms: Atoms,
    *,
    component_id: str,
    representation: str,
    show_atom_labels: bool,
    enable_measurement: bool,
    height: int = 760,
) -> None:
    components.html(
        build_structure_viewer_html(
            atoms,
            representation=representation,
            show_atom_labels=show_atom_labels,
            enable_measurement=enable_measurement,
            component_id=component_id,
        ),
        height=height,
        scrolling=False,
    )


def set_task_state(
    key: str,
    *,
    title: str,
    state: str,
    detail: str,
    steps: list[str] | None = None,
) -> None:
    st.session_state[key] = {
        "title": title,
        "state": state,
        "detail": detail,
        "steps": steps or [],
        "updated_at": datetime.now().strftime("%H:%M:%S"),
    }


def render_task_state(key: str) -> None:
    task = st.session_state.get(key)
    if not task:
        return
    state_map = {
        "running": tr("运行中"),
        "done": tr("已完成"),
        "failed": tr("失败"),
        "idle": tr("就绪"),
    }
    step_html = "".join(
        f"<div class='orca-status-step'><strong>{index + 1}.</strong><span>{step}</span></div>"
        for index, step in enumerate(task.get("steps", []))
    )
    st.markdown(
        f"""
        <div class="orca-status-panel">
          <div class="orca-status-title">{task['title']} · {state_map.get(task['state'], task['state'])}</div>
          <div class="orca-status-meta">{task['detail']}<br>{tr("最近更新")} {task['updated_at']}</div>
          {f"<div class='orca-status-steps'>{step_html}</div>" if step_html else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_float(value: float | None) -> str:
    return "-" if value is None else f"{value:.8f}"


def image_mime_type(file_name: str) -> str:
    suffix = Path(file_name).suffix.lower()
    if suffix == ".svg":
        return "image/svg+xml"
    if suffix == ".pdf":
        return "application/pdf"
    return "image/png"


def slug_key(value: str) -> str:
    return value.replace(".", "-").replace("/", "-").replace(" ", "-").lower()


def get_structure_view_settings() -> tuple[str, bool]:
    representation_map = {
        tr("球棍"): "ball_stick",
        tr("空间填充"): "space_filling",
        tr("棒状"): "stick",
        tr("线框"): "wireframe",
    }
    label = st.session_state.get("global-structure-representation", tr("球棍"))
    representation = representation_map.get(label, "ball_stick")
    show_labels = bool(st.session_state.get("global-structure-labels", False))
    return representation, show_labels
