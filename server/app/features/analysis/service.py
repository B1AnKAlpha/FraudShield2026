from __future__ import annotations

import csv
import json
import re
import threading
import time
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import UploadFile
from openpyxl import load_workbook
import requests

from app.core.config import settings
from app.core.errors import AppError
from app.features.focus.repository import repository as focus_repository
from app.features.params.service import service as params_service

from .helpers import (
    HTML_EXTENSIONS,
    SPREADSHEET_EXTENSIONS,
    TEXT_EXTENSIONS,
    build_actions,
    classify_asset_type,
    confidence_label_from_probability,
    display_risk_level,
    find_matching_key,
    guess_mime_type,
    normalize_date_value,
    normalize_direction_value,
    normalize_gender_value,
    normalize_risk_level_value,
    normalize_time_value,
    safe_float,
    stringify,
    to_json_safe,
    trim_text,
)
from .hybrid_adapter import hybrid_adapter
from .report.renderer import REPORT_TITLE, render_report
from .repository import repository
from .schemas import (
    AnalysisAsset,
    AnalysisJobCreateResponse,
    AnalysisJobDetailResponse,
    AnalysisJobListItem,
    AnalysisJobListResponse,
    AnalysisParserSummary,
    AnalysisReportResponse,
    AnalysisResult,
    AnalysisRiskNode,
)


HTTP_RETRY_DELAYS = (0.0, 1.5, 4.0)
STANDARD_TRANSACTION_FIELDS = (
    "jylsxh",
    "zhdh",
    "dfzh",
    "jdbj",
    "jyje",
    "zhye",
    "dfhh",
    "jyrq",
    "jysj",
    "jyqd",
    "dfmccd",
    "xb",
    "年龄",
)
SPREADSHEET_FIELD_KEYWORDS = {
    "jylsxh": ("交易流水序号", "流水号", "流水", "序号", "jylsxh"),
    "zhdh": ("账户代号", "付款账户", "付款账号", "账户", "账号", "开户账号", "zhdh"),
    "dfzh": ("对方账户", "收款账户", "收款账号", "对手账户", "对方账号", "dfzh"),
    "jdbj": ("借贷标记", "借贷", "收付标志", "交易方向", "jdbj"),
    "jyje": ("交易金额", "金额", "发生额", "交易额", "jyje"),
    "zhye": ("账户余额", "余额", "可用余额", "zhye"),
    "dfhh": ("对方行号", "对方银行", "银行行号", "联行号", "dfhh"),
    "jyrq": ("交易日期", "日期", "入账日期", "jyrq"),
    "jysj": ("交易时间", "时间", "时刻", "jysj"),
    "jyqd": ("交易渠道", "渠道", "终端渠道", "jyqd"),
    "dfmccd": ("对方陌生程度", "陌生程度", "dfmccd"),
    "xb": ("性别", "xb"),
    "年龄": ("年龄", "age"),
}


class AnalysisService:
    def __init__(self) -> None:
        self.storage_dir = Path(settings.analysis_storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.http = requests.Session()
        self.http.trust_env = settings.analysis_http_trust_env

    def create_job(
        self,
        *,
        current_user: dict,
        text_payload: str,
        files: list[UploadFile],
    ) -> AnalysisJobCreateResponse:
        if not text_payload.strip() and not files:
            raise AppError("请先上传图片、文本或文件", status_code=400, code="EMPTY_ANALYSIS_INPUT")

        job_id = self._generate_job_id()
        job_dir = self.storage_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        repository.create_job(job_id=job_id, created_by=current_user["username"], status="pending")

        if text_payload.strip():
            text_path = job_dir / "text_payload.txt"
            text_path.write_text(text_payload.strip(), encoding="utf-8")
            repository.add_asset(
                asset_id=self._generate_asset_id(),
                job_id=job_id,
                asset_type="text",
                original_name="text_payload.txt",
                mime_type="text/plain",
                local_path=str(text_path),
                size_bytes=text_path.stat().st_size,
            )

        for upload in files:
            asset_id = self._generate_asset_id()
            target_path = job_dir / f"{asset_id}_{Path(upload.filename or 'upload.bin').name}"
            content = upload.file.read()
            target_path.write_bytes(content)
            repository.add_asset(
                asset_id=asset_id,
                job_id=job_id,
                asset_type=classify_asset_type(target_path),
                original_name=upload.filename or target_path.name,
                mime_type=upload.content_type or guess_mime_type(target_path),
                local_path=str(target_path),
                size_bytes=len(content),
            )

        worker = threading.Thread(target=self._process_job, args=(job_id,), daemon=True)
        worker.start()
        return AnalysisJobCreateResponse(job_id=job_id, status="pending")

    def get_job(self, job_id: str, current_user: dict) -> AnalysisJobDetailResponse:
        job = repository.get_job(job_id)
        if not job:
            raise AppError("分析任务不存在", status_code=404, code="ANALYSIS_JOB_NOT_FOUND")

        self._ensure_job_access(job, current_user)
        assets = [self._to_asset_schema(item) for item in repository.list_assets(job_id)]
        parser_summary = (
            AnalysisParserSummary(**job["parser_summary_json"]) if job.get("parser_summary_json") else None
        )
        result_payload = self._normalize_result_payload(job.get("result_json"))
        result = AnalysisResult(**result_payload) if result_payload else None
        return AnalysisJobDetailResponse(
            job_id=job["job_id"],
            status=job["status"],
            created_by=job["created_by"],
            created_at=job["created_at"],
            started_at=job["started_at"],
            finished_at=job["finished_at"],
            error_message=job["error_message"],
            assets=assets,
            parser_summary=parser_summary,
            result=result,
            report_ready=bool(job.get("report_path")),
        )

    def list_jobs(self, current_user: dict) -> AnalysisJobListResponse:
        jobs = repository.list_jobs(created_by=None if current_user["role"] == "admin" else current_user["username"])
        return AnalysisJobListResponse(
            items=[
                AnalysisJobListItem(
                    job_id=item["job_id"],
                    status=item["status"],
                    created_by=item["created_by"],
                    created_at=item["created_at"],
                    finished_at=item["finished_at"],
                    risk_level=(item["result_json"] or {}).get("risk_level"),
                    confidence=(item["result_json"] or {}).get("confidence"),
                )
                for item in jobs
            ]
        )

    def get_report(self, job_id: str, current_user: dict) -> AnalysisReportResponse:
        job = repository.get_job(job_id)
        if not job:
            raise AppError("分析任务不存在", status_code=404, code="ANALYSIS_JOB_NOT_FOUND")
        self._ensure_job_access(job, current_user)
        report_path = self._ensure_report_files(job_id, job)
        return AnalysisReportResponse(
            job_id=job_id,
            title=job.get("report_title") or REPORT_TITLE,
            html=Path(report_path).read_text(encoding="utf-8"),
        )

    def get_report_pdf_path(self, job_id: str, current_user: dict) -> Path:
        job = repository.get_job(job_id)
        if not job:
            raise AppError("分析任务不存在", status_code=404, code="ANALYSIS_JOB_NOT_FOUND")
        self._ensure_job_access(job, current_user)
        report_path = self._ensure_report_files(job_id, job)
        pdf_path = Path(report_path).with_suffix(".pdf")
        if not pdf_path.exists():
            raise AppError("PDF 报告尚未生成", status_code=404, code="ANALYSIS_PDF_NOT_FOUND")
        return pdf_path

    def _process_job(self, job_id: str) -> None:
        repository.update_job(job_id, {"status": "processing", "started_at": self._now_iso()})
        try:
            assets = repository.list_assets(job_id)
            parser_summary = AnalysisParserSummary()
            bundle = {
                "job_id": job_id,
                "documents_markdown": [],
                "documents_json": [],
                "structured_tables": [],
                "plain_texts": [],
                "source_meta": [],
            }

            mineru_assets = [asset for asset in assets if asset["asset_type"] == "document"]
            if mineru_assets:
                mineru_results = self._parse_with_mineru(mineru_assets, parser_summary)
                bundle["documents_markdown"].extend(mineru_results["documents_markdown"])
                bundle["documents_json"].extend(mineru_results["documents_json"])
                bundle["source_meta"].extend(mineru_results["source_meta"])

            for asset in assets:
                asset_path = Path(asset["local_path"])
                if asset["asset_type"] == "spreadsheet":
                    spreadsheet_payload = self._parse_spreadsheet(asset_path)
                    parser_summary.spreadsheet_assets += 1
                    bundle["structured_tables"].extend(spreadsheet_payload["tables"])
                    bundle["source_meta"].append(
                        {
                            "asset_id": asset["asset_id"],
                            "asset_type": asset["asset_type"],
                            "original_name": asset["original_name"],
                        }
                    )
                    continue

                if asset["asset_type"] == "text":
                    parser_summary.plain_text_assets += 1
                    bundle["plain_texts"].append(
                        {
                            "asset_id": asset["asset_id"],
                            "content": asset_path.read_text(encoding="utf-8", errors="ignore"),
                        }
                    )
                    bundle["source_meta"].append(
                        {
                            "asset_id": asset["asset_id"],
                            "asset_type": asset["asset_type"],
                            "original_name": asset["original_name"],
                        }
                    )

            normalized = self._normalize_bundle(bundle, parser_summary)
            normalized = self._inject_focus_history(normalized, job_id)
            result = self._analyze_bundle(normalized, parser_summary, self.storage_dir / job_id)
            result = self._apply_focus_targets(normalized, result)
            report_path = self._render_report(job_id=job_id, assets=assets, normalized=normalized, result=result)

            repository.update_job(
                job_id,
                {
                    "status": "completed",
                    "parser_summary_json": parser_summary.model_dump(),
                    "normalized_json": normalized,
                    "result_json": result,
                    "report_path": str(report_path),
                    "report_title": REPORT_TITLE,
                    "finished_at": self._now_iso(),
                    "error_message": None,
                },
            )
        except Exception as exc:
            repository.update_job(
                job_id,
                {
                    "status": "failed",
                    "error_message": str(exc),
                    "finished_at": self._now_iso(),
                },
            )

    def _parse_with_mineru(self, assets: list[dict], parser_summary: AnalysisParserSummary) -> dict:
        if not settings.mineru_api_token:
            parser_summary.warnings.append("未配置 MinerU token，文档解析已退回本地摘要模式。")
            return self._fallback_parse_documents(assets)

        try:
            html_assets = [asset for asset in assets if Path(asset["local_path"]).suffix.lower() in HTML_EXTENSIONS]
            other_assets = [asset for asset in assets if asset not in html_assets]
            merged = {
                "documents_markdown": [],
                "documents_json": [],
                "source_meta": [],
            }

            if html_assets:
                html_results = self._submit_mineru_batch(html_assets, model_version="MinerU-HTML")
                parser_summary.mineru_documents += len(html_results)
                html_payload = self._collect_mineru_results(html_results)
                merged["documents_markdown"].extend(html_payload["documents_markdown"])
                merged["documents_json"].extend(html_payload["documents_json"])
                merged["source_meta"].extend(html_payload["source_meta"])

            if other_assets:
                document_results = self._submit_mineru_batch(other_assets, model_version="vlm")
                parser_summary.mineru_documents += len(document_results)
                document_payload = self._collect_mineru_results(document_results)
                merged["documents_markdown"].extend(document_payload["documents_markdown"])
                merged["documents_json"].extend(document_payload["documents_json"])
                merged["source_meta"].extend(document_payload["source_meta"])

            return merged
        except Exception as exc:
            parser_summary.warnings.append(f"MinerU 解析失败，已退回本地摘要模式：{exc}")
            return self._fallback_parse_documents(assets)

    def _submit_mineru_batch(self, assets: list[dict], *, model_version: str) -> list[dict]:
        body = {
            "files": [{"name": asset["original_name"], "data_id": asset["asset_id"]} for asset in assets],
            "model_version": model_version,
            "enable_formula": True,
            "enable_table": True,
            "language": "ch",
            "extra_formats": ["html"],
        }
        response = self._request_json(
            method="POST",
            url=f"{settings.mineru_api_base}/file-urls/batch",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.mineru_api_token}",
            },
            data=body,
            timeout=settings.analysis_llm_timeout_seconds,
        )
        if response.get("code") != 0:
            raise RuntimeError(response.get("msg") or "MinerU 上传链接申请失败")

        for asset, upload_url in zip(assets, response["data"]["file_urls"], strict=True):
            self._put_file(upload_url, Path(asset["local_path"]))

        return self._poll_mineru_batch(response["data"]["batch_id"])

    def _poll_mineru_batch(self, batch_id: str) -> list[dict]:
        deadline = time.time() + settings.mineru_poll_timeout_seconds
        last_payload: list[dict] = []
        while time.time() < deadline:
            response = self._request_json(
                method="GET",
                url=f"{settings.mineru_api_base}/extract-results/batch/{batch_id}",
                headers={
                    "Authorization": f"Bearer {settings.mineru_api_token}",
                    "Accept": "*/*",
                },
                timeout=settings.analysis_llm_timeout_seconds,
            )
            if response.get("code") != 0:
                raise RuntimeError(response.get("msg") or "MinerU 查询失败")

            last_payload = response.get("data", {}).get("extract_result", []) or []
            states = {item.get("state") for item in last_payload}
            if states and states.issubset({"done", "failed"}):
                return last_payload
            time.sleep(settings.mineru_poll_interval_seconds)

        raise TimeoutError(f"MinerU 轮询超时，最后状态：{last_payload}")

    def _collect_mineru_results(self, extract_results: list[dict]) -> dict:
        documents_markdown: list[dict] = []
        documents_json: list[dict] = []
        source_meta: list[dict] = []

        for item in extract_results:
            data_id = item.get("data_id")
            file_name = item.get("file_name")
            if item.get("state") != "done" or not item.get("full_zip_url"):
                documents_markdown.append(
                    {
                        "asset_id": data_id,
                        "source_type": "document",
                        "markdown": f"# {file_name}\n\nMinerU 未能完成解析：{item.get('err_msg') or item.get('state')}",
                    }
                )
                source_meta.append({"asset_id": data_id, "asset_type": "document", "original_name": file_name})
                continue

            archive_path = self._write_temp_zip(data_id or uuid.uuid4().hex, self._download_bytes(item["full_zip_url"], timeout=settings.analysis_llm_timeout_seconds))
            markdown_text = ""
            structured_payload: dict = {}
            with zipfile.ZipFile(archive_path) as archive:
                for name in archive.namelist():
                    lowered = name.lower()
                    if lowered.endswith("full.md") or lowered.endswith(".md"):
                        markdown_text = archive.read(name).decode("utf-8", errors="ignore")
                    elif lowered.endswith("content_list.json") or lowered.endswith("model.json") or lowered.endswith(".json"):
                        try:
                            structured_payload[name] = json.loads(archive.read(name).decode("utf-8", errors="ignore"))
                        except json.JSONDecodeError:
                            continue

            documents_markdown.append(
                {
                    "asset_id": data_id,
                    "source_type": "document",
                    "markdown": markdown_text or f"# {file_name}\n\nMinerU 已完成解析，但未返回 markdown 正文。",
                }
            )
            documents_json.append(
                {
                    "asset_id": data_id,
                    "source_type": "document",
                    "payload": structured_payload,
                }
            )
            source_meta.append({"asset_id": data_id, "asset_type": "document", "original_name": file_name})

        return {
            "documents_markdown": documents_markdown,
            "documents_json": documents_json,
            "source_meta": source_meta,
        }

    def _fallback_parse_documents(self, assets: list[dict]) -> dict:
        documents_markdown: list[dict] = []
        documents_json: list[dict] = []
        source_meta: list[dict] = []
        for asset in assets:
            asset_path = Path(asset["local_path"])
            documents_markdown.append(
                {
                    "asset_id": asset["asset_id"],
                    "source_type": "document",
                    "markdown": f"# {asset['original_name']}\n\n本地已接收文件，等待云端文档解析。\n\n- 文件大小：{asset['size_bytes']} 字节\n- 文件类型：{asset['mime_type']}",
                }
            )
            documents_json.append(
                {
                    "asset_id": asset["asset_id"],
                    "source_type": "document",
                    "payload": {
                        "file_name": asset["original_name"],
                        "extension": asset_path.suffix.lower(),
                        "size_bytes": asset["size_bytes"],
                    },
                }
            )
            source_meta.append(
                {
                    "asset_id": asset["asset_id"],
                    "asset_type": "document",
                    "original_name": asset["original_name"],
                }
            )
        return {
            "documents_markdown": documents_markdown,
            "documents_json": documents_json,
            "source_meta": source_meta,
        }

    def _parse_spreadsheet(self, path: Path) -> dict:
        if path.suffix.lower() == ".csv":
            return {"tables": [self._parse_csv_table(path)]}
        return {"tables": self._parse_xlsx_tables(path)}

    def _parse_csv_table(self, path: Path) -> dict:
        with path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
            reader = list(csv.reader(handle))
        headers = reader[0] if reader else []
        rows = reader[1:26] if len(reader) > 1 else []
        return {
            "asset_id": path.stem,
            "sheet_name": "Sheet1",
            "columns": headers,
            "rows": [dict(zip(headers, row, strict=False)) for row in rows],
            "markdown_summary": self._table_to_markdown("Sheet1", headers, rows[:10]),
        }

    def _parse_xlsx_tables(self, path: Path) -> list[dict]:
        workbook = load_workbook(path, read_only=True, data_only=True)
        tables: list[dict] = []
        for sheet in workbook.worksheets:
            rows = list(sheet.iter_rows(values_only=True))
            if not rows:
                continue
            headers = [str(cell or "").strip() for cell in rows[0]]
            data_rows = rows[1:]
            structured_rows = []
            for row in data_rows:
                structured_rows.append(
                    {
                        headers[index] if index < len(headers) else f"column_{index + 1}": row[index]
                        for index in range(len(row))
                    }
                )
            tables.append(
                {
                    "asset_id": path.stem,
                    "sheet_name": sheet.title,
                    "columns": headers,
                    "rows": structured_rows,
                    "markdown_summary": self._table_to_markdown(sheet.title, headers, data_rows[:10]),
                }
            )
        workbook.close()
        return tables

    def _normalize_spreadsheets(self, tables: list[dict], parser_summary: AnalysisParserSummary) -> dict:
        transactions: list[dict] = []
        candidates: list[dict] = []
        accounts: set[str] = set()
        timestamps: set[str] = set()
        amounts: list[float] = []
        mappings: list[dict] = []
        risk_signals: list[str] = []

        for table in tables:
            mapping = self._infer_spreadsheet_mapping(table, parser_summary)
            mappings.append(
                {
                    "asset_id": table.get("asset_id"),
                    "sheet_name": table.get("sheet_name"),
                    "column_mapping": mapping.get("column_mapping", {}),
                    "static_mapping": mapping.get("static_mapping", {}),
                }
            )
            standardized_rows = self._apply_spreadsheet_mapping(table, mapping)
            for row in standardized_rows:
                transactions.append(row)
                account = stringify(row.get("zhdh")).strip()
                counterpart = stringify(row.get("dfzh")).strip()
                if account:
                    accounts.add(account)
                if counterpart:
                    accounts.add(counterpart)
                amount = safe_float(row.get("jyje"))
                if amount:
                    amounts.append(amount)
                timestamp = " ".join(
                    part
                    for part in [stringify(row.get("jyrq")).strip(), stringify(row.get("jysj")).strip()]
                    if part
                ).strip()
                if timestamp:
                    timestamps.add(timestamp)
                candidates.append(
                    {
                        "payer_account": account,
                        "receiver_account": counterpart,
                        "amount": amount,
                        "timestamp": timestamp,
                        "channel": stringify(row.get("jyqd")) or "Excel结构化表格",
                        "description": f"{table['sheet_name']} 表单候选交易",
                        "evidence_refs": [table["sheet_name"]],
                    }
                )

        if any(amount >= 50000 for amount in amounts):
            risk_signals.append("存在大额转账记录")
        if len(accounts) >= 3:
            risk_signals.append("检测到多账户关联")
        if transactions:
            risk_signals.append("已完成 Excel 表头映射与全量结构化")

        return {
            "transaction_candidates": candidates,
            "standardized_transactions": transactions,
            "spreadsheet_mappings": mappings,
            "entities": {
                "accounts": sorted(accounts),
                "names": [],
                "amounts": amounts,
                "timestamps": sorted(timestamps),
                "locations": [],
            },
            "risk_signals": risk_signals,
            "evidence_alignment": [],
            "summary": "已完成 Excel 表头映射，并将全量交易数据转换为旧版混合模型可用结构。",
        }

    def _normalize_non_spreadsheet_bundle(self, bundle: dict, parser_summary: AnalysisParserSummary) -> dict:
        fallback = self._heuristic_normalize(bundle)
        if not settings.analysis_enable_llm_normalization:
            return fallback
        if not settings.analysis_llm_api_key:
            parser_summary.warnings.append("未配置 SiliconFlow API Key，非表格模态结构化已退回规则模式。")
            return fallback

        try:
            response_text = self._call_chat_completion(self._build_normalize_prompt(bundle))
            normalized = self._extract_json_object(response_text)
            return self._sanitize_llm_normalized_payload(normalized, fallback)
        except Exception as exc:
            parser_summary.warnings.append(f"非表格模态 LLM 结构化失败，已退回规则模式：{exc}")
            return fallback

    def _merge_normalized_payloads(self, spreadsheet_payload: dict, evidence_payload: dict) -> dict:
        spreadsheet_payload = self._sanitize_llm_normalized_payload(
            spreadsheet_payload,
            self._heuristic_normalize({"plain_texts": [], "documents_markdown": [], "structured_tables": [], "documents_json": []}),
        )
        evidence_payload = self._sanitize_llm_normalized_payload(
            evidence_payload,
            self._heuristic_normalize({"plain_texts": [], "documents_markdown": [], "structured_tables": [], "documents_json": []}),
        )
        accounts = set(stringify(item).strip() for item in spreadsheet_payload.get("entities", {}).get("accounts", []))
        accounts.update(stringify(item).strip() for item in evidence_payload.get("entities", {}).get("accounts", []))
        amounts = [safe_float(item) for item in spreadsheet_payload.get("entities", {}).get("amounts", [])]
        amounts.extend(safe_float(item) for item in evidence_payload.get("entities", {}).get("amounts", []))
        timestamps = set(stringify(item).strip() for item in spreadsheet_payload.get("entities", {}).get("timestamps", []))
        timestamps.update(stringify(item).strip() for item in evidence_payload.get("entities", {}).get("timestamps", []))

        risk_signals: list[str] = []
        for payload in (spreadsheet_payload, evidence_payload):
            for item in payload.get("risk_signals", []):
                text = stringify(item).strip()
                if text and text not in risk_signals:
                    risk_signals.append(text)

        summary_parts = [
            stringify(spreadsheet_payload.get("summary")).strip(),
            stringify(evidence_payload.get("summary")).strip(),
        ]
        summary = " ".join(part for part in summary_parts if part).strip()
        if not summary:
            summary = "已完成多模态证据归一化整理，可进入风险判定阶段。"

        return {
            "transaction_candidates": [
                *spreadsheet_payload.get("transaction_candidates", []),
                *evidence_payload.get("transaction_candidates", []),
            ],
            "standardized_transactions": [
                *spreadsheet_payload.get("standardized_transactions", []),
                *evidence_payload.get("standardized_transactions", []),
            ],
            "spreadsheet_mappings": spreadsheet_payload.get("spreadsheet_mappings", []),
            "entities": {
                "accounts": sorted(account for account in accounts if account),
                "names": [],
                "amounts": [amount for amount in amounts if amount],
                "timestamps": sorted(timestamp for timestamp in timestamps if timestamp),
                "locations": [],
            },
            "risk_signals": risk_signals,
            "evidence_alignment": [
                *spreadsheet_payload.get("evidence_alignment", []),
                *evidence_payload.get("evidence_alignment", []),
            ],
            "summary": summary,
        }

    def _infer_spreadsheet_mapping(self, table: dict, parser_summary: AnalysisParserSummary) -> dict:
        fallback = self._fallback_spreadsheet_mapping(table)
        if not settings.analysis_enable_llm_normalization or not settings.analysis_llm_api_key:
            return fallback

        try:
            response_text = self._call_chat_completion(self._build_spreadsheet_mapping_prompt(table))
            payload = self._extract_json_object(response_text)
            payload_column_mapping = (
                payload.get("column_mapping") if isinstance(payload.get("column_mapping"), dict) else {}
            )
            payload_static_mapping = (
                payload.get("static_mapping") if isinstance(payload.get("static_mapping"), dict) else {}
            )
            payload_column_mapping = self._normalize_mapping_direction(
                payload_column_mapping,
                allowed_targets=set(STANDARD_TRANSACTION_FIELDS) - {"xb", "年龄"},
                table_columns={stringify(column).strip() for column in table.get("columns", [])},
            )
            payload_static_mapping = self._normalize_mapping_direction(
                payload_static_mapping,
                allowed_targets={"xb", "年龄"},
                table_columns={stringify(column).strip() for column in table.get("columns", [])},
            )
            payload = {
                "table_kind": self._normalize_spreadsheet_table_kind(payload.get("table_kind"), fallback["table_kind"]),
                "column_mapping": payload_column_mapping,
                "static_mapping": payload_static_mapping,
            }
            if not {"zhdh", "dfzh", "jdbj", "jyje"} <= set(payload["column_mapping"]):
                return fallback
            return payload
        except Exception as exc:
            parser_summary.warnings.append(
                f"{stringify(table.get('sheet_name')) or '工作表'} 的表头映射退回规则模式：{exc}"
            )
            return fallback

    def _sanitize_llm_normalized_payload(self, payload: dict, fallback: dict) -> dict:
        if not isinstance(payload, dict):
            return fallback

        normalized = dict(payload)
        normalized["summary"] = stringify(normalized.get("summary")).strip() or fallback.get("summary", "")
        normalized["transaction_candidates"] = self._coerce_transaction_candidates(
            normalized.get("transaction_candidates"),
            fallback.get("transaction_candidates", []),
        )
        normalized["standardized_transactions"] = self._coerce_standardized_transactions(
            normalized.get("standardized_transactions"),
            fallback.get("standardized_transactions", []),
        )
        normalized["entities"] = self._coerce_entities(
            normalized.get("entities"),
            fallback.get("entities", {}),
        )
        normalized["risk_signals"] = self._coerce_string_list(
            normalized.get("risk_signals"),
            fallback.get("risk_signals", []),
        )
        normalized["evidence_alignment"] = (
            normalized.get("evidence_alignment")
            if isinstance(normalized.get("evidence_alignment"), list)
            else fallback.get("evidence_alignment", [])
        )
        return normalized

    def _coerce_transaction_candidates(self, value: object, fallback: list[dict]) -> list[dict]:
        if not isinstance(value, list):
            return list(fallback)
        candidates: list[dict] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            row = {
                "payer_account": stringify(item.get("payer_account")).strip(),
                "receiver_account": stringify(item.get("receiver_account")).strip(),
                "amount": safe_float(item.get("amount")),
                "timestamp": stringify(item.get("timestamp")).strip(),
                "channel": stringify(item.get("channel")).strip(),
                "description": stringify(item.get("description")).strip(),
                "evidence_refs": item.get("evidence_refs") if isinstance(item.get("evidence_refs"), list) else [],
            }
            if not any(
                [
                    row["payer_account"],
                    row["receiver_account"],
                    row["timestamp"],
                    row["channel"],
                    row["description"],
                    row["amount"] > 0,
                ]
            ):
                continue
            candidates.append(row)
        return candidates if candidates else list(fallback)

    def _coerce_standardized_transactions(self, value: object, fallback: list[dict]) -> list[dict]:
        if not isinstance(value, list):
            return list(fallback)
        rows: list[dict] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            row = {
                "jylsxh": stringify(item.get("jylsxh")).strip(),
                "zhdh": stringify(item.get("zhdh")).strip(),
                "dfzh": stringify(item.get("dfzh")).strip(),
                "jdbj": normalize_direction_value(item.get("jdbj")),
                "jyje": safe_float(item.get("jyje")),
                "zhye": safe_float(item.get("zhye")),
                "dfhh": stringify(item.get("dfhh")).strip(),
                "jyrq": normalize_date_value(item.get("jyrq")),
                "jysj": normalize_time_value(item.get("jysj")),
                "jyqd": stringify(item.get("jyqd")).strip(),
                "dfmccd": safe_float(item.get("dfmccd")),
                "xb": normalize_gender_value(item.get("xb")),
                "年龄": safe_float(item.get("年龄")),
            }
            if not any(
                [
                    row["jylsxh"],
                    row["zhdh"],
                    row["dfzh"],
                    row["dfhh"],
                    row["jyrq"],
                    row["jysj"],
                    row["jyqd"],
                    row["jyje"] > 0,
                    row["zhye"] > 0,
                ]
            ):
                continue
            rows.append(row)
        return rows if rows else list(fallback)

    def _coerce_entities(self, value: object, fallback: dict) -> dict:
        if not isinstance(value, dict):
            return dict(fallback)
        accounts = [stringify(item).strip() for item in value.get("accounts", []) if stringify(item).strip()]
        amounts = [safe_float(item) for item in value.get("amounts", []) if safe_float(item)]
        timestamps = [stringify(item).strip() for item in value.get("timestamps", []) if stringify(item).strip()]
        return {
            "accounts": accounts or list((fallback.get("accounts") or [])),
            "names": value.get("names") if isinstance(value.get("names"), list) else list((fallback.get("names") or [])),
            "amounts": amounts or list((fallback.get("amounts") or [])),
            "timestamps": timestamps or list((fallback.get("timestamps") or [])),
            "locations": value.get("locations") if isinstance(value.get("locations"), list) else list((fallback.get("locations") or [])),
        }

    def _coerce_string_list(self, value: object, fallback: list[str]) -> list[str]:
        if not isinstance(value, list):
            return list(fallback)
        items = [stringify(item).strip() for item in value if stringify(item).strip()]
        return items if items else list(fallback)

    def _fallback_spreadsheet_mapping(self, table: dict) -> dict:
        columns = [stringify(column).strip() for column in table.get("columns", [])]
        column_mapping: dict[str, str] = {}
        static_mapping: dict[str, str] = {}
        for target_field, keywords in SPREADSHEET_FIELD_KEYWORDS.items():
            matched = find_matching_key(columns, keywords)
            if matched:
                if target_field in {"xb", "年龄"}:
                    static_mapping[target_field] = matched
                else:
                    column_mapping[target_field] = matched
        return {
            "table_kind": "transaction" if {"zhdh", "dfzh", "jdbj", "jyje"} <= set(column_mapping) else "unknown",
            "column_mapping": column_mapping,
            "static_mapping": static_mapping,
        }

    def _apply_spreadsheet_mapping(self, table: dict, mapping: dict) -> list[dict]:
        column_mapping = mapping.get("column_mapping") if isinstance(mapping.get("column_mapping"), dict) else {}
        static_mapping = mapping.get("static_mapping") if isinstance(mapping.get("static_mapping"), dict) else {}
        if not {"zhdh", "dfzh", "jdbj", "jyje"} <= set(column_mapping):
            return []

        standardized_rows: list[dict] = []
        for index, row in enumerate(table.get("rows", []), start=1):
            if not isinstance(row, dict):
                continue
            normalized_row = {field: None for field in STANDARD_TRANSACTION_FIELDS}
            for target_field, source_field in column_mapping.items():
                normalized_row[target_field] = row.get(source_field)
            for target_field, source_field in static_mapping.items():
                normalized_row[target_field] = row.get(source_field)

            normalized_row["jylsxh"] = stringify(normalized_row.get("jylsxh")).strip() or f"{table.get('sheet_name', 'sheet')}-{index}"
            normalized_row["zhdh"] = stringify(normalized_row.get("zhdh")).strip()
            normalized_row["dfzh"] = stringify(normalized_row.get("dfzh")).strip()
            normalized_row["jdbj"] = normalize_direction_value(normalized_row.get("jdbj"))
            normalized_row["jyje"] = safe_float(normalized_row.get("jyje"))
            normalized_row["zhye"] = safe_float(normalized_row.get("zhye"))
            normalized_row["dfhh"] = stringify(normalized_row.get("dfhh")).strip()
            normalized_row["jyrq"] = normalize_date_value(normalized_row.get("jyrq"))
            normalized_row["jysj"] = normalize_time_value(normalized_row.get("jysj"))
            normalized_row["jyqd"] = stringify(normalized_row.get("jyqd")).strip()
            normalized_row["dfmccd"] = safe_float(normalized_row.get("dfmccd"))
            normalized_row["xb"] = normalize_gender_value(normalized_row.get("xb"))
            normalized_row["年龄"] = safe_float(normalized_row.get("年龄"))
            if normalized_row["zhdh"] and normalized_row["dfzh"]:
                standardized_rows.append(normalized_row)
        return standardized_rows

    def _build_spreadsheet_mapping_prompt(self, table: dict) -> list[dict]:
        sample_rows = []
        for row in table.get("rows", [])[:5]:
            if isinstance(row, dict):
                sample_rows.append(to_json_safe(row))
        payload = {
            "sheet_name": table.get("sheet_name"),
            "columns": [stringify(column) for column in table.get("columns", [])],
            "sample_rows": sample_rows,
        }
        example_input = {
            "sheet_name": "Sheet1",
            "columns": [
                "交易流水序号",
                "账户代号",
                "对方账户",
                "借贷标记",
                "交易金额",
                "账户余额",
                "对方行号",
                "交易日期",
                "交易时间",
                "交易渠道",
                "性别",
                "年龄",
            ],
            "sample_rows": [
                {
                    "交易流水序号": "96DE006FD8F51A8A0250C1D37DB2DCFF",
                    "账户代号": "3242244504235523",
                    "对方账户": "BA8C172953D66632",
                    "借贷标记": "是",
                    "交易金额": 349.75,
                    "账户余额": 356.86,
                    "对方行号": "D41D8CD9",
                    "交易日期": "2020-03-01 00:00:00",
                    "交易时间": "04:41:09",
                    "交易渠道": "757B505C",
                    "性别": "男",
                    "年龄": 37,
                }
            ],
        }
        example_output = {
            "table_kind": "transaction",
            "column_mapping": {
                "jylsxh": "交易流水序号",
                "zhdh": "账户代号",
                "dfzh": "对方账户",
                "jdbj": "借贷标记",
                "jyje": "交易金额",
                "zhye": "账户余额",
                "dfhh": "对方行号",
                "jyrq": "交易日期",
                "jysj": "交易时间",
                "jyqd": "交易渠道",
            },
            "static_mapping": {
                "xb": "性别",
                "年龄": "年龄",
            },
        }
        return [
            {
                "role": "system",
                "content": (
                    "你是金融表格字段映射助手。"
                    "请根据表头和前几行样本，识别交易表字段映射。"
                    "只输出合法 JSON，字段必须包含 table_kind, column_mapping, static_mapping。"
                    "table_kind 只能是 transaction 或 unknown。"
                    "column_mapping 只映射交易字段，static_mapping 只映射 xb 和 年龄。"
                    "映射方向必须固定为：标准字段名 -> 原始列名。"
                    "标准字段只允许使用：jylsxh, zhdh, dfzh, jdbj, jyje, zhye, dfhh, jyrq, jysj, jyqd, dfmccd, xb, 年龄。"
                    "不要把原始列名写成 key，不要输出解释，不要输出多余字段。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "下面是一个示例。\n\n"
                    f"输入：{json.dumps(example_input, ensure_ascii=False)}\n\n"
                    f"输出：{json.dumps(example_output, ensure_ascii=False)}"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False),
            },
        ]

    def _normalize_mapping_direction(
        self,
        mapping: dict[str, str],
        *,
        allowed_targets: set[str],
        table_columns: set[str],
    ) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, value in mapping.items():
            key_text = stringify(key).strip()
            value_text = stringify(value).strip()
            if key_text in allowed_targets and value_text in table_columns:
                normalized[key_text] = value_text
            elif value_text in allowed_targets and key_text in table_columns:
                normalized[value_text] = key_text
        return normalized

    def _normalize_spreadsheet_table_kind(self, value: object, fallback: str) -> str:
        normalized = stringify(value).strip().lower()
        mapping = {
            "transaction": "transaction",
            "unknown": "unknown",
            "交易表": "transaction",
            "交易": "transaction",
            "表格": "transaction",
            "未知": "unknown",
        }
        return mapping.get(normalized, fallback)

    def _build_hybrid_result_payload(self, normalized: dict, hybrid_result: dict) -> dict:
        accounts = hybrid_result.get("accounts") if isinstance(hybrid_result.get("accounts"), list) else []
        overall = hybrid_result.get("overall") if isinstance(hybrid_result.get("overall"), dict) else {}
        risk_level = normalize_risk_level_value(overall.get("risk_level"), "medium")
        confidence = safe_float(overall.get("confidence")) or 0.0

        account_scores = []
        for account_item in accounts:
            if not isinstance(account_item, dict):
                continue
            probability = safe_float(account_item.get("probability"))
            account_scores.append(
                {
                    "account": stringify(account_item.get("account")).strip() or "待确认账户",
                    "prediction": int(safe_float(account_item.get("prediction"))),
                    "probability": round(probability, 6),
                    "gru_probability": round(safe_float(account_item.get("gru_probability")), 6),
                    "xgb_probability": round(safe_float(account_item.get("xgb_probability")), 6),
                    "confidence_label": stringify(account_item.get("confidence_label")).strip()
                    or confidence_label_from_probability(probability),
                    "risk_level": normalize_risk_level_value(account_item.get("risk_level"), risk_level),
                }
            )

        link_path = []
        for account_item in account_scores[:5]:
            link_path.append(
                AnalysisRiskNode(
                    account=account_item["account"],
                    risk_level=account_item["risk_level"],
                    action="复核" if account_item["risk_level"] != "low" else "记录",
                ).model_dump()
            )
        if not link_path:
            link_path = [AnalysisRiskNode(account="待补充证据", risk_level=risk_level, action="复核").model_dump()]

        top_account = account_scores[0]["account"] if account_scores else "待确认账户"
        narrative = (
            f"结构化交易数据已进入旧版混合模型，当前最高风险账户为 {top_account}，"
            f"综合风险等级为 {display_risk_level(risk_level)}。"
        )
        return {
            "risk_level": risk_level,
            "confidence": confidence,
            "model_source": stringify(hybrid_result.get("model_source")) or "legacy-hybrid-gru-xgb-meta",
            "narrative": narrative,
            "suggested_actions": build_actions(risk_level),
            "link_path": link_path,
            "account_scores": account_scores,
            "normalized_summary": normalized.get("summary", ""),
            "risk_signals": normalized.get("risk_signals", []),
            "transaction_candidates": normalized.get("transaction_candidates", []),
        }

    def _normalize_bundle(self, bundle: dict, parser_summary: AnalysisParserSummary) -> dict:
        spreadsheet_normalized = self._normalize_spreadsheets(bundle.get("structured_tables", []), parser_summary)
        evidence_bundle = {
            **bundle,
            "structured_tables": [],
        }
        evidence_normalized = self._normalize_non_spreadsheet_bundle(evidence_bundle, parser_summary)
        return self._merge_normalized_payloads(spreadsheet_normalized, evidence_normalized)

    def _inject_focus_history(self, normalized: dict, current_job_id: str) -> dict:
        targets = [
            item
            for item in focus_repository.list_targets()
            if bool(item.get("is_seed")) and stringify(item.get("account")).strip()
        ]
        if not targets:
            return normalized

        history_jobs = [
            job
            for job in repository.list_jobs(created_by=None)
            if job["status"] == "completed"
            and job["job_id"] != current_job_id
            and isinstance(job.get("normalized_json"), dict)
        ]
        if not history_jobs:
            return normalized

        normal_accounts = {
            stringify(item.get("account")).strip()
            for item in targets
            if item.get("mode") == "normal"
        }
        deep_seed_accounts = {
            stringify(item.get("account")).strip()
            for item in targets
            if item.get("mode") == "deep"
        }

        injected_transactions: list[dict] = []
        normal_transactions = self._collect_history_transactions(history_jobs, normal_accounts)
        injected_transactions.extend(normal_transactions)

        deep_seed_transactions = self._collect_history_transactions(history_jobs, deep_seed_accounts)
        deep_counterparts = self._collect_counterpart_accounts(deep_seed_transactions, deep_seed_accounts)
        deep_scope_accounts = deep_seed_accounts | deep_counterparts
        deep_transactions = self._collect_history_transactions(history_jobs, deep_scope_accounts)
        injected_transactions.extend(deep_transactions)

        if not injected_transactions:
            return normalized

        merged = dict(normalized)
        existing_transactions = list(normalized.get("standardized_transactions") or [])
        merged_transactions = self._append_unique_transactions(existing_transactions, injected_transactions)
        added_count = max(0, len(merged_transactions) - len(existing_transactions))
        if added_count <= 0:
            return normalized

        merged["standardized_transactions"] = merged_transactions

        existing_candidates = list(normalized.get("transaction_candidates") or [])
        focus_candidates = [self._build_candidate_from_transaction(item) for item in injected_transactions]
        merged["transaction_candidates"] = self._append_unique_candidates(existing_candidates, focus_candidates)

        entities = dict(normalized.get("entities") or {})
        entities["accounts"] = self._merge_string_values(
            entities.get("accounts"),
            self._extract_accounts_from_transactions(injected_transactions),
        )
        entities["amounts"] = self._merge_float_values(
            entities.get("amounts"),
            [
                safe_float(item.get("jyje"))
                for item in injected_transactions
                if safe_float(item.get("jyje"))
            ]
            + [
                safe_float(item.get("zhye"))
                for item in injected_transactions
                if safe_float(item.get("zhye"))
            ],
        )
        entities["timestamps"] = self._merge_string_values(
            entities.get("timestamps"),
            self._extract_timestamps_from_transactions(injected_transactions),
        )
        merged["entities"] = entities

        risk_signals = list(normalized.get("risk_signals") or [])
        signal_parts: list[str] = []
        if normal_transactions:
            signal_parts.append(f"普通关注历史日志 {len(normal_transactions)} 条")
        if deep_transactions:
            signal_parts.append(f"深度追踪历史日志 {len(deep_transactions)} 条")
        if signal_parts:
            merged["risk_signals"] = [f"已自动并入重点关注交易日志：{'，'.join(signal_parts)}", *risk_signals]

        evidence_alignment = list(normalized.get("evidence_alignment") or [])
        evidence_alignment.append(
            {
                "asset_id": "focus-history",
                "mapped_fields": list(STANDARD_TRANSACTION_FIELDS),
                "focus_accounts": sorted(normal_accounts | deep_seed_accounts),
                "deep_counterparts": sorted(deep_counterparts),
                "injected_transactions": added_count,
            }
        )
        merged["evidence_alignment"] = evidence_alignment

        summary = stringify(normalized.get("summary")).strip()
        focus_summary = f"已自动并入重点关注历史交易日志 {added_count} 条。"
        merged["summary"] = f"{summary} {focus_summary}".strip() if summary else focus_summary
        return merged

    def _collect_history_transactions(self, jobs: list[dict], accounts: set[str]) -> list[dict]:
        if not accounts:
            return []

        rows: list[dict] = []
        seen: set[tuple] = set()
        for job in jobs:
            normalized = job.get("normalized_json") or {}
            candidates = normalized.get("transaction_candidates") or []
            for row in normalized.get("standardized_transactions") or []:
                if not self._transaction_matches_accounts(row, accounts):
                    continue
                normalized_row = self._normalize_history_transaction_row(row)
                key = self._build_transaction_key(normalized_row)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(normalized_row)

            if normalized.get("standardized_transactions"):
                continue

            for candidate in candidates:
                pseudo_row = self._candidate_to_transaction_row(candidate)
                if not self._transaction_matches_accounts(pseudo_row, accounts):
                    continue
                key = self._build_transaction_key(pseudo_row)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(pseudo_row)
        return rows

    def _collect_counterpart_accounts(self, transactions: list[dict], seed_accounts: set[str]) -> set[str]:
        counterparts: set[str] = set()
        for row in transactions:
            payer = stringify(row.get("zhdh")).strip()
            receiver = stringify(row.get("dfzh")).strip()
            if payer in seed_accounts and receiver:
                counterparts.add(receiver)
            if receiver in seed_accounts and payer:
                counterparts.add(payer)
        return counterparts - seed_accounts

    def _transaction_matches_accounts(self, row: dict, accounts: set[str]) -> bool:
        payer = stringify(row.get("zhdh")).strip()
        receiver = stringify(row.get("dfzh")).strip()
        return payer in accounts or receiver in accounts

    def _normalize_history_transaction_row(self, row: dict) -> dict:
        return {
            "jylsxh": stringify(row.get("jylsxh")).strip(),
            "zhdh": stringify(row.get("zhdh")).strip(),
            "dfzh": stringify(row.get("dfzh")).strip(),
            "jdbj": normalize_direction_value(row.get("jdbj")),
            "jyje": safe_float(row.get("jyje")),
            "zhye": safe_float(row.get("zhye")),
            "dfhh": stringify(row.get("dfhh")).strip(),
            "jyrq": normalize_date_value(row.get("jyrq")),
            "jysj": normalize_time_value(row.get("jysj")),
            "jyqd": stringify(row.get("jyqd")).strip(),
            "dfmccd": safe_float(row.get("dfmccd")),
            "xb": normalize_gender_value(row.get("xb")),
            "年龄": safe_float(row.get("年龄")),
        }

    def _candidate_to_transaction_row(self, row: dict) -> dict:
        timestamp = stringify(row.get("timestamp")).strip()
        date_part, time_part = "", ""
        if timestamp:
            pieces = timestamp.replace("T", " ").split(" ", 1)
            date_part = normalize_date_value(pieces[0])
            time_part = normalize_time_value(pieces[1] if len(pieces) > 1 else "")

        return {
            "jylsxh": "",
            "zhdh": stringify(row.get("payer_account")).strip(),
            "dfzh": stringify(row.get("receiver_account")).strip(),
            "jdbj": 1,
            "jyje": safe_float(row.get("amount")),
            "zhye": 0.0,
            "dfhh": "",
            "jyrq": date_part,
            "jysj": time_part,
            "jyqd": stringify(row.get("channel")).strip(),
            "dfmccd": 0.0,
            "xb": 0,
            "年龄": 0.0,
        }

    def _append_unique_transactions(self, base: list[dict], extras: list[dict]) -> list[dict]:
        merged = list(base)
        seen = {self._build_transaction_key(item) for item in merged}
        for item in extras:
            key = self._build_transaction_key(item)
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
        return merged

    def _append_unique_candidates(self, base: list[dict], extras: list[dict]) -> list[dict]:
        merged = list(base)
        seen = {self._build_candidate_key(item) for item in merged if isinstance(item, dict)}
        for item in extras:
            key = self._build_candidate_key(item)
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
        return merged

    def _build_transaction_key(self, row: dict) -> tuple:
        return (
            stringify(row.get("jylsxh")).strip(),
            stringify(row.get("zhdh")).strip(),
            stringify(row.get("dfzh")).strip(),
            normalize_date_value(row.get("jyrq")),
            normalize_time_value(row.get("jysj")),
            round(safe_float(row.get("jyje")), 6),
            round(safe_float(row.get("zhye")), 6),
            stringify(row.get("jyqd")).strip(),
        )

    def _build_candidate_key(self, row: dict) -> tuple:
        return (
            stringify(row.get("payer_account")).strip(),
            stringify(row.get("receiver_account")).strip(),
            round(safe_float(row.get("amount")), 6),
            stringify(row.get("timestamp")).strip(),
            stringify(row.get("channel")).strip(),
        )

    def _build_candidate_from_transaction(self, row: dict) -> dict:
        timestamp = " ".join(
            part
            for part in [
                normalize_date_value(row.get("jyrq")),
                normalize_time_value(row.get("jysj")),
            ]
            if part
        ).strip()
        return {
            "payer_account": stringify(row.get("zhdh")).strip(),
            "receiver_account": stringify(row.get("dfzh")).strip(),
            "amount": safe_float(row.get("jyje")),
            "timestamp": timestamp,
            "channel": stringify(row.get("jyqd")).strip() or "重点关注历史交易日志",
            "description": "重点关注历史交易日志",
            "evidence_refs": ["focus-history"],
        }

    def _extract_accounts_from_transactions(self, transactions: list[dict]) -> list[str]:
        accounts: list[str] = []
        seen: set[str] = set()
        for row in transactions:
            for value in (row.get("zhdh"), row.get("dfzh")):
                account = stringify(value).strip()
                if account and account not in seen:
                    seen.add(account)
                    accounts.append(account)
        return accounts

    def _extract_timestamps_from_transactions(self, transactions: list[dict]) -> list[str]:
        timestamps: list[str] = []
        seen: set[str] = set()
        for row in transactions:
            timestamp = " ".join(
                part
                for part in [
                    normalize_date_value(row.get("jyrq")),
                    normalize_time_value(row.get("jysj")),
                ]
                if part
            ).strip()
            if timestamp and timestamp not in seen:
                seen.add(timestamp)
                timestamps.append(timestamp)
        return timestamps

    def _merge_string_values(self, base: object, extras: list[str]) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for item in list(base or []) + list(extras or []):
            value = stringify(item).strip()
            if value and value not in seen:
                seen.add(value)
                merged.append(value)
        return merged

    def _merge_float_values(self, base: object, extras: list[float]) -> list[float]:
        merged: list[float] = []
        seen: set[float] = set()
        for item in list(base or []) + list(extras or []):
            value = safe_float(item)
            if not value:
                continue
            normalized_value = round(value, 6)
            if normalized_value in seen:
                continue
            seen.add(normalized_value)
            merged.append(value)
        return merged

    def _analyze_bundle(self, normalized: dict, parser_summary: AnalysisParserSummary, job_dir: Path) -> dict:
        fallback = self._heuristic_analysis(normalized)
        standardized_transactions = normalized.get("standardized_transactions") or []
        if not standardized_transactions:
            parser_summary.warnings.append("未提取到可进入旧版混合模型的结构化交易数据，已退回规则分析。")
            return fallback

        try:
            hybrid_result = hybrid_adapter.predict(
                transactions=standardized_transactions,
                work_dir=job_dir / "_hybrid_runtime",
                inference_params=params_service.get_hybrid_inference_params(),
            )
            payload = self._build_hybrid_result_payload(normalized, hybrid_result)
            return self._normalize_result_payload(payload) or fallback
        except Exception as exc:
            parser_summary.warnings.append(f"旧版混合模型推理失败，已退回规则分析：{exc}")
            return fallback

    def _heuristic_normalize(self, bundle: dict) -> dict:
        accounts: set[str] = set()
        amounts: list[float] = []
        timestamps: set[str] = set()
        candidates: list[dict] = []
        risk_signals: list[str] = []

        for text_block in bundle["plain_texts"]:
            text = text_block["content"]
            accounts.update(re.findall(r"\b\d{8,32}\b", text))
            amounts.extend(float(item) for item in re.findall(r"\b\d+(?:\.\d{1,2})?\b", text)[:10])

        for document in bundle["documents_markdown"]:
            markdown = document["markdown"]
            accounts.update(re.findall(r"\b\d{8,32}\b", markdown))
            amounts.extend(float(item) for item in re.findall(r"\b\d+(?:\.\d{1,2})?\b", markdown)[:10])

        for table in bundle["structured_tables"]:
            columns = table["columns"]
            rows = table["rows"]
            payer_key = find_matching_key(columns, ("付款", "payer", "转出", "付款方"))
            receiver_key = find_matching_key(columns, ("收款", "receiver", "转入", "收款方"))
            amount_key = find_matching_key(columns, ("金额", "amount", "交易额"))
            time_key = find_matching_key(columns, ("时间", "日期", "timestamp"))
            for row in rows:
                payer_value = stringify(row.get(payer_key)) if payer_key else ""
                receiver_value = stringify(row.get(receiver_key)) if receiver_key else ""
                amount_value = safe_float(row.get(amount_key)) if amount_key else 0.0
                time_value = stringify(row.get(time_key)) if time_key else ""
                if payer_value:
                    accounts.add(payer_value)
                if receiver_value:
                    accounts.add(receiver_value)
                if amount_value:
                    amounts.append(amount_value)
                if time_value:
                    timestamps.add(time_value)
                if payer_value or receiver_value or amount_value:
                    candidates.append(
                        {
                            "payer_account": payer_value,
                            "receiver_account": receiver_value,
                            "amount": amount_value,
                            "timestamp": time_value,
                            "channel": "Excel结构化表格",
                            "description": f"{table['sheet_name']} 表单候选交易",
                            "evidence_refs": [table["sheet_name"]],
                        }
                    )

        if any(amount >= 50000 for amount in amounts):
            risk_signals.append("存在大额转账记录")
        if len(accounts) >= 3:
            risk_signals.append("检测到多账户关联")
        if bundle["documents_markdown"]:
            risk_signals.append("存在文档类多模态证据")

        return {
            "transaction_candidates": candidates,
            "standardized_transactions": [],
            "entities": {
                "accounts": sorted(accounts),
                "names": [],
                "amounts": amounts,
                "timestamps": sorted(timestamps),
                "locations": [],
            },
            "risk_signals": risk_signals,
            "evidence_alignment": [],
            "summary": "已完成多模态证据归一化整理，可进入风险判定阶段。",
        }

    def _heuristic_analysis(self, normalized: dict) -> dict:
        candidates = normalized.get("transaction_candidates", [])
        accounts = normalized.get("entities", {}).get("accounts", [])
        amounts = normalized.get("entities", {}).get("amounts", [])
        risk_signals = normalized.get("risk_signals", [])
        dynamic_thresholds = params_service.get_dynamic_thresholds()
        high_threshold = dynamic_thresholds["high_risk_threshold"]
        medium_threshold = dynamic_thresholds["medium_risk_threshold"]
        self_attention_enabled = dynamic_thresholds["self_attention_enabled"]
        adaptive_threshold_enabled = dynamic_thresholds["adaptive_threshold_enabled"]

        highest_amount = max((safe_float(value) for value in amounts), default=0.0)
        candidate_count = len(candidates)
        account_count = len(accounts)
        risk_signal_count = len(risk_signals)

        if adaptive_threshold_enabled:
            if risk_signal_count >= 3 or candidate_count >= 2:
                high_threshold = max(medium_threshold * 1.6, high_threshold * 0.72)
            if risk_signal_count >= 2 or account_count >= 2:
                medium_threshold = max(1.0, medium_threshold * 0.7)

        attention_score = 0.0
        if self_attention_enabled:
            attention_score += min(highest_amount / max(high_threshold, 1.0), 1.4) * 0.42
            attention_score += min(risk_signal_count / 3.0, 1.0) * 0.26
            attention_score += min(account_count / 4.0, 1.0) * 0.18
            attention_score += min(candidate_count / 3.0, 1.0) * 0.14

        if highest_amount >= high_threshold or risk_signal_count >= 3 or attention_score >= 0.86:
            risk_level = "high"
            confidence = min(0.95, 0.78 + min(attention_score, 1.0) * 0.14)
        elif highest_amount >= medium_threshold or account_count >= 2 or attention_score >= 0.56:
            risk_level = "medium"
            confidence = min(0.86, 0.64 + min(attention_score, 1.0) * 0.12)
        else:
            risk_level = "low"
            confidence = max(0.52, 0.58 + min(attention_score, 0.3) * 0.08)

        if candidates:
            primary = candidates[0]
            link_path = [
                AnalysisRiskNode(
                    account=primary.get("payer_account") or "待确认付款方",
                    risk_level="medium",
                    action="观察",
                ).model_dump(),
                AnalysisRiskNode(
                    account=primary.get("receiver_account") or "待确认收款方",
                    risk_level=risk_level,
                    action="复核" if risk_level != "low" else "记录",
                ).model_dump(),
            ]
        else:
            link_path = [
                AnalysisRiskNode(account=account, risk_level=risk_level, action="复核").model_dump()
                for account in accounts[:2]
            ]
        if not link_path:
            link_path = [AnalysisRiskNode(account="待补充证据", risk_level=risk_level, action="复核").model_dump()]

        return {
            "risk_level": risk_level,
            "confidence": round(confidence, 4),
            "model_source": "dynamic-heuristic",
            "narrative": "系统已基于多模态证据完成初步判定，建议结合报告中的关键证据进行人工复核。",
            "suggested_actions": build_actions(risk_level),
            "link_path": link_path,
            "normalized_summary": normalized.get("summary", ""),
            "risk_signals": risk_signals,
            "transaction_candidates": candidates,
        }

    def _render_report(self, *, job_id: str, assets: list[dict], normalized: dict, result: dict) -> Path:
        return render_report(
            job_id=job_id,
            assets=assets,
            normalized=normalized,
            result=result,
            storage_dir=self.storage_dir,
        )

    def _ensure_report_files(self, job_id: str, job: dict) -> Path:
        report_path = Path(job["report_path"]) if job.get("report_path") else self.storage_dir / job_id / "report.html"
        pdf_path = report_path.with_suffix(".pdf")
        if report_path.exists() and pdf_path.exists():
            return report_path

        normalized = job.get("normalized_json")
        result = job.get("result_json")
        if not normalized or not result:
            raise AppError("分析报告尚未生成", status_code=404, code="ANALYSIS_REPORT_NOT_FOUND")

        assets = repository.list_assets(job_id)
        report_path = self._render_report(job_id=job_id, assets=assets, normalized=normalized, result=result)
        repository.update_job(
            job_id,
            {
                "report_path": str(report_path),
                "report_title": REPORT_TITLE,
            },
        )
        return report_path

    def _select_columns_for_normalization(self, columns: list[str]) -> list[str]:
        selected: list[str] = []
        keyword_groups = (
            ("付款", "payer", "转出", "付款方", "付款账号", "付款账户", "账户代号", "账户", "账号"),
            ("收款", "receiver", "转入", "收款方", "对方账户", "对方账号", "对手账户", "对方"),
            ("金额", "amount", "交易额"),
            ("日期", "date"),
            ("时间", "time", "timestamp"),
            ("余额", "balance"),
            ("渠道", "channel"),
            ("银行", "行号", "bank"),
        )
        for keywords in keyword_groups:
            matched = find_matching_key(columns, keywords)
            if matched and matched not in selected:
                selected.append(matched)
        return selected or columns[:8]

    def _build_normalize_payload(self, bundle: dict) -> dict:
        payload = {
            "job_id": bundle.get("job_id"),
            "documents_markdown": [],
            "structured_tables": [],
            "plain_texts": [],
            "source_meta": to_json_safe(bundle.get("source_meta", [])),
        }

        for item in bundle.get("documents_markdown", []):
            payload["documents_markdown"].append(
                {
                    "asset_id": item.get("asset_id"),
                    "source_type": item.get("source_type"),
                    "markdown": trim_text(stringify(item.get("markdown")), 6000),
                }
            )

        for item in bundle.get("plain_texts", []):
            payload["plain_texts"].append(
                {
                    "asset_id": item.get("asset_id"),
                    "content": trim_text(stringify(item.get("content")), 6000),
                }
            )

        for table in bundle.get("structured_tables", []):
            columns = [stringify(column) for column in table.get("columns", [])]
            selected_columns = self._select_columns_for_normalization(columns)
            compact_rows = []
            for row in table.get("rows", []):
                compact_rows.append([to_json_safe(row.get(column)) for column in selected_columns])
            payload["structured_tables"].append(
                {
                    "asset_id": table.get("asset_id"),
                    "sheet_name": table.get("sheet_name"),
                    "row_count": len(table.get("rows", [])),
                    "selected_columns": selected_columns,
                    "rows": compact_rows,
                }
            )

        return payload

    def _build_normalize_prompt(self, bundle: dict) -> list[dict]:
        normalize_payload = self._build_normalize_payload(bundle)
        example_input = {
            "job_id": "example-voucher",
            "documents_markdown": [
                {
                    "asset_id": "voucher-1",
                    "source_type": "document",
                    "markdown": (
                        "# 转账凭证单\n\n"
                        "交易日期：2020/3/1 交易时间：4:11\n\n"
                        "交易流水序号：123\n\n"
                        "<table>"
                        "<tr><td>账户代号</td><td colspan=\"2\">324255555555565</td></tr>"
                        "<tr><td>对方账户</td><td colspan=\"2\">8848884888488840</td></tr>"
                        "<tr><td>交易金额</td><td>2554.45</td><td>账户余额：356.1</td></tr>"
                        "<tr><td>借贷标记</td><td>是</td></tr>"
                        "<tr><td>对方行号</td><td>c01</td></tr>"
                        "<tr><td>交易渠道</td><td>网银转账</td></tr>"
                        "<tr><td>年龄</td><td>22</td></tr>"
                        "<tr><td>性别</td><td>男</td></tr>"
                        "</table>"
                    ),
                }
            ],
            "structured_tables": [],
            "plain_texts": [],
            "source_meta": [{"asset_id": "voucher-1", "asset_type": "document", "original_name": "转账凭证.png"}],
        }
        example_output = {
            "standardized_transactions": [
                {
                    "jylsxh": "123",
                    "zhdh": "324255555555565",
                    "dfzh": "8848884888488840",
                    "jdbj": 1,
                    "jyje": 2554.45,
                    "zhye": 356.1,
                    "dfhh": "c01",
                    "jyrq": "2020-03-01",
                    "jysj": "04:11:00",
                    "jyqd": "网银转账",
                    "dfmccd": 0,
                    "xb": 1,
                    "年龄": 22
                }
            ],
            "transaction_candidates": [
                {
                    "payer_account": "324255555555565",
                    "receiver_account": "8848884888488840",
                    "amount": 2554.45,
                    "timestamp": "2020-03-01 04:11:00",
                    "channel": "网银转账",
                    "description": "转账凭证提取结果",
                    "evidence_refs": ["voucher-1"]
                }
            ],
            "entities": {
                "accounts": ["324255555555565", "8848884888488840"],
                "names": [],
                "amounts": [2554.45, 356.1],
                "timestamps": ["2020-03-01 04:11:00"],
                "locations": []
            },
            "risk_signals": ["存在文档类多模态证据"],
            "evidence_alignment": [
                {
                    "asset_id": "voucher-1",
                    "mapped_fields": ["jylsxh", "zhdh", "dfzh", "jdbj", "jyje", "zhye", "dfhh", "jyrq", "jysj", "jyqd", "xb", "年龄"]
                }
            ],
            "summary": "已从转账凭证中提取出一条标准交易记录。"
        }
        return [
            {
                "role": "system",
                "content": (
                    "你是金融多模态证据归一化引擎。你的任务不是做最终欺诈判断，而是从干净的 Markdown、文本中抽取标准交易记录、实体、风险信号。"
                    "只输出合法 JSON，不要输出解释。"
                    "严格要求："
                    "1. 如果凭证里出现了账户代号、对方账户、交易金额、日期/时间、借贷标记等字段，必须优先生成 standardized_transactions。"
                    "2. entities.amounts 只允许保留真实金额字段，例如交易金额、账户余额；绝不能放日期拆分数字、流水号、账号、页码、坐标、bbox。"
                    "3. accounts 只允许保留账号；timestamps 只允许保留时间戳；不要把任何无关数字混进去。"
                    "4. 缺失字段可以留空或填 0，但不要捏造。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "下面是一个示例。\n\n"
                    f"输入：{json.dumps(example_input, ensure_ascii=False)}\n\n"
                    f"输出：{json.dumps(example_output, ensure_ascii=False)}"
                ),
            },
            {
                "role": "user",
                "content": (
                    "请将以下证据包整理成 JSON，字段必须包含：standardized_transactions, transaction_candidates, entities, risk_signals, evidence_alignment, summary。\n\n"
                    f"{json.dumps(normalize_payload, ensure_ascii=False)}"
                ),
            },
        ]

    def _build_analysis_prompt(self, normalized: dict) -> list[dict]:
        json_safe_normalized = to_json_safe(normalized)
        return [
            {
                "role": "system",
                "content": (
                    "你是金融欺诈分析助手。请基于结构化证据输出最终风险结论。"
                    "只输出合法 JSON，字段必须包含：risk_level, confidence, model_source, narrative, suggested_actions, link_path。"
                    "link_path 为数组，元素必须包含 account, risk_level, action。"
                ),
            },
            {"role": "user", "content": json.dumps(json_safe_normalized, ensure_ascii=False)},
        ]

    def _call_chat_completion(self, messages: list[dict]) -> str:
        response = self._request_json(
            method="POST",
            url=f"{settings.analysis_llm_base_url.rstrip('/')}/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.analysis_llm_api_key}",
            },
            data={
                "model": settings.analysis_llm_model,
                "messages": messages,
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            },
            timeout=settings.analysis_llm_timeout_seconds,
        )
        choice = (response.get("choices") or [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")
        if isinstance(content, list):
            return "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return content

    def _extract_json_object(self, payload: str) -> dict:
        payload = payload.strip()
        if not payload:
            raise ValueError("模型返回为空")
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            start = payload.find("{")
            end = payload.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise
            return json.loads(payload[start : end + 1])

    def _request_json(self, *, method: str, url: str, headers: dict, data: dict | None = None, timeout: int | float) -> dict:
        response = self._request_with_retry(
            method=method,
            url=url,
            headers=headers,
            json=data,
            timeout=timeout,
        )
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(f"外部服务返回的不是合法 JSON：{response.text[:200]}") from exc

    def _put_file(self, upload_url: str, path: Path) -> None:
        self._request_with_retry(
            method="PUT",
            url=upload_url,
            data=path.read_bytes(),
            timeout=settings.analysis_llm_timeout_seconds,
        )

    def _download_bytes(self, url: str, timeout: int | float) -> bytes:
        response = self._request_with_retry(method="GET", url=url, timeout=timeout)
        return response.content

    def _request_with_retry(self, *, method: str, url: str, timeout: int | float, **kwargs) -> requests.Response:
        last_error: Exception | None = None
        for index, delay in enumerate(HTTP_RETRY_DELAYS, start=1):
            if delay > 0:
                time.sleep(delay)
            try:
                response = self.http.request(method=method, url=url, timeout=timeout, **kwargs)
                response.raise_for_status()
                return response
            except requests.HTTPError as exc:
                status_code = exc.response.status_code if exc.response is not None else None
                if status_code is not None and 400 <= status_code < 500:
                    detail = exc.response.text if exc.response is not None else ""
                    raise RuntimeError(detail or str(exc)) from exc
                last_error = exc
            except requests.RequestException as exc:
                last_error = exc

        raise RuntimeError(str(last_error) if last_error is not None else "外部请求失败")

    def _write_temp_zip(self, asset_id: str, content: bytes) -> Path:
        temp_dir = self.storage_dir / "_mineru_cache"
        temp_dir.mkdir(parents=True, exist_ok=True)
        zip_path = temp_dir / f"{asset_id}.zip"
        zip_path.write_bytes(content)
        return zip_path

    def _table_to_markdown(self, sheet_name: str, headers: list[str], rows: list[tuple | list]) -> str:
        safe_headers = [header or "-" for header in headers]
        if not safe_headers:
            return f"## {sheet_name}\n\n空表"
        lines = [f"## {sheet_name}", "", "| " + " | ".join(safe_headers) + " |"]
        lines.append("| " + " | ".join("---" for _ in safe_headers) + " |")
        for row in rows:
            values = [stringify(row[index]) if index < len(row) else "" for index in range(len(safe_headers))]
            lines.append("| " + " | ".join(values) + " |")
        return "\n".join(lines)

    def _generate_job_id(self) -> str:
        return f"analysis-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

    def _generate_asset_id(self) -> str:
        return f"asset-{uuid.uuid4().hex}"

    def _to_asset_schema(self, item: dict) -> AnalysisAsset:
        return AnalysisAsset(
            asset_id=item["asset_id"],
            asset_type=item["asset_type"],
            original_name=item["original_name"],
            mime_type=item["mime_type"],
            size_bytes=item["size_bytes"],
        )

    def _ensure_job_access(self, job: dict, current_user: dict) -> None:
        if current_user["role"] != "admin" and job["created_by"] != current_user["username"]:
            raise AppError("当前账户无权访问该分析任务", status_code=403, code="FORBIDDEN")

    def _now_iso(self) -> str:
        return datetime.utcnow().replace(microsecond=0).isoformat()

    def _normalize_result_payload(self, payload: dict | None) -> dict | None:
        if not isinstance(payload, dict):
            return None

        normalized = dict(payload)
        fallback_level = normalize_risk_level_value(normalized.get("risk_level"), "medium")
        normalized["risk_level"] = fallback_level
        normalized["confidence"] = safe_float(normalized.get("confidence")) or 0.0
        normalized["model_source"] = stringify(normalized.get("model_source")) or "heuristic-fallback"
        normalized["narrative"] = stringify(normalized.get("narrative")) or "系统已完成初步判定。"
        normalized["normalized_summary"] = stringify(normalized.get("normalized_summary"))
        normalized["transaction_candidates"] = (
            normalized.get("transaction_candidates")
            if isinstance(normalized.get("transaction_candidates"), list)
            else []
        )

        normalized_actions: list[str] = []
        for item in normalized.get("suggested_actions") or []:
            if isinstance(item, str):
                action_text = item.strip()
            elif isinstance(item, dict):
                action_text = stringify(item.get("action") or item.get("label") or item.get("name")).strip()
            else:
                action_text = stringify(item).strip()
            if action_text:
                normalized_actions.append(action_text)
        normalized["suggested_actions"] = normalized_actions or build_actions(fallback_level)

        normalized_signals: list[str] = []
        for item in normalized.get("risk_signals") or []:
            signal_text = stringify(item).strip()
            if signal_text:
                normalized_signals.append(signal_text)
        normalized["risk_signals"] = normalized_signals

        normalized_path: list[dict] = []
        for item in normalized.get("link_path") or []:
            if not isinstance(item, dict):
                continue
            account = stringify(item.get("account")).strip() or "待确认账户"
            action = stringify(item.get("action")).strip() or "复核"
            risk_level = normalize_risk_level_value(item.get("risk_level"), fallback_level)
            normalized_path.append(
                AnalysisRiskNode(
                    account=account,
                    risk_level=risk_level,
                    action=action,
                ).model_dump()
            )
        if not normalized_path:
            normalized_path = [
                AnalysisRiskNode(
                    account="待补充证据",
                    risk_level=fallback_level,
                    action="复核",
                ).model_dump()
            ]
        normalized["link_path"] = normalized_path

        return normalized

    def _apply_focus_targets(self, normalized: dict, result: dict) -> dict:
        if not isinstance(result, dict):
            return result

        focus_accounts = {
            stringify(item.get("account")).strip()
            for item in focus_repository.list_targets()
            if stringify(item.get("account")).strip()
        }
        if not focus_accounts:
            return result

        matched_accounts: list[str] = []
        seen_accounts: set[str] = set()

        def collect(account: object) -> None:
            text = stringify(account).strip()
            if text and text in focus_accounts and text not in seen_accounts:
                seen_accounts.add(text)
                matched_accounts.append(text)

        for account in (normalized.get("entities") or {}).get("accounts", []):
            collect(account)

        for row in normalized.get("standardized_transactions") or []:
            collect(row.get("zhdh"))
            collect(row.get("dfzh"))

        for row in normalized.get("transaction_candidates") or []:
            collect(row.get("payer_account"))
            collect(row.get("receiver_account"))

        for row in result.get("link_path") or []:
            if isinstance(row, dict):
                collect(row.get("account"))

        if not matched_accounts:
            return result

        enriched = dict(result)
        risk_signals = [
            stringify(item).strip()
            for item in enriched.get("risk_signals", [])
            if stringify(item).strip()
        ]
        focus_signal = f"命中重点关注账号：{'、'.join(matched_accounts)}"
        if focus_signal not in risk_signals:
            risk_signals.insert(0, focus_signal)
        enriched["risk_signals"] = risk_signals

        suggested_actions = [
            stringify(item).strip()
            for item in enriched.get("suggested_actions", [])
            if stringify(item).strip()
        ]
        focus_action = "优先复核重点关注账号及其关联交易链路"
        if focus_action not in suggested_actions:
            suggested_actions.insert(0, focus_action)
        enriched["suggested_actions"] = suggested_actions

        narrative = stringify(enriched.get("narrative")).strip()
        focus_prefix = f"本次分析命中重点关注账号：{'、'.join(matched_accounts)}。"
        if focus_prefix not in narrative:
            enriched["narrative"] = f"{focus_prefix}{narrative}" if narrative else focus_prefix

        return enriched


service = AnalysisService()

