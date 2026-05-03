from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from statistics import median

import joblib
import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from xgboost import XGBClassifier


SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.features.realtime.light_model import FEATURE_NAMES, build_feature_payload  # noqa: E402


@dataclass
class AccountEvent:
    event_time: datetime
    amount: float
    counterparty: str
    channel: str
    flow: str


@dataclass
class AccountState:
    events: deque[AccountEvent] = field(default_factory=lambda: deque(maxlen=240))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="训练实时监测轻量模型")
    parser.add_argument("--transactions", required=True, help="账户交易信息.csv 路径")
    parser.add_argument("--labels", required=True, help="训练集标签.csv 路径")
    parser.add_argument("--output", required=True, help="输出 joblib 文件路径")
    parser.add_argument("--max-rows", type=int, default=0, help="最多读取多少条交易，0 表示全量")
    return parser.parse_args()


def parse_event_time(date_text: str, time_text: str) -> datetime:
    raw = f"{str(date_text).strip()} {str(time_text).strip()}".strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return datetime(1970, 1, 1, 0, 0, 0)


def prune_account_state(state: AccountState, now: datetime) -> None:
    max_age_seconds = 24 * 60 * 60
    while state.events and (now - state.events[0].event_time).total_seconds() > max_age_seconds:
        state.events.popleft()


def window_metrics(account_states: dict[str, AccountState], account: str, now: datetime) -> dict[str, float]:
    state = account_states[account]
    prune_account_state(state, now)
    events = list(state.events)

    def subset(seconds: int, flow: str | None = None) -> list[AccountEvent]:
        filtered = [event for event in events if (now - event.event_time).total_seconds() <= seconds]
        if flow is not None:
            filtered = [event for event in filtered if event.flow == flow]
        return filtered

    events_60s = subset(60)
    events_300s = subset(300)
    events_600s = subset(600)
    out_300s = subset(300, "out")
    in_300s = subset(300, "in")
    total_1800s = subset(1800)

    return {
        "count_60s": float(len(events_60s)),
        "count_300s": float(len(events_300s)),
        "count_600s": float(len(events_600s)),
        "out_count_300s": float(len(out_300s)),
        "in_count_300s": float(len(in_300s)),
        "out_amount_300s": float(sum(event.amount for event in out_300s)),
        "in_amount_300s": float(sum(event.amount for event in in_300s)),
        "total_amount_1800s": float(sum(event.amount for event in total_1800s)),
        "counterparties_600s": float(len({event.counterparty for event in events_600s})),
        "channels_600s": float(len({event.channel for event in events_600s})),
        "sample_size": float(len(events)),
    }


def amount_spike_ratio(account_states: dict[str, AccountState], account: str, amount: float, now: datetime) -> float:
    state = account_states[account]
    prune_account_state(state, now)
    baseline = [event.amount for event in state.events if event.flow == "out"][-20:]
    if len(baseline) < 3:
        return 1.0
    return amount / max(median(baseline), 1.0)


def is_first_seen_counterparty(
    account_states: dict[str, AccountState],
    account: str,
    counterparty: str,
    now: datetime,
) -> bool:
    state = account_states[account]
    prune_account_state(state, now)
    return all(event.counterparty != counterparty for event in state.events)


def register_transaction_state(
    account_states: dict[str, AccountState],
    *,
    payer_account: str,
    receiver_account: str,
    amount: float,
    channel: str,
    event_dt: datetime,
) -> None:
    payer_state = account_states[payer_account]
    receiver_state = account_states[receiver_account]
    payer_state.events.append(
        AccountEvent(
            event_time=event_dt,
            amount=amount,
            counterparty=receiver_account,
            channel=channel,
            flow="out",
        )
    )
    receiver_state.events.append(
        AccountEvent(
            event_time=event_dt,
            amount=amount,
            counterparty=payer_account,
            channel=channel,
            flow="in",
        )
    )
    prune_account_state(payer_state, event_dt)
    prune_account_state(receiver_state, event_dt)


def load_labels(path: Path) -> dict[str, int]:
    label_map: dict[str, int] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            account = str(row.get("zhdh") or "").strip()
            if not account:
                continue
            label_map[account] = 1 if str(row.get("black_flag") or "0").strip() == "1" else 0
    return label_map


def build_dataset(transactions_path: Path, label_map: dict[str, int], max_rows: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    account_states: dict[str, AccountState] = defaultdict(AccountState)
    feature_rows: list[list[float]] = []
    labels: list[int] = []
    groups: list[str] = []
    started = datetime.now()

    with transactions_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader, start=1):
            payer_account = str(row.get("zhdh") or "").strip()
            receiver_account = str(row.get("dfzh") or "").strip()
            if not payer_account or not receiver_account:
                continue
            event_dt = parse_event_time(str(row.get("jyrq") or ""), str(row.get("jysj") or ""))
            amount = float(row.get("jyje") or 0.0)
            direction = "收入" if str(row.get("jdbj") or "0").strip() == "1" else "支出"
            channel = str(row.get("jyqd") or "").strip()
            balance = float(row.get("zhye") or 0.0)
            counterparty_score = float(row.get("dfmccd") or 0.0)

            payer_metrics = window_metrics(account_states, payer_account, event_dt)
            receiver_metrics = window_metrics(account_states, receiver_account, event_dt)
            payload = build_feature_payload(
                amount=amount,
                balance=balance,
                counterparty_score=counterparty_score,
                direction=direction,
                channel=channel,
                event_time=event_dt,
                payer_metrics=payer_metrics,
                receiver_metrics=receiver_metrics,
                amount_spike_ratio=amount_spike_ratio(account_states, payer_account, amount, event_dt),
                first_seen_counterparty=is_first_seen_counterparty(account_states, payer_account, receiver_account, event_dt),
            )
            feature_rows.append([float(payload.get(name, 0.0)) for name in FEATURE_NAMES])
            labels.append(label_map.get(payer_account, 0))
            groups.append(payer_account)

            register_transaction_state(
                account_states,
                payer_account=payer_account,
                receiver_account=receiver_account,
                amount=amount,
                channel=channel,
                event_dt=event_dt,
            )
            if index % 50000 == 0:
                elapsed = (datetime.now() - started).total_seconds()
                print(
                    json.dumps(
                        {
                            "stage": "build_dataset",
                            "rows": index,
                            "samples": len(feature_rows),
                            "seconds": round(elapsed, 1),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
            if max_rows > 0 and index >= max_rows:
                break

    return (
        np.asarray(feature_rows, dtype=np.float32),
        np.asarray(labels, dtype=np.int8),
        np.asarray(groups, dtype=object),
    )


def compute_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> dict[str, float]:
    y_pred = (y_prob >= 0.5).astype(np.int8)
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-8)
    return {
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
        "average_precision": float(average_precision_score(y_true, y_prob)),
        "precision_at_0_5": float(precision),
        "recall_at_0_5": float(recall),
        "f1_at_0_5": float(f1),
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
    }


def detect_device() -> str:
    try:
        completed = subprocess.run(
            ["nvidia-smi", "-L"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=5,
            check=False,
        )
        if completed.returncode == 0 and completed.stdout.strip():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def train_model(features: np.ndarray, labels: np.ndarray, groups: np.ndarray) -> tuple[XGBClassifier, dict]:
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=20260417)
    train_idx, valid_idx = next(splitter.split(features, labels, groups))

    x_train = features[train_idx]
    y_train = labels[train_idx]
    x_valid = features[valid_idx]
    y_valid = labels[valid_idx]

    positive = int(y_train.sum())
    negative = int(len(y_train) - positive)
    pos_weight = negative / max(positive, 1)
    device = detect_device()
    print(
        json.dumps(
            {
                "stage": "train_start",
                "device": device,
                "train_rows": int(len(train_idx)),
                "valid_rows": int(len(valid_idx)),
                "positive_ratio_train": float(y_train.mean()),
                "positive_ratio_valid": float(y_valid.mean()),
                "scale_pos_weight": float(pos_weight),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    model = XGBClassifier(
        n_estimators=320,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_weight=4,
        reg_alpha=0.05,
        reg_lambda=0.2,
        tree_method="hist",
        device=device,
        objective="binary:logistic",
        eval_metric=["auc", "aucpr", "logloss"],
        scale_pos_weight=float(pos_weight),
        random_state=20260417,
        verbosity=1,
    )
    try:
        model.fit(
            x_train,
            y_train,
            eval_set=[(x_train, y_train), (x_valid, y_valid)],
            verbose=20,
        )
    except Exception as exc:
        if device != "cuda":
            raise
        print(json.dumps({"stage": "train_retry_cpu", "reason": str(exc)}, ensure_ascii=False), flush=True)
        model = XGBClassifier(
            n_estimators=320,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.85,
            colsample_bytree=0.85,
            min_child_weight=4,
            reg_alpha=0.05,
            reg_lambda=0.2,
            tree_method="hist",
            device="cpu",
            objective="binary:logistic",
            eval_metric=["auc", "aucpr", "logloss"],
            scale_pos_weight=float(pos_weight),
            random_state=20260417,
            verbosity=1,
        )
        model.fit(
            x_train,
            y_train,
            eval_set=[(x_train, y_train), (x_valid, y_valid)],
            verbose=20,
        )
        device = "cpu"

    valid_prob = model.predict_proba(x_valid)[:, 1]
    metrics = compute_metrics(y_valid, valid_prob)
    metrics["train_rows"] = int(len(train_idx))
    metrics["valid_rows"] = int(len(valid_idx))
    metrics["positive_ratio_train"] = float(y_train.mean())
    metrics["positive_ratio_valid"] = float(y_valid.mean())
    metrics["device"] = device
    return model, metrics


def main() -> int:
    args = parse_args()
    transactions_path = Path(args.transactions)
    labels_path = Path(args.labels)
    output_path = Path(args.output)

    label_map = load_labels(labels_path)
    features, labels, groups = build_dataset(transactions_path, label_map, max_rows=args.max_rows)
    if len(features) == 0:
        raise RuntimeError("没有构建出可训练样本")

    model, metrics = train_model(features, labels, groups)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
        "model": model,
        "feature_names": list(FEATURE_NAMES),
        "metadata": {
            "model_type": "XGBClassifier",
            "trained_at": datetime.now().isoformat(timespec="seconds"),
            "sample_count": int(len(features)),
            "positive_ratio": float(labels.mean()),
            "metrics": metrics,
        },
    }
    joblib.dump(artifact, output_path)
    print(
        json.dumps(
            {
                "output": str(output_path),
                "sample_count": int(len(features)),
                "positive_ratio": float(labels.mean()),
                "metrics": metrics,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
