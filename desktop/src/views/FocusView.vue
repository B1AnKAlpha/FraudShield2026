<template>
  <section class="page-grid focus-layout">
    <section class="panel">
      <header class="panel-title">操作日志列表</header>
      <div class="table-scroll">
        <table class="legacy-table medium-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>操作者id</th>
              <th>导出账号</th>
              <th>删除日志</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in logList"
              :key="item.job_id"
              class="focus-log-row"
              :class="{ active: item.job_id === selectedJobId }"
              @click="selectLog(item.job_id)"
            >
              <td>
                <div>{{ formatTime(item.created_at) }}</div>
                <small class="log-meta">{{ item.account_count }} 个账号</small>
              </td>
              <td>{{ item.operator }}</td>
              <td class="action-cell">
                <button class="table-action success" type="button" @click.stop="exportAccounts(item.job_id)">
                  导出账号
                </button>
              </td>
              <td class="action-cell">
                <button class="table-action danger" type="button" @click.stop="deleteLog(item.job_id)">
                  删除日志
                </button>
              </td>
            </tr>
            <tr v-if="logList.length === 0" class="table-empty-row">
              <td colspan="4">暂无操作日志</td>
            </tr>
          </tbody>
        </table>
      </div>

      <textarea
        v-model.trim="accountInput"
        class="legacy-textarea compact focus-input"
        placeholder="请在此输入需要操作的交易账户"
      />
      <div class="panel-actions action-row-triple">
        <button class="legacy-button wide" type="button" :disabled="submitting" @click="addAccount">加入重点关注</button>
        <button class="legacy-button wide" type="button" :disabled="submitting" @click="removeAccount">解除重点关注</button>
        <select v-model="trackMode" class="legacy-select full-select" :disabled="submitting">
          <option value="normal">正常追踪</option>
          <option value="deep">深度追踪</option>
        </select>
      </div>
      <div class="status-inline" v-if="message">{{ message }}</div>
    </section>

    <section class="panel panel-slim">
      <header class="panel-title">操作账号</header>
      <div class="table-scroll">
        <table class="legacy-table single-column tall-table">
          <thead>
            <tr><th>交易账号</th></tr>
          </thead>
          <tbody>
            <tr v-for="item in localFocusList" :key="`local-${item.account}`"><td>{{ item.account }}</td></tr>
            <tr v-if="localFocusList.length === 0" class="table-empty-row"><td>暂无操作账号</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="panel panel-slim">
      <header class="panel-title">云端重点关注账号</header>
      <div class="table-scroll">
        <table class="legacy-table single-column tall-table">
          <thead>
            <tr><th>交易账号</th></tr>
          </thead>
          <tbody>
            <tr v-for="item in cloudFocusList" :key="`cloud-${item.account}`">
              <td>
                <div>{{ item.account }}</div>
                <small class="log-meta">
                  {{ item.mode === "deep" ? "深度追踪" : "正常追踪" }}
                  <span v-if="item.source_account"> · 来源 {{ item.source_account }}</span>
                </small>
              </td>
            </tr>
            <tr v-if="cloudFocusList.length === 0" class="table-empty-row"><td>暂无云端重点关注账号</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";

import { ApiError } from "@/api/client";
import { addFocusAccount, fetchFocusOverview, hideFocusLog, removeFocusAccount } from "@/api/modules/focus";
import type { FocusCloudAccountItem, FocusLocalAccountItem, FocusLogItem, FocusMode } from "@/types/focus";

const accountInput = ref("");
const trackMode = ref<FocusMode>("normal");
const message = ref("");
const submitting = ref(false);
const selectedJobId = ref<string | null>(null);
const localFocusList = ref<FocusLocalAccountItem[]>([]);
const cloudFocusList = ref<FocusCloudAccountItem[]>([]);
const logList = ref<FocusLogItem[]>([]);

onMounted(async () => {
  await loadOverview();
});

async function loadOverview(jobId?: string | null) {
  try {
    const response = await fetchFocusOverview(jobId ?? undefined);
    selectedJobId.value = response.selected_job_id;
    logList.value = response.logs;
    localFocusList.value = response.local_accounts;
    cloudFocusList.value = response.cloud_accounts;
  } catch (error) {
    message.value = toErrorMessage(error, "重点监测数据加载失败");
  }
}

async function selectLog(jobId: string) {
  if (jobId === selectedJobId.value) {
    return;
  }
  await loadOverview(jobId);
}

async function addAccount() {
  if (!accountInput.value) {
    message.value = "请输入需要加入重点关注的账号。";
    return;
  }

  submitting.value = true;
  try {
    await addFocusAccount({
      account: accountInput.value,
      mode: trackMode.value,
      job_id: selectedJobId.value,
    });
    message.value = "";
    accountInput.value = "";
    await loadOverview(selectedJobId.value);
  } catch (error) {
    message.value = toErrorMessage(error, "加入重点关注失败");
  } finally {
    submitting.value = false;
  }
}

async function removeAccount() {
  if (!accountInput.value) {
    message.value = "请输入需要解除重点关注的账号。";
    return;
  }

  submitting.value = true;
  try {
    await removeFocusAccount(accountInput.value);
    message.value = "";
    accountInput.value = "";
    await loadOverview(selectedJobId.value);
  } catch (error) {
    message.value = toErrorMessage(error, "解除重点关注失败");
  } finally {
    submitting.value = false;
  }
}

async function deleteLog(jobId: string) {
  submitting.value = true;
  try {
    await hideFocusLog(jobId);
    message.value = "";
    const nextSelected = jobId === selectedJobId.value ? null : selectedJobId.value;
    await loadOverview(nextSelected);
  } catch (error) {
    message.value = toErrorMessage(error, "删除日志失败");
  } finally {
    submitting.value = false;
  }
}

async function exportAccounts(jobId: string) {
  try {
    const response = await fetchFocusOverview(jobId);
    const lines = response.local_accounts.map((item) => item.account);
    const blob = new Blob([lines.join("\r\n")], { type: "text/plain;charset=utf-8" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${jobId}-accounts.txt`;
    link.click();
    window.URL.revokeObjectURL(url);
    message.value = "";
  } catch (error) {
    message.value = toErrorMessage(error, "导出账号失败");
  }
}

function formatTime(value: string) {
  return value.replace("T", " ");
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

<style scoped>
.focus-log-row {
  cursor: pointer;
  transition: background-color 160ms ease, box-shadow 160ms ease;
}

.focus-log-row.active {
  background: rgba(56, 121, 217, 0.12);
  box-shadow: inset 3px 0 0 rgba(56, 121, 217, 0.9);
}

.log-meta {
  display: inline-block;
  margin-top: 3px;
  opacity: 0.68;
  font-size: 12px;
}
</style>
