# 🗺️ 旅行专家智能体 (Travel Expert Agent)

基于 **FastAPI + LangGraph + HTML/CSS/JS** 构建的旅行规划 AI Agent 应用，支持流式对话、联网搜索、图片识别、文件上传、对话导出等功能，界面采用 ChatGPT 风格设计。

---

## 📋 目录

- [功能特性](#功能特性)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [环境配置](#环境配置)
- [快速启动](#快速启动)
- [代码架构详解](#代码架构详解)
- [使用指南](#使用指南)
- [API 接口文档](#api-接口文档)
- [常见问题](#常见问题)

---

## ✨ 功能特性

| 功能 | 描述 |
|------|------|
| 🤖 流式 AI 对话 | 基于 LangGraph + 通义千问，逐 token 实时流式输出，类 ChatGPT 体验 |
| 🔍 联网搜索 | 集成 Tavily 搜索引擎，自动获取最新旅行资讯、签证政策、优惠活动 |
| 📷 图片识别 | 上传景点/美食照片，自动调用 qwen-vl-plus 视觉模型识别并回答 |
| 📄 文件上传 | 支持 PDF/DOCX/TXT 文件上传，AI 自动读取内容并回答相关问题 |
| 🔗 参考来源 | AI 搜索后自动展示参考链接，支持点击跳转原文 |
| 📝 Markdown 渲染 | 表格、代码块、列表、粗体等 Markdown 格式完美渲染 |
| 💾 对话导出 | 支持将对话记录导出为 Markdown 文件下载到本地 |
| ⏹️ 停止生成 | AI 输出过程中可随时点击停止按钮中断生成 |
| 💬 多轮对话 | 自动保留上下文，支持多轮连续对话 |
| 📂 对话管理 | 新建聊天、切换对话、删除对话、搜索对话 |
| 🔐 用户认证 | 注册/登录/登出，JWT Token 鉴权 |
| 📱 响应式布局 | 适配桌面端和移动端，侧边栏可折叠 |

---

## 🛠️ 技术栈

### 后端

| 技术 | 用途 |
|------|------|
| Python 3.10 | 开发语言 |
| FastAPI | Web 框架 |
| SQLAlchemy 2.0 | ORM 数据库操作 |
| MySQL 8.0 + PyMySQL | 数据库 |
| LangChain 0.3 | LLM 应用开发框架 |
| LangGraph 0.2 | AI Agent 工作流编排 |
| LangChain-OpenAI | 通义千问 API 对接（兼容 OpenAI 接口） |
| LangChain-Tavily | 联网搜索工具 |
| PyJWT + PassLib | JWT 认证 + 密码加密 |
| PyMuPDF | PDF 文件文本提取 |
| python-docx | DOCX 文件文本提取 |

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
| qwen-plus | 通义千问文本模型，主对话生成 |
| qwen-vl-plus | 通义千问视觉模型，图片识别 |

### 外部 API

| 服务 | 用途 |
|------|------|
| 通义千问 DashScope | AI 大模型 API |
| Tavily Search | 联网搜索引擎 |

---

## 📁 项目结构

```
travel-agent/
├── main.py                          # 应用入口，FastAPI 配置与启动
├── requirements.txt                 # Python 依赖列表
├── config/
│   └── .env                         # 环境变量配置（API Key、数据库等）
├── uploads/                         # 用户上传文件存储目录
├── backend/
│   └── app/
│       ├── core/                    # 核心配置模块
│       │   ├── config.py            #   全局配置读取（.env）
│       │   ├── database.py          #   数据库连接与会话管理
│       │   ├── security.py          #   JWT 令牌 + 密码加密
│       │   └── deps.py              #   依赖注入（获取当前用户）
│       ├── models/                  # SQLAlchemy 数据模型
│       │   ├── user.py              #   用户表模型
│       │   ├── conversation.py      #   对话表模型
│       │   └── message.py           #   消息表模型
│       ├── schemas/                 # Pydantic 数据校验模型
│       │   ├── auth.py              #   认证相关（注册/登录/Token）
│       │   └── chat.py              #   聊天相关（对话/消息/请求）
│       ├── api/
│       │   └── routers/             # API 路由
│       │       ├── auth.py          #   认证接口（注册/登录）
│       │       ├── chat.py          #   聊天接口（对话列表/消息/删除）
│       │       ├── stream.py        #   流式聊天接口（SSE 实时推送）
│       │       └── upload.py        #   文件上传接口
│       └── services/                # 业务逻辑层
│           ├── llm.py               #   LLM 实例管理（文本+视觉模型）
│           ├── tools.py             #   搜索工具（Tavily）
│           ├── agent.py             #   LangGraph Agent 定义
│           ├── image_recognizer.py  #   图片识别服务
│           └── file_processor.py    #   文件处理服务（PDF/DOCX/TXT）
└── frontend/
    ├── templates/
    │   └── index.html               # 主页面 HTML
    └── static/
        ├── css/
        │   └── style.css            # 全局样式
        ├── js/
        │   └── app.js               # 前端交互逻辑
        └── images/                  # 静态图片资源
```

## ⚙️ 环境配置

### 1. Python 环境

- **Python 版本**：3.10
- **开发工具**：PyCharm（推荐）或 VS Code
- **终端**：PowerShell（Windows）

### 2. MySQL 数据库

- **版本**：MySQL 8.0
- **安装**：[MySQL 官网下载](https://dev.mysql.com/downloads/)
- **创建数据库**：

```sql
CREATE DATABASE travel_agent DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 3. 通义千问 API Key

1. 访问 [DashScope 控制台](https://dashscope.console.aliyun.com/)
2. 登录阿里云账号（没有就注册）
3. 点击左侧「API-KEY 管理」→「创建新的 API-KEY」
4. 复制 `sk-` 开头的 Key
5. 确保已开通 `qwen-plus` 和 `qwen-vl-plus` 模型权限

### 4. Tavily 搜索 API Key

1. 访问 [Tavily 官网](https://tavily.com/)
2. 注册账号
3. 在 Dashboard 中复制 API Key（`tvly-` 开头）

---

## 🚀 快速启动

### 第一步：创建项目

```powershell
# 在 PyCharm 中新建项目
# 项目路径：D:\travel-agent
# Python 解释器：新建虚拟环境（venv），Python 3.10
```

### 第二步：安装依赖

```powershell
cd D:\travel-agent
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 第三步：配置环境变量

编辑 `config/.env` 文件，填入你的配置：

```env
# 数据库配置
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=你的MySQL密码
DB_NAME=travel_agent

# JWT 密钥
SECRET_KEY=travel-agent-secret-key-2024

# 通义千问 API Key
DASHSCOPE_API_KEY=sk-你的Key

# Tavily 搜索 API Key
TAVILY_API_KEY=tvly-你的Key
```

### 第四步：创建数据库

```sql
CREATE DATABASE travel_agent DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 第五步：启动服务器

```powershell
cd D:\travel-agent
python main.py
```

看到以下输出说明启动成功：

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

### 第六步：访问应用

浏览器打开 **http://127.0.0.1:8000**

---

## 🏗️ 代码架构详解

### 后端核心模块

#### `core/config.py` — 全局配置

- 使用 `pydantic-settings` 自动从 `.env` 文件加载配置
- 包含数据库、JWT、通义千问、Tavily 的所有配置项
- `Settings` 类提供类型安全的配置访问
- `extra = "ignore"` 忽略 `.env` 中的多余字段，避免报错

#### `core/database.py` — 数据库连接

- 使用 SQLAlchemy 2.0 的声明式映射
- `engine`：数据库引擎，连接 MySQL
- `SessionLocal`：会话工厂，每次请求创建独立会话
- `get_db()`：FastAPI 依赖注入函数，自动管理会话生命周期
- `Base`：所有模型的基类

#### `core/security.py` — 安全模块

- `hash_password()` — 密码加密（bcrypt）
- `verify_password()` — 密码校验
- `create_access_token()` — 生成 JWT Token（有效期 24 小时）
- `decode_access_token()` — 解析验证 JWT Token

#### `core/deps.py` — 依赖注入

- `get_current_user()` — 从请求头 Authorization 中提取 Bearer Token，解析后返回当前用户对象
- 所有需要登录的接口都通过 `Depends(get_current_user)` 获取当前用户

### 数据模型

#### `models/user.py` — 用户表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer (主键) | 用户 ID |
| username | String(50, 唯一) | 用户名 |
| email | String(100, 唯一) | 邮箱 |
| hashed_password | String(200) | 加密后的密码 |
| is_active | Boolean | 是否激活 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

#### `models/conversation.py` — 对话表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer (主键) | 对话 ID |
| user_id | Integer (外键) | 所属用户 |
| title | String(100) | 对话标题 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

#### `models/message.py` — 消息表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer (主键) | 消息 ID |
| conversation_id | Integer (外键) | 所属对话 |
| role | String(20) | 角色：user / assistant |
| content | Text | 消息内容 |
| files | JSON | 附件信息列表 |
| created_at | DateTime | 创建时间 |

### API 路由

#### `api/routers/auth.py` — 认证接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /register | 用户注册，返回 JWT Token |
| POST | /login | 用户登录，返回 JWT Token |

- 注册时自动检测用户名/邮箱是否重复
- 密码使用 bcrypt 加密存储
- 登录成功返回 `access_token` + 用户信息

#### `api/routers/chat.py` — 对话管理接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /conversations | 获取对话列表（按时间分组） |
| POST | /conversations | 创建新对话 |
| GET | /conversations/{id}/messages | 获取指定对话的消息列表 |
| DELETE | /conversations/{id} | 删除对话 |
| PUT | /conversations/{id}/title | 更新对话标题 |
| POST | /send | 发送消息（临时版本，非流式） |

- 对话列表按时间分组返回：今天 / 近3天 / 近7天 / 近30天
- 所有接口需要 Bearer Token 鉴权

#### `api/routers/stream.py` — 流式聊天接口（核心）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /stream | 流式聊天，SSE 实时推送 |

**工作流程：**

1. 接收用户消息 + 可选附件
2. 如有图片，先用 `qwen-vl-plus` 视觉模型识别图片内容
3. 如有文档，先提取文本内容
4. 构建上下文消息（最近10条）
5. 调用 LangGraph Agent 流式生成回复
6. 通过 SSE（Server-Sent Events）逐 token 推送到前端
7. 搜索工具调用时，提取来源链接并推送
8. 生成完成后保存到数据库

**SSE 事件类型：**

| type | 说明 | data 字段 |
|------|------|-----------|
| token | AI 输出的文本片段 | content: string |
| tool_start | 开始调用搜索工具 | tool: string |
| tool_end | 搜索工具调用结束 | — |
| sources | 搜索参考来源列表 | sources: [{title, url}] |
| done | 生成完成 | conversation_id: int |
| error | 发生错误 | content: string |

#### `api/routers/upload.py` — 文件上传接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /upload | 上传文件，返回文件信息 |

- 支持格式：JPG/JPEG/PNG/GIF/WEBP/PDF/DOC/DOCX/TXT
- 文件保存到 `uploads/` 目录
- 返回文件 ID、文件名、保存名、文件类型、文件大小

### 业务逻辑层

#### `services/llm.py` — LLM 管理

- `get_llm(streaming=True)` — 获取通义千问文本模型实例（qwen-plus），用于主对话
- `get_vision_llm()` — 获取通义千问视觉模型实例（qwen-vl-plus），用于图片识别
- 两个模型共用同一个 `DASHSCOPE_API_KEY`，通过 `DASHSCOPE_BASE_URL` 兼容 OpenAI 接口

#### `services/tools.py` — 搜索工具

- `get_search_tool()` — 获取 Tavily 搜索工具实例
- `get_tools()` — 返回所有工具列表（目前只有搜索）
- 优先使用 `langchain-tavily`（新版），如未安装则降级使用 `langchain-community` 版本
- 搜索结果默认返回 5 条

#### `services/agent.py` — LangGraph Agent

- 使用 `create_react_agent` 创建 ReAct 模式的 Agent
- Agent 可以自主决定是否调用搜索工具
- 系统提示词定义了旅行专家的角色、能力和回答要求
- 要求 AI 使用搜索工具后必须在末尾列出参考来源

#### `services/image_recognizer.py` — 图片识别

- `recognize_image(save_name, user_question)` — 调用视觉模型识别图片
- 将图片转为 base64 编码后传给 `qwen-vl-plus`
- 提示词引导模型从景点、美食、住宿等角度分析
- 返回图片描述文本，供旅行专家 Agent 使用

#### `services/file_processor.py` — 文件处理

- `process_image(save_name)` — 将图片转为 base64 编码
- `process_document(save_name)` — 提取文档文本内容
  - PDF：使用 PyMuPDF (fitz) 逐页提取
  - DOCX：使用 python-docx 逐段提取
  - TXT：直接读取文件内容
- 文本内容限制 5000 字符，避免 Token 过多
- `process_file(save_name, file_type)` — 统一入口，根据文件类型选择处理方式

### 前端模块

#### `templates/index.html` — 页面结构

- **左侧边栏**：新建聊天、搜索框、对话列表、登录/用户区
- **主聊天区**：顶部栏、消息区域、输入区域
- **弹窗**：登录/注册弹窗、导出弹窗
- 外部依赖：Font Awesome、Marked.js、Highlight.js

#### `static/css/style.css` — 样式系统

- CSS 变量定义全局主题色（深色 ChatGPT 风格）
- 侧边栏（260px）+ 主聊天区自适应布局
- 消息气泡样式（用户/AI 区分）
- 搜索来源卡片样式
- Markdown 渲染样式（表格、代码块、列表等）
- 停止按钮样式（发送按钮状态切换）
- 移动端响应式适配

#### `static/js/app.js` — 交互逻辑

**全局状态管理：**

- `authToken` — JWT Token（localStorage 持久化）
- `currentUser` — 当前用户信息
- `currentConversationId` — 当前对话 ID
- `isStreaming` — 是否正在流式输出
- `abortController` — 用于中断请求
- `selectedFiles` — 已选择的文件列表

**核心函数：**

| 函数 | 说明 |
|------|------|
| `initSidebar()` | 侧边栏事件绑定（折叠/新建/搜索） |
| `initAuth()` | 认证事件绑定（登录/注册/登出） |
| `initChat()` | 聊天事件绑定（发送/附件/快捷提示） |
| `initExport()` | 导出事件绑定 |
| `sendMessage()` | 核心函数：发送消息 + 接收流式回复 |
| `loadConversations()` | 加载对话列表 |
| `switchConversation()` | 切换对话 |
| `exportAsMarkdown()` | 导出对话为 Markdown 文件 |
| `formatContent()` | 使用 Marked.js 渲染 Markdown |
| `updateSendButton()` | 切换发送/停止按钮状态 |

**流式输出处理：**

- 使用 `fetch` + `ReadableStream` 读取 SSE 事件
- 逐 token 拼接内容并实时渲染到页面
- 搜索时显示"正在搜索最新信息..."提示
- 收到来源数据时渲染来源卡片
- 支持 `AbortController` 中断请求

---

## 📖 使用指南

### 1. 注册与登录

1. 点击左下角「登录」按钮
2. 在弹窗中切换到「注册」标签
3. 输入用户名、邮箱、密码完成注册
4. 注册成功后自动登录

### 2. 开始对话

- 直接在输入框输入问题，按 **Enter** 发送
- **Shift + Enter** 换行
- 也可以点击欢迎页的快捷提示卡片快速提问

### 3. 上传图片

1. 点击输入框左侧的 📎 按钮
2. 选择图片文件（JPG/PNG/GIF/WEBP）
3. 输入问题（如"这是哪个景点？"）
4. 点击发送，AI 会自动识别图片并回答

### 4. 上传文档

1. 点击 📎 按钮，选择 PDF/DOCX/TXT 文件
2. 输入问题（如"根据这个文档帮我规划行程"）
3. AI 会读取文档内容后回答

### 5. 对话管理

- **新建聊天**：点击侧边栏顶部「新建聊天」
- **切换对话**：点击侧边栏中的对话项
- **删除对话**：鼠标悬停对话项，点击 🗑️ 按钮
- **搜索对话**：在搜索框中输入关键词

### 6. 导出对话

1. 点击右上角「导出此对话」按钮
2. 点击「确认导出」
3. Markdown 文件自动下载到本地

### 7. 停止生成

- AI 输出过程中，发送按钮变为 ⏹ 停止按钮
- 点击停止按钮可立即中断 AI 生成

---

## 📡 API 接口文档

启动服务器后访问 **http://127.0.0.1:8000/docs** 可查看自动生成的 Swagger 文档。

| 方法 | 路径 | 说明 | 需要登录 |
|------|------|------|----------|
| GET | / | 首页 | ❌ |
| GET | /api/health | 健康检查 | ❌ |
| POST | /api/auth/register | 用户注册 | ❌ |
| POST | /api/auth/login | 用户登录 | ❌ |
| GET | /api/chat/conversations | 获取对话列表 | ✅ |
| POST | /api/chat/conversations | 创建对话 | ✅ |
| GET | /api/chat/conversations/{id}/messages | 获取消息列表 | ✅ |
| DELETE | /api/chat/conversations/{id} | 删除对话 | ✅ |
| PUT | /api/chat/conversations/{id}/title | 更新标题 | ✅ |
| POST | /api/chat/send | 发送消息（非流式） | ✅ |
| POST | /api/chat/stream | 流式聊天（SSE） | ✅ |
| POST | /api/chat/upload | 上传文件 | ✅ |

---

## ❓ 常见问题

### 1. 依赖安装失败（langchain-core 版本冲突）

LangChain 0.3 + LangGraph 0.2 存在 `langchain-core` 版本冲突，需在 `requirements.txt` 中使用 `>=` 范围版本号让 pip 自动解决：

```
langchain>=0.3.0
langgraph>=0.2.28
```

### 2. PyCharm 导入报红

- 将项目根目录标记为 **Sources Root**（右键 → Mark Directory as → Sources Root）
- 项目中使用绝对导入（`from backend.app.xxx`）而非相对导入

### 3. MySQL 连接失败

- 确认 MySQL 服务已启动
- 检查 `config/.env` 中的 `DB_PASSWORD` 是否正确
- 确认数据库 `travel_agent` 已创建

### 4. 注册接口报 500 错误（Unknown column）

说明数据库表结构与模型不同步，需要重建表：

```sql
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS messages, conversations, users;
SET FOREIGN_KEY_CHECKS = 1;
```

然后重启服务器，SQLAlchemy 会自动重建表。

### 5. AI 回复"无法识别图片"

- 确认 `DASHSCOPE_API_KEY` 已正确配置
- 确认通义千问账号已开通 `qwen-vl-plus` 模型权限
- 在 DashScope 控制台检查 API 调用额度

### 6. 搜索功能不工作

- 确认 `TAVILY_API_KEY` 已正确配置
- 检查 Tavily 账号的免费额度是否用完

### 7. Python 3.10 f-string 反斜杠报错

Python 3.10 不允许在 f-string 的大括号表达式 `{}` 内使用反斜杠（如 `\n`），需提取到变量：

```python
# 错误写法
f"data: {json.dumps({'content': 'text\n'})}"

# 正确写法
newline = "\n"
f"data: {json.dumps({'content': f'text{newline}'})}"
```

### 8. 服务器启动后立即退出（返回码0）

确认 `main.py` 末尾有启动代码：

```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
```

---

## 📄 License

本项目仅供学习交流使用。