# FraudShield 2026

基于 `Vue 3 + Tauri + FastAPI` 的实时多模态金融反欺诈重构版。

## 🚀 在线访问

- **前端页面：** http://8.137.175.248
- **API 文档：** http://8.137.175.248/docs
- **健康检查：** http://8.137.175.248/health

**默认登录账户：** 用户名 `1` / 密码 `1`

## 目标

- 用桌面壳替代旧的 PySide6 主程序
- 将识别、预测、链路分析、报表生成收敛到 Python 服务
- 将实时告警、案件工作台、报告中心拆成清晰的前后端边界

## 目录

```text
FraudShield2026/
├── desktop/   # Vue 3 + Tauri 桌面端
├── server/    # FastAPI 服务
└── docs/      # 架构和迁移说明
```

## 架构决策

1. 前后端分离，接口采用 `REST + SSE`
2. 服务端按业务域拆分：认证、实时流、检测、报告、系统
3. 桌面端只做交互和状态，不承载模型逻辑
4. 检测服务优先兼容旧模型目录 `Project/final/model`

## 本地启动

### 1. 启动后端

```bash
cd server
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 2. 启动前端

```bash
cd desktop
npm install
npm run dev
```

### 3. 启动 Tauri 壳

需要本机已安装 Rust 工具链：

```bash
cd desktop
npm run tauri:dev
```

## 当前状态

- 已完成：单仓结构、FastAPI 骨架、Vue + Tauri 前端骨架、API 客户端、核心页面
- 未完成：真实数据库接入、JWT 刷新令牌、Kafka 生产接入、旧模型与 OCR 的全部迁移
