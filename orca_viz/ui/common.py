from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from ase import Atoms
import streamlit as st
import streamlit.components.v1 as components

from ..i18n import tr
from ..plot_theme import (
    ModelSizeSettings,
    clamp_model_size_settings,
    model_size_preset,
    visual_style_display_map,
    visual_style_preset,
)
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

SHARED_ORCA_PATH_HINT_KEY = "shared-local-orca-path-hint"


def inject_app_styles() -> None:
    palette = {
        "page_spot_a": "rgba(14, 116, 144, 0.08)",
        "page_spot_b": "rgba(15, 118, 110, 0.10)",
        "page_top": "#f8fafc",
        "page_bottom": "#ffffff",
        "border": "#cbd5e1",
        "paper_bg": "#ffffff",
        "viewer_card_bg": "#ffffff",
        "viewer_card_alt_bg": "#f8fafc",
        "accent_secondary": "#0f766e",
        "accent_secondary_dark": "#115e59",
        "text_primary": "#0f172a",
        "text_muted": "#475569",
    }
    css = "\n".join(
        [
            "<style>",
            ".stApp {",
            "  background:",
            f"    radial-gradient(circle at top right, {palette['page_spot_a']}, transparent 34%),",
            f"    radial-gradient(circle at top left, {palette['page_spot_b']}, transparent 28%),",
            f"    linear-gradient(180deg, {palette['page_top']} 0%, {palette['page_bottom']} 16%, {palette['page_bottom']} 100%);",
            "}",
            ".orca-hero {",
            f"  border: 1px solid {palette['border']};",
            "  border-radius: 24px;",
            "  padding: 26px 28px;",
            f"  background: linear-gradient(135deg, {palette['paper_bg']}F5 0%, {palette['viewer_card_alt_bg']}FA 100%);",
            "  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.08);",
            "  margin-bottom: 16px;",
            "}",
            ".orca-hero-kicker {",
            "  display: inline-block;",
            "  margin-bottom: 12px;",
            "  padding: 6px 12px;",
            "  border-radius: 999px;",
            f"  background: {palette['accent_secondary']}1A;",
            f"  color: {palette['accent_secondary_dark']};",
            "  font-size: 12px;",
            "  font-weight: 700;",
            "  letter-spacing: 0.06em;",
            "  text-transform: uppercase;",
            "}",
            ".orca-hero h1 {",
            "  margin: 0 0 10px 0;",
            "  font-size: 32px;",
            "  line-height: 1.16;",
            f"  color: {palette['text_primary']};",
            "}",
            ".orca-hero p {",
            "  margin: 0;",
            "  max-width: 900px;",
            f"  color: {palette['text_muted']};",
            "  font-size: 16px;",
            "  line-height: 1.7;",
            "}",
            ".orca-card-grid {",
            "  display: grid;",
            "  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));",
            "  gap: 14px;",
            "  margin: 12px 0 8px 0;",
            "}",
            ".orca-card {",
            f"  border: 1px solid {palette['border']};",
            "  border-radius: 20px;",
            "  padding: 18px 18px 16px 18px;",
            f"  background: {palette['viewer_card_bg']}F0;",
            "  min-height: 156px;",
            "  box-shadow: 0 16px 40px rgba(15, 23, 42, 0.06);",
            "}",
            ".orca-card h3 {",
            "  margin: 0 0 8px 0;",
            "  font-size: 18px;",
            f"  color: {palette['text_primary']};",
            "}",
            ".orca-card .orca-card-meta {",
            "  display: inline-block;",
            "  margin-bottom: 8px;",
            "  font-size: 12px;",
            f"  color: {palette['accent_secondary']};",
            "  font-weight: 700;",
            "  letter-spacing: 0.04em;",
            "  text-transform: uppercase;",
            "}",
            ".orca-card p {",
            "  margin: 0;",
            f"  color: {palette['text_muted']};",
            "  font-size: 14px;",
            "  line-height: 1.6;",
            "}",
            ".orca-section-card {",
            f"  border: 1px solid {palette['border']};",
            "  border-radius: 20px;",
            "  padding: 18px 20px;",
            f"  background: {palette['viewer_card_bg']}F5;",
            "  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.05);",
            "  margin-bottom: 12px;",
            "}",
            ".orca-section-card h3 {",
            "  margin: 0 0 6px 0;",
            "  font-size: 19px;",
            f"  color: {palette['text_primary']};",
            "}",
            ".orca-section-card p {",
            "  margin: 0;",
            f"  color: {palette['text_muted']};",
            "  font-size: 14px;",
            "  line-height: 1.7;",
            "}",
            ".orca-status-panel {",
            f"  border: 1px solid {palette['border']};",
            "  border-radius: 18px;",
            "  padding: 14px 16px;",
            f"  background: linear-gradient(180deg, {palette['viewer_card_alt_bg']}FA 0%, {palette['viewer_card_bg']}FA 100%);",
            "  margin: 8px 0 14px 0;",
            "}",
            ".orca-status-title {",
            "  font-weight: 700;",
            f"  color: {palette['text_primary']};",
            "  margin-bottom: 4px;",
            "  font-size: 15px;",
            "}",
            ".orca-status-meta {",
            f"  color: {palette['text_muted']};",
            "  font-size: 13px;",
            "  line-height: 1.6;",
            "}",
            ".orca-status-steps {",
            "  margin-top: 10px;",
            "  display: grid;",
            "  gap: 6px;",
            "}",
            ".orca-status-step {",
            "  display: flex;",
            "  gap: 8px;",
            "  align-items: flex-start;",
            f"  color: {palette['text_muted']};",
            "  font-size: 13px;",
            "}",
            ".orca-status-step strong {",
            f"  color: {palette['text_primary']};",
            "}",
            "</style>",
        ]
    )
    st.markdown(
        css,
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
    model_size_settings: ModelSizeSettings,
    visual_style_key: str,
    height: int = 760,
) -> None:
    components.html(
        build_structure_viewer_html(
            atoms,
            representation=representation,
            show_atom_labels=show_atom_labels,
            enable_measurement=enable_measurement,
            component_id=component_id,
            model_size_settings=model_size_settings,
            visual_style_key=visual_style_key,
        ),
        height=height,
        scrolling=False,
    )


def render_pathway_animation_component(
    *,
    html: str,
    height: int = 760,
) -> None:
    components.html(
        html,
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
    if suffix == ".html":
        return "text/html"
    if suffix == ".svg":
        return "image/svg+xml"
    if suffix == ".pdf":
        return "application/pdf"
    if suffix == ".gif":
        return "image/gif"
    if suffix == ".mp4":
        return "video/mp4"
    if suffix == ".webm":
        return "video/webm"
    return "image/png"


def slug_key(value: str) -> str:
    return value.replace(".", "-").replace("/", "-").replace(" ", "-").lower()


def get_shared_orca_path_hint(default: str = "") -> str:
    return str(st.session_state.get(SHARED_ORCA_PATH_HINT_KEY, default)).strip()


def set_shared_orca_path_hint(value: str) -> None:
    st.session_state[SHARED_ORCA_PATH_HINT_KEY] = value.strip()


def render_global_structure_controls() -> None:
    _normalize_representation_state()
    st.selectbox(
        tr("分子模型"),
        ["ball_stick", "space_filling", "stick", "wireframe"],
        index=0,
        key="global-structure-representation",
        format_func=lambda value: {
            "ball_stick": tr("球棍"),
            "space_filling": tr("空间填充"),
            "stick": tr("棒状"),
            "wireframe": tr("线框"),
        }.get(value, value),
    )
    st.checkbox(tr("显示原子标签"), value=False, key="global-structure-labels")
    with st.expander(tr("模型尺寸"), expanded=False):
        _render_model_size_controls("global-model-size", defaults=model_size_preset("standard"))


def render_global_visual_style_controls() -> None:
    style_labels = visual_style_display_map()
    style_keys = list(style_labels)
    current_key = resolve_visual_style_key()
    if st.session_state.get("global-visual-style-preset") not in style_keys:
        st.session_state["global-visual-style-preset"] = current_key
    st.selectbox(
        tr("出图配色方案"),
        options=style_keys,
        index=style_keys.index(st.session_state.get("global-visual-style-preset", current_key)),
        key="global-visual-style-preset",
        format_func=lambda value: tr(style_labels.get(value, value)),
    )
    st.caption(
        tr("仅影响图表、3D 结构、动画和导出，不改变页面主题。")
    )
    st.caption(tr("当前全局配色：{style}", style=tr(style_labels.get(resolve_visual_style_key(), current_key))))
    if st.button(tr("恢复默认配色"), key="global-visual-style-reset"):
        st.session_state["global-visual-style-preset"] = "scientific_standard"
        st.rerun()


def render_page_visual_style_override(page_key: str) -> None:
    override_key = f"{page_key}-visual-style-override"
    style_labels = visual_style_display_map()
    with st.expander(tr("当前页面出图配色"), expanded=False):
        st.checkbox(
            tr("当前页面覆盖全局配色"),
            value=bool(st.session_state.get(override_key, False)),
            key=override_key,
        )
        if st.session_state.get(override_key, False):
            local_key = f"{page_key}-visual-style-preset"
            style_keys = list(style_labels)
            if st.session_state.get(local_key) not in style_keys:
                st.session_state[local_key] = resolve_visual_style_key()
            st.selectbox(
                tr("页面配色预设"),
                options=style_keys,
                index=style_keys.index(st.session_state.get(local_key, "scientific_standard")),
                key=local_key,
                format_func=lambda value: tr(style_labels.get(value, value)),
            )
            if st.button(tr("页面恢复默认配色"), key=f"{page_key}-visual-style-reset"):
                st.session_state[local_key] = "scientific_standard"
                st.rerun()
        else:
            current_style = resolve_visual_style_key()
            st.caption(tr("当前页面未覆盖，继承全局配色：{style}", style=tr(style_labels.get(current_style, current_style))))


def render_page_model_size_override(page_key: str) -> None:
    override_key = f"{page_key}-model-size-override"
    with st.expander(tr("当前页面 3D 模型尺寸"), expanded=False):
        st.checkbox(
            tr("当前页面覆盖全局尺寸"),
            value=bool(st.session_state.get(override_key, False)),
            key=override_key,
        )
        if st.session_state.get(override_key, False):
            _render_model_size_controls(
                f"{page_key}-model-size",
                defaults=resolve_model_size_settings(None),
            )
        else:
            settings = resolve_model_size_settings(None)
            st.caption(
                tr(
                    "当前页面未覆盖，继承全局：球大小 {sphere:.2f} / 棍粗细 {stick:.2f} Å / 空间填充比例 {space:.2f} / 线框粗细 {wire:.2f}",
                    sphere=settings.sphere_scale,
                    stick=settings.stick_radius,
                    space=settings.space_filling_scale,
                    wire=settings.wireframe_line_width,
                )
            )


def get_structure_view_settings(page_key: str | None = None) -> tuple[str, bool, ModelSizeSettings]:
    _normalize_representation_state()
    representation = str(st.session_state.get("global-structure-representation", "ball_stick"))
    show_labels = bool(st.session_state.get("global-structure-labels", False))
    return representation, show_labels, resolve_model_size_settings(page_key)


def resolve_visual_style_key(page_key: str | None = None) -> str:
    if page_key and st.session_state.get(f"{page_key}-visual-style-override", False):
        return visual_style_preset(
            str(st.session_state.get(f"{page_key}-visual-style-preset", "scientific_standard"))
        ).key
    return visual_style_preset(str(st.session_state.get("global-visual-style-preset", "scientific_standard"))).key


def resolve_model_size_settings(page_key: str | None = None) -> ModelSizeSettings:
    if page_key and st.session_state.get(f"{page_key}-model-size-override", False):
        return _read_model_size_settings(f"{page_key}-model-size", model_size_preset("standard"))
    return _read_model_size_settings("global-model-size", model_size_preset("standard"))


def _render_model_size_controls(prefix: str, *, defaults: ModelSizeSettings) -> None:
    _ensure_model_size_state(prefix, defaults)
    st.selectbox(
        tr("模型尺寸预设"),
        options=["compact", "standard", "presentation"],
        index=["compact", "standard", "presentation"].index(
            st.session_state.get(f"{prefix}-preset", defaults.preset_key)
        ),
        format_func=lambda value: {
            "compact": tr("紧凑"),
            "standard": tr("标准"),
            "presentation": tr("演示"),
        }[value],
        key=f"{prefix}-preset",
        on_change=_apply_model_size_preset_to_state,
        args=(prefix,),
    )
    row1 = st.columns(2)
    row1[0].slider(
        tr("球大小"),
        min_value=0.15,
        max_value=0.50,
        value=float(st.session_state[f"{prefix}-sphere-scale"]),
        step=0.01,
        key=f"{prefix}-sphere-scale",
    )
    row1[1].slider(
        tr("棍粗细"),
        min_value=0.08,
        max_value=0.35,
        value=float(st.session_state[f"{prefix}-stick-radius"]),
        step=0.01,
        key=f"{prefix}-stick-radius",
    )
    row2 = st.columns(2)
    row2[0].slider(
        tr("空间填充比例"),
        min_value=0.70,
        max_value=1.35,
        value=float(st.session_state[f"{prefix}-space-filling-scale"]),
        step=0.01,
        key=f"{prefix}-space-filling-scale",
    )
    row2[1].slider(
        tr("线框粗细"),
        min_value=0.8,
        max_value=4.5,
        value=float(st.session_state[f"{prefix}-wireframe-line-width"]),
        step=0.1,
        key=f"{prefix}-wireframe-line-width",
    )
    if st.button(tr("恢复默认"), key=f"{prefix}-reset-model-size"):
        _set_model_size_state(prefix, model_size_preset("standard"))
        st.rerun()


def _apply_model_size_preset_to_state(prefix: str) -> None:
    preset_key = st.session_state.get(f"{prefix}-preset", "standard")
    _set_model_size_state(prefix, model_size_preset(str(preset_key)))


def _ensure_model_size_state(prefix: str, defaults: ModelSizeSettings) -> None:
    if f"{prefix}-initialized" in st.session_state:
        return
    _set_model_size_state(prefix, defaults)
    st.session_state[f"{prefix}-initialized"] = True


def _set_model_size_state(prefix: str, settings: ModelSizeSettings) -> None:
    normalized = clamp_model_size_settings(settings)
    st.session_state[f"{prefix}-preset"] = normalized.preset_key
    st.session_state[f"{prefix}-sphere-scale"] = float(normalized.sphere_scale)
    st.session_state[f"{prefix}-stick-radius"] = float(normalized.stick_radius)
    st.session_state[f"{prefix}-space-filling-scale"] = float(normalized.space_filling_scale)
    st.session_state[f"{prefix}-wireframe-line-width"] = float(normalized.wireframe_line_width)


def _read_model_size_settings(prefix: str, defaults: ModelSizeSettings) -> ModelSizeSettings:
    _ensure_model_size_state(prefix, defaults)
    return clamp_model_size_settings(
        ModelSizeSettings(
            preset_key=str(st.session_state.get(f"{prefix}-preset", defaults.preset_key)),
            sphere_scale=float(st.session_state.get(f"{prefix}-sphere-scale", defaults.sphere_scale)),
            stick_radius=float(st.session_state.get(f"{prefix}-stick-radius", defaults.stick_radius)),
            space_filling_scale=float(
                st.session_state.get(f"{prefix}-space-filling-scale", defaults.space_filling_scale)
            ),
            wireframe_line_width=float(
                st.session_state.get(f"{prefix}-wireframe-line-width", defaults.wireframe_line_width)
            ),
        )
    )


def _normalize_representation_state() -> None:
    raw_value = st.session_state.get("global-structure-representation")
    if raw_value in {"ball_stick", "space_filling", "stick", "wireframe"}:
        return
    legacy_map = {
        tr("球棍"): "ball_stick",
        tr("空间填充"): "space_filling",
        tr("棒状"): "stick",
        tr("线框"): "wireframe",
        "Ball-and-Stick": "ball_stick",
        "Space Filling": "space_filling",
        "Stick": "stick",
        "Wireframe": "wireframe",
    }
    st.session_state["global-structure-representation"] = legacy_map.get(str(raw_value), "ball_stick")
