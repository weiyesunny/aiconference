# AI 会议助手

基于 DashScope（阿里云）的会议录音转录与智能分析工具。

## 功能

- 网页上传音频文件（支持 MP3/M4A/WAV/FLAC/OGG/MP4/WebM/AAC/OPUS）
- 浏览器内录音（需 HTTPS）
- DashScope Paraformer 语音转文字（支持说话人识别）
- Qwen 大模型生成结构化会议纪要
- 支持自定义分析提示词重新分析
- 处理完成后自动推送到飞书群（通过 Incoming Webhook）
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
| `QWEN_API_KEY` | DashScope API Key（LLM + ASR 共用） | 是 |
| `QWEN_MODEL` | LLM 模型 | 否（默认 qwen-plus） |
| `LLM_TEMPERATURE` | LLM 生成温度 | 否（默认 0.3） |
| `LLM_MAX_TOKENS` | LLM 最大输出 token | 否（默认 4096） |
| `ASR_MODEL` | ASR 模型 | 否（默认 paraformer-realtime-v2） |
| `FEISHU_WEBHOOK_URL` | 飞书 Incoming Webhook URL | 否（留空不推送） |
| `ACCESS_PASSWORD` | 网页访问密码 | 否（留空不启用） |

## 项目结构

```
app/
├── main.py              # FastAPI 应用入口
├── config.py            # 环境变量配置
├── constants.py         # 状态枚举、品牌文案、常量
├── prompts.py           # LLM Prompt 模板（可调整）
├── database.py          # SQLite 数据层
├── routes/
│   ├── auth.py          # 认证路由
│   └── meeting.py       # 会议 CRUD 与处理路由
├── services/
│   ├── asr.py           # DashScope Paraformer 语音识别
│   ├── analyzer.py      # Qwen LLM 会议纪要生成
│   └── feishu.py        # 飞书 Incoming Webhook 推送
├── templates/           # Jinja2 页面模板
└── static/css/          # 样式文件
deploy/
├── DEPLOY.md            # DMIT 部署指南
└── nginx-healthsupply.conf
```

## 扩展新功能

项目采用模块化设计，新增功能（如 AI 翻译）的步骤：

1. 在 `app/prompts.py` 添加对应的 Prompt 模板
2. 在 `app/services/` 中添加或复用服务模块
3. 在 `app/routes/` 中添加新的路由文件
4. 在 `app/main.py` 中注册新路由
