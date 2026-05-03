from pydantic import BaseModel, ConfigDict, Field


class DetectionBaseModel(BaseModel):
    model_config = ConfigDict(protected_namespaces=())


class TransactionPayload(DetectionBaseModel):
    transaction_id: str
    payer_account: str
    receiver_account: str
    amount: float
    location: str | None = None
    channel: str | None = None
    description: str | None = None


class DetectionRequest(DetectionBaseModel):
    transaction: TransactionPayload
    evidence_files: list[str] = Field(default_factory=list)


class RiskNode(DetectionBaseModel):
    account: str
    risk_level: str
    action: str


class DetectionResponse(DetectionBaseModel):
    risk_level: str
    confidence: float
    model_source: str
    narrative: str
    suggested_actions: list[str]
    link_path: list[RiskNode]


class UploadBatchRequest(DetectionBaseModel):
    file_paths: list[str]
