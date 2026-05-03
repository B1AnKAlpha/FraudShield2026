<template>
  <section class="page-grid home-layout">
    <section class="panel">
      <header class="panel-title">系统主页</header>
      <div class="info-document compact">
        <h2>实时多模态金融欺诈链检测系统</h2>
        <p>
          系统围绕交易流水、风险链路、重点监测、多模态识别和报告导出建立统一工作台，
          将旧版 PySide 桌面端交互完整迁移到新桌面壳中。
        </p>
      </div>
      <div class="stats-strip">
        <div class="stat-box">
          <span>检测引擎</span>
          <strong>{{ systemStore.overview?.detection_engine ?? "legacy-adapter" }}</strong>
        </div>
        <div class="stat-box">
          <span>实时模式</span>
          <strong>{{ systemStore.overview?.realtime_mode ?? "sse-mock" }}</strong>
        </div>
        <div class="stat-box">
          <span>模型目录</span>
          <strong>{{ systemStore.overview?.legacy_model_exists ? "已发现" : "未发现" }}</strong>
        </div>
      </div>
    </section>

    <section class="panel">
      <header class="panel-title">运行状态</header>
      <div class="detail-grid">
        <div class="detail-row"><span>当前用户</span><strong>{{ authStore.displayName }}</strong></div>
        <div class="detail-row"><span>账户级别</span><strong>{{ authStore.accountRole }}</strong></div>
        <div class="detail-row"><span>服务名称</span><strong>{{ systemStore.overview?.server_name ?? "FraudShield 2026 API" }}</strong></div>
        <div class="detail-row"><span>模型路径</span><strong>{{ systemStore.overview?.legacy_model_dir ?? "--" }}</strong></div>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { onMounted } from "vue";

import { useAuthStore } from "@/stores/auth";
import { useSystemStore } from "@/stores/system";

const authStore = useAuthStore();
const systemStore = useSystemStore();

onMounted(() => {
  if (!systemStore.overview && !systemStore.loading) {
    void systemStore.loadOverview();
  }
});
</script>
