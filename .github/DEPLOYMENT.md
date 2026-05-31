# 🚀 GitHub Actions 自动部署配置指南

## 📋 前置要求

- GitHub 仓库已创建
- 服务器已准备好（Ubuntu 22.04）
- 服务器 SSH 密钥（AQQQ.pem）

---

## 🔐 配置 GitHub Secrets

在 GitHub 仓库中配置以下 Secrets：

### 1. 进入仓库设置
```
仓库页面 → Settings → Secrets and variables → Actions → New repository secret
```

### 2. 添加以下 Secrets

#### `SSH_PRIVATE_KEY`
**值：** AQQQ.pem 文件的完整内容

```bash
# 在本地执行，复制输出内容
cat E:\Economy\Download\AQQQ.pem
```

复制从 `-----BEGIN RSA PRIVATE KEY-----` 到 `-----END RSA PRIVATE KEY-----` 的所有内容（包括这两行）。

#### `SERVER_HOST`
**值：** `8.137.175.248`

---

## 🎯 部署流程

### 自动部署触发条件

1. **推送到 master/main 分支**
   ```bash
   git add .
   git commit -m "更新代码"
   git push origin master
   ```

2. **手动触发**
   - 进入 GitHub 仓库
   - 点击 `Actions` 标签
   - 选择 `Deploy to Server` workflow
   - 点击 `Run workflow`

---

## 📦 部署内容

### 后端部署
- **位置：** `/opt/fraudshield2026/server`
- **端口：** 8001（内部）
- **服务：** `fraudshield-backend.service`
- **启动命令：** `systemctl start fraudshield-backend`
- **日志查看：** `journalctl -u fraudshield-backend -f`

### 前端部署
- **位置：** `/opt/fraudshield2026/frontend`
- **服务：** Nginx 静态文件服务
- **端口：** 80（外部访问）

### Nginx 配置
- **配置文件：** `/etc/nginx/sites-available/fraudshield`
- **路由规则：**
  - `/` → 前端静态文件
  - `/api/*` → 后端 API（代理到 8001 端口）
  - `/health` → 健康检查

---

## 🔍 部署验证

### 1. 检查服务状态
```bash
ssh -i AQQQ.pem root@8.137.175.248

# 检查后端服务
systemctl status fraudshield-backend

# 检查 Nginx
systemctl status nginx

# 检查端口监听
netstat -tlnp | grep -E ':80|:8001'
```

### 2. 访问测试
- **前端页面：** http://8.137.175.248
- **API 文档：** http://8.137.175.248/docs
- **健康检查：** http://8.137.175.248/health

### 3. 查看日志
```bash
# 后端日志
journalctl -u fraudshield-backend -f

# Nginx 访问日志
tail -f /var/log/nginx/access.log

# Nginx 错误日志
tail -f /var/log/nginx/error.log
```

---

## 🛠️ 常用运维命令

### 后端服务管理
```bash
# 启动服务
systemctl start fraudshield-backend

# 停止服务
systemctl stop fraudshield-backend

# 重启服务
systemctl restart fraudshield-backend

# 查看状态
systemctl status fraudshield-backend

# 查看实时日志
journalctl -u fraudshield-backend -f
```

### Nginx 管理
```bash
# 测试配置
nginx -t

# 重载配置
systemctl reload nginx

# 重启 Nginx
systemctl restart nginx
```

### 手动更新代码
```bash
cd /opt/fraudshield2026
git pull origin master

# 更新后端
cd server
source .venv/bin/activate
pip install -r requirements.txt
systemctl restart fraudshield-backend

# 更新前端（需要本地构建后上传）
# 或者等待下次 GitHub Actions 自动部署
```

---

## 🐛 故障排查

### 问题 1：后端服务启动失败
```bash
# 查看详细错误
journalctl -u fraudshield-backend -n 50

# 检查 Python 环境
cd /opt/fraudshield2026/server
source .venv/bin/activate
python -c "import fastapi; print('FastAPI OK')"

# 手动启动测试
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

### 问题 2：前端页面 404
```bash
# 检查前端文件是否存在
ls -la /opt/fraudshield2026/frontend/

# 检查 Nginx 配置
nginx -t
cat /etc/nginx/sites-available/fraudshield

# 重启 Nginx
systemctl restart nginx
```

### 问题 3：API 请求失败
```bash
# 检查后端是否运行
curl http://localhost:8001/health

# 检查 Nginx 代理配置
cat /etc/nginx/sites-available/fraudshield | grep proxy_pass

# 查看 Nginx 错误日志
tail -f /var/log/nginx/error.log
```

---

## 📝 环境变量配置

后端环境变量文件：`/opt/fraudshield2026/server/.env`

```bash
# 编辑环境变量
nano /opt/fraudshield2026/server/.env

# 修改后重启服务
systemctl restart fraudshield-backend
```

---

## 🔄 回滚部署

如果新版本有问题，可以回滚到上一个版本：

```bash
cd /opt/fraudshield2026
git log --oneline -5  # 查看最近的提交
git reset --hard <commit-hash>  # 回滚到指定版本
systemctl restart fraudshield-backend
```

---

## 📊 监控建议

### 1. 设置日志轮转
```bash
# 编辑 logrotate 配置
nano /etc/logrotate.d/fraudshield
```

### 2. 配置告警
- 使用 `systemctl` 的邮件通知
- 或集成第三方监控服务（如 Prometheus）

### 3. 定期备份
```bash
# 备份数据库
cp /opt/fraudshield2026/server/data/*.db /backup/

# 备份配置
cp /opt/fraudshield2026/server/.env /backup/
```

---

## ✅ 部署完成检查清单

- [ ] GitHub Secrets 已配置（SSH_PRIVATE_KEY, SERVER_HOST）
- [ ] 首次部署成功（Actions 显示绿色 ✓）
- [ ] 后端服务运行正常（`systemctl status fraudshield-backend`）
- [ ] Nginx 配置正确（`nginx -t`）
- [ ] 前端页面可访问（http://8.137.175.248）
- [ ] API 文档可访问（http://8.137.175.248/docs）
- [ ] 健康检查通过（http://8.137.175.248/health）
- [ ] 可以正常登录（用户名：1，密码：1）

---

## 🎉 完成！

现在每次推送代码到 GitHub，都会自动部署到服务器。

**访问地址：** http://8.137.175.248
