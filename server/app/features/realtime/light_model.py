from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

import joblib

from app.core.config import settings


FEATURE_NAMES = (
    "amount",
    "amount_log",
    "balance",
    "counterparty_score",
    "hour",
    "is_income",
    "is_night",
    "is_thirdpay",
    "payer_count_60s",
    "payer_count_300s",
    "payer_count_600s",
    "payer_out_count_300s",
    "payer_in_count_300s",
    "payer_out_amount_300s",
    "payer_in_amount_300s",
    "payer_total_amount_1800s",
    "payer_counterparties_600s",
    "payer_channels_600s",
    "payer_sample_size",
    "receiver_count_300s",
    "receiver_in_count_300s",
    "receiver_sample_size",
    "receiver_counterparties_600s",
    "amount_spike_ratio",
    "first_seen_counterparty",
    "flow_imbalance_300s",
)


def build_feature_payload(
    *,
    amount: float,
    balance: float,
    counterparty_score: float,
    direction: str,
    channel: str,
    event_time: datetime,
    payer_metrics: dict[str, float],
    receiver_metrics: dict[str, float],
    amount_spike_ratio: float,
    first_seen_counterparty: bool,
) -> dict[str, float]:
    flow_total = payer_metrics.get("out_amount_300s", 0.0) + payer_metrics.get("in_amount_300s", 0.0)
    flow_imbalance = abs(payer_metrics.get("out_amount_300s", 0.0) - payer_metrics.get("in_amount_300s", 0.0)) / max(
        flow_total,
        1.0,
    )
    normalized_channel = str(channel).strip().upper()
    return {
        "amount": float(amount),
        "amount_log": math.log1p(max(float(amount), 0.0)),
        "balance": float(balance),
        "counterparty_score": float(counterparty_score),
        "hour": float(event_time.hour),
        "is_income": 1.0 if str(direction).strip() == "收入" else 0.0,
        "is_night": 1.0 if event_time.hour <= 5 or event_time.hour >= 23 else 0.0,
        "is_thirdpay": 1.0 if normalized_channel in {"THIRDPAY", "第三方支付"} else 0.0,
        "payer_count_60s": float(payer_metrics.get("count_60s", 0.0)),
        "payer_count_300s": float(payer_metrics.get("count_300s", 0.0)),
        "payer_count_600s": float(payer_metrics.get("count_600s", 0.0)),
        "payer_out_count_300s": float(payer_metrics.get("out_count_300s", 0.0)),
        "payer_in_count_300s": float(payer_metrics.get("in_count_300s", 0.0)),
        "payer_out_amount_300s": float(payer_metrics.get("out_amount_300s", 0.0)),
        "payer_in_amount_300s": float(payer_metrics.get("in_amount_300s", 0.0)),
        "payer_total_amount_1800s": float(payer_metrics.get("total_amount_1800s", 0.0)),
        "payer_counterparties_600s": float(payer_metrics.get("counterparties_600s", 0.0)),
        "payer_channels_600s": float(payer_metrics.get("channels_600s", 0.0)),
        "payer_sample_size": float(payer_metrics.get("sample_size", 0.0)),
        "receiver_count_300s": float(receiver_metrics.get("count_300s", 0.0)),
        "receiver_in_count_300s": float(receiver_metrics.get("in_count_300s", 0.0)),
        "receiver_sample_size": float(receiver_metrics.get("sample_size", 0.0)),
        "receiver_counterparties_600s": float(receiver_metrics.get("counterparties_600s", 0.0)),
        "amount_spike_ratio": float(amount_spike_ratio),
        "first_seen_counterparty": 1.0 if first_seen_counterparty else 0.0,
        "flow_imbalance_300s": float(flow_imbalance),
    }


class RealtimeLightModel:
    def __init__(self) -> None:
        self.model_path = Path(settings.realtime_light_model_path)
        self._artifact: dict | None = None
        self._load_error = ""
        self._load()

    def _load(self) -> None:
        if not self.model_path.exists():
            self._artifact = None
            self._load_error = "模型文件不存在"
            return
        try:
            artifact = joblib.load(self.model_path)
            if not isinstance(artifact, dict) or "model" not in artifact:
                raise RuntimeError("模型文件格式不正确")
            model = artifact["model"]
            if hasattr(model, "set_params"):
                try:
                    model.set_params(device="cpu", eval_metric="logloss")
                except Exception:
                    pass
            self._artifact = artifact
            self._load_error = ""
        except Exception as exc:  # pragma: no cover - 依赖部署时决定
            self._artifact = None
            self._load_error = str(exc)

    def available(self) -> bool:
        return self._artifact is not None

    def load_error(self) -> str:
        return self._load_error

    def metadata(self) -> dict:
        if not self._artifact:
            return {}
        meta = self._artifact.get("metadata")
        return meta if isinstance(meta, dict) else {}

    def predict_proba(self, payload: dict[str, float]) -> float | None:
        if not self._artifact:
            return None
        model = self._artifact["model"]
        vector = [[float(payload.get(name, 0.0)) for name in FEATURE_NAMES]]
        if hasattr(model, "predict_proba"):
            return float(model.predict_proba(vector)[0][1])
        prediction = float(model.predict(vector)[0])
        return min(max(prediction, 0.0), 1.0)


light_model = RealtimeLightModel()
