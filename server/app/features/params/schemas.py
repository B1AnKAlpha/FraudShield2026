from __future__ import annotations

from pydantic import BaseModel, Field


class VersionPair(BaseModel):
    current: str
    latest: str


class ParamsVersions(BaseModel):
    software: VersionPair
    model: VersionPair
    parameter: VersionPair


class FraudModelParams(BaseModel):
    decisionThreshold: str
    metaWeight: str
    gruWeight: str
    xgbWeight: str


class AdvancedModelParams(BaseModel):
    highRiskScoreThreshold: str
    mediumRiskScoreThreshold: str
    highConfidenceThreshold: str
    mediumConfidenceThreshold: str


class DynamicModelParams(BaseModel):
    highRiskThreshold: str
    mediumRiskThreshold: str
    selfAttentionEnabled: bool
    adaptiveThresholdEnabled: bool


class ParamsOverviewResponse(BaseModel):
    versions: ParamsVersions
    fraud_model: FraudModelParams
    advanced_model: AdvancedModelParams
    dynamic_model: DynamicModelParams


class SaveMessageResponse(BaseModel):
    message: str
    overview: ParamsOverviewResponse


class UpdateCheckResponse(BaseModel):
    updated: bool
    message: str
    overview: ParamsOverviewResponse


class FraudModelParamsUpdateRequest(BaseModel):
    decisionThreshold: str = Field(min_length=1, max_length=64)
    metaWeight: str = Field(min_length=1, max_length=64)
    gruWeight: str = Field(min_length=1, max_length=64)
    xgbWeight: str = Field(min_length=1, max_length=64)


class AdvancedModelParamsUpdateRequest(BaseModel):
    highRiskScoreThreshold: str = Field(min_length=1, max_length=64)
    mediumRiskScoreThreshold: str = Field(min_length=1, max_length=64)
    highConfidenceThreshold: str = Field(min_length=1, max_length=64)
    mediumConfidenceThreshold: str = Field(min_length=1, max_length=64)


class DynamicModelParamsUpdateRequest(BaseModel):
    highRiskThreshold: str = Field(min_length=1, max_length=64)
    mediumRiskThreshold: str = Field(min_length=1, max_length=64)
    selfAttentionEnabled: bool
    adaptiveThresholdEnabled: bool
