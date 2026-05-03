export interface RealtimeTransactionItem {
  transaction_id: string;
  payer_account: string;
  payer_name: string;
  receiver_account: string;
  receiver_name: string;
  amount: number;
  direction: string;
  channel: string;
  risk_level: string;
  confidence: number;
  event_time: string;
  analysis_ms: number;
  freeze_ms: number;
  flagged_reason: string;
}

export interface RealtimeSummary {
  mode: string;
  generated_at: string;
  total_alerts: number;
  high_risk_alerts: number;
  average_confidence: number;
  total_transactions: number;
  total_amount: number;
  average_amount: number;
  net_flow: number;
  latest_transactions: RealtimeTransactionItem[];
  latest_alerts: RealtimeTransactionItem[];
}
