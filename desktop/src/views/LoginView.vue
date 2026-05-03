<template>
  <main class="beautiful-login">
    <div class="login-container">
      <!-- 左侧品牌展示区 -->
      <aside class="brand-showcase">
        <div class="brand-content">
          <div class="brand-logo">金盾实验室</div>
          <h1 class="brand-title">诈骗防御系统<br><span class="highlight">FraudShield 2026</span></h1>
          <p class="brand-desc">新一代多模态金融欺诈链检测终端</p>
          
          <div class="features-grid">
            <div class="feature-item">
              <div class="icon"></div>
              <div class="text">双重认证保护</div>
            </div>
            <div class="feature-item">
              <div class="icon"></div>
              <div class="text">实时风险监控</div>
            </div>
            <div class="feature-item">
              <div class="icon"></div>
              <div class="text">全天候行为检测</div>
            </div>
          </div>
        </div>
        <div class="showcase-bg-effect"></div>
      </aside>

      <!-- 右侧登录表单区 -->
      <section class="login-form-wrapper">
        <div class="login-form-inner">
          <div class="form-header">
            <h2>欢迎登录</h2>
            <p>基于硬件动态指令与强校验体系</p>
          </div>

          <form class="modern-form" @submit.prevent="handleSubmit">
            <div class="form-group">
              <label>用户名</label>
              <div class="input-wrap">
                <span class="input-icon"></span>
                <input v-model.trim="username" autocomplete="username" placeholder="请输入账号" required />
              </div>
            </div>

            <div class="form-group">
              <label>密码</label>
              <div class="input-wrap">
                <span class="input-icon"></span>
                <input
                  v-model="password"
                  :type="showPassword ? 'text' : 'password'"
                  autocomplete="current-password"
                  placeholder="请输入密码"
                  required
                />
              </div>
            </div>

            <div class="form-group">
              <label>动态令牌验证</label>
              <div class="input-wrap token-wrap">
                <span class="input-icon"></span>
                <input
                  v-model.trim="tokenCode"
                  inputmode="numeric"
                  maxlength="6"
                  :type="showPassword ? 'text' : 'password'"
                  placeholder="6位动态口令"
                  required
                />
              </div>
            </div>

            <div class="form-options">
              <label class="custom-checkbox">
                <input v-model="showPassword" type="checkbox" />
                <span class="checkmark"></span>
                <span class="label-text">显示密码明文</span>
              </label>
            </div>

            <button type="submit" class="submit-btn" :class="{ 'is-loading': authStore.loading }" :disabled="authStore.loading">
              <span class="btn-text">{{ authStore.loading ? '安全验证中...' : '进入系统' }}</span>
              <span class="btn-loader" v-if="authStore.loading"></span>
            </button>
            
            <transition name="fade">
              <div v-if="statusText" class="status-alert" :class="{ 'is-error': localError || authStore.error }">
                {{ statusText }}
              </div>
            </transition>
          </form>
        </div>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import { ApiError } from "@/api/client";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const authStore = useAuthStore();

const username = ref("");
const password = ref("");
const tokenCode = ref("");
const showPassword = ref(false);
const localError = ref("");

const statusText = computed(() => localError.value || authStore.error);

async function handleSubmit() {
  localError.value = "";

  try {
    await authStore.loginWithLegacyForm({
      username: username.value,
      password: password.value,
      token_code: tokenCode.value,
    });
    await router.replace("/home");
  } catch (error) {
    if (error instanceof ApiError && error.code === "TOTP_NOT_BOUND") {
      localError.value = "当前账户尚未绑定动态令牌，请联系管理员处理。";
      return;
    }
    localError.value = error instanceof Error ? error.message : "登录失败";
  }
}
</script>

<style scoped>
/* 现代风登录页重构 */
.beautiful-login {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f0f4f8;
  padding: 2rem;
  font-family: system-ui, -apple-system, sans-serif;
  color: #1e293b;
}

.login-container {
  display: flex;
  width: 100%;
  max-width: 1100px;
  min-height: 600px;
  background: #ffffff;
  border-radius: 20px;
  box-shadow: 0 20px 40px rgba(0,0,0,0.08);
  overflow: hidden;
}

/* 左侧品牌区 */
.brand-showcase {
  flex: 5;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  color: white;
  padding: 3.5rem;
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: center;
  overflow: hidden;
}

.showcase-bg-effect {
  position: absolute;
  top: -20%;
  right: -20%;
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, rgba(56,189,248,0.15) 0%, transparent 70%);
  border-radius: 50%;
  pointer-events: none;
}

.brand-logo {
  font-size: 1.25rem;
  font-weight: 600;
  color: #94a3b8;
  margin-bottom: 2rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.brand-title {
  font-size: 2.5rem;
  font-weight: 700;
  line-height: 1.3;
  margin-bottom: 1rem;
}

.brand-title .highlight {
  background: linear-gradient(to right, #38bdf8, #818cf8);
  -webkit-background-clip: text;
  color: transparent;
}

.brand-desc {
  font-size: 1.1rem;
  color: #cbd5e1;
  margin-bottom: 3.5rem;
}

.features-grid {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  margin-top: auto;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.feature-item .icon {
  width: 40px;
  height: 40px;
  background: rgba(255,255,255,0.05);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.25rem;
  border: 1px solid rgba(255,255,255,0.1);
}

.feature-item .text {
  font-size: 1rem;
  color: #f1f5f9;
}

/* 右侧表单区 */
.login-form-wrapper {
  flex: 4;
  padding: 3.5rem 4rem;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: #ffffff;
}

.form-header {
  margin-bottom: 2.5rem;
}

.form-header h2 {
  font-size: 2rem;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 0.5rem;
}

.form-header p {
  color: #64748b;
  font-size: 0.95rem;
}

.modern-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.form-group label {
  display: block;
  font-size: 0.9rem;
  font-weight: 600;
  color: #334155;
  margin-bottom: 0.5rem;
}

.input-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.input-icon {
  position: absolute;
  left: 1rem;
  color: #94a3b8;
  font-size: 1.1rem;
  pointer-events: none;
}

.input-wrap input {
  width: 100%;
  padding: 0.85rem 1rem 0.85rem 3rem;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  font-size: 1rem;
  transition: all 0.2s;
  background: #f8fafc;
  color: #1e293b;
  box-sizing: border-box;
}

.input-wrap input:focus {
  outline: none;
  border-color: #38bdf8;
  background: #ffffff;
  box-shadow: 0 0 0 3px rgba(56,189,248,0.1);
}

.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 0.5rem;
  margin-bottom: 0.5rem;
}

.custom-checkbox {
  display: inline-flex;
  align-items: center;
  flex-direction: row;
  gap: 0.35rem;
  cursor: pointer;
  font-size: 0.9rem;
  color: #64748b;
  white-space: nowrap;
}

.forgot-link {
  font-size: 0.85rem;
  color: #10b981;
  text-decoration: none;
  pointer-events: none;
}

.submit-btn {
  background: #2563eb;
  color: white;
  border: none;
  padding: 1rem;
  border-radius: 10px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s, transform 0.1s;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.5rem;
  width: 100%;
}

.submit-btn:hover:not(:disabled) {
  background: #1d4ed8;
  transform: translateY(-1px);
}

.submit-btn:disabled {
  background: #94a3b8;
  cursor: not-allowed;
}

.status-alert {
  padding: 0.75rem 1rem;
  border-radius: 8px;
  background: #f1f5f9;
  color: #64748b;
  font-size: 0.9rem;
  border: 1px solid #e2e8f0;
  margin-top: 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.status-alert.is-error {
  background: #fef2f2;
  color: #ef4444;
  border-color: #fecaca;
}

/* 响应式 */
@media (max-width: 900px) {
  .login-container {
    flex-direction: column;
  }
  .brand-showcase {
    flex: 1;
    padding: 2.5rem;
  }
  .login-form-wrapper {
    flex: 1;
    padding: 2.5rem;
  }
  .features-grid {
    display: none;
  }
}
</style>
