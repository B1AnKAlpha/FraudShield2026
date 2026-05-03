import { apiGet, apiGetBlob } from "@/api/client";
import type { ReportItem, ReportListResponse } from "@/types/reports";

export function fetchReports() {
  return apiGet<ReportListResponse>("/api/reports");
}

export function fetchReportDetail(reportId: string) {
  return apiGet<ReportItem>(`/api/reports/${reportId}`);
}

export function fetchReportPdf(downloadUrl: string) {
  return apiGetBlob(downloadUrl);
}
