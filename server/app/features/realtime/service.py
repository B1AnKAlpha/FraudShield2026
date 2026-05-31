from __future__ import annotations

import asyncio
import json
import os
import random
import threading
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from statistics import median
from time import perf_counter
from uuid import uuid4

from app.features.analysis.repository import repository as analysis_repository
from app.features.focus.repository import repository as focus_repository
from app.features.realtime.light_model import build_feature_payload, light_model
from app.features.realtime.schemas import RealtimeSummary, RealtimeTransactionItem

try:
    from kafka import KafkaConsumer, KafkaProducer
except Exception:  # pragma: no cover - runtime environment decides availability
    KafkaConsumer = None  # type: ignore[assignment]
    KafkaProducer = None  # type: ignore[assignment]


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


@dataclass
class RiskAssessment:
    risk_level: str
    confidence: float
    reason: str
    analysis_ms: int
    freeze_ms: int


class RealtimeService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rng = random.Random(20260416)
        self._max_transactions = 100
        self._max_alerts = 50
        self._transactions: deque[RealtimeTransactionItem] = deque(maxlen=self._max_transactions)
        self._alerts: deque[RealtimeTransactionItem] = deque(maxlen=self._max_alerts)
        self._account_states: dict[str, AccountState] = defaultdict(AccountState)
        self._recent_edges: deque[tuple[datetime, str, str, float]] = deque(maxlen=480)
        self._total_transactions = 0
        self._total_amount = 0.0
        self._net_flow = 0.0
        self._total_alerts = 0
        self._high_risk_alerts = 0
        self._alert_confidence_total = 0.0
        self._last_generated_at = datetime.now().timestamp() - 20
        self._focus_accounts = self._load_focus_accounts()
        self._historical_accounts = self._load_historical_accounts()
        self._historical_account_set = set(self._historical_accounts)
        self._account_name_cache: dict[str, str] = {}
        self._scenario_hub_account, self._scenario_counterparties = self._build_scenario_accounts()
        self._light_model = light_model
        self._simulated_kafka_pool: list[dict] = []
        self._simulated_kafka_index = 0
        self._simulated_kafka_round = 0
        self._channels = ["手机银行", "网银", "柜面", "ATM", "第三方支付"]
        self._channel_weights = [0.35, 0.25, 0.10, 0.08, 0.22]
        self._channel_codes = {
            "手机银行": "MOBILE",
            "网银": "ONLINE",
            "柜面": "COUNTER",
            "ATM": "ATM",
            "第三方支付": "THIRDPAY",
        }
        self._family_names = list("赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章苏潘葛范彭郎鲁韦昌马苗凤花方俞任袁柳邓")
        self._given_names = [
            "伟", "磊", "静", "玲", "军", "帆", "雪", "楠", "浩", "敏",
            "丹", "博", "颖", "凯", "洋", "婷", "超", "晨", "鑫", "悦",
        ]
        self._given_names_compound = [
            "建华", "桂芳", "志强", "秀英", "明辉", "丽娟", "国强", "淑珍",
            "文博", "雅琴", "天宇", "思涵", "浩然", "欣怡", "子轩", "梓萱",
        ]
        self._normal_memos = [
            "工资代发", "货款结算", "生活消费", "房租转账", "保险缴费",
            "水电燃气", "信用卡还款", "基金申购", "往来款", "借款归还",
            "采购货款", "服务费", "咨询费", "物业费", "学费缴纳",
            "差旅报销", "税款缴纳", "劳务报酬", "分红款", "投资收益",
        ]
        self._suspicious_memos = [
            "投资咨询费", "技术服务费", "居间服务费", "信息服务费",
            "往来款", "借款", "代付款", "保证金", "咨询顾问费",
            "商务合作款", "市场推广费", "平台充值",
        ]
        self._bank_codes = [
            "102100099996", "103100000026", "104100000004", "105100000017",
            "301290000007", "302100011000", "303100000006", "305100000013",
            "306581000003", "307584007998", "308584000013", "309391000011",
            "310290000013", "313100000013", "314100000060", "315100000013",
            "316100000011", "317100000014", "318100000014", "319100000014",
        ]
        self._account_balances: dict[str, float] = {}
        self._simulated_kafka_pool = self._build_simulated_kafka_pool(size=300)
        self._source = os.getenv("FS_REALTIME_SOURCE", "kafka").strip().lower()
        self._kafka_bootstrap = os.getenv("FS_KAFKA_BOOTSTRAP", "47.109.150.203:9092").strip()
        self._kafka_topic = os.getenv("FS_KAFKA_TOPIC", "financial_transactions").strip()
        self._kafka_group = os.getenv("FS_KAFKA_GROUP", f"fraudshield-2026-{uuid4().hex[:8]}").strip()
        self._kafka_simulator_enabled = self._truthy(os.getenv("FS_KAFKA_SIMULATOR", "1"))
        self._kafka_enabled = False
        self._kafka_status = "未启用"
        self._kafka_producer = None
        self._kafka_consumer = None

        self._init_kafka()

        if self._source == "kafka" and self._kafka_enabled and self._kafka_simulator_enabled:
            for _ in range(10):
                self._publish_simulated_kafka_message()
            self._drain_kafka_messages(max_records=40, timeout_ms=300)

        if not self._transactions:
            self._bootstrap_seed_transactions()

    def mode(self) -> str:
        suffix = "+light-model" if self._light_model.available() else ""
        if self._source == "kafka":
            if self._kafka_enabled:
                return f"kafka-live-simulated{suffix}"
            return f"kafka-unavailable-fallback{suffix}"
        if self._focus_accounts:
            return f"focus-seeded-stream{suffix}"
        if self._historical_accounts:
            return f"history-seeded-stream{suffix}"
        return f"synthetic-stream{suffix}"

    @staticmethod
    def _truthy(value: str | None) -> bool:
        if value is None:
            return False
        return value.strip().lower() in {"1", "true", "yes", "on"}

    def _init_kafka(self) -> None:
        if self._source != "kafka":
            self._kafka_status = "未启用"
            return
        if KafkaConsumer is None or KafkaProducer is None:
            self._kafka_status = "缺少 kafka-python 依赖"
            return
        try:
            self._kafka_producer = KafkaProducer(
                bootstrap_servers=self._kafka_bootstrap,
                value_serializer=lambda payload: json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                request_timeout_ms=8000,
            )
            self._kafka_consumer = KafkaConsumer(
                self._kafka_topic,
                bootstrap_servers=self._kafka_bootstrap,
                group_id=self._kafka_group,
                auto_offset_reset="latest",
                enable_auto_commit=True,
                value_deserializer=lambda payload: json.loads(payload.decode("utf-8")),
                request_timeout_ms=8000,
                consumer_timeout_ms=200,
            )
            self._kafka_enabled = True
            self._kafka_status = f"已连接 {self._kafka_bootstrap}/{self._kafka_topic}"
        except Exception as exc:
            self._kafka_enabled = False
            self._kafka_consumer = None
            self._kafka_producer = None
            self._kafka_status = f"连接失败: {exc}"

    def _load_focus_accounts(self) -> list[str]:
        return [
            str(item.get("account")).strip()
            for item in focus_repository.list_targets()
            if str(item.get("account")).strip()
        ]

    def _load_historical_accounts(self) -> list[str]:
        accounts: list[str] = []
        seen: set[str] = set()
        for job in analysis_repository.list_jobs(created_by=None):
            normalized = job.get("normalized_json") or {}
            for tx in normalized.get("standardized_transactions") or []:
                for key in ("zhdh", "dfzh"):
                    account = str(tx.get(key) or "").strip()
                    if account and account not in seen:
                        seen.add(account)
                        accounts.append(account)
            if len(accounts) >= 80:
                break
        return accounts

    def _pick_account(self, exclude: str = "") -> str:
        weighted_pool: list[str] = []
        if self._focus_accounts:
            weighted_pool.extend(self._focus_accounts * 5)
        if self._historical_accounts:
            weighted_pool.extend(self._historical_accounts * 3)
        if weighted_pool:
            for _ in range(8):
                candidate = self._rng.choice(weighted_pool)
                if candidate != exclude:
                    return candidate
        while True:
            candidate = "".join(str(self._rng.randint(0, 9)) for _ in range(16))
            if candidate != exclude:
                return candidate

    def _get_account_name(self, account: str) -> str:
        cached = self._account_name_cache.get(account)
        if cached:
            return cached
        if account in self._focus_accounts:
            name = f"重点账户{account[-4:]}"
        else:
            family = self._rng.choice(self._family_names)
            if self._rng.random() < 0.45:
                given = self._rng.choice(self._given_names_compound)
            else:
                given = self._rng.choice(self._given_names)
            name = family + given
        self._account_name_cache[account] = name
        return name

    def _get_account_balance(self, account: str, amount: float, is_outflow: bool) -> float:
        if account not in self._account_balances:
            self._account_balances[account] = round(self._rng.uniform(8000.0, 450000.0), 2)
        balance = self._account_balances[account]
        if is_outflow:
            balance = max(balance - amount, round(self._rng.uniform(200, 5000), 2))
        else:
            balance += amount
        self._account_balances[account] = round(balance, 2)
        return self._account_balances[account]

    def _pick_channel_weighted(self) -> str:
        return self._rng.choices(self._channels, weights=self._channel_weights, k=1)[0]

    def _counterparty_score(self, account: str, counterparty: str) -> float:
        state = self._account_states.get(account)
        if not state or not state.events:
            return round(self._rng.uniform(0, 20), 1)
        past_counterparties = {e.counterparty for e in state.events}
        if counterparty in past_counterparties:
            return round(self._rng.uniform(5, 35), 1)
        return round(self._rng.uniform(40, 90), 1)

    def _pick_amount(self) -> float:
        level = self._rng.random()
        if level >= 0.97:
            return round(self._rng.uniform(100000, 220000), 2)
        if level >= 0.9:
            return round(self._rng.uniform(50000, 98000), 2)
        if level >= 0.62:
            return round(self._rng.uniform(12000, 48000), 2)
        return round(self._rng.uniform(50, 9800), 2)

    def _build_scenario_accounts(self) -> tuple[str, list[str]]:
        preferred_pool = self._focus_accounts + self._historical_accounts
        hub = preferred_pool[0] if preferred_pool else self._pick_account()
        counterparties: list[str] = []
        seen = {hub}

        for account in self._focus_accounts + self._historical_accounts:
            normalized = str(account).strip()
            if normalized and normalized not in seen:
                counterparties.append(normalized)
                seen.add(normalized)
            if len(counterparties) >= 4:
                break

        while len(counterparties) < 4:
            candidate = self._pick_account(exclude=hub)
            if candidate not in seen:
                counterparties.append(candidate)
                seen.add(candidate)

        return hub, counterparties

    def _bootstrap_seed_transactions(self) -> None:
        if self._source == "kafka":
            for _ in range(18):
                self._append_transaction(self._legacy_to_transaction(self._next_simulated_kafka_message()))
            return
        for _ in range(10):
            self._append_transaction(self._generate_transaction(prefer_suspicious=True))
        for _ in range(8):
            self._append_transaction(self._generate_transaction(prefer_suspicious=False))

    def _build_simulated_kafka_pool(self, size: int = 300) -> list[dict]:
        pool: list[dict] = []
        for index in range(size):
            if index < size * 0.30:
                pool.append(self._generate_legacy_kafka_message(prefer_suspicious=True))
            elif index < size * 0.75:
                pool.append(self._generate_legacy_kafka_message(prefer_suspicious=False))
            else:
                pool.append(self._generate_legacy_kafka_message(prefer_suspicious=None))
        self._rng.shuffle(pool)
        return pool

    def _generate_legacy_kafka_message(self, prefer_suspicious: bool | None = None) -> dict:
        suspicious = prefer_suspicious if prefer_suspicious is not None else self._rng.random() < 0.32
        if suspicious:
            scenario = self._rng.random()
            if scenario < 0.40:
                payer_account = self._scenario_hub_account
                receiver_account = self._rng.choice(self._scenario_counterparties)
                amount = round(self._rng.uniform(25000, 150000), 2)
                direction = "0"
                channel = self._rng.choice(["手机银行", "网银", "第三方支付"])
                memo = self._rng.choice(self._suspicious_memos)
            elif scenario < 0.65:
                receiver_account = self._scenario_hub_account
                payer_account = self._rng.choice(self._scenario_counterparties)
                amount = round(self._rng.uniform(30000, 120000), 2)
                direction = "1"
                channel = self._rng.choice(["网银", "第三方支付"])
                memo = self._rng.choice(self._suspicious_memos)
            elif scenario < 0.85:
                cp_a = self._rng.choice(self._scenario_counterparties)
                others = [c for c in self._scenario_counterparties if c != cp_a]
                cp_b = self._rng.choice(others) if others else self._pick_account(exclude=cp_a)
                payer_account = cp_a
                receiver_account = cp_b
                amount = round(self._rng.uniform(15000, 80000), 2)
                direction = "0"
                channel = self._rng.choice(["手机银行", "第三方支付"])
                memo = self._rng.choice(self._suspicious_memos)
            else:
                payer_account = self._pick_account()
                receiver_account = self._pick_account(exclude=payer_account)
                amount = round(self._rng.uniform(48000, 198000), 2)
                direction = "0"
                channel = "第三方支付"
                memo = self._rng.choice(self._suspicious_memos)
        else:
            payer_account = self._pick_account()
            receiver_account = self._pick_account(exclude=payer_account)
            amount = self._pick_amount()
            direction = "1" if self._rng.random() >= 0.45 else "0"
            channel = self._pick_channel_weighted()
            memo = self._rng.choice(self._normal_memos)
        payer_name = self._get_account_name(payer_account)
        receiver_name = self._get_account_name(receiver_account)
        is_outflow = direction == "0"
        balance = self._get_account_balance(payer_account, amount, is_outflow)
        cp_score = self._counterparty_score(payer_account, receiver_account)
        now = datetime.now()
        return {
            "jylsxh": f"JY{now.strftime('%Y%m%d%H%M%S')}{self._rng.randint(100000, 999999)}",
            "zhdh": payer_account,
            "zhxm": payer_name,
            "dfzh": receiver_account,
            "dfxm": receiver_name,
            "jdbj": direction,
            "jyje": amount,
            "zhye": balance,
            "dfhh": self._rng.choice(self._bank_codes),
            "jyrq": now.strftime("%Y/%m/%d"),
            "jysj": now.strftime("%H:%M:%S"),
            "jyqd": self._channel_codes[channel],
            "zy": memo,
            "dfmccd": cp_score,
        }

    def _next_simulated_kafka_message(self) -> dict:
        if not self._simulated_kafka_pool:
            self._simulated_kafka_pool = self._build_simulated_kafka_pool(size=300)

        template = dict(self._simulated_kafka_pool[self._simulated_kafka_index])
        self._simulated_kafka_index += 1
        if self._simulated_kafka_index >= len(self._simulated_kafka_pool):
            self._simulated_kafka_index = 0
            self._simulated_kafka_round += 1

        now = datetime.now()
        template["jylsxh"] = (
            f"SIM{self._simulated_kafka_round:03d}"
            f"{self._simulated_kafka_index:03d}"
            f"{now.strftime('%Y%m%d%H%M%S')}"
            f"{self._rng.randint(1000, 9999)}"
        )
        template["jyrq"] = now.strftime("%Y/%m/%d")
        template["jysj"] = now.strftime("%H:%M:%S")
        return template

    def _normalize_event_time(self, date_text: str, time_text: str) -> str:
        raw = f"{date_text} {time_text}".strip()
        for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(raw, fmt).isoformat(timespec="seconds")
            except ValueError:
                continue
        return datetime.now().isoformat(timespec="seconds")

    def _parse_event_time(self, value: str) -> datetime:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return datetime.now()

    def _prune_account_state(self, state: AccountState, now: datetime) -> None:
        max_age_seconds = 24 * 60 * 60
        while state.events and (now - state.events[0].event_time).total_seconds() > max_age_seconds:
            state.events.popleft()

    def _window_metrics(self, account: str, now: datetime) -> dict[str, float]:
        state = self._account_states[account]
        self._prune_account_state(state, now)
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

    def _amount_spike_ratio(self, account: str, amount: float, now: datetime) -> float:
        state = self._account_states[account]
        self._prune_account_state(state, now)
        baseline = [event.amount for event in state.events if event.flow == "out"][-20:]
        if len(baseline) < 3:
            return 1.0
        return amount / max(median(baseline), 1.0)

    def _is_first_seen_counterparty(self, account: str, counterparty: str, now: datetime) -> bool:
        state = self._account_states[account]
        self._prune_account_state(state, now)
        return all(event.counterparty != counterparty for event in state.events)

    def _prune_recent_edges(self, now: datetime) -> None:
        max_age_seconds = 2 * 60 * 60
        while self._recent_edges and (now - self._recent_edges[0][0]).total_seconds() > max_age_seconds:
            self._recent_edges.popleft()

    def _graph_hops_to_focus(self, accounts: set[str], now: datetime, max_depth: int = 2) -> int | None:
        self._prune_recent_edges(now)
        if not self._focus_accounts:
            return None

        adjacency: dict[str, set[str]] = defaultdict(set)
        for _, payer, receiver, _ in self._recent_edges:
            adjacency[payer].add(receiver)
            adjacency[receiver].add(payer)

        queue = deque((account, 0) for account in accounts)
        visited = set(accounts)
        focus_set = set(self._focus_accounts)

        while queue:
            account, depth = queue.popleft()
            if account in focus_set:
                return depth
            if depth >= max_depth:
                continue
            for neighbor in adjacency.get(account, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, depth + 1))
        return None

    def _assess_transaction(
        self,
        *,
        payer_account: str,
        receiver_account: str,
        amount: float,
        direction: str,
        channel: str,
        event_time: datetime,
        balance: float,
        counterparty_score: float,
    ) -> RiskAssessment:
        started = perf_counter()
        reasons: list[str] = []
        score = 0.18 + self._rng.random() * 0.04

        payer_metrics = self._window_metrics(payer_account, event_time)
        receiver_metrics = self._window_metrics(receiver_account, event_time)
        amount_spike_ratio = self._amount_spike_ratio(payer_account, amount, event_time)
        first_seen_counterparty = self._is_first_seen_counterparty(payer_account, receiver_account, event_time)
        graph_hops = self._graph_hops_to_focus({payer_account, receiver_account}, event_time, max_depth=2)

        if payer_account in self._focus_accounts or receiver_account in self._focus_accounts:
            score += 0.58
            reasons.append("命中重点关注账号")
        elif graph_hops == 1:
            score += 0.18
            reasons.append("一跳关联重点关注账号")
        elif graph_hops == 2:
            score += 0.1
            reasons.append("两跳关联重点关注账号")

        if amount >= 100000:
            score += 0.24
            reasons.append("超大额交易")
        elif amount >= 50000:
            score += 0.18
            reasons.append("大额交易")
        elif amount >= 15000:
            score += 0.08
            reasons.append("中高金额交易")

        if payer_metrics["count_60s"] >= 6:
            score += 0.16
            reasons.append("付款账户1分钟内高频交易")
        elif payer_metrics["count_60s"] >= 4:
            score += 0.1
            reasons.append("付款账户短时频繁往来")

        if payer_metrics["out_amount_300s"] >= 150000:
            score += 0.16
            reasons.append("付款账户5分钟累计外流异常")
        elif payer_metrics["out_amount_300s"] >= 80000:
            score += 0.1
            reasons.append("付款账户5分钟外流偏高")

        if payer_metrics["counterparties_600s"] >= 5:
            score += 0.08
            reasons.append("付款账户10分钟内对手方分散")

        if receiver_metrics["in_count_300s"] >= 4 and amount >= 10000:
            score += 0.08
            reasons.append("收款账户短时多笔入账")

        if first_seen_counterparty and amount >= 20000:
            score += 0.12
            reasons.append("首次对手方即发生中高金额交易")

        if amount_spike_ratio >= 5 and payer_metrics["sample_size"] >= 4:
            score += 0.12
            reasons.append("金额相对近期基线突增")

        if event_time.hour <= 5 or event_time.hour >= 23:
            if amount >= 20000:
                score += 0.08
                reasons.append("夜间大额交易")
            elif payer_metrics["count_300s"] >= 3:
                score += 0.05
                reasons.append("夜间短时活跃异常")

        if channel == "第三方支付" and amount >= 30000:
            score += 0.05
            reasons.append("第三方支付渠道大额转移")

        if payer_account in self._historical_account_set or receiver_account in self._historical_account_set:
            score += 0.04
            reasons.append("关联历史分析账户")

        flow_total = payer_metrics["out_amount_300s"] + payer_metrics["in_amount_300s"]
        if flow_total >= 80000:
            imbalance = abs(payer_metrics["out_amount_300s"] - payer_metrics["in_amount_300s"]) / max(flow_total, 1.0)
            if imbalance >= 0.85:
                score += 0.08
                reasons.append("账户短时收支失衡")

        model_probability = self._light_model.predict_proba(
            build_feature_payload(
                amount=amount,
                balance=balance,
                counterparty_score=counterparty_score,
                direction=direction,
                channel=channel,
                event_time=event_time,
                payer_metrics=payer_metrics,
                receiver_metrics=receiver_metrics,
                amount_spike_ratio=amount_spike_ratio,
                first_seen_counterparty=first_seen_counterparty,
            )
        )
        if model_probability is not None:
            score = score * 0.68 + model_probability * 0.32
            if model_probability >= 0.82:
                reasons.insert(0, "轻量模型命中高风险模式")
            elif model_probability >= 0.62:
                reasons.append("轻量模型命中中风险模式")

        confidence = round(min(max(score, 0.08), 0.99), 4)
        if confidence >= 0.82:
            risk_level = "high"
        elif confidence >= 0.56:
            risk_level = "medium"
        else:
            risk_level = "low"

        analysis_ms = min(420, 55 + len(reasons) * 24 + int((perf_counter() - started) * 1000) + self._rng.randint(0, 24))
        if risk_level == "high":
            freeze_ms = self._rng.randint(28, 86)
        elif risk_level == "medium":
            freeze_ms = self._rng.randint(8, 28)
        else:
            freeze_ms = self._rng.randint(0, 12)

        return RiskAssessment(
            risk_level=risk_level,
            confidence=confidence,
            reason="；".join(reasons[:4]) if reasons else "交易正常",
            analysis_ms=analysis_ms,
            freeze_ms=freeze_ms,
        )

    def _build_transaction(
        self,
        *,
        transaction_id: str,
        payer_account: str,
        payer_name: str,
        receiver_account: str,
        receiver_name: str,
        amount: float,
        direction: str,
        channel: str,
        event_time: str,
        balance: float = 0.0,
        counterparty_score: float = 0.0,
    ) -> RealtimeTransactionItem:
        event_dt = self._parse_event_time(event_time)
        assessment = self._assess_transaction(
            payer_account=payer_account,
            receiver_account=receiver_account,
            amount=amount,
            direction=direction,
            channel=channel,
            event_time=event_dt,
            balance=balance,
            counterparty_score=counterparty_score,
        )
        return RealtimeTransactionItem(
            transaction_id=transaction_id,
            payer_account=payer_account,
            payer_name=payer_name,
            receiver_account=receiver_account,
            receiver_name=receiver_name,
            amount=amount,
            direction=direction,
            channel=channel,
            risk_level=assessment.risk_level,
            confidence=assessment.confidence,
            event_time=event_dt.isoformat(timespec="seconds"),
            analysis_ms=assessment.analysis_ms,
            freeze_ms=assessment.freeze_ms,
            flagged_reason=assessment.reason,
        )

    def _legacy_to_transaction(self, message: dict) -> RealtimeTransactionItem:
        payer_account = str(message.get("zhdh") or "").strip() or self._pick_account()
        receiver_account = str(message.get("dfzh") or "").strip() or self._pick_account(exclude=payer_account)
        payer_name = str(message.get("zhxm") or "").strip() or self._get_account_name(payer_account)
        receiver_name = str(message.get("dfxm") or "").strip() or self._get_account_name(receiver_account)
        amount = float(message.get("jyje") or 0.0)
        direction = "收入" if str(message.get("jdbj", "0")) == "1" else "支出"
        channel_code = str(message.get("jyqd") or "").strip()
        channel = next((name for name, code in self._channel_codes.items() if code == channel_code), "网银")
        event_time = self._normalize_event_time(str(message.get("jyrq") or ""), str(message.get("jysj") or ""))
        balance = float(message.get("zhye") or 0.0)
        counterparty_score = float(message.get("dfmccd") or 0.0)
        return self._build_transaction(
            transaction_id=str(message.get("jylsxh") or f"TXN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{self._rng.randint(1000, 9999)}"),
            payer_account=payer_account,
            payer_name=payer_name,
            receiver_account=receiver_account,
            receiver_name=receiver_name,
            amount=amount,
            direction=direction,
            channel=channel,
            event_time=event_time,
            balance=balance,
            counterparty_score=counterparty_score,
        )

    def _generate_transaction(self, prefer_suspicious: bool | None = None) -> RealtimeTransactionItem:
        suspicious = prefer_suspicious if prefer_suspicious is not None else self._rng.random() < 0.32
        if suspicious:
            scenario = self._rng.random()
            if scenario < 0.45:
                payer_account = self._scenario_hub_account
                receiver_account = self._rng.choice(self._scenario_counterparties)
                amount = round(self._rng.uniform(25000, 150000), 2)
                direction = "支出"
                channel = self._rng.choice(["手机银行", "网银", "第三方支付"])
            elif scenario < 0.70:
                receiver_account = self._scenario_hub_account
                payer_account = self._rng.choice(self._scenario_counterparties)
                amount = round(self._rng.uniform(30000, 120000), 2)
                direction = "收入"
                channel = self._rng.choice(["网银", "第三方支付"])
            else:
                payer_account = self._pick_account()
                receiver_account = self._pick_account(exclude=payer_account)
                amount = round(self._rng.uniform(48000, 198000), 2)
                direction = "支出"
                channel = "第三方支付"
        else:
            payer_account = self._pick_account()
            receiver_account = self._pick_account(exclude=payer_account)
            amount = self._pick_amount()
            direction = "收入" if self._rng.random() >= 0.45 else "支出"
            channel = self._pick_channel_weighted()
        is_outflow = direction == "支出"
        balance = self._get_account_balance(payer_account, amount, is_outflow)
        cp_score = self._counterparty_score(payer_account, receiver_account)
        return self._build_transaction(
            transaction_id=f"TXN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{self._rng.randint(1000, 9999)}",
            payer_account=payer_account,
            payer_name=self._get_account_name(payer_account),
            receiver_account=receiver_account,
            receiver_name=self._get_account_name(receiver_account),
            amount=amount,
            direction=direction,
            channel=channel,
            event_time=datetime.now().isoformat(timespec="seconds"),
            balance=balance,
            counterparty_score=cp_score,
        )

    def _register_transaction_state(self, item: RealtimeTransactionItem) -> None:
        event_dt = self._parse_event_time(item.event_time)
        payer_state = self._account_states[item.payer_account]
        receiver_state = self._account_states[item.receiver_account]

        payer_state.events.append(
            AccountEvent(
                event_time=event_dt,
                amount=item.amount,
                counterparty=item.receiver_account,
                channel=item.channel,
                flow="out",
            )
        )
        receiver_state.events.append(
            AccountEvent(
                event_time=event_dt,
                amount=item.amount,
                counterparty=item.payer_account,
                channel=item.channel,
                flow="in",
            )
        )

        self._prune_account_state(payer_state, event_dt)
        self._prune_account_state(receiver_state, event_dt)
        self._recent_edges.append((event_dt, item.payer_account, item.receiver_account, item.amount))
        self._prune_recent_edges(event_dt)

    def _append_transaction(self, item: RealtimeTransactionItem) -> None:
        self._transactions.appendleft(item)
        self._register_transaction_state(item)
        self._total_transactions += 1
        self._total_amount += item.amount
        if item.direction == "收入":
            self._net_flow += item.amount
        else:
            self._net_flow -= item.amount

        if item.risk_level in {"medium", "high"}:
            self._alerts.appendleft(item)
            self._total_alerts += 1
            self._alert_confidence_total += item.confidence
            if item.risk_level == "high":
                self._high_risk_alerts += 1

    def _publish_simulated_kafka_message(self) -> None:
        if not self._kafka_enabled or self._kafka_producer is None:
            return
        payload = self._next_simulated_kafka_message()
        future = self._kafka_producer.send(self._kafka_topic, payload)
        future.get(timeout=3)
        self._kafka_producer.flush(timeout=3)

    def _append_simulated_stream_transaction(self) -> None:
        self._append_transaction(self._legacy_to_transaction(self._next_simulated_kafka_message()))

    def _drain_kafka_messages(self, *, max_records: int, timeout_ms: int = 120) -> int:
        if not self._kafka_enabled or self._kafka_consumer is None:
            return 0
        consumed = 0
        polled = self._kafka_consumer.poll(timeout_ms=timeout_ms, max_records=max_records)
        for records in polled.values():
            for record in records:
                message = record.value or {}
                if isinstance(message, dict):
                    self._append_transaction(self._legacy_to_transaction(message))
                    consumed += 1
        return consumed

    def _ensure_activity(self) -> None:
        now = datetime.now().timestamp()
        delta_seconds = now - self._last_generated_at
        if delta_seconds < 0.5:
            return
        missing = max(1, min(12, int(delta_seconds // 0.5)))

        if self._source == "kafka" and self._kafka_enabled:
            if self._kafka_simulator_enabled:
                for _ in range(missing):
                    self._publish_simulated_kafka_message()
            consumed = self._drain_kafka_messages(max_records=max(20, missing * 8), timeout_ms=200)
            if consumed == 0 and not self._transactions:
                for _ in range(missing):
                    self._append_simulated_stream_transaction()
            self._last_generated_at = now
            return

        if self._source == "kafka":
            for _ in range(missing):
                self._append_simulated_stream_transaction()
        else:
            for _ in range(missing):
                self._append_transaction(self._generate_transaction())
        self._last_generated_at = now

    def _snapshot(self) -> RealtimeSummary:
        average_amount = self._total_amount / self._total_transactions if self._total_transactions else 0.0
        average_confidence = self._alert_confidence_total / self._total_alerts if self._total_alerts else 0.0
        return RealtimeSummary(
            mode=self.mode(),
            generated_at=datetime.now().isoformat(timespec="seconds"),
            total_alerts=self._total_alerts,
            high_risk_alerts=self._high_risk_alerts,
            average_confidence=round(average_confidence, 4),
            total_transactions=self._total_transactions,
            total_amount=round(self._total_amount, 2),
            average_amount=round(average_amount, 2),
            net_flow=round(self._net_flow, 2),
            latest_transactions=list(self._transactions),
            latest_alerts=list(self._alerts),
        )

    def summary(self) -> RealtimeSummary:
        with self._lock:
            self._ensure_activity()
            return self._snapshot()

    async def stream(self):
        while True:
            with self._lock:
                self._ensure_activity()
                payload = self._snapshot().model_dump()
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.8)


service = RealtimeService()
