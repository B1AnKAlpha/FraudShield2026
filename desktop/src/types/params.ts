export interface VersionPair {
  current: string;
  latest: string;
}

export interface ParamsVersions {
  software: VersionPair;
  model: VersionPair;
  parameter: VersionPair;
}

export interface FraudModelParams {
  decisionThreshold: string;
  metaWeight: string;
  gruWeight: string;
  xgbWeight: string;
}

export interface AdvancedModelParams {
  highRiskScoreThreshold: string;
  mediumRiskScoreThreshold: string;
  highConfidenceThreshold: string;
  mediumConfidenceThreshold: string;
}

export interface DynamicModelParams {
  highRiskThreshold: string;
  mediumRiskThreshold: string;
  selfAttentionEnabled: boolean;
  adaptiveThresholdEnabled: boolean;
}

export interface ParamsOverviewResponse {
  versions: ParamsVersions;
  fraud_model: FraudModelParams;
  advanced_model: AdvancedModelParams;
  dynamic_model: DynamicModelParams;
}

export interface SaveMessageResponse {
  message: string;
  overview: ParamsOverviewResponse;
}

export interface UpdateCheckResponse {
  updated: boolean;
  message: string;
  overview: ParamsOverviewResponse;
}
