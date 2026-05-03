<template>
  <section class="page-grid single about-layout">
    <section class="panel about-hero-panel">
      <header class="panel-title">软件信息</header>
      <div class="about-version-grid">
        <div class="about-version-card">
          <div class="about-version-label">当前软件版本</div>
          <strong>{{ paramsOverview?.versions.software.current ?? "v1.0.3" }}</strong>
          <span>云端最新版本 {{ paramsOverview?.versions.software.latest ?? "v1.0.3" }}</span>
        </div>
        <div class="about-version-card">
          <div class="about-version-label">当前模型版本</div>
          <strong>{{ paramsOverview?.versions.model.current ?? "--" }}</strong>
          <span>云端最新版本 {{ paramsOverview?.versions.model.latest ?? "--" }}</span>
        </div>
        <div class="about-version-card">
          <div class="about-version-label">当前参数版本</div>
          <strong>{{ paramsOverview?.versions.parameter.current ?? "--" }}</strong>
          <span>云端最新版本 {{ paramsOverview?.versions.parameter.latest ?? "--" }}</span>
        </div>
      </div>
    </section>

    <section class="panel about-document-panel">
      <div class="about-info-grid">
        <div class="about-info-block">
          <div class="about-info-title">系统名称</div>
          <div class="about-info-value">金盾 FraudShield 金融数据欺诈检测系统</div>
        </div>
        <div class="about-info-block">
          <div class="about-info-title">检测引擎</div>
          <div class="about-info-value">{{ overview?.detection_engine ?? "Hybrid + Realtime Light Model" }}</div>
        </div>
        <div class="about-info-block">
          <div class="about-info-title">实时模式</div>
          <div class="about-info-value">{{ overview?.realtime_mode ?? "--" }}</div>
        </div>
        <div class="about-info-block">
          <div class="about-info-title">服务名称</div>
          <div class="about-info-value">{{ overview?.server_name ?? "FraudShield 2026 API" }}</div>
        </div>
      </div>

      <div class="info-document compact about-document-copy">
        <h3>系统说明</h3>
        <p>本系统用于金融欺诈风险识别、实时监测、链路分析、重点关注与历史报告管理。</p>
        <h3>运行说明</h3>
        <p>当前桌面端负责交互展示，检测与实时分析由服务端统一处理。</p>
        <h3>版权说明</h3>
        <p>版权所有 2025 金盾 FraudShield 项目组。当前版本仅用于展示、联调与评审环境。</p>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted } from "vue";

import { useSystemStore } from "@/stores/system";

const systemStore = useSystemStore();

const overview = computed(() => systemStore.overview);
const paramsOverview = computed(() => systemStore.paramsOverview);

onMounted(() => {
  if ((!systemStore.overview || !systemStore.paramsOverview) && !systemStore.loading) {
    void systemStore.loadOverview();
  }
});
</script>
