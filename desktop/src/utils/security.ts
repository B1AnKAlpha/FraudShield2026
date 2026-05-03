export interface LoginSecurityCheckResult {
  machine_code: string;
  integrity_checked: boolean;
  integrity_message: string;
}

function isTauriRuntime() {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export async function runLoginSecurityChecks(): Promise<LoginSecurityCheckResult> {
  if (!isTauriRuntime()) {
    return {
      machine_code: "",
      integrity_checked: false,
      integrity_message: "浏览器预览模式已跳过本地安全检查",
    };
  }

  try {
    const { invoke } = await import("@tauri-apps/api/core");
    return await invoke<LoginSecurityCheckResult>("run_login_security_checks");
  } catch (error) {
    throw new Error(error instanceof Error ? error.message : "本地安全检查失败");
  }
}
