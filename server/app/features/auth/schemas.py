from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


UserRole = Literal["admin", "analyst"]

class LoginRequest(BaseModel):
    username: str
    password: str
    token_code: str = Field(min_length=6, max_length=6)
    machine_code: str | None = None


class UserProfile(BaseModel):
    username: str
    display_name: str
    role: UserRole
    organization: str
    phone: str
    email: str
    job_id: str
    is_active: bool
    totp_enabled: bool


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile


class ProfileUpdateRequest(BaseModel):
    display_name: str
    organization: str
    phone: str
    email: str
    job_id: str
    token_code: str = Field(min_length=6, max_length=6)


class AccountCreateRequest(BaseModel):
    username: str
    password: str = Field(min_length=4)
    display_name: str
    role: UserRole
    organization: str
    phone: str
    email: str
    job_id: str


class AccountUpdateRequest(BaseModel):
    display_name: str
    role: UserRole
    organization: str
    phone: str
    email: str
    job_id: str
    is_active: bool = True
    password: str | None = Field(default=None, min_length=4)


class AccountListResponse(BaseModel):
    items: list[UserProfile]


class TotpProvisioning(BaseModel):
    secret: str
    otpauth_url: str
    issuer: str


class TotpBootstrapRequest(BaseModel):
    username: str
    password: str


class AccountMutationResponse(BaseModel):
    user: UserProfile
    provisioning: TotpProvisioning | None = None
