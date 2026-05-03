import { createRouter, createWebHistory } from "vue-router";

import AppShell from "@/components/AppShell.vue";
import { readStoredSession } from "@/stores/auth";
import AboutView from "@/views/AboutView.vue";
import AnalysisView from "@/views/AnalysisView.vue";
import FocusView from "@/views/FocusView.vue";
import LoginView from "@/views/LoginView.vue";
import MonitorView from "@/views/MonitorView.vue";
import ParamsView from "@/views/ParamsView.vue";
import PdfViewerView from "@/views/PdfViewerView.vue";
import RealtimeView from "@/views/RealtimeView.vue";
import ReportsView from "@/views/ReportsView.vue";
import SettingsView from "@/views/SettingsView.vue";
import WorkbenchView from "@/views/WorkbenchView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      component: LoginView,
      meta: { guestOnly: true, title: "登录" },
    },
    {
      path: "/",
      component: AppShell,
      meta: { requiresAuth: true },
      children: [
        { path: "", redirect: "/home" },
        { path: "home", component: WorkbenchView, meta: { title: "主页" } },
        { path: "monitor", component: MonitorView, meta: { title: "实时监测" } },
        { path: "alerts", component: RealtimeView, meta: { title: "实时告警" } },
        { path: "analysis", component: AnalysisView, meta: { title: "实时分析" } },
        { path: "focus", component: FocusView, meta: { title: "重点监测" } },
        { path: "logs", component: ReportsView, meta: { title: "历史日志" } },
        { path: "params", component: ParamsView, meta: { title: "参数调整" } },
        { path: "accounts", component: SettingsView, meta: { title: "账户设置" } },
        { path: "about", component: AboutView, meta: { title: "软件信息" } },
      ],
    },
    {
      path: "/report-viewer",
      component: PdfViewerView,
      meta: { requiresAuth: true, title: "PDF 报告" },
    },
  ],
});

router.beforeEach((to) => {
  const session = readStoredSession();
  const isAuthenticated = Boolean(session?.accessToken);

  if (to.meta.requiresAuth && !isAuthenticated) {
    return "/login";
  }

  if (to.meta.guestOnly && isAuthenticated) {
    return "/home";
  }

  return true;
});

export default router;
