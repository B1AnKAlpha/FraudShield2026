import { apiGet, apiPost, apiPut } from "@/api/client";
import type {
  AdvancedModelParams,
  DynamicModelParams,
  FraudModelParams,
  ParamsOverviewResponse,
  SaveMessageResponse,
  UpdateCheckResponse,
} from "@/types/params";

export function fetchParamsOverview() {
  return apiGet<ParamsOverviewResponse>("/api/params/overview");
}

export function saveFraudModelParams(payload: FraudModelParams) {
  return apiPut<SaveMessageResponse>("/api/params/fraud-model", payload);
}

export function saveAdvancedModelParams(payload: AdvancedModelParams) {
  return apiPut<SaveMessageResponse>("/api/params/advanced-model", payload);
}

export function saveDynamicModelParams(payload: DynamicModelParams) {
  return apiPut<SaveMessageResponse>("/api/params/dynamic-model", payload);
}

export function triggerSoftwareUpdate() {
  return apiPost<UpdateCheckResponse>("/api/params/actions/software-update", {});
}

export function triggerModelUpdate() {
  return apiPost<UpdateCheckResponse>("/api/params/actions/model-update", {});
}

export function triggerParameterUpdate() {
  return apiPost<UpdateCheckResponse>("/api/params/actions/parameter-update", {});
}
