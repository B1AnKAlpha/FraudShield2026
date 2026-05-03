from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import AppError
from app.features.auth.schemas import (
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
from app.features.auth.service import AuthService

router = APIRouter()
service = AuthService()
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError("缺少登录凭证", status_code=401, code="MISSING_AUTHORIZATION")
    return service.get_user_by_token(credentials.credentials)


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest):
    return service.login(payload)


@router.post("/bootstrap-totp", response_model=TotpProvisioning)
async def bootstrap_totp(payload: TotpBootstrapRequest):
    return service.bootstrap_totp(payload)


@router.get("/me", response_model=UserProfile)
async def me(current_user=Depends(get_current_user)):
    return service.me(current_user)


@router.post("/logout", status_code=204)
async def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    current_user=Depends(get_current_user),
):
    if credentials is None:
        raise AppError("缺少登录凭证", status_code=401, code="MISSING_AUTHORIZATION")
    service.logout(credentials.credentials, current_user)


@router.put("/profile", response_model=UserProfile)
async def update_profile(payload: ProfileUpdateRequest, current_user=Depends(get_current_user)):
    return service.update_profile(current_user, payload)


@router.get("/accounts", response_model=AccountListResponse)
async def list_accounts(current_user=Depends(get_current_user)):
    return service.list_accounts(current_user)


@router.post("/accounts", response_model=AccountMutationResponse)
async def create_account(payload: AccountCreateRequest, current_user=Depends(get_current_user)):
    return service.create_account(current_user, payload)


@router.put("/accounts/{username}", response_model=AccountMutationResponse)
async def update_account(
    username: str, payload: AccountUpdateRequest, current_user=Depends(get_current_user)
):
    return service.update_account(current_user, username, payload)


@router.delete("/accounts/{username}", status_code=204)
async def delete_account(username: str, current_user=Depends(get_current_user)):
    service.delete_account(current_user, username)


@router.post("/accounts/{username}/reset-totp", response_model=AccountMutationResponse)
async def reset_totp(username: str, current_user=Depends(get_current_user)):
    return service.reset_totp(current_user, username)
