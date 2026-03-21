from __future__ import annotations

from ..i18n import tr


def ts_status_label(status: str | None) -> str:
    mapping = {
        "confirmed_ts": tr("已确认 TS"),
        "multiple_imaginaries": tr("多重虚频"),
        "ts_search_without_imaginary": tr("TS 搜索但无虚频"),
        "not_ts": tr("非 TS"),
        "unknown": tr("未知"),
    }
    return mapping.get(status or "unknown", status or tr("未知"))


def process_category_label(category: str) -> str:
    mapping = {
        "orca": "ORCA",
        "python_streamlit": tr("Python / Streamlit"),
        "system_service": tr("系统服务"),
        "other": tr("其他"),
    }
    return mapping.get(category, category)


def process_risk_label(risk: str) -> str:
    mapping = {
        "low": tr("低"),
        "medium": tr("中"),
        "high": tr("高"),
    }
    return mapping.get(risk, risk)


def process_reason_text(raw_value: str) -> str:
    if not raw_value:
        return "-"
    return " / ".join(tr(part.strip()) for part in raw_value.split("|") if part.strip())
