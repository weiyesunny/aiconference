# DMIT 服务器部署指南

> 服务器：154.26.179.252 (1 vCPU / 2 GB RAM / 20 GB SSD)
> 域名：healthsupply.top

## 一、服务器准备

```bash
ssh -i ~/.ssh/dmit_key root@154.26.179.252

# 安装 certbot
apt update
apt install -y certbot python3-certbot-nginx

# 取消旧的 cron 抓取任务
crontab -e
# 删除 update_feeds.py 那一行
```

## 二、部署应用（Docker）

```bash
# 拉取代码
cd /opt
git clone https://github.com/weiyesunny/aiconference.git
cd aiconference

# 配置环境变量
cp .env.example .env
nano .env
# 必填：QWEN_API_KEY
# 必填：ACCESS_PASSWORD（网页访问密码）
# 可选：FEISHU_APP_ID, FEISHU_APP_SECRET 等（飞书机器人）

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

## 四、配置飞书机器人（可选）

### 4.1 创建飞书应用

1. 打开 [飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 添加「机器人」能力
4. 记录 App ID 和 App Secret

### 4.2 配置权限

在应用的「权限管理」中申请：
- `im:message` — 获取与发送单聊、群组消息
- `im:message.group_at_msg` — 接收群聊中 @机器人消息
- `im:resource` — 获取与上传图片或文件资源

### 4.3 配置事件订阅

1. 进入「事件订阅」页面
2. 请求地址填：`https://healthsupply.top/feishu/webhook`
3. 添加事件：`im.message.receive_v1`（接收消息）
4. 获取 Verification Token

### 4.4 更新服务器配置

```bash
cd /opt/aiconference
nano .env
# 填入：
# FEISHU_APP_ID=cli_xxxx
# FEISHU_APP_SECRET=xxxx
# FEISHU_VERIFICATION_TOKEN=xxxx

# 重启容器
docker compose restart
```

### 4.5 发布应用

1. 在飞书开放平台提交应用版本审核
2. 审核通过后，管理员在企业后台启用
3. 将机器人添加到群聊中

### 4.6 使用方式

在飞书群聊中：
1. 发送录音文件或音频文件
2. 机器人自动接收并处理
3. 等待 2-5 分钟后，机器人回复会议纪要

## 五、日常运维

```bash
# 查看服务状态
docker compose ps

# 查看实时日志
docker compose logs -f

# 重启
docker compose restart

# 更新代码
cd /opt/aiconference
git pull
docker compose up -d --build

# 查看磁盘使用
du -sh uploads/ data/

# 清理旧音频文件（保留最近 7 天）
find uploads/ -name "*.m4a" -mtime +7 -delete
find uploads/ -name "*.webm" -mtime +7 -delete
```

## 六、部署后架构

```
DMIT (154.26.179.252)
│
├── Nginx (80/443)
│   └── healthsupply.top → 反代 → 127.0.0.1:8899
│
├── Docker: aiconference (127.0.0.1:8899)
│   ├── /upload          ← 网页上传（密码保护）
│   └── /feishu/webhook  ← 飞书回调（签名验证）
│
└── Xray (10443) ← 不变
```
