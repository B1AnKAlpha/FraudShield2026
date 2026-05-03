from app.features.detection.legacy_adapter import LegacyDetectionAdapter
from app.features.detection.schemas import (
    DetectionRequest,
    DetectionResponse,
    RiskNode,
    UploadBatchRequest,
)


class DetectionService:
    def __init__(self) -> None:
        self.adapter = LegacyDetectionAdapter()

    def detect_single(self, payload: DetectionRequest) -> DetectionResponse:
        risk_level, confidence = self.adapter.predict(payload.transaction.amount)
        return DetectionResponse(
            risk_level=risk_level,
            confidence=confidence,
            model_source="legacy-adapter" if self.adapter.available() else "mock-engine",
            narrative="系统检测到账户链路存在多跳转移和可疑地区特征，建议进入人工复核。",
            suggested_actions=[
                "冻结高风险账户",
                "拉取近 24 小时关联交易",
                "生成案件报告并提交复核",
            ],
            link_path=[
                RiskNode(account=payload.transaction.payer_account, risk_level="medium", action="观察"),
                RiskNode(account=payload.transaction.receiver_account, risk_level=risk_level, action="复核"),
            ],
        )

    def detect_batch(self, payload: UploadBatchRequest):
        return {
            "accepted": len(payload.file_paths),
            "job_id": "batch-demo-001",
            "message": "批量检测任务已入队，下一阶段接 Celery/Redis。",
        }
