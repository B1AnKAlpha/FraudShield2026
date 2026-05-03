from __future__ import annotations

from app.core.errors import AppError

from .repository import repository
from .schemas import (
    AdvancedModelParams,
    AdvancedModelParamsUpdateRequest,
    DynamicModelParams,
    DynamicModelParamsUpdateRequest,
    FraudModelParams,
    FraudModelParamsUpdateRequest,
    ParamsOverviewResponse,
    ParamsVersions,
    SaveMessageResponse,
    UpdateCheckResponse,
    VersionPair,
)


class ParamsService:
    def _to_bool(self, value: object) -> bool:
        return str(value).strip() in {"1", "true", "True", "yes", "on"}

    def _parse_probability(self, value: str, label: str) -> str:
        try:
            parsed = float(value)
        except ValueError as exc:
            raise AppError(f"{label}必须为数字", status_code=400, code="INVALID_INFERENCE_PARAM") from exc
        if parsed < 0 or parsed > 1:
            raise AppError(f"{label}必须在 0 到 1 之间", status_code=400, code="INVALID_INFERENCE_PARAM")
        return value.strip()

    def _parse_weight(self, value: str, label: str) -> str:
        try:
            parsed = float(value)
        except ValueError as exc:
            raise AppError(f"{label}必须为数字", status_code=400, code="INVALID_INFERENCE_PARAM") from exc
        if parsed < 0:
            raise AppError(f"{label}不能小于 0", status_code=400, code="INVALID_INFERENCE_PARAM")
        return value.strip()

    def _to_overview(self, state: dict) -> ParamsOverviewResponse:
        return ParamsOverviewResponse(
            versions=ParamsVersions(
                software=VersionPair(current=state["software_current_version"], latest=state["software_latest_version"]),
                model=VersionPair(current=state["model_current_version"], latest=state["model_latest_version"]),
                parameter=VersionPair(current=state["parameter_current_version"], latest=state["parameter_latest_version"]),
            ),
            fraud_model=FraudModelParams(
                decisionThreshold=state["fraud_decision_threshold"],
                metaWeight=state["fraud_meta_weight"],
                gruWeight=state["fraud_gru_weight"],
                xgbWeight=state["fraud_xgb_weight"],
            ),
            advanced_model=AdvancedModelParams(
                highRiskScoreThreshold=state["advanced_high_risk_score_threshold"],
                mediumRiskScoreThreshold=state["advanced_medium_risk_score_threshold"],
                highConfidenceThreshold=state["advanced_high_confidence_threshold"],
                mediumConfidenceThreshold=state["advanced_medium_confidence_threshold"],
            ),
            dynamic_model=DynamicModelParams(
                highRiskThreshold=state["dynamic_high_risk_threshold"],
                mediumRiskThreshold=state["dynamic_medium_risk_threshold"],
                selfAttentionEnabled=self._to_bool(state["dynamic_self_attention_enabled"]),
                adaptiveThresholdEnabled=self._to_bool(state["dynamic_adaptive_threshold_enabled"]),
            ),
        )

    def overview(self) -> ParamsOverviewResponse:
        return self._to_overview(repository.get_state())

    def save_fraud_model(self, payload: FraudModelParamsUpdateRequest) -> SaveMessageResponse:
        decision_threshold = self._parse_probability(payload.decisionThreshold, "最终判定阈值")
        meta_weight = self._parse_weight(payload.metaWeight, "元模型权重")
        gru_weight = self._parse_weight(payload.gruWeight, "GRU 输出权重")
        xgb_weight = self._parse_weight(payload.xgbWeight, "XGBoost 输出权重")
        if float(meta_weight) + float(gru_weight) + float(xgb_weight) <= 0:
            raise AppError("三个模型权重之和必须大于 0", status_code=400, code="INVALID_INFERENCE_PARAM")
        state = repository.update_state(
            {
                "fraud_decision_threshold": decision_threshold,
                "fraud_meta_weight": meta_weight,
                "fraud_gru_weight": gru_weight,
                "fraud_xgb_weight": xgb_weight,
            }
        )
        return SaveMessageResponse(message="混合模型推理决策参数已保存并接入运行时推理", overview=self._to_overview(state))

    def save_advanced_model(self, payload: AdvancedModelParamsUpdateRequest) -> SaveMessageResponse:
        high_risk = self._parse_probability(payload.highRiskScoreThreshold, "高风险分级阈值")
        medium_risk = self._parse_probability(payload.mediumRiskScoreThreshold, "中风险分级阈值")
        high_confidence = self._parse_probability(payload.highConfidenceThreshold, "高置信度阈值")
        medium_confidence = self._parse_probability(payload.mediumConfidenceThreshold, "中置信度阈值")
        if float(high_risk) <= float(medium_risk):
            raise AppError("高风险分级阈值必须大于中风险分级阈值", status_code=400, code="INVALID_INFERENCE_PARAM")
        if float(high_confidence) <= float(medium_confidence):
            raise AppError("高置信度阈值必须大于中置信度阈值", status_code=400, code="INVALID_INFERENCE_PARAM")
        state = repository.update_state(
            {
                "advanced_high_risk_score_threshold": high_risk,
                "advanced_medium_risk_score_threshold": medium_risk,
                "advanced_high_confidence_threshold": high_confidence,
                "advanced_medium_confidence_threshold": medium_confidence,
            }
        )
        return SaveMessageResponse(message="风险分级与置信度阈值已保存并接入运行时推理", overview=self._to_overview(state))

    def save_dynamic_model(self, payload: DynamicModelParamsUpdateRequest) -> SaveMessageResponse:
        try:
            high = float(payload.highRiskThreshold)
            medium = float(payload.mediumRiskThreshold)
        except ValueError as exc:
            raise AppError("风险阈值必须为数字", status_code=400, code="INVALID_THRESHOLD") from exc

        if high <= 0 or medium <= 0:
            raise AppError("风险阈值必须大于 0", status_code=400, code="INVALID_THRESHOLD")
        if high <= medium:
            raise AppError("高风险阈值必须大于中风险阈值", status_code=400, code="INVALID_THRESHOLD")

        state = repository.update_state(
            {
                "dynamic_high_risk_threshold": payload.highRiskThreshold.strip(),
                "dynamic_medium_risk_threshold": payload.mediumRiskThreshold.strip(),
                "dynamic_self_attention_enabled": "1" if payload.selfAttentionEnabled else "0",
                "dynamic_adaptive_threshold_enabled": "1" if payload.adaptiveThresholdEnabled else "0",
            }
        )
        return SaveMessageResponse(message="动态识别模型推理参数已保存并接入运行时判定", overview=self._to_overview(state))

    def update_software_version(self) -> UpdateCheckResponse:
        state = repository.get_state()
        if state["software_current_version"] == state["software_latest_version"]:
            return UpdateCheckResponse(updated=False, message="当前软件已是最新版本", overview=self._to_overview(state))
        next_state = repository.update_state({"software_current_version": state["software_latest_version"]})
        return UpdateCheckResponse(updated=True, message="软件已更新至最新版本", overview=self._to_overview(next_state))

    def update_model_version(self) -> UpdateCheckResponse:
        state = repository.get_state()
        if state["model_current_version"] == state["model_latest_version"]:
            return UpdateCheckResponse(updated=False, message="当前模型架构已是最新版本", overview=self._to_overview(state))
        next_state = repository.update_state({"model_current_version": state["model_latest_version"]})
        return UpdateCheckResponse(updated=True, message="模型架构已更新至最新版本", overview=self._to_overview(next_state))

    def update_parameter_version(self) -> UpdateCheckResponse:
        state = repository.get_state()
        if state["parameter_current_version"] == state["parameter_latest_version"]:
            return UpdateCheckResponse(updated=False, message="当前模型参数已是最新版本", overview=self._to_overview(state))
        next_state = repository.update_state({"parameter_current_version": state["parameter_latest_version"]})
        return UpdateCheckResponse(updated=True, message="模型参数已更新至最新版本", overview=self._to_overview(next_state))

    def get_dynamic_thresholds(self) -> dict:
        state = repository.get_state()
        return {
            "high_risk_threshold": float(state["dynamic_high_risk_threshold"]),
            "medium_risk_threshold": float(state["dynamic_medium_risk_threshold"]),
            "self_attention_enabled": self._to_bool(state["dynamic_self_attention_enabled"]),
            "adaptive_threshold_enabled": self._to_bool(state["dynamic_adaptive_threshold_enabled"]),
        }

    def get_hybrid_inference_params(self) -> dict:
        state = repository.get_state()
        return {
            "decision_threshold": float(state["fraud_decision_threshold"]),
            "meta_weight": float(state["fraud_meta_weight"]),
            "gru_weight": float(state["fraud_gru_weight"]),
            "xgb_weight": float(state["fraud_xgb_weight"]),
            "high_risk_score_threshold": float(state["advanced_high_risk_score_threshold"]),
            "medium_risk_score_threshold": float(state["advanced_medium_risk_score_threshold"]),
            "high_confidence_threshold": float(state["advanced_high_confidence_threshold"]),
            "medium_confidence_threshold": float(state["advanced_medium_confidence_threshold"]),
        }


service = ParamsService()
