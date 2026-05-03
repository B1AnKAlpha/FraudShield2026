import { apiGet, apiGetBlob, apiPostForm } from "@/api/client";
import type {
  AnalysisJobCreateResponse,
  AnalysisJobDetailResponse,
  AnalysisReportResponse,
} from "@/types/analysis";

export function createAnalysisJob(payload: FormData) {
  return apiPostForm<AnalysisJobCreateResponse>("/api/analysis/jobs", payload);
}

export function fetchAnalysisJob(jobId: string) {
  return apiGet<AnalysisJobDetailResponse>(`/api/analysis/jobs/${jobId}`);
}

export function fetchAnalysisReport(jobId: string) {
  return apiGet<AnalysisReportResponse>(`/api/analysis/jobs/${jobId}/report`);
}

export function fetchAnalysisReportPdf(jobId: string) {
  return apiGetBlob(`/api/analysis/jobs/${jobId}/report.pdf`);
}
