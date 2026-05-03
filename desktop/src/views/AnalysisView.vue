<template>
  <section class="page-grid single analysis-page">
    <section class="panel analysis-upload-panel">
      <header class="section-strip analysis-strip">上传待分析动态多模态数据</header>
      <div class="analysis-top">
        <div class="analysis-main">
          <textarea
            v-model="textPayload"
            class="legacy-textarea analysis-box"
            placeholder="请在此输入待分析动态数据或在右侧上传文件"
          />
        </div>

        <div class="analysis-actions">
          <button class="legacy-button upload-button" type="button" @click="imageInput?.click()">上传图片</button>
          <button class="legacy-button upload-button" type="button" @click="appendTextPayload">上传文字</button>
          <button class="legacy-button upload-button" type="button" @click="fileInput?.click()">上传文件</button>
          <button class="legacy-button analyze-start" type="button" :disabled="submitting" @click="startAnalysis">
            {{ submitting ? "分析中..." : "开始分析" }}
          </button>
        </div>
      </div>
      <p class="panel-hint" v-if="uploadedLabels.length > 0">已选择：{{ uploadedLabels.join("、") }}</p>

      <input ref="imageInput" class="hidden-input" type="file" accept="image/*" multiple @change="handleFiles" />
      <input ref="fileInput" class="hidden-input" type="file" multiple @change="handleFiles" />
    </section>

    <section class="panel analysis-task-panel">
      <header class="section-strip analysis-strip">分析任务</header>

      <div v-if="job" class="detail-grid">
        <div class="detail-row">
          <span>任务编号</span>
          <strong>{{ job.job_id }}</strong>
        </div>
        <div class="detail-row">
          <span>任务状态</span>
          <strong>{{ statusMap[job.status] ?? job.status }}</strong>
        </div>
        <div class="detail-row">
          <span>创建时间</span>
          <strong>{{ formatDate(job.created_at) }}</strong>
        </div>
        <div class="detail-row">
          <span>解析资产数</span>
          <strong>{{ job.assets.length }}</strong>
        </div>
      </div>

      <div class="detail-grid" v-if="job?.parser_summary">
        <div class="detail-row">
          <span>MinerU 文档数</span>
          <strong>{{ job.parser_summary.mineru_documents }}</strong>
        </div>
        <div class="detail-row">
          <span>表格资产数</span>
          <strong>{{ job.parser_summary.spreadsheet_assets }}</strong>
        </div>
        <div class="detail-row">
          <span>文本资产数</span>
          <strong>{{ job.parser_summary.plain_text_assets }}</strong>
        </div>
      </div>

      <div class="narrative-box" v-if="job?.parser_summary?.warnings.length">
        <h3>解析提示</h3>
        <ul>
          <li v-for="warning in job.parser_summary.warnings" :key="warning">{{ warning }}</li>
        </ul>
      </div>

      <div class="detail-grid" v-if="job?.result">
        <div class="detail-row">
          <span>风险等级</span>
          <strong>{{ riskLevelMap[job.result.risk_level] ?? job.result.risk_level }}</strong>
        </div>
        <div class="detail-row">
          <span>置信度</span>
          <strong>{{ (job.result.confidence * 100).toFixed(2) }}%</strong>
        </div>
        <div class="detail-row">
          <span>模型来源</span>
          <strong>{{ job.result.model_source }}</strong>
        </div>
      </div>

      <div class="narrative-box" v-if="job?.result">
        <h3>分析结论</h3>
        <p>{{ job.result.narrative }}</p>
        <ul>
          <li v-for="action in job.result.suggested_actions" :key="action">{{ action }}</li>
        </ul>
      </div>

      <div class="narrative-box" v-if="job?.result?.risk_signals.length">
        <h3>风险信号</h3>
        <ul>
          <li v-for="signal in job.result.risk_signals" :key="signal">{{ signal }}</li>
        </ul>
      </div>

      <div class="panel-actions center" v-if="job?.report_ready">
        <button class="legacy-button wide" type="button" @click="openReport">导出 PDF 报告</button>
      </div>

      <div class="empty-state analysis-empty-state" v-else-if="!job && !error">
        发起分析后，系统会在完成时自动打开 PDF 报告。
      </div>
      <div class="empty-state analysis-empty-state" v-if="error">{{ error }}</div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";

import { createAnalysisJob, fetchAnalysisJob } from "@/api/modules/analysis";
import type { AnalysisJobDetailResponse } from "@/types/analysis";

const router = useRouter();
const imageInput = ref<HTMLInputElement | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const textPayload = ref("");
const textCommitted = ref(false);
const queuedFiles = ref<File[]>([]);
const job = ref<AnalysisJobDetailResponse | null>(null);
const error = ref("");
const submitting = ref(false);
const pollTimer = ref<number | null>(null);

const statusMap: Record<string, string> = {
  pending: "待处理",
  processing: "处理中",
  completed: "已完成",
  failed: "失败",
};

const riskLevelMap: Record<string, string> = {
  high: "高风险",
  medium: "中风险",
  low: "低风险",
};

const uploadedLabels = computed(() => {
  const labels = queuedFiles.value.map((file) => file.name);
  if (textCommitted.value && textPayload.value.trim()) {
    labels.unshift("文本输入");
  }
  return labels;
});

function appendTextPayload() {
  if (!textPayload.value.trim()) {
    error.value = "请输入需要分析的文本内容。";
    return;
  }
  error.value = "";
  textCommitted.value = true;
}

function handleFiles(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files ?? []);
  queuedFiles.value = [...queuedFiles.value, ...files];
  input.value = "";
}

function stopPolling() {
  if (pollTimer.value !== null) {
    window.clearInterval(pollTimer.value);
    pollTimer.value = null;
  }
}

async function pollJob(jobId: string) {
  try {
    job.value = await fetchAnalysisJob(jobId);
    if (job.value.status === "completed" || job.value.status === "failed") {
      stopPolling();
    }
  } catch (exception) {
    error.value = exception instanceof Error ? exception.message : "获取任务状态失败";
    stopPolling();
  }
}

function buildViewerUrl(jobId: string) {
  return router.resolve({
    path: "/report-viewer",
    query: {
      jobId,
      autoWait: "1",
    },
  }).href;
}

function openReportViewer(jobId: string, reportWindow?: Window | null) {
  const viewerUrl = buildViewerUrl(jobId);
  if (reportWindow && !reportWindow.closed) {
    reportWindow.location.href = viewerUrl;
    reportWindow.focus();
    return true;
  }

  const nextWindow = window.open(viewerUrl, "_blank");
  if (!nextWindow) {
    error.value = "浏览器已拦截报告窗口，请允许弹窗后重试。";
    return false;
  }
  nextWindow.focus();
  return true;
}

async function startAnalysis() {
  if (!textCommitted.value && queuedFiles.value.length === 0) {
    error.value = "请先上传图片、文本或文件。";
    return;
  }

  const reportWindow = window.open("", "_blank");
  if (!reportWindow) {
    error.value = "浏览器已拦截报告窗口，请允许弹窗后重试。";
    return;
  }

  reportWindow.document.open();
  reportWindow.document.write(`
    <!doctype html>
    <html lang="zh-CN">
      <head>
        <meta charset="utf-8" />
        <title>分析任务已提交</title>
        <style>
          body {
            margin: 0;
            font-family: "Microsoft YaHei", sans-serif;
            background: #f5f7fb;
            color: #1f2937;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
          }
          .loading {
            padding: 24px 28px;
            border: 1px solid #dbe2ea;
            border-radius: 8px;
            background: #ffffff;
            box-shadow: 0 12px 30px rgba(15, 23, 42, 0.08);
          }
        </style>
      </head>
      <body>
        <div class="loading">分析任务已提交，PDF 报告生成后将自动打开...</div>
      </body>
    </html>
  `);
  reportWindow.document.close();

  const formData = new FormData();
  if (textCommitted.value && textPayload.value.trim()) {
    formData.append("text_payload", textPayload.value.trim());
  }
  queuedFiles.value.forEach((file) => formData.append("files", file));

  submitting.value = true;
  error.value = "";
  stopPolling();

  try {
    const created = await createAnalysisJob(formData);
    openReportViewer(created.job_id, reportWindow);
    await pollJob(created.job_id);
    pollTimer.value = window.setInterval(() => {
      void pollJob(created.job_id);
    }, 2000);
  } catch (exception) {
    reportWindow.document.open();
    reportWindow.document.write(`
      <!doctype html>
      <html lang="zh-CN">
        <head>
          <meta charset="utf-8" />
          <title>分析任务提交失败</title>
          <style>
            body {
              margin: 0;
              font-family: "Microsoft YaHei", sans-serif;
              background: #f5f7fb;
              color: #1f2937;
              display: flex;
              align-items: center;
              justify-content: center;
              min-height: 100vh;
            }
            .error-box {
              max-width: 520px;
              padding: 24px 28px;
              border: 1px solid #f0caca;
              border-radius: 8px;
              background: #ffffff;
              box-shadow: 0 12px 30px rgba(15, 23, 42, 0.08);
            }
          </style>
        </head>
        <body>
          <div class="error-box">${exception instanceof Error ? exception.message : "分析失败"}</div>
        </body>
      </html>
    `);
    reportWindow.document.close();
    error.value = exception instanceof Error ? exception.message : "分析失败";
  } finally {
    submitting.value = false;
  }
}

async function openReport() {
  if (!job.value) {
    return;
  }
  openReportViewer(job.value.job_id);
}

function formatDate(value: string | null) {
  if (!value) {
    return "--";
  }
  return value.replace("T", " ");
}

onUnmounted(() => {
  stopPolling();
});
</script>
