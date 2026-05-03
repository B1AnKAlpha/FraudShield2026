import { apiGet } from "@/api/client";
import type { SystemOverview } from "@/types/system";

export function fetchSystemOverview() {
  return apiGet<SystemOverview>("/api/system/overview");
}
