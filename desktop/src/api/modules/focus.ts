import { apiDeleteJson, apiGet, apiPost } from "@/api/client";
import type { FocusMode, FocusMutationResponse, FocusOverviewResponse } from "@/types/focus";

export function fetchFocusOverview(jobId?: string) {
  const query = jobId ? `?job_id=${encodeURIComponent(jobId)}` : "";
  return apiGet<FocusOverviewResponse>(`/api/focus/overview${query}`);
}

export function addFocusAccount(payload: { account: string; mode: FocusMode; job_id?: string | null }) {
  return apiPost<FocusMutationResponse>("/api/focus/watch", payload);
}

export function removeFocusAccount(account: string) {
  return apiDeleteJson<FocusMutationResponse>(`/api/focus/watch/${encodeURIComponent(account)}`);
}

export function hideFocusLog(jobId: string) {
  return apiDeleteJson<FocusMutationResponse>(`/api/focus/logs/${encodeURIComponent(jobId)}`);
}
