import { createRouter, createWebHistory } from "vue-router";

import AppShell from "@/components/AppShell.vue";
import { readStoredSession } from "@/stores/auth";

const LoginView = () => import("@/views/LoginView.vue");
const WorkbenchView = () => import("@/views/WorkbenchView.vue");
const MonitorView = () => import("@/views/MonitorView.vue");
const RealtimeView = () => import("@/views/RealtimeView.vue");
const AnalysisView = () => import("@/views/AnalysisView.vue");
const FocusView = () => import("@/views/FocusView.vue");
const ReportsView = () => import("@/views/ReportsView.vue");
const ParamsView = () => import("@/views/ParamsView.vue");
const SettingsView = () => import("@/views/SettingsView.vue");
const AboutView = () => import("@/views/AboutView.vue");
const PdfViewerView = () => import("@/views/PdfViewerView.vue");

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
