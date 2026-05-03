from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AnalysisBaseModel(BaseModel):
    model_config = ConfigDict(protected_namespaces=())


class AnalysisAsset(AnalysisBaseModel):
    asset_id: str
    asset_type: str
    original_name: str
    mime_type: str
    size_bytes: int


class AnalysisParserSummary(AnalysisBaseModel):
    mineru_documents: int = 0
    spreadsheet_assets: int = 0
    plain_text_assets: int = 0
    warnings: list[str] = Field(default_factory=list)


class AnalysisRiskNode(AnalysisBaseModel):
    account: str
    risk_level: str
    action: str


class AnalysisResult(AnalysisBaseModel):
    risk_level: str
    confidence: float
    model_source: str
    narrative: str
    suggested_actions: list[str]
    link_path: list[AnalysisRiskNode]
    normalized_summary: str
    risk_signals: list[str] = Field(default_factory=list)
    transaction_candidates: list[dict] = Field(default_factory=list)


class AnalysisJobCreateResponse(AnalysisBaseModel):
    job_id: str
    status: str


class AnalysisJobDetailResponse(AnalysisBaseModel):
    job_id: str
    status: str
    created_by: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error_message: str | None = None
    assets: list[AnalysisAsset]
    parser_summary: AnalysisParserSummary | None = None
    result: AnalysisResult | None = None
    report_ready: bool = False


class AnalysisJobListItem(AnalysisBaseModel):
    job_id: str
    status: str
    created_by: str
    created_at: str
    finished_at: str | None = None
    risk_level: str | None = None
    confidence: float | None = None


class AnalysisJobListResponse(AnalysisBaseModel):
    items: list[AnalysisJobListItem]


class AnalysisReportResponse(AnalysisBaseModel):
    job_id: str
    title: str
    html: str
