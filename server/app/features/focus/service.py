from __future__ import annotations

from app.core.errors import AppError
from app.features.analysis.repository import repository as analysis_repository

from .repository import repository
from .schemas import (
    FocusCloudAccountItem,
    FocusLocalAccountItem,
    FocusLogItem,
    FocusMode,
    FocusMutationResponse,
    FocusOverviewResponse,
    FocusWatchRequest,
)


class FocusService:
    def _normalize_account(self, value: object) -> str:
        return str(value or "").strip()

    def _iter_jobs(self, current_user: dict) -> list[dict]:
        return analysis_repository.list_jobs(created_by=None)

    def _extract_local_accounts(self, job: dict | None) -> list[str]:
        if not job:
            return []

        normalized = job.get("normalized_json") or {}
        accounts: list[str] = []
        seen: set[str] = set()

        for row in normalized.get("standardized_transactions") or []:
            account = self._normalize_account(row.get("zhdh"))
            if account and account not in seen:
                accounts.append(account)
                seen.add(account)

        if accounts:
            return accounts

        for account in (normalized.get("entities") or {}).get("accounts", []):
            text = self._normalize_account(account)
            if text and text not in seen:
                accounts.append(text)
                seen.add(text)
        return accounts

    def _collect_counterparts(self, account: str, jobs: list[dict]) -> list[str]:
        counterparts: list[str] = []
        seen = {account}

        for job in jobs:
            normalized = job.get("normalized_json") or {}

            for row in normalized.get("standardized_transactions") or []:
                payer = self._normalize_account(row.get("zhdh"))
                receiver = self._normalize_account(row.get("dfzh"))
                if payer == account and receiver and receiver not in seen:
                    counterparts.append(receiver)
                    seen.add(receiver)

            for row in normalized.get("transaction_candidates") or []:
                payer = self._normalize_account(row.get("payer_account"))
                receiver = self._normalize_account(row.get("receiver_account"))
                if payer == account and receiver and receiver not in seen:
                    counterparts.append(receiver)
                    seen.add(receiver)

        return counterparts

    def get_overview(self, current_user: dict, selected_job_id: str | None = None) -> FocusOverviewResponse:
        jobs = self._iter_jobs(current_user)
        hidden_logs = repository.list_hidden_logs(current_user["username"])
        visible_jobs = [job for job in jobs if job["job_id"] not in hidden_logs]

        selected_job = None
        if selected_job_id:
            selected_job = next((job for job in visible_jobs if job["job_id"] == selected_job_id), None)
        if selected_job is None and visible_jobs:
            selected_job = visible_jobs[0]

        log_items = [
            FocusLogItem(
                job_id=job["job_id"],
                created_at=job["created_at"],
                operator=job["created_by"],
                status=job["status"],
                account_count=len(self._extract_local_accounts(job)),
            )
            for job in visible_jobs
        ]

        local_accounts = [
            FocusLocalAccountItem(account=account)
            for account in self._extract_local_accounts(selected_job)
        ]
        cloud_accounts = [
            FocusCloudAccountItem(
                account=item["account"],
                mode=item["mode"],
                source_account=item.get("source_account"),
                is_seed=bool(item.get("is_seed")),
                created_by=item["created_by"],
                updated_at=item["updated_at"],
            )
            for item in repository.list_targets()
        ]

        return FocusOverviewResponse(
            selected_job_id=selected_job["job_id"] if selected_job else None,
            logs=log_items,
            local_accounts=local_accounts,
            cloud_accounts=cloud_accounts,
        )

    def watch_account(self, current_user: dict, payload: FocusWatchRequest) -> FocusMutationResponse:
        account = self._normalize_account(payload.account)
        if not account:
            raise AppError("请输入需要操作的交易账户", status_code=400, code="EMPTY_ACCOUNT")

        jobs = self._iter_jobs(current_user)
        mode: FocusMode = payload.mode
        affected_accounts = [account]

        repository.upsert_target(
            account=account,
            mode=mode,
            source_account=None,
            source_job_id=payload.job_id,
            is_seed=True,
            created_by=current_user["username"],
        )
        repository.create_event(
            account=account,
            action="watch",
            mode=mode,
            source_account=None,
            source_job_id=payload.job_id,
            operator=current_user["username"],
        )

        if mode == "deep":
            for counterpart in self._collect_counterparts(account, jobs):
                repository.upsert_target(
                    account=counterpart,
                    mode=mode,
                    source_account=account,
                    source_job_id=payload.job_id,
                    is_seed=False,
                    created_by=current_user["username"],
                )
                repository.create_event(
                    account=counterpart,
                    action="watch",
                    mode=mode,
                    source_account=account,
                    source_job_id=payload.job_id,
                    operator=current_user["username"],
                )
                affected_accounts.append(counterpart)

        mode_label = "正常追踪" if mode == "normal" else "深度追踪"
        return FocusMutationResponse(
            message=f"已按{mode_label}加入重点关注",
            affected_accounts=affected_accounts,
            selected_job_id=payload.job_id,
        )

    def unwatch_account(self, current_user: dict, account: str) -> FocusMutationResponse:
        normalized_account = self._normalize_account(account)
        if not normalized_account:
            raise AppError("请输入需要解除重点关注的账号", status_code=400, code="EMPTY_ACCOUNT")

        deleted = repository.delete_target(normalized_account)
        repository.create_event(
            account=normalized_account,
            action="unwatch",
            mode=None,
            source_account=None,
            source_job_id=None,
            operator=current_user["username"],
        )
        if not deleted:
            raise AppError("该账号当前不在重点关注列表中", status_code=404, code="FOCUS_TARGET_NOT_FOUND")

        return FocusMutationResponse(
            message=f"已解除重点关注：{normalized_account}",
            affected_accounts=[normalized_account],
            selected_job_id=None,
        )

    def hide_log(self, current_user: dict, job_id: str) -> FocusMutationResponse:
        if not analysis_repository.get_job(job_id):
            raise AppError("日志记录不存在", status_code=404, code="FOCUS_LOG_NOT_FOUND")

        repository.hide_log(job_id=job_id, hidden_by=current_user["username"])
        repository.create_event(
            account=job_id,
            action="hide_log",
            mode=None,
            source_account=None,
            source_job_id=job_id,
            operator=current_user["username"],
        )
        return FocusMutationResponse(
            message="该日志已从重点监测列表移除",
            affected_accounts=[],
            selected_job_id=None,
        )


service = FocusService()
