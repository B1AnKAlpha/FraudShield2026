import { apiDelete, apiGet, apiPost, apiPut } from "@/api/client";
import type {
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
} from "@/types/auth";

export function login(payload: LoginRequest) {
  return apiPost<LoginResponse>("/api/auth/login", payload);
}

export function bootstrapTotp(payload: TotpBootstrapRequest) {
  return apiPost<TotpProvisioning>("/api/auth/bootstrap-totp", payload);
}

export function fetchCurrentUser() {
  return apiGet<UserProfile>("/api/auth/me");
}

export function logout() {
  return apiPost<void>("/api/auth/logout", {});
}

export function updateProfile(payload: ProfileUpdateRequest) {
  return apiPut<UserProfile>("/api/auth/profile", payload);
}

export function fetchAccounts() {
  return apiGet<AccountListResponse>("/api/auth/accounts");
}

export function createAccount(payload: AccountCreateRequest) {
  return apiPost<AccountMutationResponse>("/api/auth/accounts", payload);
}

export function updateAccount(username: string, payload: AccountUpdateRequest) {
  return apiPut<AccountMutationResponse>(`/api/auth/accounts/${username}`, payload);
}

export function deleteAccount(username: string) {
  return apiDelete(`/api/auth/accounts/${username}`);
}

export function resetAccountTotp(username: string) {
  return apiPost<AccountMutationResponse>(`/api/auth/accounts/${username}/reset-totp`, {});
}
