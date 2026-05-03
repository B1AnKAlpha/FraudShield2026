"""SVG chart builders for the analysis report."""
from __future__ import annotations

import html
import math

from ..helpers import (
    confidence_label_from_probability,
    normalize_risk_level_value,
    safe_float,
    stringify,
    svg_to_data_uri,
    trim_text,
)


def get_report_account_scores(result: dict) -> list[dict]:
    raw_rows = result.get("account_scores")
    normalized_rows: list[dict] = []
    if isinstance(raw_rows, list):
        for item in raw_rows:
            if not isinstance(item, dict):
                continue
            normalized_rows.append(
                {
                    "account": stringify(item.get("account")).strip(),
                    "prediction": int(safe_float(item.get("prediction"))),
                    "probability": safe_float(item.get("probability")),
                    "gru_probability": safe_float(item.get("gru_probability")),
                    "xgb_probability": safe_float(item.get("xgb_probability")),
                    "confidence_label": stringify(item.get("confidence_label")).strip(),
                }
            )
    normalized_rows = [item for item in normalized_rows if item.get("account")]
    normalized_rows.sort(key=lambda item: item.get("probability", 0.0), reverse=True)
    return normalized_rows


def build_prediction_distribution_svg(result: dict) -> str:
    score_rows = get_report_account_scores(result)
    fraud_count = sum(1 for item in score_rows if int(item.get("prediction", 0)) == 1)
    normal_count = max(len(score_rows) - fraud_count, 0)
    total = max(fraud_count + normal_count, 1)
    fraud_ratio = fraud_count / total
    circumference = 2 * math.pi * 92
    fraud_dash = circumference * fraud_ratio
    normal_dash = max(circumference - fraud_dash, 0.0)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="520" viewBox="0 0 900 520">'
        '<rect width="900" height="520" rx="16" fill="#ffffff"/>'
        '<text x="60" y="80" font-size="32" font-weight="700" fill="#1f4e79">预测结果分布</text>'
        '<circle cx="280" cy="270" r="92" fill="none" stroke="#e8eef6" stroke-width="48"/>'
        f'<circle cx="280" cy="270" r="92" fill="none" stroke="#e57373" stroke-width="48" stroke-linecap="round" stroke-dasharray="{fraud_dash:.2f} {circumference:.2f}" transform="rotate(-90 280 270)"/>'
        f'<circle cx="280" cy="270" r="92" fill="none" stroke="#81c784" stroke-width="48" stroke-linecap="butt" stroke-dasharray="{normal_dash:.2f} {circumference:.2f}" stroke-dashoffset="{-fraud_dash:.2f}" transform="rotate(-90 280 270)"/>'
        f'<text x="280" y="258" text-anchor="middle" font-size="38" font-weight="700" fill="#2c3e50">{len(score_rows) or 1}</text>'
        '<text x="280" y="295" text-anchor="middle" font-size="20" fill="#6b7280">账户样本</text>'
        '<rect x="510" y="170" width="26" height="26" rx="6" fill="#e57373"/>'
        f'<text x="556" y="190" font-size="24" fill="#2c3e50">欺诈账户：{fraud_count}</text>'
        '<rect x="510" y="240" width="26" height="26" rx="6" fill="#81c784"/>'
        f'<text x="556" y="260" font-size="24" fill="#2c3e50">非欺诈账户：{normal_count}</text>'
        f'<text x="510" y="338" font-size="22" fill="#6b7280">欺诈占比：{fraud_ratio * 100:.1f}%</text>'
        '</svg>'
    )
    return svg_to_data_uri(svg)


def build_confidence_distribution_svg(result: dict) -> str:
    score_rows = get_report_account_scores(result)
    buckets = {"高置信度": 0, "中置信度": 0, "低置信度": 0}
    for item in score_rows:
        label = stringify(item.get("confidence_label")).strip() or confidence_label_from_probability(
            safe_float(item.get("probability"))
        )
        buckets[label] = buckets.get(label, 0) + 1
    colors = {"高置信度": "#ef9a9a", "中置信度": "#ffe082", "低置信度": "#90caf9"}
    max_count = max(buckets.values(), default=1) or 1
    bars: list[str] = []
    labels: list[str] = []
    for index, key in enumerate(["高置信度", "中置信度", "低置信度"]):
        count = buckets.get(key, 0)
        height = 240 * (count / max_count)
        x = 170 + index * 190
        y = 380 - height
        bars.append(f'<rect x="{x}" y="{y:.1f}" width="90" height="{height:.1f}" rx="12" fill="{colors[key]}"/>')
        labels.append(f'<text x="{x + 45}" y="420" text-anchor="middle" font-size="24" fill="#2c3e50">{key}</text>')
        labels.append(f'<text x="{x + 45}" y="{y - 18:.1f}" text-anchor="middle" font-size="24" fill="#2c3e50">{count}</text>')
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="520" viewBox="0 0 900 520">'
        '<rect width="900" height="520" rx="16" fill="#ffffff"/>'
        '<text x="60" y="80" font-size="32" font-weight="700" fill="#1f4e79">样本置信度分布</text>'
        '<line x1="120" y1="380" x2="780" y2="380" stroke="#94a3b8" stroke-width="3"/>'
        '<line x1="120" y1="110" x2="120" y2="380" stroke="#94a3b8" stroke-width="3"/>'
        f'{"".join(bars)}{"".join(labels)}'
        '</svg>'
    )
    return svg_to_data_uri(svg)


def build_probability_distribution_svg(result: dict) -> str:
    score_rows = get_report_account_scores(result)
    probabilities = [min(max(safe_float(item.get("probability")), 0.0), 1.0) for item in score_rows]
    bins = [0, 0, 0, 0, 0]
    for probability in probabilities:
        index = min(int(probability * 5), 4)
        bins[index] += 1
    max_count = max(bins, default=1) or 1
    bars: list[str] = []
    labels: list[str] = []
    for index, count in enumerate(bins):
        height = 220 * (count / max_count)
        x = 120 + index * 125
        y = 370 - height
        bars.append(f'<rect x="{x}" y="{y:.1f}" width="78" height="{height:.1f}" rx="10" fill="#64b5f6"/>')
        labels.append(f'<text x="{x + 39}" y="410" text-anchor="middle" font-size="20" fill="#2c3e50">{index / 5:.1f}-{(index + 1) / 5:.1f}</text>')
        labels.append(f'<text x="{x + 39}" y="{y - 16:.1f}" text-anchor="middle" font-size="22" fill="#2c3e50">{count}</text>')
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="520" viewBox="0 0 900 520">'
        '<rect width="900" height="520" rx="16" fill="#ffffff"/>'
        '<text x="60" y="80" font-size="32" font-weight="700" fill="#1f4e79">预测概率分布图</text>'
        '<line x1="90" y1="370" x2="780" y2="370" stroke="#94a3b8" stroke-width="3"/>'
        '<line x1="90" y1="110" x2="90" y2="370" stroke="#94a3b8" stroke-width="3"/>'
        f'{"".join(bars)}{"".join(labels)}'
        '</svg>'
    )
    return svg_to_data_uri(svg)


def build_model_comparison_svg(result: dict) -> str:
    score_rows = get_report_account_scores(result)[:5]
    if not score_rows:
        score_rows = [{"account": "样本1", "gru_probability": 0.0, "xgb_probability": 0.0}]
    bars: list[str] = []
    labels: list[str] = []
    for index, item in enumerate(score_rows):
        base_x = 110 + index * 145
        gru_probability = min(max(safe_float(item.get("gru_probability")), 0.0), 1.0)
        xgb_probability = min(max(safe_float(item.get("xgb_probability")), 0.0), 1.0)
        gru_height = 230 * gru_probability
        xgb_height = 230 * xgb_probability
        bars.append(f'<rect x="{base_x}" y="{370 - gru_height:.1f}" width="34" height="{gru_height:.1f}" rx="8" fill="#64b5f6"/>')
        bars.append(f'<rect x="{base_x + 44}" y="{370 - xgb_height:.1f}" width="34" height="{xgb_height:.1f}" rx="8" fill="#ffb74d"/>')
        labels.append(f'<text x="{base_x + 39}" y="404" text-anchor="middle" font-size="18" fill="#2c3e50">{html.escape(trim_text(stringify(item.get("account")) or f"#{index + 1}", 8))}</text>')
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="520" viewBox="0 0 900 520">'
        '<rect width="900" height="520" rx="16" fill="#ffffff"/>'
        '<text x="60" y="80" font-size="32" font-weight="700" fill="#1f4e79">传递模块与图核模块概率对比</text>'
        '<rect x="580" y="120" width="22" height="22" rx="5" fill="#64b5f6"/><text x="614" y="138" font-size="20" fill="#2c3e50">传递模块</text>'
        '<rect x="580" y="158" width="22" height="22" rx="5" fill="#ffb74d"/><text x="614" y="176" font-size="20" fill="#2c3e50">图核模块</text>'
        '<line x1="90" y1="370" x2="810" y2="370" stroke="#94a3b8" stroke-width="3"/>'
        '<line x1="90" y1="110" x2="90" y2="370" stroke="#94a3b8" stroke-width="3"/>'
        f'{"".join(bars)}{"".join(labels)}'
        '</svg>'
    )
    return svg_to_data_uri(svg)


def build_high_risk_features_svg(normalized: dict, result: dict) -> str:
    score_rows = get_report_account_scores(result)
    target_account = score_rows[0]["account"] if score_rows else ""
    transactions = [item for item in normalized.get("standardized_transactions", []) or [] if stringify(item.get("zhdh")).strip() == target_account]
    if not transactions:
        transactions = list(normalized.get("standardized_transactions", []) or [])
    amounts = [safe_float(item.get("jyje")) for item in transactions if safe_float(item.get("jyje")) > 0]
    counterpart_count = len({stringify(item.get("dfzh")).strip() for item in transactions if stringify(item.get("dfzh")).strip()})
    feature_rows = [
        ("平均交易金额", sum(amounts) / len(amounts) if amounts else 0.0),
        ("最大交易金额", max(amounts, default=0.0)),
        ("关联对手数", float(counterpart_count)),
    ]
    max_value = max((item[1] for item in feature_rows), default=1.0) or 1.0
    bars: list[str] = []
    labels: list[str] = []
    for index, (label, value) in enumerate(feature_rows):
        width = 420 * (value / max_value) if max_value else 0.0
        y = 150 + index * 105
        bars.append(f'<rect x="210" y="{y}" width="{width:.1f}" height="36" rx="12" fill="#90caf9"/>')
        labels.append(f'<text x="70" y="{y + 25}" font-size="24" fill="#2c3e50">{label}</text>')
        labels.append(f'<text x="{225 + width:.1f}" y="{y + 25}" font-size="22" fill="#2c3e50">{value:.2f}</text>')
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="520" viewBox="0 0 900 520">'
        '<rect width="900" height="520" rx="16" fill="#ffffff"/>'
        '<text x="60" y="80" font-size="32" font-weight="700" fill="#1f4e79">高风险样本 TOP3 特征均值</text>'
        f'{"".join(bars)}{"".join(labels)}'
        '</svg>'
    )
    return svg_to_data_uri(svg)


def build_probability_violin_boxplot_svg(result: dict) -> str:
    score_rows = get_report_account_scores(result)
    probabilities = sorted(min(max(safe_float(item.get("probability")), 0.0), 1.0) for item in score_rows)
    if not probabilities:
        probabilities = [0.0]
    minimum = probabilities[0]
    maximum = probabilities[-1]
    median = probabilities[len(probabilities) // 2]
    q1 = probabilities[max(int((len(probabilities) - 1) * 0.25), 0)]
    q3 = probabilities[max(int((len(probabilities) - 1) * 0.75), 0)]

    def y_pos(value: float) -> float:
        return 410 - value * 250

    dots = []
    for index, value in enumerate(probabilities):
        offset = (index % 5) * 18 - 36
        dots.append(f'<circle cx="{450 + offset}" cy="{y_pos(value):.1f}" r="7" fill="#64b5f6" opacity="0.75"/>')

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="520" viewBox="0 0 900 520">'
        '<rect width="900" height="520" rx="16" fill="#ffffff"/>'
        '<text x="60" y="80" font-size="32" font-weight="700" fill="#1f4e79">预测概率的箱线图与小提琴图</text>'
        '<ellipse cx="450" cy="270" rx="88" ry="140" fill="#dbeafe" opacity="0.85"/>'
        '<line x1="450" y1="160" x2="450" y2="410" stroke="#475569" stroke-width="4"/>'
        f'<line x1="450" y1="{y_pos(minimum):.1f}" x2="450" y2="{y_pos(maximum):.1f}" stroke="#334155" stroke-width="5"/>'
        f'<rect x="408" y="{y_pos(q3):.1f}" width="84" height="{max(y_pos(q1) - y_pos(q3), 12):.1f}" fill="#93c5fd" stroke="#2563eb" stroke-width="3"/>'
        f'<line x1="408" y1="{y_pos(median):.1f}" x2="492" y2="{y_pos(median):.1f}" stroke="#1e293b" stroke-width="4"/>'
        f'{"".join(dots)}'
        '<text x="560" y="200" font-size="22" fill="#2c3e50">最小值 / Q1 / 中位数 / Q3 / 最大值</text>'
        f'<text x="560" y="238" font-size="20" fill="#6b7280">{minimum:.3f} / {q1:.3f} / {median:.3f} / {q3:.3f} / {maximum:.3f}</text>'
        '</svg>'
    )
    return svg_to_data_uri(svg)


def _pearson(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        return 0.0
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((lx - left_mean) * (rx - right_mean) for lx, rx in zip(left, right, strict=True))
    left_denominator = sum((lx - left_mean) ** 2 for lx in left)
    right_denominator = sum((rx - right_mean) ** 2 for rx in right)
    denominator = math.sqrt(left_denominator * right_denominator)
    if denominator == 0:
        return 0.0
    return max(min(numerator / denominator, 1.0), -1.0)


def _heatmap_color(value: float) -> str:
    normalized = (value + 1.0) / 2.0
    red = int(255 - (80 * normalized))
    green = int(236 - (60 * normalized))
    blue = int(246 - (180 * normalized))
    return f"rgb({red},{green},{blue})"


def build_correlation_heatmap_svg(result: dict) -> str:
    score_rows = get_report_account_scores(result)
    final_values = [safe_float(item.get("probability")) for item in score_rows]
    gru_values = [safe_float(item.get("gru_probability")) for item in score_rows]
    xgb_values = [safe_float(item.get("xgb_probability")) for item in score_rows]
    labels = ["AT-GNN", "传递模块", "图核模块"]
    matrix = [
        [1.0, _pearson(final_values, gru_values), _pearson(final_values, xgb_values)],
        [_pearson(gru_values, final_values), 1.0, _pearson(gru_values, xgb_values)],
        [_pearson(xgb_values, final_values), _pearson(xgb_values, gru_values), 1.0],
    ]
    blocks: list[str] = []
    texts: list[str] = []
    for row_index, row in enumerate(matrix):
        for col_index, value in enumerate(row):
            x = 240 + col_index * 130
            y = 140 + row_index * 90
            fill = _heatmap_color(value)
            blocks.append(f'<rect x="{x}" y="{y}" width="110" height="70" rx="12" fill="{fill}"/>')
            texts.append(f'<text x="{x + 55}" y="{y + 44}" text-anchor="middle" font-size="22" font-weight="700" fill="#1f2937">{value:.2f}</text>')
    axis_labels = []
    for index, label in enumerate(labels):
        axis_labels.append(f'<text x="{295 + index * 130}" y="118" text-anchor="middle" font-size="22" fill="#2c3e50">{label}</text>')
        axis_labels.append(f'<text x="200" y="{184 + index * 90}" text-anchor="end" font-size="22" fill="#2c3e50">{label}</text>')
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="520" viewBox="0 0 900 520">'
        '<rect width="900" height="520" rx="16" fill="#ffffff"/>'
        '<text x="60" y="80" font-size="32" font-weight="700" fill="#1f4e79">模型概率之间的相关性热力图</text>'
        f'{"".join(blocks)}{"".join(texts)}{"".join(axis_labels)}'
        '</svg>'
    )
    return svg_to_data_uri(svg)


def build_confidence_vs_prediction_svg(result: dict) -> str:
    score_rows = get_report_account_scores(result)
    labels = ["高置信度", "中置信度", "低置信度"]
    fraud_counts = {label: 0 for label in labels}
    normal_counts = {label: 0 for label in labels}
    for item in score_rows:
        label = stringify(item.get("confidence_label")).strip() or confidence_label_from_probability(
            safe_float(item.get("probability"))
        )
        if label not in fraud_counts:
            continue
        if int(safe_float(item.get("prediction"))) == 1:
            fraud_counts[label] += 1
        else:
            normal_counts[label] += 1
    max_count = max([fraud_counts[label] + normal_counts[label] for label in labels], default=1) or 1
    bars: list[str] = []
    annotations: list[str] = []
    for index, label in enumerate(labels):
        total = fraud_counts[label] + normal_counts[label]
        base_x = 150 + index * 190
        fraud_height = 230 * (fraud_counts[label] / max_count)
        normal_height = 230 * (normal_counts[label] / max_count)
        fraud_y = 370 - fraud_height
        normal_y = fraud_y - normal_height
        bars.append(f'<rect x="{base_x}" y="{fraud_y:.1f}" width="92" height="{fraud_height:.1f}" rx="10" fill="#ef9a9a"/>')
        bars.append(f'<rect x="{base_x}" y="{normal_y:.1f}" width="92" height="{normal_height:.1f}" rx="10" fill="#a5d6a7"/>')
        annotations.append(f'<text x="{base_x + 46}" y="406" text-anchor="middle" font-size="22" fill="#2c3e50">{label}</text>')
        annotations.append(f'<text x="{base_x + 46}" y="{normal_y - 16:.1f}" text-anchor="middle" font-size="22" fill="#2c3e50">{total}</text>')
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="520" viewBox="0 0 900 520">'
        '<rect width="900" height="520" rx="16" fill="#ffffff"/>'
        '<text x="60" y="80" font-size="32" font-weight="700" fill="#1f4e79">置信度与预测标签的关系</text>'
        '<rect x="600" y="128" width="22" height="22" rx="5" fill="#ef9a9a"/><text x="634" y="146" font-size="20" fill="#2c3e50">欺诈账户</text>'
        '<rect x="600" y="166" width="22" height="22" rx="5" fill="#a5d6a7"/><text x="634" y="184" font-size="20" fill="#2c3e50">非欺诈账户</text>'
        '<line x1="100" y1="370" x2="800" y2="370" stroke="#94a3b8" stroke-width="3"/>'
        '<line x1="100" y1="110" x2="100" y2="370" stroke="#94a3b8" stroke-width="3"/>'
        f'{"".join(bars)}{"".join(annotations)}'
        '</svg>'
    )
    return svg_to_data_uri(svg)


def build_link_analysis_svg(result: dict) -> str:
    nodes = result.get("link_path", [])[:5]
    if not nodes:
        nodes = [{"account": "待补充证据", "risk_level": result.get("risk_level", "low"), "action": "复核"}]
    positions = [(120, 210), (300, 110), (300, 310), (520, 110), (520, 310)]
    circles = []
    arrows = []
    for index, node in enumerate(nodes):
        x, y = positions[index] if index < len(positions) else (720, 210)
        risk_level = normalize_risk_level_value(node.get("risk_level"), result.get("risk_level", "medium"))
        color = {"high": "#e74c3c", "medium": "#f39c12", "low": "#2ecc71"}.get(risk_level, "#3498db")
        circles.append(f'<circle cx="{x}" cy="{y}" r="56" fill="{color}" opacity="0.92"/>')
        circles.append(f'<text x="{x}" y="{y - 4}" font-size="18" text-anchor="middle" fill="#ffffff">{html.escape(trim_text(stringify(node.get("account")), 12))}</text>')
        circles.append(f'<text x="{x}" y="{y + 20}" font-size="16" text-anchor="middle" fill="#ffffff">{html.escape(trim_text(stringify(node.get("action")), 8))}</text>')
        if index > 0:
            prev_x, prev_y = positions[index - 1]
            arrows.append(f'<line x1="{prev_x + 52}" y1="{prev_y}" x2="{x - 52}" y2="{y}" stroke="#6b7280" stroke-width="5" marker-end="url(#arrow2)" />')
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="500" viewBox="0 0 1200 500">'
        '<defs><marker id="arrow2" markerWidth="12" markerHeight="12" refX="9" refY="6" orient="auto">'
        '<path d="M0,0 L12,6 L0,12 z" fill="#6b7280"/></marker></defs>'
        '<rect width="1200" height="500" rx="18" fill="#fdfefe"/>'
        '<rect x="20" y="20" width="1160" height="460" rx="18" fill="#ffffff" stroke="#d8dee9" stroke-width="3"/>'
        f'{"".join(arrows)}{"".join(circles)}'
        "</svg>"
    )
    return svg_to_data_uri(svg)
