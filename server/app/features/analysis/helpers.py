"""Lightweight pure-function helpers shared across the analysis feature."""
from __future__ import annotations

import base64
import mimetypes
from datetime import date, datetime, time as dt_time
from pathlib import Path

SPREADSHEET_EXTENSIONS = {".xlsx", ".csv"}
TEXT_EXTENSIONS = {".txt", ".md", ".json"}
HTML_EXTENSIONS = {".html", ".htm"}


def safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def stringify(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def trim_text(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return value[: max_length - 1] + "…"


def normalize_direction_value(value: object) -> int:
    normalized = stringify(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "in", "credit", "贷", "入", "收入", "是"}:
        return 1
    if normalized in {"0", "false", "no", "n", "out", "debit", "借", "出", "支出", "否"}:
        return 0
    return int(safe_float(value)) if stringify(value).strip() else 0


def normalize_gender_value(value: object) -> int:
    normalized = stringify(value).strip().lower()
    if normalized in {"1", "male", "m", "男"}:
        return 1
    if normalized in {"0", "female", "f", "女"}:
        return 0
    return int(safe_float(value)) if stringify(value).strip() else 0


def normalize_date_value(value: object) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    text = stringify(value).strip()
    if not text:
        return ""
    if len(text) >= 10:
        return text[:10]
    return text


def normalize_time_value(value: object) -> str:
    if isinstance(value, datetime):
        return value.strftime("%H:%M:%S")
    if isinstance(value, dt_time):
        return value.strftime("%H:%M:%S")
    text = stringify(value).strip()
    if not text:
        return ""
    if len(text) >= 8:
        return text[-8:]
    return text


def normalize_risk_level_value(value: object, fallback: str) -> str:
    normalized = stringify(value).strip().lower()
    mapping = {
        "high": "high",
        "medium": "medium",
        "low": "low",
        "critical": "high",
        "高": "high",
        "高风险": "high",
        "中": "medium",
        "中风险": "medium",
        "低": "low",
        "低风险": "low",
    }
    return mapping.get(normalized, fallback)


def display_risk_level(value: str) -> str:
    return {
        "high": "高风险",
        "medium": "中风险",
        "low": "低风险",
    }.get(value, value)


def display_gender(value: object) -> str:
    normalized = normalize_gender_value(value)
    if normalized == 1:
        return "男"
    if normalized == 0 and stringify(value).strip():
        return "女"
    return "-"


def display_age(value: object) -> str:
    age = int(round(safe_float(value)))
    return str(age) if age > 0 else "-"


def confidence_label_from_probability(probability: float) -> str:
    if probability > 0.7:
        return "高置信度"
    if probability > 0.3:
        return "中置信度"
    return "低置信度"


def prediction_label(prediction: int) -> str:
    return "欺诈账户" if prediction == 1 else "非欺诈账户"


def build_actions(risk_level: str) -> list[str]:
    if risk_level == "high":
        return ["冻结高风险账户", "拉取关联交易链路", "生成案件报告并提交人工复核"]
    if risk_level == "medium":
        return ["继续重点监测", "补充核验交易凭证", "安排分析员复核"]
    return ["记录本次分析结果", "保留后续复查入口"]


def classify_asset_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in SPREADSHEET_EXTENSIONS:
        return "spreadsheet"
    if suffix in TEXT_EXTENSIONS:
        return "text"
    return "document"


def guess_mime_type(path: Path) -> str:
    return mimetypes.guess_type(str(path))[0] or "application/octet-stream"


def file_to_data_uri(path: Path, mime_type: str | None = None) -> str:
    resolved_mime = mime_type or guess_mime_type(path)
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{resolved_mime};base64,{encoded}"


def svg_to_data_uri(svg: str) -> str:
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def to_json_safe(value: object) -> object:
    if isinstance(value, dict):
        return {stringify(key): to_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_json_safe(item) for item in value]
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, dt_time):
        return value.strftime("%H:%M:%S")
    return value


def find_matching_key(columns: list[str], keywords: tuple[str, ...]) -> str | None:
    lowered = [(column or "").lower() for column in columns]
    for keyword in keywords:
        keyword_lower = keyword.lower()
        for index, column in enumerate(lowered):
            if keyword_lower in column:
                return columns[index]
    return None
