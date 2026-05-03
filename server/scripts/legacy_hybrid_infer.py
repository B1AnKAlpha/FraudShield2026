from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

from keras.models import load_model
import joblib
import numpy as np
import pandas as pd


USER_ID_COL = "zhdh"
RECORD_CAT_COLS = ["jyqd", "zydh", "dfhh", "dfzh"]
EPS = 1e-5
DEFAULT_INFERENCE_PARAMS = {
    "decision_threshold": 0.5,
    "meta_weight": 1.0,
    "gru_weight": 0.0,
    "xgb_weight": 0.0,
    "high_risk_score_threshold": 0.5,
    "medium_risk_score_threshold": 0.3,
    "high_confidence_threshold": 0.85,
    "medium_confidence_threshold": 0.7,
}


def _stringify(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and np.isnan(value):
        return ""
    return str(value).strip()


def _safe_float(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        if isinstance(value, str):
            text = value.strip().replace(",", "")
            if not text:
                return default
            return float(text)
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(round(_safe_float(value, float(default))))
    except (TypeError, ValueError):
        return default


def _clamp_probability(value: object, default: float) -> float:
    return min(max(_safe_float(value, default), 0.0), 1.0)


def _normalize_direction(value: object) -> int:
    text = _stringify(value).lower()
    if text in {"1", "true", "yes", "y", "in", "credit", "贷", "入", "收入", "是"}:
        return 1
    if text in {"0", "false", "no", "n", "out", "debit", "借", "出", "支出", "否"}:
        return 0
    return _safe_int(value, 0)


def _normalize_gender(value: object) -> int:
    text = _stringify(value).lower()
    if text in {"1", "m", "male", "男"}:
        return 1
    if text in {"0", "f", "female", "女"}:
        return 0
    return _safe_int(value, 0)


def _normalize_date(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    text = _stringify(value)
    if not text:
        return ""
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return text
    return parsed.strftime("%Y-%m-%d")


def _normalize_time(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, pd.Timestamp):
        return value.strftime("%H:%M:%S")
    text = _stringify(value)
    if not text:
        return ""
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return text
    return parsed.strftime("%H:%M:%S")


def load_hybrid_model(model_dir: Path) -> dict:
    with (model_dir / "model_config.json").open("r", encoding="utf-8") as handle:
        model_config = json.load(handle)

    return {
        "gru_model": load_model(model_dir / "gru_model.h5", compile=False),
        "xgb_model": joblib.load(model_dir / "xgb_model.pkl"),
        "meta_model": joblib.load(model_dir / "meta_model.pkl"),
        "feature_selector": joblib.load(model_dir / "feature_selector.pkl"),
        "scaler": joblib.load(model_dir / "scaler.pkl"),
        "imputer": joblib.load(model_dir / "imputer.pkl"),
        "config": model_config,
    }


def _resolve_inference_params(payload: dict) -> dict:
    runtime = payload.get("inference_params") if isinstance(payload, dict) else {}
    resolved = dict(DEFAULT_INFERENCE_PARAMS)
    if isinstance(runtime, dict):
        for key, default in DEFAULT_INFERENCE_PARAMS.items():
            if key in runtime:
                resolved[key] = _safe_float(runtime.get(key), default)

    for key in (
        "decision_threshold",
        "high_risk_score_threshold",
        "medium_risk_score_threshold",
        "high_confidence_threshold",
        "medium_confidence_threshold",
    ):
        resolved[key] = _clamp_probability(resolved[key], DEFAULT_INFERENCE_PARAMS[key])

    for key in ("meta_weight", "gru_weight", "xgb_weight"):
        resolved[key] = max(_safe_float(resolved[key], DEFAULT_INFERENCE_PARAMS[key]), 0.0)

    if resolved["meta_weight"] + resolved["gru_weight"] + resolved["xgb_weight"] <= 0:
        raise ValueError("推理参数无效：模型权重之和必须大于 0")
    if resolved["high_risk_score_threshold"] <= resolved["medium_risk_score_threshold"]:
        raise ValueError("推理参数无效：高风险分级阈值必须大于中风险分级阈值")
    if resolved["high_confidence_threshold"] <= resolved["medium_confidence_threshold"]:
        raise ValueError("推理参数无效：高置信度阈值必须大于中置信度阈值")
    return resolved


def _blend_probability(meta_probability: float, gru_probability: float, xgb_probability: float, params: dict) -> float:
    total_weight = params["meta_weight"] + params["gru_weight"] + params["xgb_weight"]
    return (
        meta_probability * params["meta_weight"]
        + gru_probability * params["gru_weight"]
        + xgb_probability * params["xgb_weight"]
    ) / total_weight


def predict_with_hybrid_model(
    models: dict,
    new_data: pd.DataFrame,
    inference_params: dict,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    required_features = list(models["config"]["feature_names"])
    working = new_data.copy()
    for feature in required_features:
        if feature not in working.columns:
            working[feature] = 0.0
    working = working[required_features].apply(pd.to_numeric, errors="coerce")
    working = working.replace([np.inf, -np.inf], np.nan)

    imputed = pd.DataFrame(models["imputer"].transform(working), columns=required_features)
    scaled = models["scaler"].transform(imputed)
    selected = models["feature_selector"].transform(scaled)

    gru_input = selected.reshape(selected.shape[0], selected.shape[1], 1)
    gru_proba = models["gru_model"].predict(gru_input, verbose=0).ravel()
    xgb_proba = models["xgb_model"].predict_proba(selected)[:, 1]
    meta_features = np.column_stack([gru_proba, xgb_proba])
    meta_proba = models["meta_model"].predict_proba(meta_features)[:, 1]
    final_proba = np.array(
        [
            _blend_probability(float(meta_proba[index]), float(gru_proba[index]), float(xgb_proba[index]), inference_params)
            for index in range(len(meta_proba))
        ]
    )
    final_predictions = (final_proba > inference_params["decision_threshold"]).astype(int)
    return final_predictions, final_proba, gru_proba, xgb_proba, meta_proba


def _load_payload(input_path: Path) -> dict:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("输入文件格式无效")
    return payload


def _load_transactions(payload: dict) -> pd.DataFrame:
    transactions = payload.get("transactions") or []
    if not isinstance(transactions, list) or not transactions:
        raise ValueError("transactions 为空，无法执行旧版混合模型推理")
    df = pd.DataFrame(transactions)
    if df.empty:
        raise ValueError("transactions 为空表")
    return df


def _load_static_user_info(static_path: Path) -> pd.DataFrame:
    if not static_path.exists():
        return pd.DataFrame(columns=["zhdh", "xb", "年龄"])
    df = pd.read_excel(static_path)
    rename_map = {}
    for column in df.columns:
        column_text = _stringify(column)
        if column_text == "账户代号":
            rename_map[column] = "zhdh"
        elif column_text in {"性别", "xb"}:
            rename_map[column] = "xb"
        elif column_text in {"年龄", "age"}:
            rename_map[column] = "年龄"
    df = df.rename(columns=rename_map)
    for column in ["zhdh", "xb", "年龄"]:
        if column not in df.columns:
            df[column] = None
    df = df[["zhdh", "xb", "年龄"]].copy()
    df["zhdh"] = df["zhdh"].map(_stringify)
    df["xb"] = df["xb"].map(_normalize_gender)
    df["年龄"] = df["年龄"].map(lambda value: _safe_int(value, 0))
    return df.drop_duplicates(subset=["zhdh"], keep="first")


def _prepare_record_df(df: pd.DataFrame) -> pd.DataFrame:
    working = df.copy()
    rename_map = {
        "账户代号": "zhdh",
        "对方账户": "dfzh",
        "借贷标记": "jdbj",
        "交易金额": "jyje",
        "账户余额": "zhye",
        "对方行号": "dfhh",
        "交易日期": "jyrq",
        "交易时间": "jysj",
        "交易渠道": "jyqd",
        "交易流水序号": "jylsxh",
        "性别": "xb",
        "age": "年龄",
    }
    working = working.rename(columns={key: value for key, value in rename_map.items() if key in working.columns})

    for column in ["zhdh", "dfzh", "dfhh", "jyqd", "jylsxh"]:
        if column not in working.columns:
            working[column] = ""
        working[column] = working[column].map(_stringify)

    if "jdbj" not in working.columns:
        working["jdbj"] = 0
    working["jdbj"] = working["jdbj"].map(_normalize_direction)

    for column in ["jyje", "zhye", "dfmccd"]:
        if column not in working.columns:
            working[column] = 0
        working[column] = working[column].map(lambda value: _safe_float(value, 0.0))

    if "jyrq" not in working.columns:
        working["jyrq"] = ""
    if "jysj" not in working.columns:
        working["jysj"] = ""
    working["jyrq"] = working["jyrq"].map(_normalize_date)
    working["jysj"] = working["jysj"].map(_normalize_time)
    working["jyts"] = pd.to_datetime(
        working["jyrq"].astype(str) + " " + working["jysj"].astype(str),
        errors="coerce",
    )

    if "xb" in working.columns:
        working["xb"] = working["xb"].map(_normalize_gender)
    if "年龄" in working.columns:
        working["年龄"] = working["年龄"].map(lambda value: _safe_int(value, 0))

    working = working[working["zhdh"].astype(str).str.len() > 0].copy()
    if working.empty:
        raise ValueError("未识别到账户代号字段，无法生成交易特征")
    return working


def _build_static_from_transactions(record_df: pd.DataFrame) -> pd.DataFrame:
    static_rows = []
    if "xb" not in record_df.columns and "年龄" not in record_df.columns:
        return pd.DataFrame(columns=["zhdh", "xb", "年龄"])

    for account, group in record_df.groupby("zhdh"):
        gender = 0
        age = 0
        if "xb" in group.columns:
            series = group["xb"].dropna()
            if not series.empty:
                gender = _normalize_gender(series.iloc[0])
        if "年龄" in group.columns:
            series = group["年龄"].dropna()
            if not series.empty:
                age = _safe_int(series.iloc[0], 0)
        static_rows.append({"zhdh": _stringify(account), "xb": gender, "年龄": age})
    return pd.DataFrame(static_rows)


def _cat2cnt(series: pd.Series) -> pd.Series:
    series = series.astype(str)
    mapping = series.groupby(series).agg("count").to_dict()
    return series.map(mapping)


def generate_user_features(static_df: pd.DataFrame, record_df: pd.DataFrame) -> pd.DataFrame:
    user_info_df = static_df[["zhdh", "xb", "年龄"]].copy()
    user_info_df["zhdh"] = user_info_df["zhdh"].map(_stringify)
    user_info_df["xb"] = user_info_df["xb"].map(_normalize_gender)
    user_info_df["年龄"] = user_info_df["年龄"].map(lambda value: _safe_int(value, 0))
    user_info_df = user_info_df.drop_duplicates(subset=["zhdh"], keep="first")

    all_user_ids = user_info_df["zhdh"].unique()
    user_record_df = record_df[record_df["zhdh"].isin(all_user_ids)].copy()
    if user_record_df.empty:
        raise ValueError("静态信息与交易信息没有可匹配的账户")

    for col in [c for c in RECORD_CAT_COLS if c != "zydh"]:
        if col in user_record_df.columns:
            user_record_df[f"{col}_cnt"] = _cat2cnt(user_record_df[col])
        else:
            user_record_df[f"{col}_cnt"] = 0

    def agg_user_record_features(group: pd.DataFrame) -> pd.DataFrame:
        one = group.copy()
        for col in ["dfzh", "dfhh", "jyqd"]:
            if col not in one.columns:
                one[col] = ""
            one[col] = one[col].astype(str)

        feature_dict: dict[str, object] = {
            USER_ID_COL: _stringify(one[USER_ID_COL].iloc[0]),
            "NumRecord": len(one),
        }
        num_ops = ["min", "max", "std", "mean", "median"]

        for col in ["dfzh", "dfhh"]:
            feature_dict[f"{col}_Nunique"] = one[col].nunique()
            feature_dict[f"{col}_NuniqueDivLen"] = one[col].nunique() / max(len(one), 1)

        one["jdbj"] = one["jdbj"].fillna(0).astype(int)
        feature_dict["jdbj_InCnt"] = int(one["jdbj"].sum())
        feature_dict["jdbj_OutCnt"] = int(len(one) - one["jdbj"].sum())
        feature_dict["jdbj_InRatio"] = float(one["jdbj"].sum() / max(len(one), 1))

        for col in ["jyje", "zhye", "jyqd_cnt", "dfhh_cnt", "dfzh_cnt"]:
            if col not in one.columns:
                one[col] = 0.0
            one[col] = pd.to_numeric(one[col], errors="coerce").fillna(0.0)
            for op in num_ops:
                feature_dict[f"{col}_{op.capitalize()}"] = float(getattr(one[col], op)())
            feature_dict[f"{col}_Range"] = feature_dict[f"{col}_Max"] - feature_dict[f"{col}_Min"]

        for op in num_ops:
            in_series = one.loc[one["jdbj"] == 1, "jyje"]
            out_series = one.loc[one["jdbj"] == 0, "jyje"]
            in_val = float(getattr(in_series, op)()) if not in_series.empty else 0.0
            out_val = float(getattr(out_series, op)()) if not out_series.empty else 0.0
            feature_dict[f"InMoney_{op.capitalize()}"] = in_val
            feature_dict[f"OutMoney_{op.capitalize()}"] = out_val
            feature_dict[f"InMoney_{op.capitalize()}Ratio"] = in_val / (in_val + out_val + EPS)

        feature_dict["jdbj_InUserCnt"] = int(one.loc[one["jdbj"] == 1, "dfzh"].nunique())
        feature_dict["jdbj_OutUserCnt"] = int(one.loc[one["jdbj"] == 0, "dfzh"].nunique())
        feature_dict["jdbj_InUserRatio"] = feature_dict["jdbj_InUserCnt"] / (
            feature_dict["jdbj_InUserCnt"] + feature_dict["jdbj_OutUserCnt"] + EPS
        )

        if one["jyts"].isna().all():
            one["jyts"] = pd.Timestamp("1970-01-01")
        else:
            one["jyts"] = one["jyts"].ffill().bfill().fillna(pd.Timestamp("1970-01-01"))

        feature_dict["whole_life_jy_Interval(h)"] = (
            (one["jyts"].max() - one["jyts"].min()).total_seconds() / 3600 if len(one) > 1 else 0.0
        )
        feature_dict["jy_Freq(h)"] = feature_dict["whole_life_jy_Interval(h)"] / max(len(one), 1)

        for op in num_ops:
            feature_dict[f"jyje_{op.capitalize()}DivFreq"] = feature_dict[f"jyje_{op.capitalize()}"] / (
                feature_dict["jy_Freq(h)"] + EPS
            )
            daily_counts = one.groupby("jyrq")["jyts"].agg("count")
            feature_dict[f"oneday_jytimes_{op.capitalize()}"] = float(getattr(daily_counts, op)()) if not daily_counts.empty else 0.0
            timestamps = pd.to_numeric(one["jyts"], errors="coerce") / 1e9
            feature_dict[f"jytimestampval_{op.capitalize()}"] = float(getattr(timestamps, op)())

        intervals = one["jyts"].diff(1).dt.total_seconds().fillna(0.0)
        for op in num_ops:
            feature_dict[f"jy_interval_{op.capitalize()}"] = float(getattr(intervals, op)())
            feature_dict[f"jy_day_{op.capitalize()}"] = float(getattr(one["jyts"].dt.day, op)())
            feature_dict[f"jy_weekday_{op.capitalize()}"] = float(getattr(one["jyts"].dt.dayofweek, op)())
            feature_dict[f"jy_hour_{op.capitalize()}"] = float(getattr(one["jyts"].dt.hour, op)())
            feature_dict[f"jy_monthstart_{op.capitalize()}"] = float(getattr(one["jyts"].dt.is_month_start.astype(int), op)())
            feature_dict[f"jy_monthend_{op.capitalize()}"] = float(getattr(one["jyts"].dt.is_month_end.astype(int), op)())
            feature_dict[f"jy_wkend_{op.capitalize()}"] = float(getattr((one["jyts"].dt.dayofweek // 6), op)())

        feature_dict["jy_day_nunique"] = int(one["jyts"].dt.day.nunique())
        feature_dict["jy_weekday_nunique"] = int(one["jyts"].dt.dayofweek.nunique())
        feature_dict["jy_hour_nunique"] = int(one["jyts"].dt.hour.nunique())

        for col in ["dfzh", "dfhh"]:
            counts = one.groupby(col)[col].agg("count")
            for op in num_ops:
                feature_dict[f"{col}_GroupCount_{op.capitalize()}"] = float(getattr(counts, op)()) if not counts.empty else 0.0

        feature_dict["jyqd_nunique"] = int(one["jyqd"].nunique())
        if "dfmccd" not in one.columns:
            one["dfmccd"] = 0.0
        one["dfmccd"] = pd.to_numeric(one["dfmccd"], errors="coerce").fillna(0.0)
        for op in num_ops:
            feature_dict[f"dfmccd_{op.capitalize()}"] = float(getattr(one["dfmccd"], op)())

        return pd.DataFrame([feature_dict])

    aggregated = [agg_user_record_features(group) for _, group in user_record_df.groupby(USER_ID_COL)]
    user_agg_record_df = pd.concat(aggregated, ignore_index=True)
    all_user_record_and_static_info_df = user_agg_record_df.merge(user_info_df, on="zhdh", how="left")
    all_user_record_and_static_info_df["age"] = all_user_record_and_static_info_df["年龄"].map(lambda value: _safe_int(value, 0))
    all_user_record_and_static_info_df = all_user_record_and_static_info_df.replace([np.inf, -np.inf], np.nan).fillna(0)
    return all_user_record_and_static_info_df


def _confidence_label(probability: float, inference_params: dict) -> str:
    if probability >= inference_params["high_confidence_threshold"]:
        return "高置信度"
    if probability >= inference_params["medium_confidence_threshold"]:
        return "中置信度"
    return "低置信度"


def _risk_level_from_probability(probability: float, inference_params: dict, prediction: int | None = None) -> str:
    if prediction == 1 or probability >= inference_params["high_risk_score_threshold"]:
        return "high"
    if probability >= inference_params["medium_risk_score_threshold"]:
        return "medium"
    return "low"


def run_inference(input_path: Path, static_path: Path, model_dir: Path) -> dict:
    payload = _load_payload(input_path)
    inference_params = _resolve_inference_params(payload)
    record_df = _prepare_record_df(_load_transactions(payload))
    static_df = _load_static_user_info(static_path)
    derived_static_df = _build_static_from_transactions(record_df)
    static_df = pd.concat([static_df, derived_static_df], ignore_index=True)
    static_df = static_df.drop_duplicates(subset=["zhdh"], keep="first")

    features_df = generate_user_features(static_df, record_df)
    models = load_hybrid_model(model_dir)
    predictions, probabilities, gru_probabilities, xgb_probabilities, meta_probabilities = predict_with_hybrid_model(
        models,
        features_df,
        inference_params,
    )

    account_rows = []
    for index, row in features_df.iterrows():
        probability = float(probabilities[index])
        prediction = int(predictions[index])
        account_rows.append(
            {
                "account": _stringify(row.get("zhdh")),
                "prediction": prediction,
                "probability": round(probability, 6),
                "gru_probability": round(float(gru_probabilities[index]), 6),
                "xgb_probability": round(float(xgb_probabilities[index]), 6),
                "meta_probability": round(float(meta_probabilities[index]), 6),
                "confidence_label": _confidence_label(probability, inference_params),
                "risk_level": _risk_level_from_probability(probability, inference_params, prediction),
            }
        )

    account_rows.sort(key=lambda item: item["probability"], reverse=True)
    top_probability = float(account_rows[0]["probability"]) if account_rows else 0.0
    overall_risk = _risk_level_from_probability(
        top_probability,
        inference_params,
        1 if any(item["prediction"] == 1 for item in account_rows) else 0,
    )

    return {
        "model_source": "legacy-hybrid-gru-xgb-meta-runtime",
        "inference_params": inference_params,
        "overall": {
            "risk_level": overall_risk,
            "confidence": round(top_probability, 6),
            "account_count": len(account_rows),
        },
        "accounts": account_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--static-data", required=True)
    parser.add_argument("--model-dir", required=True)
    args = parser.parse_args()

    payload = run_inference(
        input_path=Path(args.input),
        static_path=Path(args.static_data),
        model_dir=Path(args.model_dir),
    )
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



