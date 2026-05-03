<template>
  <section class="page-grid alerts-layout">
    <section class="panel">
      <header class="panel-title">链路分析</header>

      <div class="table-scroll table-scroll-compact">
        <table class="legacy-table compact">
          <thead>
            <tr>
              <th>时间</th>
              <th>付款方</th>
              <th>收款方</th>
              <th>金额</th>
              <th>风险等级</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in alerts"
              :key="item.transaction_id"
              :class="['table-row', item.risk_level, { active: item.transaction_id === selectedAlert?.transaction_id }]"
              @click="selectAlert(item)"
            >
              <td>{{ item.event_time.slice(11, 19) }}</td>
              <td>{{ item.payer_name }}</td>
              <td>{{ item.receiver_name }}</td>
              <td>{{ item.amount.toFixed(2) }}</td>
              <td>{{ riskLabel(item.risk_level) }}</td>
            </tr>
            <tr v-if="alerts.length === 0" class="table-empty-row">
              <td colspan="5">暂无链路分析数据</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="graph-stage graph-stage-dynamic">
        <template v-if="graphNodes.length > 0">
          <svg ref="graphSvgRef" class="graph-svg" viewBox="0 0 780 260" preserveAspectRatio="none">
            <defs>
              <marker id="graph-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">
                <path d="M 0 0 L 8 4 L 0 8 z" fill="currentColor" />
              </marker>
            </defs>

            <g v-for="edge in graphEdges" :key="edge.id">
              <path
                :d="edge.path"
                :class="['graph-edge', { disabled: edge.disabled, selected: edge.id === selectedEdgeId }]"
                :style="{ stroke: edge.stroke, strokeWidth: edge.width }"
                marker-end="url(#graph-arrow)"
                @click="selectEdge(edge.id)"
              />
              <text
                class="graph-edge-label"
                :class="{ disabled: edge.disabled }"
                :x="edge.labelX"
                :y="edge.labelY"
                text-anchor="middle"
                @click="selectEdge(edge.id)"
              >
                {{ edge.amount.toFixed(0) }}
              </text>
            </g>

            <g
              v-for="node in graphNodes"
              :key="node.id"
              class="graph-node-group"
              :class="{
                selected: node.id === selectedGraphNodeId,
                disabled: node.disabled,
                origin: node.kind === 'origin',
                target: node.kind === 'target'
              }"
              @click="openNodeDetails(node.id)"
            >
              <rect
                class="graph-node-rect"
                :x="node.x - node.width / 2"
                :y="node.y - node.height / 2"
                :width="node.width"
                :height="node.height"
                rx="24"
              />
              <text class="graph-node-label" :x="node.x" :y="node.y - 2" text-anchor="middle">
                {{ node.label }}
              </text>
              <text class="graph-node-subtitle" :x="node.x" :y="node.y + 15" text-anchor="middle">
                {{ node.account.slice(-4) }}
              </text>
            </g>
          </svg>
        </template>
        <div v-else class="graph-empty-state">点击上方告警表格中的条目以分析可疑链路</div>
      </div>

      <div class="panel-actions wrap">
        <button class="legacy-button" type="button" :disabled="!selectedGraphNodeId || selectedGraphNodeStatus === 'Frozen'" @click="freezeSelectedNode">
          封禁
        </button>
        <button class="legacy-button" type="button" :disabled="!selectedGraphNodeId || selectedGraphNodeStatus !== 'Frozen'" @click="releaseSelectedNode">
          放行
        </button>
        <button class="legacy-button wide" type="button" :disabled="!selectedGraphNodeId" @click="freezeSelectedChain">
          全链路手动封禁
        </button>
        <button class="legacy-button wide" type="button" :disabled="graphNodes.length === 0" @click="exportGraph">
          保存分析图表
        </button>
      </div>
    </section>

    <section class="panel">
      <header class="panel-title">实时告警</header>
      <div class="stats-strip">
        <div class="stat-box">
          <span>累计告警</span>
          <strong>{{ summary?.total_alerts ?? "--" }}</strong>
        </div>
        <div class="stat-box">
          <span>高风险告警</span>
          <strong>{{ summary?.high_risk_alerts ?? "--" }}</strong>
        </div>
        <div class="stat-box">
          <span>平均置信度</span>
          <strong>{{ summary ? `${(summary.average_confidence * 100).toFixed(1)}%` : "--" }}</strong>
        </div>
      </div>

      <div class="table-scroll">
        <table class="legacy-table">
          <thead>
            <tr>
              <th>交易时间</th>
              <th>付款方姓名</th>
              <th>收款方姓名</th>
              <th>金额</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in alerts" :key="`${item.transaction_id}-stream`">
              <td>{{ item.event_time.slice(11, 19) }}</td>
              <td>{{ item.payer_name }}</td>
              <td>{{ item.receiver_name }}</td>
              <td>{{ item.amount.toFixed(2) }}</td>
            </tr>
            <tr v-if="alerts.length === 0" class="table-empty-row">
              <td colspan="4">暂无实时告警数据</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="panel-actions">
        <button class="legacy-button" type="button" @click="streamPaused = true">停止</button>
        <button class="legacy-button" type="button" @click="streamPaused = false">继续</button>
      </div>

      <div class="detail-grid slim">
        <div class="detail-row">
          <span>链路分析时间</span>
          <strong>{{ currentEdgeTransaction ? `${currentEdgeTransaction.analysis_ms} ms` : "--- ms" }}</strong>
        </div>
        <div class="detail-row">
          <span>链路冻结时间</span>
          <strong>{{ currentEdgeTransaction ? `${currentEdgeTransaction.freeze_ms} ms` : "--- ms" }}</strong>
        </div>
        <div class="detail-row">
          <span>流状态</span>
          <strong>{{ streamStatus }}</strong>
        </div>
      </div>
    </section>
  </section>

  <div v-if="selectedNodeDetail" class="account-modal-backdrop" @click.self="selectedNodeDetail = null">
    <section class="account-modal monitor-detail-modal">
      <header class="account-modal-header">
        <div class="account-modal-title">账户静态信息</div>
        <button class="account-modal-close" type="button" @click="selectedNodeDetail = null">关闭</button>
      </header>
      <div class="graph-detail-grid">
        <div class="detail-row"><span>账户姓名</span><strong>{{ selectedNodeDetail.label }}</strong></div>
        <div class="detail-row"><span>账户代号</span><strong>{{ selectedNodeDetail.account }}</strong></div>
        <div class="detail-row"><span>当前状态</span><strong>{{ selectedNodeDetail.status === "Frozen" ? "已冻结" : "正常" }}</strong></div>
        <div class="detail-row"><span>入边数量</span><strong>{{ selectedNodeDetail.inbound }}</strong></div>
        <div class="detail-row"><span>出边数量</span><strong>{{ selectedNodeDetail.outbound }}</strong></div>
        <div class="detail-row"><span>节点角色</span><strong>{{ graphRoleLabel(selectedNodeDetail.kind) }}</strong></div>
      </div>
    </section>
  </div>

  <div v-if="edgeDetailOpen && selectedEdgeTransaction" class="account-modal-backdrop" @click.self="closeEdgeTransactionDetail">
    <section class="account-modal monitor-detail-modal">
      <header class="account-modal-header">
        <div class="account-modal-title">交易详情</div>
        <button class="account-modal-close" type="button" @click="closeEdgeTransactionDetail">关闭</button>
      </header>
      <div class="graph-detail-grid">
        <div class="detail-row"><span>交易编号</span><strong>{{ selectedEdgeTransaction.transaction_id }}</strong></div>
        <div class="detail-row"><span>交易时间</span><strong>{{ selectedEdgeTransaction.event_time.replace("T", " ") }}</strong></div>
        <div class="detail-row"><span>付款方</span><strong>{{ selectedEdgeTransaction.payer_name }} / {{ selectedEdgeTransaction.payer_account }}</strong></div>
        <div class="detail-row"><span>收款方</span><strong>{{ selectedEdgeTransaction.receiver_name }} / {{ selectedEdgeTransaction.receiver_account }}</strong></div>
        <div class="detail-row"><span>交易金额</span><strong>{{ selectedEdgeTransaction.amount.toFixed(2) }}</strong></div>
        <div class="detail-row"><span>交易渠道</span><strong>{{ selectedEdgeTransaction.channel }}</strong></div>
        <div class="detail-row"><span>风险等级</span><strong>{{ riskLabel(selectedEdgeTransaction.risk_level) }}</strong></div>
        <div class="detail-row"><span>风险置信度</span><strong>{{ (selectedEdgeTransaction.confidence * 100).toFixed(2) }}%</strong></div>
        <div class="detail-row"><span>触发原因</span><strong>{{ selectedEdgeTransaction.flagged_reason || "无" }}</strong></div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";

import { fetchRealtimeSummary, openRealtimeStream } from "@/api/modules/realtime";
import type { RealtimeSummary, RealtimeTransactionItem } from "@/types/realtime";

type AccountStatus = "Normal" | "Frozen";

interface GraphNode {
  id: string;
  label: string;
  account: string;
  kind: "origin" | "target" | "context";
  x: number;
  y: number;
  width: number;
  height: number;
  inbound: number;
  outbound: number;
  disabled: boolean;
  status: AccountStatus;
}

interface GraphEdge {
  id: string;
  from: string;
  to: string;
  amount: number;
  path: string;
  labelX: number;
  labelY: number;
  stroke: string;
  width: number;
  disabled: boolean;
  transaction: RealtimeTransactionItem;
}

const GRAPH_WIDTH = 780;
const GRAPH_HEIGHT = 260;
const NODE_WIDTH = 126;
const NODE_HEIGHT = 52;

const summary = ref<RealtimeSummary | null>(null);
const alerts = ref<RealtimeTransactionItem[]>([]);
const selectedAlert = ref<RealtimeTransactionItem | null>(null);
const selectedGraphNodeId = ref<string | null>(null);
const selectedEdgeId = ref<string | null>(null);
const selectedNodeDetail = ref<GraphNode | null>(null);
const selectedEdgeTransaction = ref<RealtimeTransactionItem | null>(null);
const edgeDetailOpen = ref(false);
const streamStatus = ref("连接中");
const streamPaused = ref(false);
const graphSvgRef = ref<SVGSVGElement | null>(null);
const accountStatus = ref<Record<string, AccountStatus>>({});

let eventSource: EventSource | null = null;

function createFallbackSummary(): RealtimeSummary {
  return {
    mode: "local-demo",
    generated_at: "2026-04-16T23:59:00",
    total_alerts: 128,
    high_risk_alerts: 37,
    average_confidence: 0.83,
    total_transactions: 128,
    total_amount: 885200.52,
    average_amount: 6915.63,
    net_flow: 138820.1,
    latest_transactions: [],
    latest_alerts: [
      {
        transaction_id: "TXN-2026-001",
        payer_account: "6222000000000001",
        payer_name: "何军",
        receiver_account: "4333000000000001",
        receiver_name: "杨玲",
        amount: 30,
        direction: "支出",
        channel: "手机银行",
        risk_level: "high",
        confidence: 0.8224,
        event_time: "2026-04-15T03:43:20",
        analysis_ms: 301,
        freeze_ms: 48,
        flagged_reason: "命中重点关注账号",
      },
      {
        transaction_id: "TXN-2026-002",
        payer_account: "6222000000000002",
        payer_name: "秦桂芳",
        receiver_account: "4333000000000002",
        receiver_name: "胡冬梅",
        amount: 500,
        direction: "收入",
        channel: "网银",
        risk_level: "medium",
        confidence: 0.6293,
        event_time: "2026-04-15T03:28:23",
        analysis_ms: 218,
        freeze_ms: 17,
        flagged_reason: "交易金额异常波动",
      },
      {
        transaction_id: "TXN-2026-003",
        payer_account: "6222000000000003",
        payer_name: "罗帆",
        receiver_account: "4333000000000003",
        receiver_name: "李建华",
        amount: 12.78,
        direction: "支出",
        channel: "柜面",
        risk_level: "medium",
        confidence: 0.6476,
        event_time: "2026-04-15T03:17:03",
        analysis_ms: 164,
        freeze_ms: 11,
        flagged_reason: "短时频繁往来",
      },
    ],
  };
}

const currentEdgeTransaction = computed(() => {
  if (selectedEdgeTransaction.value) {
    return selectedEdgeTransaction.value;
  }
  if (selectedEdgeId.value) {
    return graphEdges.value.find((edge) => edge.id === selectedEdgeId.value)?.transaction ?? null;
  }
  return selectedAlert.value;
});

const selectedGraphNodeStatus = computed(() => {
  if (!selectedGraphNodeId.value) {
    return "Normal";
  }
  return accountStatus.value[selectedGraphNodeId.value] ?? "Normal";
});

function dedupeTransactions(items: RealtimeTransactionItem[]) {
  const seen = new Set<string>();
  const result: RealtimeTransactionItem[] = [];
  for (const item of items) {
    if (seen.has(item.transaction_id)) {
      continue;
    }
    seen.add(item.transaction_id);
    result.push(item);
  }
  return result;
}

function buildGraphTransactions(sourceAlerts: RealtimeTransactionItem[], origin: RealtimeTransactionItem | null) {
  if (!origin) {
    return [] as RealtimeTransactionItem[];
  }
  const chosen: RealtimeTransactionItem[] = [origin];
  const chosenIds = new Set<string>([origin.transaction_id]);
  const accountsInGraph = new Set<string>([origin.payer_account, origin.receiver_account]);
  const maxNodes = 6;
  const maxPathDepth = 4;
  const maxDegreePerNode = 1;

  let lastAccount = origin.receiver_account;
  while (accountsInGraph.size < maxNodes && chosen.length < maxPathDepth) {
    const nextTx = sourceAlerts.find(
      (item) =>
        item.transaction_id !== origin.transaction_id &&
        !chosenIds.has(item.transaction_id) &&
        item.payer_account === lastAccount &&
        !accountsInGraph.has(item.receiver_account),
    );
    if (!nextTx) {
      break;
    }
    chosen.push(nextTx);
    chosenIds.add(nextTx.transaction_id);
    accountsInGraph.add(nextTx.receiver_account);
    lastAccount = nextTx.receiver_account;
  }

  const contextQueue = [...accountsInGraph];
  const processed = new Set<string>();
  while (contextQueue.length > 0 && accountsInGraph.size < 7) {
    const account = contextQueue.shift();
    if (!account || processed.has(account)) {
      continue;
    }
    processed.add(account);

    const incoming = sourceAlerts.filter(
      (item) => !chosenIds.has(item.transaction_id) && item.receiver_account === account && !accountsInGraph.has(item.payer_account),
    );
    for (const tx of incoming.slice(0, maxDegreePerNode)) {
      if (accountsInGraph.size >= 7) {
        break;
      }
      chosen.push(tx);
      chosenIds.add(tx.transaction_id);
      accountsInGraph.add(tx.payer_account);
      contextQueue.push(tx.payer_account);
    }

    const outgoing = sourceAlerts.filter(
      (item) => !chosenIds.has(item.transaction_id) && item.payer_account === account && !accountsInGraph.has(item.receiver_account),
    );
    for (const tx of outgoing.slice(0, maxDegreePerNode)) {
      if (accountsInGraph.size >= 7) {
        break;
      }
      chosen.push(tx);
      chosenIds.add(tx.transaction_id);
      accountsInGraph.add(tx.receiver_account);
      contextQueue.push(tx.receiver_account);
    }
  }

  return dedupeTransactions(chosen);
}

function computeDisabledNodes(transactions: RealtimeTransactionItem[]) {
  const edgeMap = new Map<string, string[]>();
  for (const tx of transactions) {
    const list = edgeMap.get(tx.payer_account) ?? [];
    list.push(tx.receiver_account);
    edgeMap.set(tx.payer_account, list);
  }
  const disabled = new Set<string>();
  const queue = Object.entries(accountStatus.value)
    .filter(([, status]) => status === "Frozen")
    .map(([account]) => account);
  for (const account of queue) {
    disabled.add(account);
  }
  while (queue.length > 0) {
    const current = queue.shift()!;
    for (const next of edgeMap.get(current) ?? []) {
      if (!disabled.has(next)) {
        disabled.add(next);
        queue.push(next);
      }
    }
  }
  return disabled;
}

const graphModel = computed(() => {
  const transactions = buildGraphTransactions(alerts.value, selectedAlert.value);
  if (transactions.length === 0) {
    return { nodes: [] as GraphNode[], edges: [] as GraphEdge[] };
  }

  const disabledNodes = computeDisabledNodes(transactions);
  const nodeMeta = new Map<
    string,
    {
      id: string;
      label: string;
      account: string;
      kind: "origin" | "target" | "context";
      inbound: number;
      outbound: number;
      level?: number;
    }
  >();

  const selected = selectedAlert.value!;
  nodeMeta.set(selected.payer_account, {
    id: selected.payer_account,
    label: selected.payer_name,
    account: selected.payer_account,
    kind: "origin",
    inbound: 0,
    outbound: 0,
    level: 0,
  });
  nodeMeta.set(selected.receiver_account, {
    id: selected.receiver_account,
    label: selected.receiver_name,
    account: selected.receiver_account,
    kind: "target",
    inbound: 0,
    outbound: 0,
    level: 1,
  });

  for (const tx of transactions) {
    if (!nodeMeta.has(tx.payer_account)) {
      nodeMeta.set(tx.payer_account, {
        id: tx.payer_account,
        label: tx.payer_name,
        account: tx.payer_account,
        kind: "context",
        inbound: 0,
        outbound: 0,
      });
    }
    if (!nodeMeta.has(tx.receiver_account)) {
      nodeMeta.set(tx.receiver_account, {
        id: tx.receiver_account,
        label: tx.receiver_name,
        account: tx.receiver_account,
        kind: "context",
        inbound: 0,
        outbound: 0,
      });
    }

    nodeMeta.get(tx.payer_account)!.outbound += 1;
    nodeMeta.get(tx.receiver_account)!.inbound += 1;
  }

  for (let round = 0; round < 4; round += 1) {
    for (const tx of transactions) {
      const payer = nodeMeta.get(tx.payer_account)!;
      const receiver = nodeMeta.get(tx.receiver_account)!;
      if (payer.level !== undefined && receiver.level === undefined) {
        receiver.level = payer.level + 1;
      } else if (receiver.level !== undefined && payer.level === undefined) {
        payer.level = Math.max(0, receiver.level - 1);
      }
    }
  }

  for (const meta of nodeMeta.values()) {
    if (meta.level === undefined) {
      meta.level = 0;
    }
  }

  const minLevel = Math.min(...Array.from(nodeMeta.values(), (item) => item.level ?? 0));
  const levelBuckets = new Map<number, typeof nodeMeta extends Map<string, infer T> ? T[] : never>();
  for (const meta of nodeMeta.values()) {
    const normalizedLevel = (meta.level ?? 0) - minLevel;
    meta.level = normalizedLevel;
    const bucket = levelBuckets.get(normalizedLevel) ?? [];
    bucket.push(meta);
    levelBuckets.set(normalizedLevel, bucket);
  }

  const maxLevel = Math.max(...levelBuckets.keys(), 0);
  const nodes: GraphNode[] = [];
  for (const [level, bucket] of [...levelBuckets.entries()].sort((a, b) => a[0] - b[0])) {
    bucket.sort((a, b) => a.label.localeCompare(b.label, "zh-CN"));
    const x = maxLevel === 0 ? GRAPH_WIDTH / 2 : 84 + (level * (GRAPH_WIDTH - 168)) / maxLevel;
    const spacing = GRAPH_HEIGHT / (bucket.length + 1);
    bucket.forEach((meta, index) => {
      nodes.push({
        id: meta.id,
        label: meta.label,
        account: meta.account,
        kind: meta.kind,
        x,
        y: spacing * (index + 1),
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        inbound: meta.inbound,
        outbound: meta.outbound,
        disabled: disabledNodes.has(meta.id),
        status: accountStatus.value[meta.id] ?? "Normal",
      });
    });
  }

  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const amounts = transactions.map((tx) => tx.amount);
  const minAmount = Math.min(...amounts);
  const maxAmount = Math.max(...amounts);
  const edges: GraphEdge[] = transactions.map((tx) => {
    const from = nodeById.get(tx.payer_account)!;
    const to = nodeById.get(tx.receiver_account)!;
    const startX = from.x + NODE_WIDTH / 2 - 8;
    const endX = to.x - NODE_WIDTH / 2 + 8;
    const startY = from.y;
    const endY = to.y;
    const midX = startX + (endX - startX) / 2;
    const curve = Math.max(18, Math.abs(endY - startY) * 0.25);
    const path = `M ${startX} ${startY} C ${midX - 24} ${startY}, ${midX + 24} ${endY}, ${endX} ${endY}`;
    const normalized = maxAmount > minAmount ? (tx.amount - minAmount) / (maxAmount - minAmount) : 0.5;
    const hue = 32 - normalized * 20;
    const lightness = 62 - normalized * 22;
    const stroke = `hsl(${hue}, 86%, ${lightness}%)`;
    return {
      id: tx.transaction_id,
      from: tx.payer_account,
      to: tx.receiver_account,
      amount: tx.amount,
      path,
      labelX: (startX + endX) / 2,
      labelY: (startY + endY) / 2 - curve * 0.18,
      stroke,
      width: normalized >= 0.75 ? 3.8 : normalized >= 0.4 ? 3.2 : 2.6,
      disabled: disabledNodes.has(tx.payer_account),
      transaction: tx,
    };
  });

  return { nodes, edges };
});

const graphNodes = computed(() => graphModel.value.nodes);
const graphEdges = computed(() => graphModel.value.edges);

function riskLabel(value: string) {
  if (value === "high") return "高风险";
  if (value === "medium") return "中风险";
  return "低风险";
}

function graphRoleLabel(value: GraphNode["kind"]) {
  if (value === "origin") return "起始账户";
  if (value === "target") return "目标账户";
  return "关联账户";
}

function selectAlert(item: RealtimeTransactionItem) {
  selectedAlert.value = item;
  selectedGraphNodeId.value = null;
  selectedEdgeId.value = null;
  selectedNodeDetail.value = null;
  selectedEdgeTransaction.value = null;
  edgeDetailOpen.value = false;
  accountStatus.value = {};
}

function openNodeDetails(nodeId: string) {
  selectedGraphNodeId.value = nodeId;
  const node = graphNodes.value.find((item) => item.id === nodeId) ?? null;
  selectedNodeDetail.value = node;
}

function selectEdge(edgeId: string) {
  selectedEdgeId.value = edgeId;
  const edge = graphEdges.value.find((item) => item.id === edgeId);
  selectedEdgeTransaction.value = edge?.transaction ?? null;
  edgeDetailOpen.value = !!edge;
}

function closeEdgeTransactionDetail() {
  edgeDetailOpen.value = false;
  selectedEdgeTransaction.value = null;
}

function freezeSelectedNode() {
  if (!selectedGraphNodeId.value) {
    return;
  }
  accountStatus.value = {
    ...accountStatus.value,
    [selectedGraphNodeId.value]: "Frozen",
  };
  const node = graphNodes.value.find((item) => item.id === selectedGraphNodeId.value);
  if (node) {
    selectedNodeDetail.value = {
      ...node,
      status: "Frozen",
      disabled: true,
    };
  }
}

function releaseSelectedNode() {
  if (!selectedGraphNodeId.value) {
    return;
  }
  accountStatus.value = {
    ...accountStatus.value,
    [selectedGraphNodeId.value]: "Normal",
  };
  const node = graphNodes.value.find((item) => item.id === selectedGraphNodeId.value);
  if (node) {
    selectedNodeDetail.value = {
      ...node,
      status: "Normal",
      disabled: false,
    };
  }
}

function freezeSelectedChain() {
  if (!selectedGraphNodeId.value) {
    return;
  }
  const nextStatus = { ...accountStatus.value };
  const queue = [selectedGraphNodeId.value];
  const visited = new Set(queue);
  while (queue.length > 0) {
    const current = queue.shift()!;
    nextStatus[current] = "Frozen";
    for (const edge of graphEdges.value.filter((item) => item.from === current)) {
      if (!visited.has(edge.to)) {
        visited.add(edge.to);
        queue.push(edge.to);
      }
    }
  }
  accountStatus.value = nextStatus;
  const node = graphNodes.value.find((item) => item.id === selectedGraphNodeId.value);
  if (node) {
    selectedNodeDetail.value = {
      ...node,
      status: "Frozen",
      disabled: true,
    };
  }
}

function exportGraph() {
  const svg = graphSvgRef.value;
  if (!svg) {
    return;
  }
  const serialized = new XMLSerializer().serializeToString(svg);
  const blob = new Blob([serialized], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `link-analysis-${Date.now()}.svg`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

async function loadSummary() {
  try {
    summary.value = await fetchRealtimeSummary();
    streamStatus.value = "已连接";
  } catch {
    summary.value = createFallbackSummary();
    streamStatus.value = "本地演示";
  }

  const initialAlerts =
    summary.value.latest_alerts.length > 0
      ? summary.value.latest_alerts
      : summary.value.latest_transactions.filter((item) => item.risk_level !== "low");
  alerts.value = initialAlerts;
  selectedAlert.value = initialAlerts[0] ?? null;
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
    const streamAlerts =
      payload.latest_alerts.length > 0
        ? payload.latest_alerts
        : payload.latest_transactions.filter((item) => item.risk_level !== "low");
    alerts.value = streamAlerts;
    if (selectedAlert.value) {
      selectedAlert.value =
        streamAlerts.find((item) => item.transaction_id === selectedAlert.value?.transaction_id) ?? streamAlerts[0] ?? null;
    } else {
      selectedAlert.value = streamAlerts[0] ?? null;
    }
    if (selectedEdgeId.value && edgeDetailOpen.value) {
      const currentEdge = streamAlerts.find((item) => item.transaction_id === selectedEdgeId.value);
      selectedEdgeTransaction.value = currentEdge ?? null;
      if (!currentEdge) {
        edgeDetailOpen.value = false;
      }
    }
    streamStatus.value = "已连接";
  };
  eventSource.onerror = () => {
    streamStatus.value = "本地演示";
  };
});

onUnmounted(() => {
  eventSource?.close();
});
</script>
