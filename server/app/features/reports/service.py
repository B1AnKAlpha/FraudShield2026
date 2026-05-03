from __future__ import annotations

from app.features.analysis.repository import repository as analysis_repository
from app.features.reports.schemas import ReportItem, ReportListResponse


class ReportService:
    def list_reports(self) -> ReportListResponse:
        jobs = analysis_repository.list_jobs(created_by=None)
        items = [
            ReportItem(
                report_id=job["job_id"],
                title=job.get("report_title") or "金融欺诈检测分析报告",
                created_at=job["created_at"],
                operator=job["created_by"],
                status="ready" if job["status"] == "completed" else job["status"],
                format="pdf",
                download_url=f"/api/analysis/jobs/{job['job_id']}/report.pdf" if job.get("report_path") else None,
            )
            for job in jobs
            if job["status"] in {"completed", "processing", "failed"}
        ]
        return ReportListResponse(items=items)

    def get_report(self, report_id: str) -> ReportItem:
        job = analysis_repository.get_job(report_id)
        if not job:
            return ReportItem(
                report_id=report_id,
                title="金融欺诈检测分析报告",
                created_at="",
                operator="",
                status="missing",
                format="pdf",
                download_url=None,
            )

        return ReportItem(
            report_id=job["job_id"],
            title=job.get("report_title") or "金融欺诈检测分析报告",
            created_at=job["created_at"],
            operator=job["created_by"],
            status="ready" if job["status"] == "completed" else job["status"],
            format="pdf",
            download_url=f"/api/analysis/jobs/{job['job_id']}/report.pdf" if job.get("report_path") else None,
        )
