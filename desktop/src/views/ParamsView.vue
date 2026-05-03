<template>
  <section class="page-grid params-layout">
    <section class="panel versions-panel">
      <div class="version-block">
        <div class="version-row"><span>当前软件版本:</span><strong>{{ overview?.versions.software.current ?? "--" }}</strong></div>
        <div class="version-row"><span>云端最新版本:</span><strong>{{ overview?.versions.software.latest ?? "--" }}</strong></div>
      </div>
      <div class="version-block">
        <div class="version-row"><span>当前模型版本:</span><strong>{{ overview?.versions.model.current ?? "--" }}</strong></div>
        <div class="version-row"><span>云端最新版本:</span><strong>{{ overview?.versions.model.latest ?? "--" }}</strong></div>
      </div>
      <div class="version-block">
        <div class="version-row"><span>当前参数版本:</span><strong>{{ overview?.versions.parameter.current ?? "--" }}</strong></div>
        <div class="version-row"><span>云端最新版本:</span><strong>{{ overview?.versions.parameter.latest ?? "--" }}</strong></div>
      </div>
      <div class="panel-actions vertical">
        <button class="legacy-button wide" type="button" :disabled="loading" @click="runVersionAction('software')">检测软件更新</button>
        <button class="legacy-button wide" type="button" :disabled="loading" @click="runVersionAction('model')">模型架构更新</button>
        <button class="legacy-button wide" type="button" :disabled="loading" @click="runVersionAction('parameter')">模型参数更新</button>
      </div>
    </section>

    <section class="panel">
      <header class="panel-title">金融欺诈识别模型参数</header>
      <div class="parameter-form">
        <label v-for="field in modelFields" :key="field.key" class="parameter-row">
          <span>{{ field.label }}</span>
          <input v-model="fraudModel[field.key]" />
        </label>
      </div>
      <div class="panel-actions">
        <button class="legacy-button wide" type="button" :disabled="loading" @click="saveFraudModel">将自定义参数保存至本地</button>
      </div>
    </section>

    <section class="panel">
      <header class="panel-title">高级参数设置</header>
      <div class="parameter-form">
        <label v-for="field in advancedFields" :key="field.key" class="parameter-row">
          <span>{{ field.label }}</span>
          <input v-model="advancedModel[field.key]" />
        </label>
      </div>
      <div class="panel-actions">
        <button class="legacy-button wide" type="button" :disabled="loading" @click="saveAdvancedModel">将自定义参数保存至本地</button>
      </div>
    </section>

    <section class="panel params-bottom">
      <header class="panel-title">动态识别模型参数</header>
      <div class="parameter-form">
        <label class="parameter-row">
          <span>高风险阈值:</span>
          <input v-model="dynamicModel.highRiskThreshold" />
        </label>
        <label class="parameter-row">
          <span>中风险阈值:</span>
          <input v-model="dynamicModel.mediumRiskThreshold" />
        </label>
        <label class="parameter-row">
          <span>自注意力机制开关:</span>
          <select class="legacy-select" v-model="dynamicSelfAttentionValue">
            <option value="on">开启自注意力机制</option>
            <option value="off">关闭自注意力机制</option>
          </select>
        </label>
        <label class="parameter-row">
          <span>自适应阈值开关:</span>
          <select class="legacy-select" v-model="dynamicAdaptiveValue">
            <option value="on">开启自适应阈值</option>
            <option value="off">关闭自适应阈值</option>
          </select>
        </label>
      </div>
      <div class="panel-actions">
        <button class="legacy-button wide" type="button" :disabled="loading" @click="saveDynamicModel">保存动态识别模型参数</button>
      </div>
    </section>

    <section class="panel params-status-panel" v-if="statusMessage || errorMessage">
      <header class="panel-title">操作结果</header>
      <div class="status-inline" v-if="statusMessage">{{ statusMessage }}</div>
      <div class="status-inline error" v-if="errorMessage">{{ errorMessage }}</div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { ApiError } from "@/api/client";
import {
  fetchParamsOverview,
  saveAdvancedModelParams,
  saveDynamicModelParams,
  saveFraudModelParams,
  triggerModelUpdate,
  triggerParameterUpdate,
  triggerSoftwareUpdate,
} from "@/api/modules/params";
import type {
  AdvancedModelParams,
  DynamicModelParams,
  FraudModelParams,
  ParamsOverviewResponse,
} from "@/types/params";

const modelFields = [
  { key: "decisionThreshold", label: "最终判定阈值:" },
  { key: "metaWeight", label: "元模型输出权重:" },
  { key: "gruWeight", label: "GRU 输出权重:" },
  { key: "xgbWeight", label: "XGBoost 输出权重:" },
] as const;

const advancedFields = [
  { key: "highRiskScoreThreshold", label: "高风险分级阈值:" },
  { key: "mediumRiskScoreThreshold", label: "中风险分级阈值:" },
  { key: "highConfidenceThreshold", label: "高置信度阈值:" },
  { key: "mediumConfidenceThreshold", label: "中置信度阈值:" },
] as const;

const loading = ref(false);
const statusMessage = ref("");
const errorMessage = ref("");
const overview = ref<ParamsOverviewResponse | null>(null);
const fraudModel = reactive<FraudModelParams>({
  decisionThreshold: "",
  metaWeight: "",
  gruWeight: "",
  xgbWeight: "",
});
const advancedModel = reactive<AdvancedModelParams>({
  highRiskScoreThreshold: "",
  mediumRiskScoreThreshold: "",
  highConfidenceThreshold: "",
  mediumConfidenceThreshold: "",
});
const dynamicModel = reactive<DynamicModelParams>({
  highRiskThreshold: "",
  mediumRiskThreshold: "",
  selfAttentionEnabled: true,
  adaptiveThresholdEnabled: true,
});

const dynamicSelfAttentionValue = computed({
  get: () => (dynamicModel.selfAttentionEnabled ? "on" : "off"),
  set: (value: string) => {
    dynamicModel.selfAttentionEnabled = value === "on";
  },
});

const dynamicAdaptiveValue = computed({
  get: () => (dynamicModel.adaptiveThresholdEnabled ? "on" : "off"),
  set: (value: string) => {
    dynamicModel.adaptiveThresholdEnabled = value === "on";
  },
});

onMounted(async () => {
  await loadOverview();
});

async function loadOverview() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const data = await fetchParamsOverview();
    applyOverview(data);
  } catch (error) {
    errorMessage.value = toErrorMessage(error, "参数配置加载失败");
  } finally {
    loading.value = false;
  }
}

function applyOverview(data: ParamsOverviewResponse) {
  overview.value = data;
  Object.assign(fraudModel, data.fraud_model);
  Object.assign(advancedModel, data.advanced_model);
  Object.assign(dynamicModel, data.dynamic_model);
}

async function saveFraudModel() {
  await runAction(() => saveFraudModelParams({ ...fraudModel }));
}

async function saveAdvancedModel() {
  await runAction(() => saveAdvancedModelParams({ ...advancedModel }));
}

async function saveDynamicModel() {
  await runAction(() => saveDynamicModelParams({ ...dynamicModel }));
}

async function runVersionAction(kind: "software" | "model" | "parameter") {
  const actionMap = {
    software: triggerSoftwareUpdate,
    model: triggerModelUpdate,
    parameter: triggerParameterUpdate,
  } as const;
  await runAction(actionMap[kind]);
}

async function runAction<T extends { message: string; overview: ParamsOverviewResponse }>(executor: () => Promise<T>) {
  loading.value = true;
  statusMessage.value = "";
  errorMessage.value = "";
  try {
    const response = await executor();
    statusMessage.value = response.message;
    applyOverview(response.overview);
  } catch (error) {
    errorMessage.value = toErrorMessage(error, "参数操作失败");
  } finally {
    loading.value = false;
  }
}

function toErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}
</script>
