<template>
  <section class="page-grid monitor-layout">
    <section class="panel">
      <header class="panel-title">实时数据流</header>
      <div class="table-scroll monitor-stream-scroll">
        <table class="legacy-table tall-table">
          <thead>
            <tr>
              <th>交易时间</th>
              <th>付款方姓名</th>
              <th>收款方姓名</th>
              <th>交易金额</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in visibleTransactions"
              :key="item.transaction_id"
              :class="['table-row', item.risk_level]"
              @click="openTransactionDetail(item)"
            >
              <td>{{ formatTime(item.event_time) }}</td>
              <td>{{ item.payer_name }}</td>
              <td>{{ item.receiver_name }}</td>
              <td>{{ item.amount.toFixed(2) }}</td>
            </tr>
            <tr v-if="visibleTransactions.length === 0" class="table-empty-row">
              <td colspan="4">暂无实时数据流</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="detail-grid slim">
        <div class="detail-row">
          <span>流状态</span>
          <strong>{{ streamStatus }}</strong>
        </div>
        <div class="detail-row">
          <span>数据模式</span>
          <strong>{{ summary?.mode ?? "--" }}</strong>
        </div>
      </div>

      <div class="panel-actions">
        <button class="legacy-button" type="button" @click="streamPaused = true">停止</button>
        <button class="legacy-button" type="button" @click="streamPaused = false">继续</button>
      </div>
    </section>

    <section class="panel">
      <header class="panel-title">实时分析</header>
      <div class="stats-quad">
        <div class="detail-row"><span>总交易笔数：</span><strong>{{ summary?.total_transactions ?? "--" }}</strong></div>
        <div class="detail-row"><span>总交易金额：</span><strong>{{ formatAmount(summary?.total_amount) }}</strong></div>
        <div class="detail-row"><span>平均交易金额：</span><strong>{{ formatAmount(summary?.average_amount) }}</strong></div>
        <div class="detail-row"><span>资金流向：</span><strong>{{ formatAmount(summary?.net_flow) }}</strong></div>
      </div>
      <div class="chart-grid realtime-chart-grid">
        <div class="chart-card">
          <div class="chart-title">实时交易金额</div>
          <svg class="chart-svg" viewBox="0 0 320 160" preserveAspectRatio="none">
            <polyline :points="amountTrendPoints" class="chart-polyline chart-polyline-blue" />
          </svg>
        </div>
        <div class="chart-card">
          <div class="chart-title">交易金额直方图</div>
          <svg class="chart-svg" viewBox="0 0 320 160" preserveAspectRatio="none">
            <rect
              v-for="bar in histogramBars"
              :key="bar.index"
              :x="bar.x"
              :y="bar.y"
              :width="bar.width"
              :height="bar.height"
              class="chart-bar"
            />
          </svg>
        </div>
        <div class="chart-card">
          <div class="chart-title">累计交易额</div>
          <svg class="chart-svg" viewBox="0 0 320 160" preserveAspectRatio="none">
            <polyline :points="cumulativePoints" class="chart-polyline chart-polyline-purple" />
          </svg>
        </div>
        <div class="chart-card">
          <div class="chart-title">累计资金流向</div>
          <svg class="chart-svg" viewBox="0 0 320 160" preserveAspectRatio="none">
            <polyline :points="netFlowPoints" class="chart-polyline chart-polyline-orange" />
          </svg>
        </div>
      </div>
      <div class="panel-actions center">
        <button class="legacy-button wide" type="button" @click="exportCharts">将图表保存至本地</button>
      </div>
    </section>
  </section>

  <div v-if="selectedTransaction" class="account-modal-backdrop" @click.self="closeTransactionDetail">
    <section class="account-modal monitor-detail-modal">
      <header class="account-modal-header">
        <div class="account-modal-title">交易详情</div>
        <button class="account-modal-close" type="button" @click="closeTransactionDetail">关闭</button>
      </header>
      <div class="monitor-detail-grid">
        <div class="detail-row"><span>交易编号</span><strong>{{ selectedTransaction.transaction_id }}</strong></div>
        <div class="detail-row"><span>交易时间</span><strong>{{ selectedTransaction.event_time.replace("T", " ") }}</strong></div>
        <div class="detail-row"><span>付款方</span><strong>{{ selectedTransaction.payer_name }} / {{ selectedTransaction.payer_account }}</strong></div>
        <div class="detail-row"><span>收款方</span><strong>{{ selectedTransaction.receiver_name }} / {{ selectedTransaction.receiver_account }}</strong></div>
        <div class="detail-row"><span>交易金额</span><strong>{{ selectedTransaction.amount.toFixed(2) }}</strong></div>
        <div class="detail-row"><span>交易方向</span><strong>{{ selectedTransaction.direction }}</strong></div>
        <div class="detail-row"><span>交易渠道</span><strong>{{ selectedTransaction.channel }}</strong></div>
        <div class="detail-row"><span>风险等级</span><strong>{{ riskLabel(selectedTransaction.risk_level) }}</strong></div>
        <div class="detail-row"><span>风险置信度</span><strong>{{ (selectedTransaction.confidence * 100).toFixed(2) }}%</strong></div>
        <div class="detail-row"><span>分析耗时</span><strong>{{ selectedTransaction.analysis_ms }} ms</strong></div>
        <div class="detail-row"><span>处置耗时</span><strong>{{ selectedTransaction.freeze_ms }} ms</strong></div>
        <div class="detail-row"><span>触发原因</span><strong>{{ selectedTransaction.flagged_reason || "无" }}</strong></div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";

import { fetchRealtimeSummary, openRealtimeStream } from "@/api/modules/realtime";
import type { RealtimeSummary, RealtimeTransactionItem } from "@/types/realtime";

const summary = ref<RealtimeSummary | null>(null);
const selectedTransaction = ref<RealtimeTransactionItem | null>(null);
const streamStatus = ref("连接中");
const streamPaused = ref(false);

let eventSource: EventSource | null = null;

const visibleTransactions = computed(() => summary.value?.latest_transactions ?? []);
const chartSeries = computed(() => [...visibleTransactions.value].reverse().slice(-24));

const amountValues = computed(() => chartSeries.value.map((item) => item.amount));
const cumulativeValues = computed(() => {
  let total = 0;
  return chartSeries.value.map((item) => {
    total += item.amount;
    return total;
  });
});
const netFlowValues = computed(() => {
  let total = 0;
  return chartSeries.value.map((item) => {
    total += item.direction === "收入" ? item.amount : -item.amount;
    return total;
  });
});

const amountTrendPoints = computed(() => buildLinePoints(amountValues.value));
const cumulativePoints = computed(() => buildLinePoints(cumulativeValues.value));
const netFlowPoints = computed(() => buildLinePoints(netFlowValues.value));
const histogramBars = computed(() => buildHistogramBars(amountValues.value));

function createFallbackSummary(): RealtimeSummary {
  return {
    mode: "local-demo",
    generated_at: "2026-04-16T23:59:00",
    total_alerts: 18,
    high_risk_alerts: 7,
    average_confidence: 0.7924,
    total_transactions: 53,
    total_amount: 38789.13,
    average_amount: 2618.66,
    net_flow: 21960.83,
    latest_transactions: [
      {
        transaction_id: "TXN-2026-001",
        payer_account: "6222000000000001",
        payer_name: "何军",
        receiver_account: "4333000000000001",
        receiver_name: "杨玲",
        amount: 28000,
        direction: "支出",
        channel: "手机银行",
        risk_level: "high",
        confidence: 0.8812,
        event_time: "2026-04-16T23:43:20",
        analysis_ms: 203,
        freeze_ms: 33,
        flagged_reason: "命中重点关注账号",
      },
      {
        transaction_id: "TXN-2026-002",
        payer_account: "6222000000000002",
        payer_name: "秦桂芳",
        receiver_account: "4333000000000002",
        receiver_name: "胡冬梅",
        amount: 12500,
        direction: "收入",
        channel: "网银",
        risk_level: "medium",
        confidence: 0.6629,
        event_time: "2026-04-16T23:28:23",
        analysis_ms: 168,
        freeze_ms: 19,
        flagged_reason: "交易金额异常波动",
      },
    ],
    latest_alerts: [],
  };
}

async function loadSummary() {
  try {
    summary.value = await fetchRealtimeSummary();
    streamStatus.value = "已连接";
  } catch {
    const fallback = createFallbackSummary();
    fallback.latest_alerts = fallback.latest_transactions.filter((item) => item.risk_level !== "low");
    summary.value = fallback;
    streamStatus.value = "本地演示";
  }
}

function openTransactionDetail(item: RealtimeTransactionItem) {
  selectedTransaction.value = item;
}

function closeTransactionDetail() {
  selectedTransaction.value = null;
}

function formatTime(value: string) {
  return value.slice(11, 19);
}

function formatAmount(value?: number) {
  if (typeof value !== "number") {
    return "--";
  }
  return value.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function riskLabel(value: string) {
  if (value === "high") return "高风险";
  if (value === "medium") return "中风险";
  return "低风险";
}

function buildLinePoints(values: number[]) {
  if (values.length === 0) {
    return "";
  }
  const width = 320;
  const height = 160;
  const paddingX = 16;
  const paddingY = 18;
  const maxValue = Math.max(...values);
  const minValue = Math.min(...values);
  const range = Math.max(maxValue - minValue, 1);
  return values
    .map((value, index) => {
      const x = paddingX + (index * (width - paddingX * 2)) / Math.max(values.length - 1, 1);
      const y = height - paddingY - ((value - minValue) / range) * (height - paddingY * 2);
      return `${x},${y}`;
    })
    .join(" ");
}

function buildHistogramBars(values: number[]) {
  const width = 320;
  const height = 160;
  const paddingX = 18;
  const paddingY = 18;
  const binCount = 8;
  if (values.length === 0) {
    return [];
  }
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = Math.max(maxValue - minValue, 1);
  const step = range / binCount;
  const bins = new Array(binCount).fill(0);
  for (const value of values) {
    const rawIndex = Math.floor((value - minValue) / step);
    const index = Math.min(binCount - 1, Math.max(0, rawIndex));
    bins[index] += 1;
  }
  const maxBin = Math.max(...bins, 1);
  const barGap = 8;
  const barWidth = (width - paddingX * 2 - barGap * (binCount - 1)) / binCount;
  return bins.map((count, index) => {
    const barHeight = (count / maxBin) * (height - paddingY * 2);
    return {
      index,
      x: paddingX + index * (barWidth + barGap),
      y: height - paddingY - barHeight,
      width: barWidth,
      height: barHeight,
    };
  });
}

function exportCharts() {
  const histogram = histogramBars.value
    .map(
      (bar) =>
        `<rect x="${bar.x}" y="${bar.y}" width="${bar.width}" height="${bar.height}" rx="4" fill="#77b7ff" />`,
    )
    .join("");
  const block = (title: string, body: string, x: number, y: number) => `
    <g transform="translate(${x}, ${y})">
      <rect x="0" y="0" width="420" height="220" rx="10" fill="#ffffff" stroke="#d8dee9" />
      <text x="210" y="28" text-anchor="middle" font-size="18" fill="#334155">${title}</text>
      <rect x="18" y="42" width="384" height="150" rx="8" fill="#f8fafc" stroke="#e2e8f0" />
      ${body}
    </g>
  `;
  const svg = `<?xml version="1.0" encoding="UTF-8"?>
  <svg xmlns="http://www.w3.org/2000/svg" width="920" height="520" viewBox="0 0 920 520">
    <rect width="920" height="520" fill="#f3f6fb" />
    <text x="460" y="36" text-anchor="middle" font-size="24" fill="#0f172a">实时数据流分析图表</text>
    ${block("实时交易金额", `<polyline points="${amountTrendPoints.value}" fill="none" stroke="#4f8cff" stroke-width="4" transform="translate(50, 52) scale(1.15, 0.9)" />`, 24, 60)}
    ${block("交易金额直方图", `<g transform="translate(24, 34)">${histogram}</g>`, 476, 60)}
    ${block("累计交易额", `<polyline points="${cumulativePoints.value}" fill="none" stroke="#9b6bff" stroke-width="4" transform="translate(50, 52) scale(1.15, 0.9)" />`, 24, 280)}
    ${block("累计资金流向", `<polyline points="${netFlowPoints.value}" fill="none" stroke="#ff8c42" stroke-width="4" transform="translate(50, 52) scale(1.15, 0.9)" />`, 476, 280)}
  </svg>`;
  const blob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `realtime-charts-${Date.now()}.svg`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

onMounted(async () => {
  await loadSummary();
  eventSource = openRealtimeStream();
  eventSource.onmessage = (event) => {
    if (streamPaused.value) {
      return;
    }
    const payload = JSON.parse(event.data) as RealtimeSummary;
    summary.value = payload;
    streamStatus.value = "已连接";
    if (selectedTransaction.value) {
      selectedTransaction.value =
        payload.latest_transactions.find((item) => item.transaction_id === selectedTransaction.value?.transaction_id) ??
        payload.latest_transactions[0] ??
        null;
    }
  };
  eventSource.onerror = () => {
    streamStatus.value = "本地演示";
  };
});

onUnmounted(() => {
  eventSource?.close();
});
</script>
