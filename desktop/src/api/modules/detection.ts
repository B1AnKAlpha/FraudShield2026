import { apiPost } from "@/api/client";
import type {
  BatchDetectionRequest,
  BatchDetectionResponse,
  DetectionRequest,
  DetectionResponse,
} from "@/types/detection";

export function submitDetection(payload: DetectionRequest) {
  return apiPost<DetectionResponse>("/api/detection/single", payload);
}

export function submitDetectionBatch(payload: BatchDetectionRequest) {
  return apiPost<BatchDetectionResponse>("/api/detection/batch", payload);
}
