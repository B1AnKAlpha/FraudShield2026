import { defineStore } from "pinia";

import { fetchCurrentUser, login, logout, updateProfile } from "@/api/modules/auth";
import type { AuthSession, LoginRequest, ProfileUpdateRequest, UserProfile } from "@/types/auth";
import { runLoginSecurityChecks } from "@/utils/security";

export const AUTH_SESSION_KEY = "fraudshield2026.session";

export function readStoredSession(): AuthSession | null {
  if (typeof window === "undefined") {
    return null;
  }

  const rawValue = window.localStorage.getItem(AUTH_SESSION_KEY);
  if (!rawValue) {
    return null;
  }

  try {
    return JSON.parse(rawValue) as AuthSession;
  } catch {
    window.localStorage.removeItem(AUTH_SESSION_KEY);
    return null;
  }
}

function persistSession(session: AuthSession | null) {
  if (typeof window === "undefined") {
    return;
  }

  if (!session) {
    window.localStorage.removeItem(AUTH_SESSION_KEY);
    return;
  }

  window.localStorage.setItem(AUTH_SESSION_KEY, JSON.stringify(session));
}

interface AuthState {
  accessToken: string;
  user: UserProfile | null;
  loading: boolean;
  error: string;
}

export const useAuthStore = defineStore("auth", {
  state: (): AuthState => ({
    accessToken: "",
    user: null,
    loading: false,
    error: "",
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.accessToken && state.user),
    accountRole: (state) => (state.user?.role === "admin" ? "管理员账户" : "分析员账户"),
    displayName: (state) => state.user?.display_name ?? state.user?.username ?? "未登录",
  },
  actions: {
    restoreSession() {
      const session = readStoredSession();
      if (!session) {
        this.accessToken = "";
        this.user = null;
        return;
      }

      this.accessToken = session.accessToken;
      this.user = session.user;
    },
    async bootstrapSession() {
      this.restoreSession();
      if (!this.accessToken) {
        return;
      }

      try {
        this.user = await fetchCurrentUser();
        persistSession({
          accessToken: this.accessToken,
          user: this.user,
        });
      } catch {
        this.logout();
      }
    },
    async loginWithLegacyForm(payload: LoginRequest) {
      if (!payload.username.trim()) {
        throw new Error("请输入账号");
      }

      if (!payload.password.trim()) {
        throw new Error("请输入密码");
      }

      if (!payload.token_code.trim()) {
        throw new Error("请输入动态令牌");
      }

      this.loading = true;
      this.error = "";

      try {
        const securityContext = await runLoginSecurityChecks();
        const response = await login({
          ...payload,
          machine_code: securityContext.machine_code || undefined,
        });
        this.accessToken = response.access_token;
        this.user = response.user;
        persistSession({
          accessToken: response.access_token,
          user: response.user,
        });
      } catch (error) {
        this.error = error instanceof Error ? error.message : "登录失败";
        throw error;
      } finally {
        this.loading = false;
      }
    },
    async saveProfile(payload: ProfileUpdateRequest) {
      this.loading = true;
      this.error = "";
      try {
        const user = await updateProfile(payload);
        this.user = user;
        persistSession({
          accessToken: this.accessToken,
          user,
        });
        return user;
      } catch (error) {
        this.error = error instanceof Error ? error.message : "保存失败";
        throw error;
      } finally {
        this.loading = false;
      }
    },
    logout() {
      this.accessToken = "";
      this.user = null;
      this.error = "";
      persistSession(null);
    },
    async logoutRemote() {
      try {
        if (this.accessToken) {
          await logout();
        }
      } finally {
        this.logout();
      }
    },
  },
});
