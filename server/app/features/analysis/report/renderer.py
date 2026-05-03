"""HTML report renderer for the analysis feature."""
from __future__ import annotations

import html
import subprocess
from datetime import datetime
from pathlib import Path

from app.core.config import settings

from ..helpers import (
    confidence_label_from_probability,
    display_age,
    display_gender,
    display_risk_level,
    file_to_data_uri,
    prediction_label,
    safe_float,
    stringify,
)
from .charts import (
    build_confidence_distribution_svg,
    build_confidence_vs_prediction_svg,
    build_correlation_heatmap_svg,
    build_high_risk_features_svg,
    build_link_analysis_svg,
    build_model_comparison_svg,
    build_prediction_distribution_svg,
    build_probability_distribution_svg,
    build_probability_violin_boxplot_svg,
    get_report_account_scores,
)

REPORT_TITLE = "金融欺诈检测分析报告"


def render_report(*, job_id: str, assets: list[dict], normalized: dict, result: dict, storage_dir: Path) -> Path:
    report_dir = storage_dir / job_id
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "report.html"
    report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    background_uri = _build_background_data_uri()
    user_info_html = _build_report_user_info_table(normalized, result)
    prediction_html = _build_report_prediction_table(result)
    link_analysis_text = _build_report_link_analysis_text(assets, normalized, result)
    link_graph_uri = build_link_analysis_svg(result)
    chart_rows = _build_report_chart_rows(assets, normalized, result)

    html_content = f"""
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>{REPORT_TITLE}</title>
  <style>
    @page {{
      size: A4;
      margin: 0mm;
    }}
    html {{
      font-family: "Microsoft YaHei", "SimHei", Arial, sans-serif;
      color: #333;
      margin: 0;
      padding: 0;
      width: 100%;
      height: 100%;
      box-sizing: border-box;
      -webkit-print-color-adjust: exact !important;
      print-color-adjust: exact !important;
    }}
    body {{
      margin: 0;
      padding: 0;
      width: 100%;
      min-height: 100%;
      box-sizing: border-box;
      background-image: url('{background_uri}');
      background-repeat: no-repeat;
      background-position: center center;
      background-size: 100% 100%;
      -webkit-print-color-adjust: exact !important;
      print-color-adjust: exact !important;
    }}
    .top-spacer {{
      height: 25mm;
      width: 100%;
    }}
    .page-content {{
      margin: 0 15mm 12mm;
      padding: 1px;
      box-sizing: border-box;
      position: relative;
      z-index: 1;
    }}
    h1, h2 {{
      text-align: center;
      color: #2c3e50;
    }}
    h1 {{
      font-size: 28px;
      margin-top: 0;
      padding-top: 10px;
    }}
    .subtitle {{
      font-size: 16px;
      text-align: center;
      margin-top: 10px;
      margin-bottom: 30px;
      color: #555;
    }}
    h2 {{
      font-size: 22px;
      margin-top: 40px;
      border-bottom: 2px solid #ccc;
      padding-bottom: 5px;
    }}
    .data-table {{
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 30px;
      font-size: 14px;
      background-color: #fff;
    }}
    .data-table th, .data-table td {{
      border: 1px solid #ccc;
      padding: 8px;
      text-align: center;
    }}
    .user-info-table th {{
      background-color: #2980b9;
      color: white;
    }}
    .data-table th {{
      background-color: #3498db;
      color: white;
    }}
    .img-table {{
      width: 100%;
      border-collapse: separate;
      border-spacing: 15px 5px;
      margin-bottom: 40px;
    }}
    .chart-td {{
      width: 50%;
      vertical-align: top;
      padding: 0;
    }}
    .chart-card {{
      background-color: #fff;
      border-radius: 8px;
      padding: 12px 15px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.10);
      text-align: center;
      height: 320px;
      box-sizing: border-box;
      display: flex;
      flex-direction: column;
      justify-content: flex-start;
      overflow: hidden;
    }}
    .chart-card h3 {{
      font-size: 18px;
      margin-top: 0;
      margin-bottom: -15px;
      color: #2c3e50;
      height: 44px;
      line-height: 22px;
      flex-shrink: 0;
    }}
    .chart-card img {{
      max-width: 100%;
      max-height: calc(100% - 44px - 12px - 2px);
      object-fit: contain;
      border: 1px solid #ccc;
      border-radius: 4px;
      margin: 0 auto;
      flex-grow: 1;
      display: block;
      background: #fff;
    }}
    .chart-card-full {{
      background-color: #fff;
      border-radius: 8px;
      padding: 15px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.10);
      text-align: center;
      margin-bottom: 25px;
      page-break-inside: avoid;
    }}
    .chart-card-full h3 {{
      font-size: 20px;
      margin-top: 0;
      margin-bottom: 15px;
    }}
    .chart-card-full img {{
      width: 100%;
      max-height: 340px;
      object-fit: contain;
      border: 1px solid #ddd;
      border-radius: 4px;
      background: #fff;
    }}
    .analysis-text-box {{
      background-color: #f8f9fa;
      border-left: 5px solid #3498db;
      padding: 15px 20px;
      margin-top: 35px;
      font-size: 15px;
      line-height: 1.6;
      text-align: justify;
    }}
    .analysis-text-box p {{
      margin-bottom: 12px;
    }}
    .analysis-text-box p:last-child {{
      margin-bottom: 0;
    }}
  </style>
</head>
<body>
  <div class="page-content">
    <div class="top-spacer"></div>
    <h1>{REPORT_TITLE}</h1>
    <div class="subtitle">
      当前使用模型版本：1.56&nbsp;&nbsp;&nbsp;&nbsp;
      当前使用参数版本：2.5&nbsp;&nbsp;&nbsp;&nbsp;
      生成报告时间：{report_time}
    </div>
    <h2>一、交易账户静态信息</h2>
    {user_info_html}
    <h2>二、预测结果</h2>
    {prediction_html}
    <h2>三、链路分析</h2>
    <div class="chart-card-full">
      <h3>金融交易链路分析图</h3>
      <img src="{link_graph_uri}" alt="金融交易链路分析图" />
    </div>
    <div class="analysis-text-box">
      {link_analysis_text}
    </div>
    <h2>四、分析图表</h2>
    <table class="img-table">
      {chart_rows}
    </table>
  </div>
</body>
</html>
"""
    report_path.write_text(html_content.strip(), encoding="utf-8")
    write_pdf_report(report_path, report_dir / "report.pdf")
    return report_path


def _build_background_data_uri() -> str:
    legacy_root = Path(settings.legacy_result_dir).parent
    for background_path, mime_type in (
        (legacy_root / "back.png", "image/png"),
        (legacy_root / "back.jpg", "image/jpeg"),
        (legacy_root / "back.jpeg", "image/jpeg"),
    ):
        if background_path.exists():
            return file_to_data_uri(background_path, mime_type)
    return "none"


def _build_report_user_info_table(normalized: dict, result: dict) -> str:
    rows = _extract_report_user_rows(normalized, result)
    body = "".join(
        "<tr>"
        f"<td>{html.escape(item['account'])}</td>"
        f"<td>{html.escape(item['gender'])}</td>"
        f"<td>{html.escape(item['age'])}</td>"
        "</tr>"
        for item in rows
    )
    return (
        '<table class="data-table user-info-table">'
        "<thead><tr><th>转账账户</th><th>性别</th><th>年龄</th></tr></thead>"
        f"<tbody>{body}</tbody></table>"
    )


def _build_report_prediction_table(result: dict) -> str:
    score_rows = get_report_account_scores(result)
    if not score_rows:
        probability = float(result.get("confidence", 0.0))
        from ..helpers import normalize_risk_level_value
        prediction = 1 if normalize_risk_level_value(result.get("risk_level"), "low") == "high" else 0
        score_rows = [
            {
                "prediction": prediction,
                "probability": probability,
                "gru_probability": probability,
                "xgb_probability": probability,
                "confidence_label": confidence_label_from_probability(probability),
            }
        ]

    body_rows: list[str] = []
    for item in score_rows:
        cl = stringify(item.get("confidence_label")).strip() or confidence_label_from_probability(
            safe_float(item.get("probability"))
        )
        row_style = ""
        if "高置信度" in cl:
            row_style = ' style="background-color: #FFC0CB;"'
        elif "中置信度" in cl:
            row_style = ' style="background-color: #FFFF99;"'
        body_rows.append(
            f"<tr{row_style}>"
            f"<td>{html.escape(prediction_label(int(safe_float(item.get('prediction')))))}</td>"
            f"<td>{safe_float(item.get('probability')):.6f}</td>"
            f"<td>{safe_float(item.get('gru_probability')):.6f}</td>"
            f"<td>{safe_float(item.get('xgb_probability')):.6f}</td>"
            f"<td>{html.escape(cl)}</td>"
            "</tr>"
        )

    return (
        '<table class="data-table"><tbody>'
        "<tr><th>预测结果</th><th>AT-GNN模型总概率</th><th>传递模块概率</th><th>图核模块概率</th><th>置信度评估</th></tr>"
        f"{''.join(body_rows)}"
        "</tbody></table>"
    )


def _build_report_link_analysis_text(assets: list[dict], normalized: dict, result: dict) -> str:
    candidates = result.get("transaction_candidates", [])
    accounts = [stringify(item.get("account")).strip() for item in result.get("link_path", []) if stringify(item.get("account")).strip()]
    amounts = [safe_float(item.get("amount")) for item in candidates]
    valid_amounts = [amount for amount in amounts if amount > 0]
    highest_amount = max(valid_amounts, default=0.0)
    image_count = len([asset for asset in assets if stringify(asset.get("mime_type")).startswith("image/")])
    document_count = len([asset for asset in assets if asset.get("asset_type") == "document"])
    spreadsheet_count = len([asset for asset in assets if asset.get("asset_type") == "spreadsheet"])
    strongest_account = accounts[0] if accounts else "待确认账户"
    counterpart = accounts[1] if len(accounts) > 1 else "待确认对手账户"
    risk_signals = result.get("risk_signals", [])

    paragraphs = [
        (
            f"<p><strong>总体概览：</strong>本次多模态分析共覆盖 <strong>{len(assets)}</strong> 份输入资产，"
            f"其中包含 <strong>{document_count}</strong> 份文档/图片证据、"
            f"<strong>{spreadsheet_count}</strong> 份结构化表格，识别出 <strong>{len(candidates)}</strong> 条候选交易线索。</p>"
        ),
        (
            f"<p><strong>关键节点分析：</strong>账户 <strong>{html.escape(strongest_account)}</strong> 为当前链路中的重点关注节点，"
            f"与账户 <strong>{html.escape(counterpart)}</strong> 构成了最主要的资金关联路径，"
            f"整体风险等级判定为 <strong>{html.escape(display_risk_level(result.get('risk_level', 'low')))}</strong>。</p>"
        ),
        (
            f"<p><strong>交易模式分析：</strong>当前识别到的最高交易金额为 <strong>{highest_amount:.2f}</strong>，"
            f"已提取 <strong>{len(risk_signals)}</strong> 项风险信号。"
            f"{'已纳入图片凭证交叉核验。' if image_count else '本次未上传图片凭证。'}</p>"
        ),
        (
            f"<p><strong>结论与建议：</strong>{html.escape(stringify(result.get('narrative')))}"
            "建议结合下方图表与证据预览，对关键账户、关键金额与上传凭证进行进一步复核。</p>"
        ),
    ]
    return "".join(paragraphs)


def _build_report_chart_rows(assets: list[dict], normalized: dict, result: dict) -> str:
    cards: list[tuple[str, str]] = [
        ("预测结果分布图", build_prediction_distribution_svg(result)),
        ("样本置信度分布", build_confidence_distribution_svg(result)),
        ("预测概率分布图", build_probability_distribution_svg(result)),
        ("传递模块与图核模块概率对比", build_model_comparison_svg(result)),
        ("高风险样本 TOP3 特征均值", build_high_risk_features_svg(normalized, result)),
        ("预测概率的箱线图与小提琴图", build_probability_violin_boxplot_svg(result)),
        ("模型概率之间的相关性热力图", build_correlation_heatmap_svg(result)),
        ("置信度与预测标签的关系", build_confidence_vs_prediction_svg(result)),
    ]

    rows: list[str] = []
    for index in range(0, len(cards), 2):
        left_title, left_src = cards[index]
        right_title, right_src = cards[index + 1]
        rows.append(
            "<tr>"
            f"{_build_chart_cell(left_title, left_src)}"
            f"{_build_chart_cell(right_title, right_src)}"
            "</tr>"
        )
    return "".join(rows)


def _build_chart_cell(title: str, src: str) -> str:
    return (
        '<td class="chart-td"><div class="chart-card">'
        f"<h3>{html.escape(title)}</h3>"
        f'<img src="{src}" alt="{html.escape(title)}" />'
        "</div></td>"
    )


def _extract_report_user_rows(normalized: dict, result: dict) -> list[dict[str, str]]:
    account_rows = get_report_account_scores(result)
    account_meta: dict[str, dict[str, str]] = {}
    for transaction in normalized.get("standardized_transactions", []) or []:
        if not isinstance(transaction, dict):
            continue
        account = stringify(transaction.get("zhdh")).strip()
        if not account or account in account_meta:
            continue
        account_meta[account] = {
            "gender": display_gender(transaction.get("xb")),
            "age": display_age(transaction.get("年龄")),
        }

    rows: list[dict[str, str]] = []
    seen_accounts: set[str] = set()
    for item in account_rows:
        account = stringify(item.get("account")).strip()
        if not account or account in seen_accounts:
            continue
        seen_accounts.add(account)
        meta = account_meta.get(account, {})
        rows.append(
            {
                "account": account,
                "gender": meta.get("gender", "-"),
                "age": meta.get("age", "-"),
            }
        )

    for account in normalized.get("entities", {}).get("accounts", []) or []:
        account_text = stringify(account).strip()
        if not account_text or account_text in seen_accounts:
            continue
        seen_accounts.add(account_text)
        meta = account_meta.get(account_text, {})
        rows.append(
            {
                "account": account_text,
                "gender": meta.get("gender", "-"),
                "age": meta.get("age", "-"),
            }
        )
        if len(rows) >= 8:
            break

    if not rows:
        rows.append({"account": "待补充证据", "gender": "-", "age": "-"})
    return rows


def write_pdf_report(report_path: Path, pdf_path: Path) -> None:
    edge_executable = _find_edge_executable()
    if edge_executable is None:
        raise RuntimeError("未找到 Microsoft Edge，无法导出 PDF 报告")

    profile_dir = report_path.parent / ".edge-pdf-profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    command = [
        str(edge_executable),
        "--headless",
        "--disable-gpu",
        "--allow-file-access-from-files",
        "--no-first-run",
        "--no-default-browser-check",
        f"--user-data-dir={profile_dir}",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path.resolve()}",
        report_path.resolve().as_uri(),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        timeout=120,
        check=False,
    )
    if completed.returncode != 0 or not pdf_path.exists():
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(detail or "PDF 报告生成失败")


def _find_edge_executable() -> Path | None:
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None
