from fastapi import APIRouter

from app.features.reports.schemas import ReportItem, ReportListResponse
from app.features.reports.service import ReportService

router = APIRouter()
service = ReportService()


@router.get("", response_model=ReportListResponse)
async def list_reports():
    return service.list_reports()


@router.get("/{report_id}", response_model=ReportItem)
async def get_report(report_id: str):
    return service.get_report(report_id)
