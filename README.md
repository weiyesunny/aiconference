# AI 会议助手

基于 DashScope（阿里云）的会议录音转录与智能分析工具。支持网页上传音频文件和飞书机器人两种使用方式。

## 功能

- 网页上传音频文件（支持 MP3/M4A/WAV/WebM 等）
- 浏览器内录音（需 HTTPS）
- 飞书机器人：群聊中发送录音文件，自动回复会议纪要
- DashScope Paraformer 语音转文字（支持说话人识别）
- Qwen 大模型生成结构化会议纪要
- 支持自定义分析提示词重新分析
- 网页访问密码保护

## 快速开始（本地开发）

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # 编辑填入 QWEN_API_KEY
uvicorn app.main:app --reload --port 8899
```

## Docker 部署

```bash
cp .env.example .env  # 编辑配置
docker compose up -d --build
```

## DMIT 服务器部署

详见 [deploy/DEPLOY.md](deploy/DEPLOY.md)

## 环境变量

| 变量 | 说明 | 必填 |
|---|---|---|
| `QWEN_API_KEY` | DashScope API Key | 是 |
| `QWEN_MODEL` | LLM 模型 | 否（默认 qwen-plus） |
| `ASR_MODEL` | ASR 模型 | 否（默认 paraformer-realtime-v2） |
| `ACCESS_PASSWORD` | 网页访问密码 | 否（留空不启用） |
| `FEISHU_APP_ID` | 飞书应用 ID | 否（不用飞书可留空） |
| `FEISHU_APP_SECRET` | 飞书应用密钥 | 否 |
| `FEISHU_VERIFICATION_TOKEN` | 飞书事件验证 Token | 否 |

## 项目结构

```
app/
├── main.py              # FastAPI 路由（Web + 飞书 Webhook）
├── config.py            # 环境变量配置
├── database.py          # SQLite 数据层
├── services/
│   ├── asr.py           # DashScope Paraformer 语音识别
│   ├── analyzer.py      # Qwen LLM 会议纪要生成
│   └── feishu.py        # 飞书 API（下载文件、发送消息）
├── templates/           # Jinja2 页面模板
└── static/css/          # 样式文件
deploy/
├── DEPLOY.md            # DMIT 部署指南
└── nginx-healthsupply.conf  # Nginx 反代配置
```
