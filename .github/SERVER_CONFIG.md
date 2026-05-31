# 🔧 服务器环境变量配置指南

## 📍 配置文件位置

服务器：`8.137.175.248`  
路径：`/opt/fraudshield2026/server/.env`

---

## 🔐 SSH 登录

```bash
ssh -i AQQQ.pem root@8.137.175.248
```

---

## ⚙️ 当前配置状态

### ✅ 已启用功能

| 功能 | 状态 | 说明 |
|------|------|------|
| 核心分析 | ✅ 可用 | Excel 规则模式分析 |
| 报告生成 | ✅ 可用 | HTML + PDF 报告 |
| 实时监控 | ✅ 可用 | 模拟数据流 |
| 用户认证 | ✅ 可用 | TOTP 已绕过（开发模式）|

### ⚠️ 需要配置的高级功能

| 功能 | 环境变量 | 说明 |
|------|---------|------|
| MinerU OCR | `MINERU_API_TOKEN` | 图片/PDF 文档识别 |
| LLM 表头映射 | `ANALYSIS_LLM_API_KEY` | 智能识别非标准表头 |
| Kafka 实时流 | `FS_KAFKA_BOOTSTRAP` | 真实交易数据流 |

---

## 📝 配置方法

### 方法 1：直接编辑（推荐）

```bash
# 1. SSH 登录服务器
ssh -i AQQQ.pem root@8.137.175.248

# 2. 编辑配置文件
nano /opt/fraudshield2026/server/.env

# 3. 修改对应的环境变量
# 例如：MINERU_API_TOKEN=your_token_here

# 4. 保存并退出（Ctrl+O, Enter, Ctrl+X）

# 5. 重启服务
systemctl restart fraudshield-backend

# 6. 查看服务状态
systemctl status fraudshield-backend
```

### 方法 2：使用 sed 命令

```bash
# 设置 MinerU Token
ssh -i AQQQ.pem root@8.137.175.248 \
  "sed -i 's/^MINERU_API_TOKEN=.*/MINERU_API_TOKEN=your_token_here/' /opt/fraudshield2026/server/.env && \
   systemctl restart fraudshield-backend"

# 设置 LLM API Key
ssh -i AQQQ.pem root@8.137.175.248 \
  "sed -i 's/^ANALYSIS_LLM_API_KEY=.*/ANALYSIS_LLM_API_KEY=your_key_here/' /opt/fraudshield2026/server/.env && \
   systemctl restart fraudshield-backend"
```

---

## 🔑 获取 API 密钥

### MinerU API Token

1. 访问 MinerU 官网注册账号
2. 获取 API Token
3. 配置到 `MINERU_API_TOKEN`

### SiliconFlow API Key

1. 访问：https://cloud.siliconflow.cn
2. 注册并获取 API Key
3. 配置到 `ANALYSIS_LLM_API_KEY`

---

## 🧪 测试配置

```bash
# SSH 登录后执行
cd /opt/fraudshield2026/server
source .venv/bin/activate
python3 << 'ENDPY'
from app.core.config import settings
print(f'MinerU: {"✅ 已配置" if settings.mineru_api_token else "❌ 未配置"}')
print(f'LLM API: {"✅ 已配置" if settings.analysis_llm_api_key else "❌ 未配置"}')
ENDPY
```

---

## 📋 完整的 .env 模板

```bash
# MinerU OCR 服务（文档识别）
MINERU_API_TOKEN=

# SiliconFlow LLM 服务（智能表头映射）
ANALYSIS_LLM_API_KEY=
ANALYSIS_LLM_BASE_URL=https://api.siliconflow.cn/v1
ANALYSIS_LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
ANALYSIS_ENABLE_LLM_NORMALIZATION=true
ANALYSIS_HTTP_TRUST_ENV=false

# 开发模式：跳过 TOTP 二次验证（生产环境请删除此行）
AUTH_DEV_TOTP_BYPASS=1

# 旧版模型路径（可选）
LEGACY_TORCH_PYTHON=python
# LEGACY_ROOT=/path/to/legacy/Project

# Kafka 配置（可选）
# FS_KAFKA_BOOTSTRAP=localhost:9092
# FS_KAFKA_TOPIC=financial_transactions
```

---

## 🔄 部署保护

**重要：** GitHub Actions 部署脚本已配置为**不覆盖**现有的 `.env` 文件。

- ✅ 首次部署：自动创建 `.env`
- ✅ 后续部署：保留现有配置
- ✅ 手动修改：不会被覆盖

---

## 🚀 服务管理命令

```bash
# 查看服务状态
systemctl status fraudshield-backend

# 重启服务
systemctl restart fraudshield-backend

# 查看日志
journalctl -u fraudshield-backend -f

# 查看最近 50 行日志
journalctl -u fraudshield-backend -n 50
```

---

## 🐛 故障排查

### 服务启动失败

```bash
# 查看详细错误
journalctl -u fraudshield-backend -n 100

# 手动启动测试
cd /opt/fraudshield2026/server
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

### API 密钥无效

```bash
# 测试 MinerU API
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://api.mineru.com/health

# 测试 SiliconFlow API
curl -H "Authorization: Bearer YOUR_KEY" \
  https://api.siliconflow.cn/v1/models
```

---

## 📞 联系方式

- **服务器 IP：** 8.137.175.248
- **前端访问：** http://8.137.175.248
- **API 文档：** http://8.137.175.248/docs
- **健康检查：** http://8.137.175.248/health

---

**最后更新：** 2026-05-31
