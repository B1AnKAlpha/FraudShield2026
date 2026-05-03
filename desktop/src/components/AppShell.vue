<template>
  <div :class="shellClasses">
    <aside class="legacy-sidebar">
      <div class="legacy-brand">
        <div class="legacy-brand-image">
          <img :src="sidebarLogo" alt="FraudShield 标识" />
        </div>
        <div class="legacy-brand-copy">
          <div class="legacy-brand-title">金盾FraudShield</div>
          <div class="legacy-brand-subtitle">AI赋能金融安全，从此更安心</div>
        </div>
      </div>

      <button class="legacy-toggle" type="button" @click="toggleSidebar">
        <span class="legacy-nav-icon legacy-icon-wrap" v-html="icons.menu"></span>
        <span class="legacy-sidebar-text">隐藏列表</span>
      </button>

      <nav class="legacy-nav">
        <RouterLink
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="legacy-nav-item"
        >
          <span class="legacy-nav-icon legacy-icon-wrap" v-html="item.icon"></span>
          <span class="legacy-sidebar-text">{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="legacy-sidebar-footer">
        <RouterLink to="/about" class="legacy-nav-item">
          <span class="legacy-nav-icon legacy-icon-wrap" v-html="icons.info"></span>
          <span class="legacy-sidebar-text">软件信息</span>
        </RouterLink>
        <button class="legacy-nav-item legacy-nav-button" type="button" @click="handleLogout">
          <span class="legacy-nav-icon legacy-icon-wrap" v-html="icons.logout"></span>
          <span class="legacy-sidebar-text">退出登录</span>
        </button>
      </div>
    </aside>

    <section class="legacy-main">
      <header class="legacy-titlebar">
        <div class="legacy-titlebar-left">金盾·FraudShield - 金融数据欺诈检测系统</div>
        <div class="legacy-titlebar-right">
          <button
            class="window-action settings-trigger"
            :class="{ active: settingsOpen }"
            type="button"
            aria-label="设置"
            @click="toggleSettings"
          >
            <span class="window-icon" v-html="icons.settings"></span>
          </button>
          <button class="window-action" type="button" aria-label="最小化">
            <span class="window-symbol">−</span>
          </button>
          <button class="window-action" type="button" aria-label="最大化">
            <span class="window-symbol">□</span>
          </button>
          <button class="window-action close" type="button" aria-label="关闭">
            <span class="window-symbol">×</span>
          </button>
        </div>
      </header>

      <div class="legacy-main-body">
        <main class="legacy-workspace">
          <section class="legacy-workspace-frame">
            <RouterView />
          </section>
        </main>

        <aside class="legacy-settings-drawer" :aria-hidden="!settingsOpen">
          <div class="legacy-settings-accent"></div>
          <div class="legacy-settings-header">
            <div class="legacy-settings-title">
              <span class="legacy-settings-icon legacy-icon-wrap" v-html="icons.settings"></span>
              <span>设置</span>
            </div>
            <button
              class="legacy-settings-close"
              type="button"
              aria-label="关闭设置"
              @click="settingsOpen = false"
            >
              ×
            </button>
          </div>

          <div class="legacy-settings-menu">
            <button class="legacy-settings-item" type="button" @click="toggleTheme">
              <span class="legacy-nav-icon legacy-icon-wrap" v-html="icons.theme"></span>
              <span>改变主题</span>
              <strong>{{ themeMode === "light" ? "浅色" : (themeMode === "modern" ? "现代" : "深色") }}</strong>
            </button>

            <button class="legacy-settings-item" type="button" @click="handleCheckUpdate">
              <span class="legacy-nav-icon legacy-icon-wrap" v-html="icons.update"></span>
              <span>检查更新</span>
              <strong>{{ versionLabel }}</strong>
            </button>

            <RouterLink to="/about" class="legacy-settings-item" @click="settingsOpen = false">
              <span class="legacy-nav-icon legacy-icon-wrap" v-html="icons.info"></span>
              <span>软件信息</span>
              <strong>版本</strong>
            </RouterLink>

            <button class="legacy-settings-item danger" type="button" @click="handleLogout">
              <span class="legacy-nav-icon legacy-icon-wrap" v-html="icons.logout"></span>
              <span>安全退出</span>
              <strong>退出</strong>
            </button>
          </div>

          <div class="legacy-settings-footer">
            <div class="legacy-settings-footer-name">{{ authStore.displayName }}</div>
            <div class="legacy-settings-footer-role">{{ authStore.accountRole }}</div>
          </div>
        </aside>
      </div>

      <footer class="legacy-statusbar">
        <span>© 2025 金盾 FraudShield 项目组 版权所有，仅用于鲁抗机器人开发者大赛展示与评审</span>
        <span>账户级别：{{ authStore.accountRole }}</span>
        <span>v1.0.3</span>
      </footer>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router";

import sidebarLogo from "@/assets/sidebar-logo.png";
import { triggerSoftwareUpdate } from "@/api/modules/params";
import { useAuthStore } from "@/stores/auth";
import { useSystemStore } from "@/stores/system";
import { icons } from "@/components/icons";

const SIDEBAR_STATE_KEY = "fraudshield2026.sidebar-collapsed";
const THEME_MODE_KEY = "fraudshield2026.theme-mode";

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const systemStore = useSystemStore();

const navItems = [
  { path: "/home", label: "主页", icon: icons.home },
  { path: "/monitor", label: "实时监测", icon: icons.monitor },
  { path: "/alerts", label: "实时告警", icon: icons.alerts },
  { path: "/analysis", label: "实时分析", icon: icons.analysis },
  { path: "/focus", label: "重点监测", icon: icons.focus },
  { path: "/logs", label: "历史日志", icon: icons.logs },
  { path: "/params", label: "参数调整", icon: icons.params },
  { path: "/accounts", label: "账户设置", icon: icons.account },
] as const;

const sidebarCollapsed = ref(false);
const settingsOpen = ref(false);
const themeMode = ref<"light" | "dark" | "modern">("light");

const shellClasses = computed(() => [
  "legacy-shell",
  `theme-${themeMode.value}`,
  {
    "sidebar-collapsed": sidebarCollapsed.value,
    "settings-open": settingsOpen.value,
  },
]);

const versionLabel = computed(() => systemStore.paramsOverview?.versions.software.current ?? "v1.0.3");

onMounted(() => {
  if (!systemStore.overview && !systemStore.loading) {
    void systemStore.loadOverview();
  }

  if (typeof window !== "undefined") {
    sidebarCollapsed.value = window.localStorage.getItem(SIDEBAR_STATE_KEY) === "1";

    const storedTheme = window.localStorage.getItem(THEME_MODE_KEY);
    if (storedTheme === "light" || storedTheme === "dark" || storedTheme === "modern") {
      themeMode.value = storedTheme;
    }
  }
});

watch(sidebarCollapsed, (value) => {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(SIDEBAR_STATE_KEY, value ? "1" : "0");
  }
});

watch(themeMode, (value) => {
  if (typeof window !== "undefined") {
    window.localStorage.setItem(THEME_MODE_KEY, value);
  }
});

watch(
  () => route.fullPath,
  () => {
    settingsOpen.value = false;
  },
);

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value;
}

function toggleSettings() {
  settingsOpen.value = !settingsOpen.value;
}

function toggleTheme() {
  if (themeMode.value === "light") {
      themeMode.value = "modern";
    } else if (themeMode.value === "modern") {
      themeMode.value = "dark";
    } else {
      themeMode.value = "light";
    }
}

function handleCheckUpdate() {
  void (async () => {
    try {
      const response = await triggerSoftwareUpdate();
      systemStore.setParamsOverview(response.overview);
      window.alert(response.message);
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "检查更新失败");
    }
  })();
}

async function handleLogout() {
  settingsOpen.value = false;
  await authStore.logoutRemote();
  await router.replace("/login");
}
</script>
