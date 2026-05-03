<template>
  <section class="pdf-viewer-page">
    <div v-if="loading" class="pdf-viewer-state">
      <div class="pdf-viewer-card">
        <h1>PDF 报告加载中</h1>
        <p>{{ statusText }}</p>
      </div>
    </div>

    <div v-else-if="error" class="pdf-viewer-state">
      <div class="pdf-viewer-card error">
        <h1>报告打开失败</h1>
        <p>{{ error }}</p>
      </div>
    </div>

    <iframe
      v-else-if="pdfUrl"
      :src="pdfUrl"
      class="pdf-viewer-frame"
      title="PDF 报告预览"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { fetchAnalysisJob, fetchAnalysisReportPdf } from "@/api/modules/analysis";
import { fetchReportPdf } from "@/api/modules/reports";

const route = useRoute();
const loading = ref(true);
const error = ref("");
const pdfUrl = ref("");
const pollTimer = ref<number | null>(null);
const statusText = ref("正在准备报告...");

const jobId = computed(() => {
  const raw = route.query.jobId;
  return typeof raw === "string" ? raw : "";
});

const downloadUrl = computed(() => {
  const raw = route.query.downloadUrl;
  return typeof raw === "string" ? raw : "";
});

const autoWait = computed(() => route.query.autoWait === "1");

function stopPolling() {
  if (pollTimer.value !== null) {
    window.clearTimeout(pollTimer.value);
    pollTimer.value = null;
  }
}

function revokePdfUrl() {
  if (pdfUrl.value) {
    URL.revokeObjectURL(pdfUrl.value);
    pdfUrl.value = "";
  }
}

async function renderPdfFromBlob(blob: Blob) {
  revokePdfUrl();
  pdfUrl.value = URL.createObjectURL(blob);
  error.value = "";
  loading.value = false;
}

async function loadAnalysisReport() {
  if (!jobId.value) {
    error.value = "缺少分析任务编号。";
    loading.value = false;
    return;
  }

  try {
    const detail = await fetchAnalysisJob(jobId.value);
    if (detail.status === "failed") {
      error.value = detail.error_message ?? "分析任务失败。";
      loading.value = false;
      stopPolling();
      return;
    }

    if (!detail.report_ready) {
      if (!autoWait.value) {
        error.value = "报告尚未生成，请稍后重试。";
        loading.value = false;
        return;
      }

      statusText.value = `分析任务处理中：${detail.job_id}`;
      pollTimer.value = window.setTimeout(() => {
        void loadAnalysisReport();
      }, 2000);
      return;
    }

    statusText.value = "正在加载 PDF 报告...";
    const reportBlob = await fetchAnalysisReportPdf(jobId.value);
    await renderPdfFromBlob(reportBlob);
    document.title = `${detail.job_id} PDF 报告`;
    stopPolling();
  } catch (exception) {
    error.value = exception instanceof Error ? exception.message : "加载分析报告失败";
    loading.value = false;
    stopPolling();
  }
}

async function loadHistoryReport() {
  if (!downloadUrl.value) {
    error.value = "缺少报告地址。";
    loading.value = false;
    return;
  }

  try {
    statusText.value = "正在加载 PDF 报告...";
    const reportBlob = await fetchReportPdf(downloadUrl.value);
    await renderPdfFromBlob(reportBlob);
    document.title = "PDF 报告";
  } catch (exception) {
    error.value = exception instanceof Error ? exception.message : "加载历史报告失败";
    loading.value = false;
  }
}

onMounted(async () => {
  if (jobId.value) {
    await loadAnalysisReport();
    return;
  }

  if (downloadUrl.value) {
    await loadHistoryReport();
    return;
  }

  error.value = "未提供可打开的报告参数。";
  loading.value = false;
});

onBeforeUnmount(() => {
  stopPolling();
  revokePdfUrl();
});
</script>
