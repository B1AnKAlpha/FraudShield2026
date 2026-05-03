<template>
  <section class="page-grid accounts-layout account-settings-layout">
    <section class="panel account-form-panel">
      <header class="panel-title">修改个人信息</header>

      <div class="form-grid single account-form">
        <label class="inline-form-row">
          <span>联系电话：</span>
          <input v-model.trim="profileForm.phone" />
        </label>
        <label class="inline-form-row">
          <span>操作员姓名：</span>
          <input v-model.trim="profileForm.display_name" />
        </label>
        <label class="inline-form-row">
          <span>操作员邮箱：</span>
          <input v-model.trim="profileForm.email" />
        </label>
        <label class="inline-form-row">
          <span>单位名称：</span>
          <input v-model.trim="profileForm.organization" />
        </label>
        <label class="inline-form-row">
          <span>员工工号：</span>
          <input v-model.trim="profileForm.job_id" />
        </label>
      </div>

      <div class="account-token-row">
        <label class="inline-form-row">
          <span>动态密码：</span>
          <input v-model.trim="profileForm.token_code" maxlength="6" />
        </label>
      </div>

      <div class="panel-actions">
        <button class="legacy-button wide" type="button" :disabled="savingProfile" @click="saveProfile">
          {{ savingProfile ? "正在保存..." : "修改上传" }}
        </button>
      </div>

      <div v-if="profileError || profileMessage" class="inline-feedback" :class="{ error: Boolean(profileError) }">
        {{ profileError || profileMessage }}
      </div>
    </section>

    <section class="panel account-management-panel">
      <header class="panel-title">账户修改</header>

      <template v-if="isAdmin">
        <div class="table-scroll">
          <table class="legacy-table tall-table">
            <thead>
              <tr>
                <th>账号</th>
                <th>姓名</th>
                <th>邮箱</th>
                <th>单位名称</th>
                <th>工号</th>
                <th>联系电话</th>
                <th>修改</th>
                <th>删除</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in accounts" :key="item.username">
                <td>{{ item.username }}</td>
                <td>{{ item.display_name }}</td>
                <td>{{ item.email }}</td>
                <td>{{ item.organization }}</td>
                <td>{{ item.job_id }}</td>
                <td>{{ item.phone }}</td>
                <td><button class="table-action" type="button" @click="beginEdit(item)">修改</button></td>
                <td>
                  <button class="table-action danger" type="button" @click="removeAccount(item.username)">
                    删除
                  </button>
                </td>
              </tr>
              <tr v-if="accounts.length === 0" class="table-empty-row">
                <td colspan="8">暂无账户数据</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="panel-actions">
          <button class="legacy-button wide" type="button" @click="beginCreate">添加账户</button>
        </div>
      </template>

      <div v-else class="account-readonly-note">当前账户无账户管理权限。</div>
    </section>

    <div v-if="editorOpen" class="account-modal-backdrop" @click.self="closeEditor">
      <section class="account-modal">
        <header class="account-modal-header">
          <div class="account-modal-title">
            {{ editorMode === "create" ? "新增账户" : `编辑账户：${editorUsername}` }}
          </div>
          <button class="account-modal-close" type="button" @click="closeEditor">×</button>
        </header>

        <div class="form-grid single account-modal-form">
          <label class="inline-form-row">
            <span>账号：</span>
            <input v-model.trim="editorForm.username" :disabled="editorMode === 'edit'" />
          </label>
          <label class="inline-form-row">
            <span>姓名：</span>
            <input v-model.trim="editorForm.display_name" />
          </label>
          <label class="inline-form-row">
            <span>角色：</span>
            <select v-model="editorForm.role" class="legacy-select">
              <option value="admin">管理员</option>
              <option value="analyst">分析员</option>
            </select>
          </label>
          <label class="inline-form-row">
            <span>邮箱：</span>
            <input v-model.trim="editorForm.email" />
          </label>
          <label class="inline-form-row">
            <span>联系电话：</span>
            <input v-model.trim="editorForm.phone" />
          </label>
          <label class="inline-form-row">
            <span>单位名称：</span>
            <input v-model.trim="editorForm.organization" />
          </label>
          <label class="inline-form-row">
            <span>员工工号：</span>
            <input v-model.trim="editorForm.job_id" />
          </label>
          <label class="inline-form-row">
            <span>{{ editorMode === "create" ? "初始密码：" : "重置密码：" }}</span>
            <input v-model.trim="editorForm.password" />
          </label>
          <label v-if="editorMode === 'edit'" class="inline-form-row">
            <span>账户状态：</span>
            <select v-model="editorForm.is_active" class="legacy-select">
              <option :value="true">启用</option>
              <option :value="false">停用</option>
            </select>
          </label>
        </div>

        <div class="panel-actions account-modal-actions">
          <button class="legacy-button wide" type="button" :disabled="savingAccount" @click="submitAccount">
            {{ savingAccount ? "提交中..." : editorMode === "create" ? "创建账户" : "保存修改" }}
          </button>
          <button
            v-if="editorMode === 'edit'"
            class="legacy-button wide muted"
            type="button"
            :disabled="savingAccount"
            @click="issueTotp"
          >
            重置动态令牌
          </button>
        </div>

        <div
          v-if="accountError || accountMessage"
          class="inline-feedback"
          :class="{ error: Boolean(accountError) }"
        >
          {{ accountError || accountMessage }}
        </div>
      </section>
    </div>

    <div v-if="provisioningDialogOpen && provisioning" class="account-modal-backdrop" @click.self="closeProvisioningDialog">
      <section class="provisioning-modal">
        <header class="account-modal-header">
          <div class="account-modal-title">绑定二次验证密钥</div>
          <button class="account-modal-close" type="button" @click="closeProvisioningDialog">×</button>
        </header>

        <p class="provisioning-copy">
          {{ provisioningDialogMessage }}
        </p>

        <div v-if="provisioningQrCode" class="provisioning-qr-wrap">
          <img :src="provisioningQrCode" alt="动态令牌二维码" class="provisioning-qr-image" />
        </div>

        <div class="panel-actions account-modal-actions">
          <button class="legacy-button wide" type="button" @click="closeProvisioningDialog">我已完成绑定</button>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";

import {
  createAccount,
  deleteAccount,
  fetchAccounts,
  resetAccountTotp,
  updateAccount,
} from "@/api/modules/auth";
import { useAuthStore } from "@/stores/auth";
import type {
  AccountCreateRequest,
  AccountUpdateRequest,
  TotpProvisioning,
  UserProfile,
} from "@/types/auth";
import { renderQrCodeDataUrl } from "@/utils/qrcode";

const authStore = useAuthStore();

const isAdmin = computed(() => authStore.user?.role === "admin");

const profileForm = reactive({
  display_name: "",
  organization: "",
  phone: "",
  email: "",
  job_id: "",
  token_code: "",
});

const profileMessage = ref("");
const profileError = ref("");
const savingProfile = ref(false);

const accounts = ref<UserProfile[]>([]);
const savingAccount = ref(false);
const accountMessage = ref("");
const accountError = ref("");
const provisioning = ref<TotpProvisioning | null>(null);
const provisioningQrCode = ref("");
const provisioningDialogOpen = ref(false);
const provisioningDialogMessage = ref("");
const editorMode = ref<"create" | "edit">("create");
const editorUsername = ref("");
const editorOpen = ref(false);

const editorForm = reactive({
  username: "",
  display_name: "",
  role: "analyst" as "admin" | "analyst",
  organization: "",
  phone: "",
  email: "",
  job_id: "",
  password: "",
  is_active: true,
});

function syncProfileForm() {
  profileForm.display_name = authStore.user?.display_name ?? "";
  profileForm.organization = authStore.user?.organization ?? "";
  profileForm.phone = authStore.user?.phone ?? "";
  profileForm.email = authStore.user?.email ?? "";
  profileForm.job_id = authStore.user?.job_id ?? "";
  profileForm.token_code = "";
}

function resetEditor() {
  editorForm.username = "";
  editorForm.display_name = "";
  editorForm.role = "analyst";
  editorForm.organization = "FraudShield Lab";
  editorForm.phone = "";
  editorForm.email = "";
  editorForm.job_id = "";
  editorForm.password = "";
  editorForm.is_active = true;
}

function closeEditor() {
  editorOpen.value = false;
  accountMessage.value = "";
  accountError.value = "";
}

function closeProvisioningDialog() {
  provisioningDialogOpen.value = false;
  provisioningDialogMessage.value = "";
  provisioning.value = null;
  provisioningQrCode.value = "";
}

async function openProvisioningDialog(payload: TotpProvisioning | null, message: string) {
  if (!payload) {
    return;
  }

  closeEditor();
  provisioningDialogOpen.value = false;
  provisioning.value = null;
  provisioningQrCode.value = "";
  provisioningDialogMessage.value = "";

  await nextTick();

  provisioning.value = payload;
  provisioningQrCode.value = await renderQrCodeDataUrl(payload.otpauth_url);
  provisioningDialogMessage.value = message;
  provisioningDialogOpen.value = true;
}

function beginCreate() {
  editorMode.value = "create";
  editorUsername.value = "";
  resetEditor();
  accountMessage.value = "";
  accountError.value = "";
  editorOpen.value = true;
}

function beginEdit(item: UserProfile) {
  editorMode.value = "edit";
  editorUsername.value = item.username;
  editorForm.username = item.username;
  editorForm.display_name = item.display_name;
  editorForm.role = item.role as "admin" | "analyst";
  editorForm.organization = item.organization;
  editorForm.phone = item.phone;
  editorForm.email = item.email;
  editorForm.job_id = item.job_id;
  editorForm.password = "";
  editorForm.is_active = item.is_active;
  accountMessage.value = "";
  accountError.value = "";
  editorOpen.value = true;
}

async function loadAccounts() {
  if (!isAdmin.value) {
    return;
  }

  accountError.value = "";
  try {
    const response = await fetchAccounts();
    accounts.value = response.items;
  } catch (error) {
    accountError.value = error instanceof Error ? error.message : "加载账户列表失败";
  }
}

async function saveProfile() {
  profileError.value = "";
  profileMessage.value = "";
  savingProfile.value = true;
  try {
    await authStore.saveProfile({
      display_name: profileForm.display_name,
      organization: profileForm.organization,
      phone: profileForm.phone,
      email: profileForm.email,
      job_id: profileForm.job_id,
      token_code: profileForm.token_code,
    });
    profileMessage.value = "个人信息已更新。";
    profileForm.token_code = "";
  } catch (error) {
    profileError.value = error instanceof Error ? error.message : "保存个人信息失败";
  } finally {
    savingProfile.value = false;
  }
}

async function submitAccount() {
  accountError.value = "";
  accountMessage.value = "";
  savingAccount.value = true;
  try {
    if (editorMode.value === "create") {
      const payload: AccountCreateRequest = {
        username: editorForm.username,
        password: editorForm.password,
        display_name: editorForm.display_name,
        role: editorForm.role,
        organization: editorForm.organization,
        phone: editorForm.phone,
        email: editorForm.email,
        job_id: editorForm.job_id,
      };
      const response = await createAccount(payload);
      await openProvisioningDialog(
        response.provisioning,
        `用户【${response.user.username}】已成功添加！请使用验证器扫码以下二维码绑定账号：`,
      );
      accountMessage.value = "";
    } else {
      const payload: AccountUpdateRequest = {
        display_name: editorForm.display_name,
        role: editorForm.role,
        organization: editorForm.organization,
        phone: editorForm.phone,
        email: editorForm.email,
        job_id: editorForm.job_id,
        is_active: editorForm.is_active,
      };
      if (editorForm.password.trim()) {
        payload.password = editorForm.password;
      }
      await updateAccount(editorUsername.value, payload);
      accountMessage.value = "账户信息已更新。";
    }

    await loadAccounts();
  } catch (error) {
    accountError.value = error instanceof Error ? error.message : "提交账户信息失败";
  } finally {
    savingAccount.value = false;
  }
}

async function removeAccount(username: string) {
  if (!window.confirm(`确认删除账户 ${username} 吗？`)) {
    return;
  }

  accountError.value = "";
  accountMessage.value = "";
  try {
    await deleteAccount(username);
    accountMessage.value = "账户已删除。";
    await loadAccounts();
  } catch (error) {
    accountError.value = error instanceof Error ? error.message : "删除账户失败";
  }
}

async function issueTotp() {
  accountError.value = "";
  accountMessage.value = "";
  provisioning.value = null;
  provisioningQrCode.value = "";
  try {
    const response = await resetAccountTotp(editorUsername.value);
    await openProvisioningDialog(
      response.provisioning,
      `用户【${editorUsername.value}】动态令牌已重置，请使用验证器重新扫码绑定：`,
    );
    accountMessage.value = "";
    await loadAccounts();
  } catch (error) {
    accountError.value = error instanceof Error ? error.message : "重置动态令牌失败";
  }
}

watch(
  () => authStore.user,
  () => {
    syncProfileForm();
  },
  { immediate: true },
);

watch(
  isAdmin,
  (value) => {
    if (value) {
      void loadAccounts();
      return;
    }
    accounts.value = [];
  },
  { immediate: true },
);

onMounted(() => {
  syncProfileForm();
});
</script>
