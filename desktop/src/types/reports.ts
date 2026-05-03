export interface ReportItem {
  report_id: string;
  title: string;
  created_at: string;
  operator: string;
  status: string;
  format: string;
  download_url: string | null;
}

export interface ReportListResponse {
  items: ReportItem[];
}
