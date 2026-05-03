from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


FocusMode = Literal["normal", "deep"]


class FocusCloudAccountItem(BaseModel):
    account: str
    mode: FocusMode
    source_account: str | None = None
    is_seed: bool = True
    created_by: str
    updated_at: str


class FocusLocalAccountItem(BaseModel):
    account: str


class FocusLogItem(BaseModel):
    job_id: str
    created_at: str
    operator: str
    status: str
    account_count: int = 0


class FocusOverviewResponse(BaseModel):
    selected_job_id: str | None = None
    logs: list[FocusLogItem]
    local_accounts: list[FocusLocalAccountItem]
    cloud_accounts: list[FocusCloudAccountItem]


class FocusWatchRequest(BaseModel):
    account: str = Field(min_length=1, max_length=128)
    mode: FocusMode = "normal"
    job_id: str | None = None


class FocusMutationResponse(BaseModel):
    message: str
    affected_accounts: list[str] = Field(default_factory=list)
    selected_job_id: str | None = None
