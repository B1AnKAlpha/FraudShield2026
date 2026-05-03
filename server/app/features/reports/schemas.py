from pydantic import BaseModel


class ReportItem(BaseModel):
    report_id: str
    title: str
    created_at: str
    operator: str
    status: str
    format: str
    download_url: str | None = None


class ReportListResponse(BaseModel):
    items: list[ReportItem]
