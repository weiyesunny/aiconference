# AI 会议助手

基于 DashScope（阿里云）的会议录音转录与智能分析工具。上传音频文件（或直接在浏览器中录音），自动完成语音识别和会议纪要生成。

## 功能

- 上传音频文件或浏览器内录音
- DashScope Paraformer 语音转文字（支持说话人识别）
- Qwen 大模型生成结构化会议纪要
- 支持自定义分析提示词重新分析
- 带时间戳的转录文本查看

## 系统要求

- Python 3.11+
- ffmpeg / ffprobe（音频预处理）
- DashScope API Key（[申请地址](https://dashscope.console.aliyun.com/)）

## 快速开始

```bash
# 克隆项目
git clone <repo-url> && cd aiconference

# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 QWEN_API_KEY

# 启动服务
uvicorn app.main:app --reload --port 8899
```

浏览器访问 http://localhost:8899

## 项目结构

```
app/
├── main.py              # FastAPI 路由与后台任务
├── config.py            # 环境变量配置
├── database.py          # SQLite 数据层
├── services/
│   ├── asr.py           # DashScope Paraformer 语音识别
│   └── analyzer.py      # Qwen LLM 会议纪要生成
├── templates/           # Jinja2 页面模板
└── static/css/          # 样式文件
```

## 环境变量

| 变量 | 说明 | 默认值 |
|---|---|---|
| `QWEN_API_KEY` | DashScope API Key（必填） | - |
| `QWEN_BASE_URL` | LLM API 地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `QWEN_MODEL` | LLM 模型 | `qwen-plus` |
| `ASR_MODEL` | ASR 模型 | `paraformer-realtime-v2` |
| `UPLOAD_DIR` | 音频文件存储目录 | `uploads` |
| `DATABASE_PATH` | SQLite 数据库路径 | `data/meetings.db` |

## 许可证

MIT
