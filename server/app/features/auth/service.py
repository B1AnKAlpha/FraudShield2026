from __future__ import annotations

from datetime import datetime, timedelta

from app.core.config import settings
from app.core.errors import AppError

from .repository import repository
from .schemas import (
    AccountCreateRequest,
    AccountListResponse,
    AccountMutationResponse,
    AccountUpdateRequest,
    LoginRequest,
    LoginResponse,
    ProfileUpdateRequest,
    TotpBootstrapRequest,
    TotpProvisioning,
    UserProfile,
)
from .security import (
    build_otpauth_url,
    generate_access_token,
    generate_totp_secret,
    hash_password,
    verify_password,
    verify_totp_code,
)


class AuthService:

    def _to_user_profile(self, user: dict) -> UserProfile:
        return UserProfile(
            username=user["username"],
            display_name=user["display_name"],
            role=user["role"],
            organization=user["organization"],
            phone=user["phone"],
            email=user["email"],
            job_id=user["job_id"],
            is_active=bool(user["is_active"]),
            totp_enabled=bool(user["totp_enabled"]),
        )

    def _verify_token_code(self, user: dict, token_code: str) -> None:
        if not user.get("totp_secret"):
            return

        dev_bypass = settings.auth_dev_totp_bypass
        if dev_bypass and token_code.strip() == dev_bypass:
            return

        if not verify_totp_code(user["totp_secret"], token_code):
            raise AppError("动态令牌错误", status_code=401, code="INVALID_TOKEN_CODE")

    def _build_provisioning(self, *, username: str, secret: str) -> TotpProvisioning:
        return TotpProvisioning(
            secret=secret,
            otpauth_url=build_otpauth_url(
                issuer=settings.auth_totp_issuer,
                username=username,
                secret=secret,
            ),
            issuer=settings.auth_totp_issuer,
        )

    def _enforce_machine_code(self, user: dict, machine_code: str | None) -> None:
        if not machine_code:
            return

        normalized_code = machine_code.strip()
        if not normalized_code:
            return

        if repository.get_active_machine(user["username"], normalized_code):
            return

        bindings = repository.list_active_machines(user["username"])
        if bindings:
            raise AppError("当前机器未注册，请联系管理员确认终端授权", status_code=403, code="MACHINE_NOT_ALLOWED")

        repository.upsert_machine(
            username=user["username"],
            machine_code=normalized_code,
            machine_label="默认终端",
        )
        repository.log_action(
            actor_username=user["username"],
            action="bind_machine",
            target_username=user["username"],
            detail=f"首次绑定机器码 {normalized_code[:12]}",
        )

    def _ensure_admin(self, user: dict) -> None:
        if user["role"] != "admin":
            raise AppError("当前账户无管理权限", status_code=403, code="FORBIDDEN")

    def login(self, payload: LoginRequest) -> LoginResponse:
        user = repository.get_user_by_username(payload.username.strip())
        if not user or not verify_password(payload.password, user["password_hash"]):
            raise AppError("账号或密码错误", status_code=401, code="INVALID_CREDENTIALS")
        if not user["is_active"]:
            raise AppError("当前账户已停用", status_code=403, code="ACCOUNT_DISABLED")

        self._enforce_machine_code(user, payload.machine_code)
        self._verify_token_code(user, payload.token_code)

        token = generate_access_token()
        expires_at = (datetime.utcnow() + timedelta(hours=settings.auth_session_hours)).replace(
            microsecond=0
        )
        repository.save_session(token=token, user_id=user["id"], expires_at=expires_at.isoformat())
        repository.log_action(
            actor_username=user["username"],
            action="login",
            target_username=user["username"],
            detail="登录成功",
        )
        return LoginResponse(access_token=token, user=self._to_user_profile(user))

    def bootstrap_totp(self, payload: TotpBootstrapRequest) -> TotpProvisioning:
        user = repository.get_user_by_username(payload.username.strip())
        if not user or not verify_password(payload.password, user["password_hash"]):
            raise AppError("账号或密码错误", status_code=401, code="INVALID_CREDENTIALS")
        if not user["is_active"]:
            raise AppError("当前账户已停用", status_code=403, code="ACCOUNT_DISABLED")
        if user.get("totp_secret"):
            raise AppError("当前账户已绑定动态令牌", status_code=409, code="TOTP_ALREADY_BOUND")

        secret = generate_totp_secret()
        repository.update_user(
            user["username"],
            {
                "totp_secret": secret,
                "bootstrap_token": None,
            },
        )
        repository.log_action(
            actor_username=user["username"],
            action="bootstrap_totp",
            target_username=user["username"],
            detail="首次绑定动态令牌",
        )
        return self._build_provisioning(username=user["username"], secret=secret)

    def get_user_by_token(self, token: str) -> dict:
        user = repository.get_session_user(token)
        if not user:
            raise AppError("登录状态已失效，请重新登录", status_code=401, code="INVALID_SESSION")
        return user

    def me(self, current_user: dict) -> UserProfile:
        return self._to_user_profile(current_user)

    def logout(self, token: str, current_user: dict) -> None:
        repository.delete_session(token)
        repository.log_action(
            actor_username=current_user["username"],
            action="logout",
            target_username=current_user["username"],
            detail="退出登录",
        )

    def update_profile(self, current_user: dict, payload: ProfileUpdateRequest) -> UserProfile:
        latest_user = repository.get_user_by_username(current_user["username"])
        if not latest_user:
            raise AppError("当前账户不存在", status_code=404, code="ACCOUNT_NOT_FOUND")

        self._verify_token_code(latest_user, payload.token_code)
        updated_user = repository.update_user(
            current_user["username"],
            {
                "display_name": payload.display_name.strip(),
                "organization": payload.organization.strip(),
                "phone": payload.phone.strip(),
                "email": payload.email.strip(),
                "job_id": payload.job_id.strip(),
            },
        )
        repository.log_action(
            actor_username=current_user["username"],
            action="update_profile",
            target_username=current_user["username"],
            detail="更新个人资料",
        )
        return self._to_user_profile(updated_user)

    def list_accounts(self, current_user: dict) -> AccountListResponse:
        self._ensure_admin(current_user)
        return AccountListResponse(items=[self._to_user_profile(item) for item in repository.list_users()])

    def create_account(self, current_user: dict, payload: AccountCreateRequest) -> AccountMutationResponse:
        self._ensure_admin(current_user)
        if repository.get_user_by_username(payload.username.strip()):
            raise AppError("该账号已存在", status_code=409, code="ACCOUNT_EXISTS")

        created_user = repository.create_user(
            {
                "username": payload.username.strip(),
                "password_hash": hash_password(payload.password),
                "display_name": payload.display_name.strip(),
                "role": payload.role,
                "organization": payload.organization.strip(),
                "phone": payload.phone.strip(),
                "email": payload.email.strip(),
                "job_id": payload.job_id.strip(),
                "is_active": True,
                "totp_secret": generate_totp_secret(),
                "bootstrap_token": None,
            }
        )
        repository.log_action(
            actor_username=current_user["username"],
            action="create_account",
            target_username=created_user["username"],
            detail="新增账户",
        )
        return AccountMutationResponse(
            user=self._to_user_profile(created_user),
            provisioning=self._build_provisioning(
                username=created_user["username"],
                secret=created_user["totp_secret"],
            ),
        )

    def update_account(
        self, current_user: dict, username: str, payload: AccountUpdateRequest
    ) -> AccountMutationResponse:
        self._ensure_admin(current_user)
        target_user = repository.get_user_by_username(username)
        if not target_user:
            raise AppError("账户不存在", status_code=404, code="ACCOUNT_NOT_FOUND")
        if target_user["username"] == current_user["username"] and not payload.is_active:
            raise AppError("不能停用当前登录管理员", status_code=409, code="INVALID_OPERATION")

        updates = {
            "display_name": payload.display_name.strip(),
            "role": payload.role,
            "organization": payload.organization.strip(),
            "phone": payload.phone.strip(),
            "email": payload.email.strip(),
            "job_id": payload.job_id.strip(),
            "is_active": int(payload.is_active),
        }
        if payload.password:
            updates["password_hash"] = hash_password(payload.password)
        updated_user = repository.update_user(username, updates)
        repository.log_action(
            actor_username=current_user["username"],
            action="update_account",
            target_username=username,
            detail="更新账户信息",
        )
        return AccountMutationResponse(user=self._to_user_profile(updated_user))

    def delete_account(self, current_user: dict, username: str) -> None:
        self._ensure_admin(current_user)
        target_user = repository.get_user_by_username(username)
        if not target_user:
            raise AppError("账户不存在", status_code=404, code="ACCOUNT_NOT_FOUND")
        if username == current_user["username"]:
            raise AppError("不能删除当前登录管理员", status_code=409, code="INVALID_OPERATION")
        if target_user["role"] == "admin" and repository.count_admin_users() <= 1:
            raise AppError("至少需要保留一个管理员账户", status_code=409, code="LAST_ADMIN")

        repository.delete_user(username)
        repository.log_action(
            actor_username=current_user["username"],
            action="delete_account",
            target_username=username,
            detail="删除账户",
        )

    def reset_totp(self, current_user: dict, username: str) -> AccountMutationResponse:
        self._ensure_admin(current_user)
        target_user = repository.get_user_by_username(username)
        if not target_user:
            raise AppError("账户不存在", status_code=404, code="ACCOUNT_NOT_FOUND")

        secret = generate_totp_secret()
        updated_user = repository.update_user(
            username,
            {"totp_secret": secret, "bootstrap_token": None},
        )
        repository.log_action(
            actor_username=current_user["username"],
            action="reset_totp",
            target_username=username,
            detail="重置动态令牌",
        )
        return AccountMutationResponse(
            user=self._to_user_profile(updated_user),
            provisioning=self._build_provisioning(username=username, secret=secret),
        )
