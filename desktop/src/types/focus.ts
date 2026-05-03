export type FocusMode = "normal" | "deep";

export interface FocusCloudAccountItem {
  account: string;
  mode: FocusMode;
  source_account: string | null;
  is_seed: boolean;
  created_by: string;
  updated_at: string;
}

export interface FocusLocalAccountItem {
  account: string;
}

export interface FocusLogItem {
  job_id: string;
  created_at: string;
  operator: string;
  status: string;
  account_count: number;
}

export interface FocusOverviewResponse {
  selected_job_id: string | null;
  logs: FocusLogItem[];
  local_accounts: FocusLocalAccountItem[];
  cloud_accounts: FocusCloudAccountItem[];
}

export interface FocusMutationResponse {
  message: string;
  affected_accounts: string[];
  selected_job_id: string | null;
}
