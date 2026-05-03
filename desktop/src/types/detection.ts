export interface DetectionRequest {
  transaction: {
    transaction_id: string;
    payer_account: string;
    receiver_account: string;
    amount: number;
    location?: string;
    channel?: string;
    description?: string;
  };
  evidence_files: string[];
}

export interface DetectionResponse {
  risk_level: string;
  confidence: number;
  model_source: string;
  narrative: string;
  suggested_actions: string[];
  link_path: Array<{
    account: string;
    risk_level: string;
    action: string;
  }>;
}

export interface BatchDetectionRequest {
  file_paths: string[];
}

export interface BatchDetectionResponse {
  accepted: number;
  job_id: string;
  message: string;
}
