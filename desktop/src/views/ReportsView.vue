<template>
  <section class="page-grid history-layout">
    <section class="panel search-panel">
      <header class="panel-title">便捷查询</header>
      <textarea
        v-model.trim="queryText"
        class="legacy-textarea search-box"
        :placeholder="queryMode === 'time' ? '在此输入需查询的时间' : '在此输入需查询的登录ID'"
      />
      <div class="query-actions vertical">
        <button
          class="legacy-button wide icon-button"
          :class="{ active: queryMode === 'time' }"
          type="button"
          @click="queryMode = 'time'"
        >
          按时间查询（支持模糊查询）
        </button>
        <button
          class="legacy-button wide icon-button"
          :class="{ active: queryMode === 'account' }"
          type="button"
          @click="queryMode = 'account'"
        >
          按登录ID查询
        </button>
      </div>
    </section>

    <section class="panel">
      <header class="panel-title">本地日志数据</header>
      <div class="table-scroll">
        <table class="legacy-table tall-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>操作者ID</th>
              <th>可选操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in filteredLogs" :key="item.id">
              <td>{{ item.time }}</td>
              <td>{{ item.operator }}</td>
              <td class="action-cell">
                <button
                  class="table-action outline"
                  type="button"
                  :disabled="!item.downloadUrl"
                  @click="openPdfReport(item)"
                >
                  查看分析报告
                </button>
              </td>
            </tr>
            <tr v-if="filteredLogs.length === 0" class="table-empty-row">
              <td colspan="3">暂无符合条件的日志数据</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { fetchReports } from "@/api/modules/reports";

interface HistoryLog {
  id: string;
  time: string;
  operator: string;
  downloadUrl: string | null;
}

const queryText = ref("");
const queryMode = ref<"time" | "account">("time");
const router = useRouter();
const logs = ref<HistoryLog[]>([
  { id: "local-1", time: "2025-09-14 19:32:54", operator: "1", downloadUrl: null },
  { id: "local-2", time: "2025-09-13 23:24:34", operator: "1", downloadUrl: null },
  { id: "local-3", time: "2025-09-13 23:22:15", operator: "1", downloadUrl: null },
  { id: "local-4", time: "2025-09-13 23:15:02", operator: "1", downloadUrl: null },
  { id: "local-5", time: "2025-09-13 04:35:57", operator: "1", downloadUrl: null },
  { id: "local-6", time: "2025-09-12 14:52:26", operator: "1", downloadUrl: null },
]);

const filteredLogs = computed(() => {
  const keyword = queryText.value.trim().toLowerCase();
  if (!keyword) {
    return logs.value;
  }

  return logs.value.filter((item) =>
    queryMode.value === "time"
      ? item.time.toLowerCase().includes(keyword.replace(/\//g, "-"))
      : item.operator.toLowerCase().includes(keyword.replace(/\s+/g, "")),
  );
});

onMounted(async () => {
  try {
    const response = await fetchReports();
    const reportLogs = response.items.map((item) => ({
      id: item.report_id,
      time: item.created_at,
      operator: item.operator,
      downloadUrl: item.download_url,
    }));
    logs.value = [...reportLogs, ...logs.value];
  } catch {
    // 历史日志页面允许使用本地兜底数据
  }
});

function openPdfReport(item: HistoryLog) {
  if (!item.downloadUrl) {
    return;
  }

  const viewerUrl = router.resolve({
    path: "/report-viewer",
    query: {
      downloadUrl: item.downloadUrl,
    },
  }).href;
  window.open(viewerUrl, "_blank");
}
</script>
