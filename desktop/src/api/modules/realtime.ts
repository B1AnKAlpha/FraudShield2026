import { apiGet, createEventStream } from "@/api/client";
import type { RealtimeSummary } from "@/types/realtime";

export function fetchRealtimeSummary() {
  return apiGet<RealtimeSummary>("/api/realtime/summary");
}

export function openRealtimeStream() {
  return createEventStream("/api/realtime/stream");
}
