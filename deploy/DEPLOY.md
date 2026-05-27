# DMIT 服务器部署指南

> 服务器：154.26.179.252 (1 vCPU / 2 GB RAM / 20 GB SSD)
> 域名：healthsupply.top

## 一、服务器准备

```bash
ssh -i ~/.ssh/dmit_key root@154.26.179.252

# 安装 certbot
apt update
apt install -y certbot python3-certbot-nginx
```

## 二、部署应用（Docker）

```bash
cd /opt
git clone https://github.com/weiyesunny/aiconference.git
cd aiconference

# 配置环境变量
cp .env.example .env
nano .env
# 必填：QWEN_API_KEY
# 必填：ACCESS_PASSWORD（网页访问密码）
# 可选：FEISHU_WEBHOOK_URL（飞书 Incoming Webhook 推送纪要到群）

# 构建并启动 Docker 容器
docker compose up -d --build

# 查看日志
docker compose logs -f
```

## 三、配置 Nginx + HTTPS

```bash
# 替换 Nginx 配置
cp /opt/aiconference/deploy/nginx-healthsupply.conf /etc/nginx/sites-available/healthsupply

# 测试配置
nginx -t

# 重载 Nginx
systemctl reload nginx

# 申请 HTTPS 证书（按提示操作，填入邮箱）
certbot --nginx -d healthsupply.top

# 验证 HTTPS
curl -I https://healthsupply.top
```

## 四、日常运维

```bash
# 查看服务状态
docker compose ps

# 查看实时日志
docker compose logs -f

# 重启
docker compose restart

# 更新代码并重新部署
cd /opt/aiconference
git pull origin main
docker compose up -d --build

# 查看磁盘使用
du -sh uploads/ data/

# 清理旧音频文件（保留最近 7 天）
find uploads/ -name "*.m4a" -mtime +7 -delete
find uploads/ -name "*.webm" -mtime +7 -delete
```

## 五、部署后架构

```
DMIT (154.26.179.252)
│
├── Nginx (80/443)
│   └── healthsupply.top → 反代 → 127.0.0.1:8899
│
├── Docker: aiconference (127.0.0.1:8899)
│   ├── /upload        ← 网页上传音频（密码保护）
│   └── 处理完成自动推送到飞书群 (Incoming Webhook)
│
└── Xray (10443) ← 代理服务不变
```
