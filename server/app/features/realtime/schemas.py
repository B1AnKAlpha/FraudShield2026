from pydantic import BaseModel, Field


class RealtimeTransactionItem(BaseModel):
    transaction_id: str
    payer_account: str
    payer_name: str
    receiver_account: str
    receiver_name: str
    amount: float
    direction: str
    channel: str
    risk_level: str
    confidence: float
    event_time: str
    analysis_ms: int
    freeze_ms: int
    flagged_reason: str = ""


class RealtimeSummary(BaseModel):
    mode: str
    generated_at: str
    total_alerts: int
    high_risk_alerts: int
    average_confidence: float
    total_transactions: int
    total_amount: float
    average_amount: float
    net_flow: float
    latest_transactions: list[RealtimeTransactionItem] = Field(default_factory=list)
    latest_alerts: list[RealtimeTransactionItem] = Field(default_factory=list)
