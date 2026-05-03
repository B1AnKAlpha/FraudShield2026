export interface LoginRequest {
  username: string;
  password: string;
  token_code: string;
  machine_code?: string;
}

export interface UserProfile {
  username: string;
  display_name: string;
  role: string;
  organization: string;
  phone: string;
  email: string;
  job_id: string;
  is_active: boolean;
  totp_enabled: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserProfile;
}

export interface AuthSession {
  accessToken: string;
  user: UserProfile;
}

export interface ProfileUpdateRequest {
  display_name: string;
  organization: string;
  phone: string;
  email: string;
  job_id: string;
  token_code: string;
}

export interface AccountCreateRequest {
  username: string;
  password: string;
  display_name: string;
  role: "admin" | "analyst";
  organization: string;
  phone: string;
  email: string;
  job_id: string;
}

export interface AccountUpdateRequest {
  display_name: string;
  role: "admin" | "analyst";
  organization: string;
  phone: string;
  email: string;
  job_id: string;
  is_active: boolean;
  password?: string;
}

export interface TotpProvisioning {
  secret: string;
  otpauth_url: string;
  issuer: string;
}

export interface TotpBootstrapRequest {
  username: string;
  password: string;
}

export interface AccountMutationResponse {
  user: UserProfile;
  provisioning: TotpProvisioning | null;
}

export interface AccountListResponse {
  items: UserProfile[];
}
