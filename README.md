# 🗺️ 旅行专家智能体 (Travel Expert Agent)

基于 **FastAPI + LangGraph + LangChain** 构建的**企业级**旅行规划 AI Agent 应用。支持流式对话、联网搜索、图片识别、文件上传、多 Agent 协作、长期记忆、Self-RAG 检索增强、输出验证等完整能力，界面采用 ChatGPT 风格设计。

---

## 📋 目录

- [功能特性](#功能特性)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [环境配置](#环境配置)
- [快速启动](#快速启动)
- [架构详解](#架构详解)
- [使用指南](#使用指南)
- [API 接口文档](#api-接口文档)
- [常见问题](#常见问题)

---

## ✨ 功能特性

### 核心能力

| 功能 | 描述 |
|------|------|
| 🤖 流式 AI 对话 | 基于 LangGraph ReAct Agent + 通义千问，逐 token 实时流式输出 |
| 🔍 联网搜索 | 集成 Tavily 搜索引擎，自动获取最新旅行资讯、签证政策、优惠活动 |
| 🌤️ 天气查询 | 集成 OpenWeatherMap API，查询全球城市天气预报（支持降级） |
| 💱 汇率换算 | 集成 Open Exchange Rates API，实时汇率查询（支持内置固定汇率降级） |
| 🛂 签证政策 | 自动查询各国签证政策与入境要求 |
| 📍 高德地图 | 集成高德地图 POI 搜索 / 路线规划 / 地理编码（3 个工具） |
| 📷 图片识别 | 上传景点/美食照片，调用 qwen-vl-plus 视觉模型识别并回答 |
| 📄 文件上传 | 支持 PDF/DOCX/TXT 文件上传，AI 自动读取内容并回答 |

### Agent 架构能力

| 能力 | 描述 |
|------|------|
| 🧠 Self-RAG 检索增强 | 三级检索决策：🔴 强制检索 / ✅ 建议检索 / ❌ 无需检索 |
| 🔄 多 Agent 协作 | Supervisor 模式：主 Agent + 行程/天气/预算/向导 4 个子 Agent |
| 🧠 长期记忆 | 三层记忆架构：短期（对话上下文）/ 长期（用户画像）/ 经验（任务教训） |
| 🔮 动态上下文 | 意图分类 → 4 套 Prompt 模板动态组装 → 上下文压缩 |
| ✅ 输出验证 | 四维验证：事实核查 / 格式校验 / 一致性检查 / 安全过滤 |
| 🎯 StateGraph 工作流 | LangGraph 状态机编排意图路由 → Agent 选择 → 输出验证 |
| 📈 自我改进 | 用户反馈循环 → 经验库积累 → 下次同类任务优化 |
| 📊 可观测性 | loguru 结构化日志：TTFT / tool call / latency 全链路追踪 |

### 用户体验

| 功能 | 描述 |
|------|------|
| 💭 思考过程可视化 | 思考内容小字浅色渲染（参考 DeepSeek），与正式回答区分 |
| 🔍 搜索状态指示器 | 工具调用时追加动画指示器，不覆盖已有内容 |
| 👍 用户反馈 | 点赞/点踩按钮，驱动自我改进循环 |
| 🔗 参考来源 | AI 搜索后自动展示参考链接，支持点击跳转原文 |
| 📝 Markdown 渲染 | 表格、代码块、列表、粗体等 Markdown 格式完美渲染 |
| 💾 对话导出 | 支持将对话记录导出为 Markdown 文件下载到本地 |
| ⏹️ 停止生成 | AI 输出过程中可随时点击停止按钮中断生成 |
| 💬 多轮对话 | 自动保留上下文，支持多轮连续对话（超长对话自动压缩） |
| 📂 对话管理 | 新建聊天、切换对话、删除对话、搜索对话 |
| 🔐 用户认证 | 注册/登录/登出，JWT Token 鉴权 |
| 📱 响应式布局 | 适配桌面端和移动端，侧边栏可折叠 |

---

## 🛠️ 技术栈

### 后端

| 技术 | 用途 |
|------|------|
| Python 3.10+ | 开发语言 |
| FastAPI | Web 框架 |
| SQLAlchemy 2.0 | ORM 数据库操作 |
| MySQL 8.0 + PyMySQL | 数据库 |
| LangChain 0.3 | LLM 应用开发框架 |
| LangGraph 0.2 | AI Agent 工作流编排（StateGraph） |
| LangChain-OpenAI | 通义千问 API 对接（兼容 OpenAI 接口） |
| LangChain-Tavily | 联网搜索工具 |
| PyJWT + PassLib | JWT 认证 + 密码加密 |
| PyMuPDF | PDF 文件文本提取 |
| python-docx | DOCX 文件文本提取 |
| Loguru | 结构化日志（带颜色、时间戳） |
| Requests | HTTP 客户端（天气/汇率/签证/地图 API） |

### 前端

| 技术 | 用途 |
|------|------|
| HTML5 + CSS3 + JavaScript | 原生前端 |
| Font Awesome 6 | 图标库 |
| Marked.js | Markdown 渲染 |
| Highlight.js | 代码高亮 |

### AI 模型

| 模型 | 用途 |
|------|------|
| qwen-plus（通义千问） | 主对话生成（可替换为 GPT-4o-mini / DeepSeek-V3） |
| qwen-vl-plus（通义千问视觉） | 图片识别 |

### 外部 API

| 服务 | 用途 | 免费额度 |
|------|------|---------|
| 通义千问 DashScope | AI 大模型 API | 按量付费 |
| Tavily Search | 联网搜索引擎 | 1000 次/月 |
| OpenWeatherMap | 天气数据 | 60 次/分钟 |
| Open Exchange Rates | 汇率数据 | 1500 次/月 |
| **高德地图** | **POI 搜索 / 路线规划 / 地理编码** | **30 万次/日** |

---

## 📁 项目结构

```
travel-agent/
├── main.py                              # 应用入口，FastAPI 配置 + loguru 初始化 + 静态文件挂载
├── requirements.txt                     # Python 依赖列表
├── config/
│   └── .env                             # 环境变量配置（API Key、数据库等）
├── uploads/                             # 用户上传文件存储目录
├── backend/
│   └── app/
│       ├── core/                        # 核心配置模块
│       │   ├── config.py                #   全局配置（.env + 8 个配置项）
│       │   ├── database.py              #   数据库连接与会话管理
│       │   ├── security.py              #   JWT 令牌 + 密码加密
│       │   └── deps.py                  #   依赖注入（获取当前用户）
│       ├── models/                      # SQLAlchemy 数据模型
│       │   ├── user.py                 #     用户表
│       │   ├── conversation.py         #     对话表
│       │   ├── message.py              #     消息表
│       │   ├── user_profile.py         #     ★ 用户画像表（偏好/目的地/历史）
│       │   └── experience_log.py       #     ★ 经验日志表（任务/评分/教训）
│       ├── schemas/                     # Pydantic 数据校验模型
│       │   ├── auth.py                 #     认证相关
│       │   ├── chat.py                 #     聊天相关
│       │   └── user.py                 #     用户相关
│       ├── api/routers/                # API 路由
│       │   ├── auth.py                 #     认证接口（注册/登录）
│       │   ├── chat.py                 #     对话管理 + ★用户画像 + ★反馈接口
│       │   ├── stream.py               #     流式聊天（SSE + 动态上下文 + 记忆 + 可观测性）
│       │   └── upload.py               #     文件上传接口
│       └── services/                   # 业务逻辑层
│           ├── llm.py                  #   LLM 实例管理（文本 max_tokens=8192 / 视觉 4096）
│           ├── tools.py                #   ★ 7 个工具（搜索/天气/汇率/签证/POI/路线/地理编码）
│           ├── agent.py                #   ★ Self-RAG Agent + 5 个 Agent 函数 + AGENT_REGISTRY
│           ├── context.py              #   ★ 动态上下文层（意图分类/4模板/日期注入/压缩）
│           ├── memory.py               #   ★ 记忆管理层（画像读写/经验存取/LLM 自评提取）
│           ├── validator.py            #   ★ 输出验证层（事实/格式/一致/安全 四维验证）
│           ├── graph.py                #   ★ StateGraph 工作流 + Supervisor 多Agent 编排
│           ├── image_recognizer.py     #   图片识别服务
│           └── file_processor.py       #   文件处理服务（PDF/DOCX/TXT）
└── frontend/
    ├── templates/
    │   └── index.html                 # 主页面 HTML（含 favicon 引用）
    └── static/
        ├── css/
        │   └── style.css              # 全局样式（含搜索指示器 + 思考块样式）
        ├── js/
        │   └── app.js                 # 前端交互逻辑（含思考标签解析 + 反馈功能）
        └── favicon.svg               # 网站图标（绿色飞机 Logo）
```

> 带 ★ 的文件/模块为本次架构升级新增或重大修改。

---

## ⚙️ 环境配置

### 1. Python 环境

- **Python 版本**：3.10+
- **虚拟环境**：`python -m venv venv && venv\Scripts\activate`

### 2. MySQL 数据库

```sql
CREATE DATABASE travel_agent DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 3. API Key 配置

编辑 `config/.env` 文件：

```env
# ====== 数据库 ======
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=你的MySQL密码
DB_NAME=travel_agent

# ====== JWT ======
SECRET_KEY=travel-agent-secret-key-2024

# ====== 通义千问（必填）=====
DASHSCOPE_API_KEY=sk-你的Key
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_MODEL=qwen-plus          # 可替换为 gpt-4o-mini / deepseek-chat 等

# ====== Tavily 搜索（必填）=====
TAVILY_API_KEY=tvly-你的Key

# ====== 天气 API - OpenWeatherMap（选填，不填则降级为 Tavily 搜索）=====
WEATHER_API_KEY=你的OpenWeatherMap_appid

# ====== 汇率 API - Open Exchange Rates（选填，不填则使用内置固定汇率）=====
OPEN_EXCHANGE_KEY=你的AppID

# ====== 高德地图 API（选填，不填则地图工具降级为 Tavily 搜索）=====
AMAP_API_KEY=你的高德Web服务API_Key
```

**获取 API Key：**

| 服务 | 注册地址 | 说明 |
|------|---------|------|
| 通义千问 | [DashScope 控制台](https://dashscope.console.aliyun.com/) | 开通 `qwen-plus` 和 `qwen-vl-plus` |
| Tavily | [tavily.com](https://tavily.com/) | 免费额度 1000 次/月 |
| OpenWeatherMap | [openweathermap.org/api](https://openweathermap.org/api) | 免费额度 60 次/分钟 |
| Open Exchange | [openexchangerates.com](https://openexchangerates.com/) | 免费额度 1500 次/月 |
| 高德地图 | [lbs.amap.com](https://lbs.amap.com/) | 免费额度 **30 万次/日** |

---

## 🚀 快速启动

```powershell
# 1. 创建虚拟环境并激活
python -m venv venv
venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 3. 配置环境变量（编辑 config/.env）

# 4. 启动服务器
python main.py
```

看到以下输出说明启动成功：

```
2026-06-15 19:39:46 | INFO | Uvicorn running on http://127.0.0.1:8000
2026-06-15 19:39:46 | INFO | Application startup complete.
```

浏览器打开 **http://127.0.0.1:8000**

首次启动时 SQLAlchemy 会**自动创建所有数据表**（包括新增的 `user_profile` 和 `experience_log` 表）。

---

## 🏗️ 架构详解

### 整体架构图

```
用户请求 (前端 SSE)
    ↓
stream.py — 流式聊天入口
    ├─→ classify_intent()      # 意图分类（qa/planning/search/complex）
    ├─→ get_or_create_profile() # 加载用户画像
    ├─→ retrieve_experiences()  # 检索历史经验
    ├─→ build_system_prompt()   # 组装动态 Prompt（日期+画像+经验+意图模板）
    ├─→ compress_long_context() # 长对话压缩（>10 轮）
    ↓
get_agent(system_prompt=dynamic_prompt)  # 注入动态 System Prompt
    ↓
LangGraph StateGraph / create_react_agent
    ├─→ Self-RAG 决策（强制检索/建议检索/无需检索）
    ├─→ 7 个工具可选调用
    │   ├─ web_search (Tavily)
    │   ├─ weather_search (OpenWeatherMap)
    │   ├─ exchange_rate (Open Exchange)
    │   ├─ visa_policy_search (Tavily)
    │   ├─ amap_poi_search (高德)
    │   ├─ amap_route_planning (高德)
    │   └─ amap_geocode (高德)
    ├─→ 输出验证（事实/格式/一致/安全）
    ↓
SSE 事件流 → 前端渲染
    ├─ token → 追加文字
    ├─ tool_start → 追加搜索指示器（不覆盖已有内容）
    ├─ tool_end → 移除搜索指示器
    ├─ sources → 渲染来源卡片
    └─ done → 保存消息 + 异步后处理
         ├─ update_profile_from_conversation()  # 更新画像
         └─ analyze_and_save_experience()       # 存储经验
```

### 核心模块说明

#### `services/context.py` — 动态上下文层

- **意图分类**：基于关键词规则将用户输入分为 4 类（44 个搜索关键词覆盖赛事/活动/时间等）
- **4 套 Prompt 模板**：QA / PLANNING / SEARCH / COMPLEX，根据意图选择
- **日期注入**：每个模板包含 `{current_date}` 占位符，运行时替换为"2026年6月15日 星期日"
- **上下文压缩**：超过 10 轮的对话自动摘要化，保留最近消息原文
- **Self-RAG 指引**：三级检索决策 + 训练数据截止警告 + 工具映射表

#### `services/agent.py` — Agent 定义

- **主 Agent** (`get_agent`)：完整的 7 工具 Self-RAG Agent，支持自定义 System Prompt
- **4 个子 Agent**：
  - `create_route_agent` — 行程规划（搜索 + 地图工具）
  - `create_weather_agent` — 天气查询（天气 + 搜索工具）
  - `create_budget_agent` — 预算分析（汇率 + 搜索工具）
  - `create_local_guide_agent` — 当地向导（搜索工具）
- **AGENT_REGISTRY**：Agent 名称到创建函数的映射表，供 Supervisor 使用

#### `services/memory.py` — 记忆管理

- **用户画像** (`user_profile`)：存储旅行偏好（预算范围/出行方式/兴趣类型）、常去目的地、旅行历史
- **经验日志** (`experience_log)`：记录每次任务的类型、评分、LLM 自评提取的教训
- **LLM 自评**：对话结束后异步调用 LLM 分析本次表现，自动提取改进要点

#### `services/tools.py` — 工具集（7 个）

| 工具名 | API | 功能 |
|--------|-----|------|
| `web_search` | Tavily | 通用互联网搜索 |
| `weather_search` | OpenWeatherMap | 全球天气预报（5 日预报） |
| `exchange_rate` | Open Exchange Rates | 180+ 种货币实时汇率 |
| `visa_policy_search` | Tavily | 各国签证政策查询 |
| `amap_poi_search` | 高德 | POI 关键词搜索（名称/地址/坐标/评分/人均消费） |
| `amap_route_planning` | 高德 | 路线规划（驾车/公交/步行/骑行 4 种模式） |
| `amap_geocode` | 高德 | 地址↔坐标互转 + 逆地理编码 |

所有工具均支持**优雅降级**：API Key 未配置或超时时自动回退到 Tavily 搜索。

#### `services/graph.py` — StateGraph 工作流

- 定义意图路由节点和各专业 Agent 节点
- Supervisor 模式协调多 Agent 协作
- 条件边根据意图类型分发到对应 Agent

#### `services/validator.py` — 输出验证

- **事实核查**：检查回复中的关键事实是否合理（如日期不在过去）
- **格式校验**：检查行程是否按天组织、是否包含必要字段
- **一致性检查**：检查前后信息是否有矛盾
- **安全过滤**：检查是否包含敏感/不当内容

#### `api/routers/stream.py` — 流式聊天核心

完整的数据处理流水线：
1. 接收消息 → 附件处理（图片识别/文档提取）
2. 保存用户消息 → 更新对话标题
3. **意图分类** → **加载画像** → **检索经验**
4. **构建动态 System Prompt**（日期 + 画像 + 经验 + 意图模板）
5. **历史消息压缩**（>10 轮）
6. **注入 Agent**（`get_agent(system_prompt=dynamic_prompt)`）
7. **SSE 流式输出**（token / tool_start / tool_end / sources / done）
8. 保存 AI 回复 → 展示来源链接
9. **异步后处理**：更新画像 + 存储经验日志

#### `static/js/app.js` — 前端交互

**新增能力：**

| 功能 | 说明 |
|------|------|
| 思考过程可视化 | 解析 `【思考】...【回答】` 标签，思考内容以小字(13px)浅色(#8b949e)渲染 |
| 搜索指示器 | `tool_start` 时追加 DOM 元素（不覆盖已有内容），带旋转动画 |
| 用户反馈 | 点赞/点踩按钮，POST 到 `/api/chat/feedback` |
| 反馈防重复 | Set 记录已提交的反馈 ID |

**SSE 事件处理：**

| type | 处理方式 |
|------|---------|
| `token` | 追加到 fullReply → `formatContent()` 渲染 |
| `tool_start` | `appendChild` 搜索指示器（显示工具名称 + 旋转动画） |
| `tool_end` | `remove()` 移除搜索指示器 |
| `sources` | 收集去重，最终渲染来源卡片 |
| `done` | 更新 conversationId + 刷新对话列表 |
| `error` | 显示错误信息 |

---

## 📖 使用指南

### 1. 注册与登录

点击左下角「登录」→ 切换「注册」→ 输入用户名/邮箱/密码

### 2. 开始对话

- 直接输入问题，按 **Enter** 发送（**Shift+Enter** 换行）
- 或点击欢迎页快捷提示卡片

### 3. 上传图片/文档

点击输入框左侧 📎 按钮，支持 JPG/PNG/PDF/DOCX/TXT

### 4. 对话管理

- **新建聊天**：侧边栏顶部「新建聊天」
- **切换/删除/搜索**：侧边栏操作
- **导出对话**：右上角「导出此对话」→ Markdown 文件下载
- **停止生成**：输出中发送按钮变为 ⏹ 停止按钮
- **反馈评价**：AI 回复下方的 👍 / 👎 按钮

### 5. Agent 能力体验

| 你可以这样问 | Agent 会做什么 |
|-------------|--------------|
| "帮我规划一个 5 天的云南之旅" | 路由 Agent → 搜索天气/景点 → 规划逐日行程 |
| "东京现在什么天气？" | 天气 Agent → 调用 OpenWeatherMap → 返回 5 日预报 |
| "10000 人民币能换多少日元？" | 预算 Agent → 查询实时汇率 → 给出参考 |
| "去新加坡需要签证吗？" | 签证 Agent → 搜索最新政策 → 详细说明 |
| "上海迪士尼怎么走？" | 地图工具 → 高德路线规划 → 步骤导航 |
| "推荐上海附近的古镇" | POI 搜索 → 高德 POI → 名称/地址/评分/消费 |

---

## 📡 API 接口文档

启动后访问 **http://127.0.0.1:8000/docs** 查看 Swagger 文档。

| 方法 | 路径 | 说明 | 登录 |
|------|------|------|------|
| GET | / | 首页 | ❌ |
| POST | /api/auth/register | 用户注册 | ❌ |
| POST | /api/auth/login | 用户登录 | ❌ |
| GET | /api/chat/conversations | 获取对话列表 | ✅ |
| POST | /api/chat/conversations | 创建新对话 | ✅ |
| DELETE | /api/chat/conversations/{id} | 删除对话（**真实删除**关联消息） | ✅ |
| GET | /api/chat/conversations/{id}/messages | 获取消息列表 | ✅ |
| POST | /api/chat/stream | **流式聊天**（SSE） | ✅ |
| POST | /api/chat/upload | 文件上传 | ✅ |
| **GET** | **/api/chat/profile** | **获取当前用户画像** | ✅ |
| **PUT** | **/api/chat/profile** | **编辑用户画像偏好** | ✅ |
| **POST** | **/api/chat/feedback** | **提交反馈（点赞/点踩）** | ✅ |
| POST | /api/chat/upload | 文件上传 | ✅ |

### SSE 事件协议

```
data: {"type": "token", "content": "你好"}
data: {"type": "tool_start", "tool": "web_search"}
data: {"type": "tool_end"}
data: {"type": "sources", "sources": [{"title": "...", "url": "..."}]}
data: {"type": "done", "conversation_id": 1}
```

---

## ❓ 常见问题

### 1. AI 回复停留在 2024 年 / 输出过时信息

**已修复**。System Prompt 中会自动注入当前日期（如 `📅 当前日期：2026年6月15日 星期日`），且 Self-RAG 规则要求涉及日期/事件的问题必须调用搜索工具验证。

如果仍有问题，检查：
- `config/.env` 中的 `DASHSCOPE_MODEL` 是否正确
- 或考虑更换为 **GPT-4o-mini**（tool calling 能力更强）

### 2. 搜索时不显示已有内容

**已修复**。搜索指示器现在追加在已有内容末尾（而非覆盖），参考 DeepSeek/豆包风格。

### 3. 依赖安装失败（langchain-core 版本冲突）

```
langchain>=0.3.0
langgraph>=0.2.28
```

### 4. 新增数据表未创建

重启服务器即可，SQLAlchemy 会自动创建 `user_profile` 和 `experience_log` 表。

### 5. 高德地图工具不工作

确认 `config/.env` 中配置了 `AMAP_API_KEY`，并在[高德开放平台](https://lbs.amap.com/)创建了 Web 服务类型的应用。

### 6. 想更换 LLM 模型

修改 `config/.env`：
```env
# 替换为 OpenAI
DASHSCOPE_BASE_URL=https://api.openai.com/v1
DASHSCOPE_API_KEY=sk-你的OpenAI_Key
DASHSCOPE_MODEL=gpt-4o-mini

# 或替换为 DeepSeek
DASHSCOPE_BASE_URL=https://api.deepseek.com/v1
DASHSCOPE_API_KEY=sk-你的DeepSeek_Key
DASHSCOPE_MODEL=deepseek-chat
```

### 7. Python 3.10 f-string 反斜杠报错

```python
# 错误
f"data: {json.dumps({'content': 'text\n'})}"
# 正确
newline = "\n"
f"data: {json.dumps({'content': f'text{newline}'})}"
```

---

## 📄 License

本项目仅供学习交流使用。
