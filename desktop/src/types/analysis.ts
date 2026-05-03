export interface AnalysisAsset {
  asset_id: string;
  asset_type: string;
  original_name: string;
  mime_type: string;
  size_bytes: number;
}

export interface AnalysisParserSummary {
  mineru_documents: number;
  spreadsheet_assets: number;
  plain_text_assets: number;
  warnings: string[];
}

export interface AnalysisRiskNode {
  account: string;
  risk_level: string;
  action: string;
}

export interface AnalysisResult {
  risk_level: string;
  confidence: number;
  model_source: string;
  narrative: string;
  suggested_actions: string[];
  link_path: AnalysisRiskNode[];
  normalized_summary: string;
  risk_signals: string[];
  transaction_candidates: Array<Record<string, unknown>>;
}

export interface AnalysisJobCreateResponse {
  job_id: string;
  status: string;
}

export interface AnalysisJobDetailResponse {
  job_id: string;
  status: string;
  created_by: string;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  assets: AnalysisAsset[];
  parser_summary: AnalysisParserSummary | null;
  result: AnalysisResult | null;
  report_ready: boolean;
}

export interface AnalysisReportResponse {
  job_id: string;
  title: string;
  html: string;
}
