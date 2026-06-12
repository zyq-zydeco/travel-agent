/* ====== 旅行专家智能体 - 前端逻辑 ====== */

// ====== API 基础地址 ======
const API_BASE = "http://127.0.0.1:8000";

// ====== 全局状态 ======
let authToken = localStorage.getItem("token") || null;
let currentUser = JSON.parse(localStorage.getItem("user") || "null");
let currentConversationId = null;
let isStreaming = false;
let abortController = null;

// ====== 页面加载完成后初始化 ======
document.addEventListener("DOMContentLoaded", () => {
    initSidebar();
    initAuth();
    initChat();
    checkAuth();
    initExport();
});

// ====== 侧边栏相关 ======
function initSidebar() {
    const sidebar = document.getElementById("sidebar");
    const toggleBtn = document.getElementById("sidebarToggle");
    const newChatBtn = document.getElementById("newChatBtn");
    const searchInput = document.getElementById("searchInput");

    toggleBtn.addEventListener("click", () => {
        sidebar.classList.toggle("collapsed");
    });

    newChatBtn.addEventListener("click", () => {
        if (!authToken) {
            showAuthModal();
            return;
        }
        startNewChat();
    });

    searchInput.addEventListener("input", (e) => {
        filterConversations(e.target.value);
    });
}

// ====== 认证相关 ======
function initAuth() {
    const loginBtn = document.getElementById("loginBtn");
    const logoutBtn = document.getElementById("logoutBtn");
    const modalClose = document.getElementById("modalClose");
    const authModal = document.getElementById("authModal");
    const tabBtns = document.querySelectorAll(".tab-btn");
    const loginForm = document.getElementById("loginForm");
    const registerForm = document.getElementById("registerForm");

    loginBtn.addEventListener("click", showAuthModal);
    logoutBtn.addEventListener("click", logout);
    modalClose.addEventListener("click", () => {
        authModal.style.display = "none";
    });

    authModal.addEventListener("click", (e) => {
        if (e.target === authModal) authModal.style.display = "none";
    });

    // 切换登录/注册标签
    tabBtns.forEach((btn) => {
        btn.addEventListener("click", () => {
            tabBtns.forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");
            const tab = btn.dataset.tab;
            loginForm.style.display = tab === "login" ? "block" : "none";
            registerForm.style.display = tab === "register" ? "block" : "none";
        });
    });

    // 登录表单提交
    loginForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const username = loginForm.username.value.trim();
        const password = loginForm.password.value;
        await handleAuth("/api/auth/login", { username, password });
    });

    // 注册表单提交
    registerForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const username = registerForm.username.value.trim();
        const email = registerForm.email.value.trim();
        const password = registerForm.password.value;
        await handleAuth("/api/auth/register", { username, email, password });
    });
}

async function handleAuth(endpoint, data) {
    try {
        const res = await fetch(`${API_BASE}${endpoint}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
        });

        const result = await res.json();

        if (!res.ok) {
            alert(result.detail || "操作失败，请重试");
            return;
        }

        // 保存登录信息
        authToken = result.access_token;
        currentUser = result.user;
        localStorage.setItem("token", authToken);
        localStorage.setItem("user", JSON.stringify(currentUser));

        // 更新 UI
        updateAuthUI();
        document.getElementById("authModal").style.display = "none";
        loadConversations();
    } catch (err) {
        alert("网络错误，请检查服务器是否启动");
        console.error(err);
    }
}

function logout() {
    authToken = null;
    currentUser = null;
    currentConversationId = null;
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    updateAuthUI();
    document.getElementById("conversationList").innerHTML = `
        <div class="empty-state">
            <i class="fas fa-comments"></i>
            <p>暂无对话</p>
        </div>`;
    startNewChat();
}

function showAuthModal() {
    document.getElementById("authModal").style.display = "flex";
}

function updateAuthUI() {
    const userInfo = document.getElementById("userInfo");
    const loginBtn = document.getElementById("loginBtn");
    const exportBtn = document.getElementById("exportBtn");

    if (currentUser) {
        userInfo.style.display = "flex";
        document.getElementById("username").textContent = currentUser.username;
        loginBtn.style.display = "none";
        exportBtn.style.display = "inline-block";
    } else {
        userInfo.style.display = "none";
        loginBtn.style.display = "flex";
        exportBtn.style.display = "none";
    }
}

function checkAuth() {
    if (authToken && currentUser) {
        updateAuthUI();
        loadConversations();
    }
}

// ====== 对话列表相关 ======
async function loadConversations() {
    if (!authToken) return;

    try {
        const res = await fetch(`${API_BASE}/api/chat/conversations`, {
            headers: { Authorization: `Bearer ${authToken}` },
        });
        if (res.status === 401) {
            logout();
            return;
        }
        const data = await res.json();
        renderConversations(data);
    } catch (err) {
        console.error("加载对话列表失败:", err);
    }
}

function renderConversations(data) {
    const list = document.getElementById("conversationList");
    let html = "";

    const groups = [
        { label: "今天", items: data.today },
        { label: "近3天", items: data.last_3_days },
        { label: "近7天", items: data.last_week },
        { label: "近30天", items: data.last_30_days },
    ];

    let hasAny = false;
    groups.forEach((group) => {
        if (group.items && group.items.length > 0) {
            hasAny = true;
            html += `<div class="conversation-group-label">${group.label}</div>`;
            group.items.forEach((conv) => {
                const isActive = conv.id === currentConversationId ? "active" : "";
                html += `
                    <div class="conversation-item ${isActive}" data-id="${conv.id}" onclick="switchConversation(${conv.id})">
                        <span class="conv-title">${escapeHtml(conv.title)}</span>
                        <button class="delete-btn" onclick="event.stopPropagation(); deleteConversation(${conv.id})" title="删除">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>`;
            });
        }
    });

    if (!hasAny) {
        html = `<div class="empty-state"><i class="fas fa-comments"></i><p>暂无对话</p></div>`;
    }

    list.innerHTML = html;
}

async function switchConversation(id) {
    currentConversationId = id;
    document.querySelectorAll(".conversation-item").forEach((el) => {
        el.classList.toggle("active", parseInt(el.dataset.id) === id);
    });
    await loadMessages(id);
}

async function deleteConversation(id) {
    if (!confirm("确定删除这个对话吗？")) return;

    try {
        await fetch(`${API_BASE}/api/chat/conversations/${id}`, {
            method: "DELETE",
            headers: { Authorization: `Bearer ${authToken}` },
        });
        if (currentConversationId === id) {
            startNewChat();
        }
        loadConversations();
    } catch (err) {
        console.error("删除对话失败:", err);
    }
}

function filterConversations(keyword) {
    const items = document.querySelectorAll(".conversation-item");
    const lower = keyword.toLowerCase();
    items.forEach((item) => {
        const title = item.querySelector(".conv-title").textContent.toLowerCase();
        item.style.display = title.includes(lower) ? "" : "none";
    });
}

// ====== 聊天消息相关 ======
function initChat() {
    const messageInput = document.getElementById("messageInput");
    const sendBtn = document.getElementById("sendBtn");
    const attachBtn = document.getElementById("attachBtn");
    const fileInput = document.getElementById("fileInput");

    // 自动调整输入框高度
    messageInput.addEventListener("input", () => {
        messageInput.style.height = "auto";
        messageInput.style.height = Math.min(messageInput.scrollHeight, 150) + "px";
    });

    // Enter 发送，Shift+Enter 换行
    messageInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    sendBtn.addEventListener("click", sendMessage);

    // 附件
    attachBtn.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", handleFileSelect);

    // 快捷提示
    document.querySelectorAll(".prompt-card").forEach((card) => {
        card.addEventListener("click", () => {
            const prompt = card.dataset.prompt;
            document.getElementById("messageInput").value = prompt;
            sendMessage();
        });
    });
}

function startNewChat() {
    currentConversationId = null;
    const chatMessages = document.getElementById("chatMessages");
    chatMessages.innerHTML = `
        <div class="welcome-screen" id="welcomeScreen">
            <div class="welcome-icon">
                <i class="fas fa-plane-departure"></i>
            </div>
            <h2>你好，我是旅行专家</h2>
            <p>告诉我你想去哪里，我来为你规划完美旅程</p>
            <div class="quick-prompts">
                <button class="prompt-card" data-prompt="帮我规划一个3天的成都之旅">
                    <i class="fas fa-map-marker-alt"></i>
                    <span>3天成都之旅</span>
                </button>
                <button class="prompt-card" data-prompt="推荐几个适合亲子游的海岛">
                    <i class="fas fa-umbrella-beach"></i>
                    <span>亲子海岛游</span>
                </button>
                <button class="prompt-card" data-prompt="日本7天深度游攻略，预算1万5">
                    <i class="fas fa-torii-gate"></i>
                    <span>日本深度游</span>
                </button>
                <button class="prompt-card" data-prompt="云南自驾游路线推荐，10天左右">
                    <i class="fas fa-car"></i>
                    <span>云南自驾游</span>
                </button>
            </div>
        </div>`;
    document.querySelectorAll(".prompt-card").forEach((card) => {
        card.addEventListener("click", () => {
            const prompt = card.dataset.prompt;
            document.getElementById("messageInput").value = prompt;
            sendMessage();
        });
    });
    document.querySelectorAll(".conversation-item").forEach((el) => el.classList.remove("active"));
}

async function loadMessages(conversationId) {
    try {
        const res = await fetch(
            `${API_BASE}/api/chat/conversations/${conversationId}/messages`,
            { headers: { Authorization: `Bearer ${authToken}` } }
        );
        const messages = await res.json();

        const chatMessages = document.getElementById("chatMessages");
        chatMessages.innerHTML = "";

        messages.forEach((msg) => {
            appendMessage(msg.role, msg.content);
        });
        scrollToBottom();
    } catch (err) {
        console.error("加载消息失败:", err);
    }
}

function appendMessage(role, content) {
    const chatMessages = document.getElementById("chatMessages");

    const welcome = document.getElementById("welcomeScreen");
    if (welcome) welcome.remove();

    const icon = role === "user" ? "fa-user" : "fa-robot";
    const msgClass = role === "user" ? "user-message" : "assistant-message";

    const div = document.createElement("div");
    div.className = `message ${msgClass}`;
    div.innerHTML = `
        <div class="message-avatar">
            <i class="fas ${icon}"></i>
        </div>
        <div class="message-content">${formatContent(content)}</div>`;
    chatMessages.appendChild(div);
    scrollToBottom();
    return div;
}

async function sendMessage() {
    const input = document.getElementById("messageInput");
    const message = input.value.trim();
        if (!message || isStreaming) {
        // 如果正在流式输出，点击则停止
        if (isStreaming && abortController) {
            abortController.abort();
            isStreaming = false;
            updateSendButton();
        }
        return;
    }

    if (!authToken) {
        showAuthModal();
        return;
    }

    // 显示用户消息
        // 如果有附件，先上传
    let uploadedFiles = [];
    if (selectedFiles.length > 0) {
        for (const file of selectedFiles) {
            try {
                const formData = new FormData();
                formData.append("file", file);
                const uploadRes = await fetch(`${API_BASE}/api/chat/upload`, {
                    method: "POST",
                    headers: { Authorization: `Bearer ${authToken}` },
                    body: formData,
                });
                if (uploadRes.ok) {
                    const fileInfo = await uploadRes.json();
                    if (!fileInfo.error) {
                        uploadedFiles.push(fileInfo);
                    }
                }
            } catch (e) {
                console.error("文件上传失败:", e);
            }
        }
        // 清除文件预览
        selectedFiles = [];
        document.getElementById("filePreviewArea").style.display = "none";
        document.getElementById("filePreviewArea").innerHTML = "";
    }

    // 显示用户消息（带附件标识）
    let displayMsg = message;
    if (uploadedFiles.length > 0) {
        displayMsg += "\n📎 " + uploadedFiles.map(f => f.filename).join(", ");
    }
    appendMessage("user", displayMsg);
    input.value = "";
    input.style.height = "auto";

    isStreaming = true;

    abortController = new AbortController();
    updateSendButton();

    // 创建 AI 消息气泡（先显示思考动画）
    const chatMessages = document.getElementById("chatMessages");
    const welcome = document.getElementById("welcomeScreen");
    if (welcome) welcome.remove();

    const aiDiv = document.createElement("div");
    aiDiv.className = "message assistant-message";
    aiDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fas fa-robot"></i>
        </div>
        <div class="message-content">
            <div class="typing-indicator">
                <span></span><span></span><span></span>
            </div>
        </div>`;
    chatMessages.appendChild(aiDiv);
    scrollToBottom();

    const contentDiv = aiDiv.querySelector(".message-content");
    let fullReply = "";
    let collectedSources = [];

    try {
            const res = await fetch(`${API_BASE}/api/chat/stream`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${authToken}`,
                },
                body: JSON.stringify({
                    message: message,
                    conversation_id: currentConversationId,
                    files: uploadedFiles.length > 0 ? uploadedFiles : undefined,
                }),
                signal: abortController.signal,
            });

        if (!res.ok) {
            contentDiv.innerHTML = "抱歉，请求失败，请稍后再试。";
            isStreaming = false;
            return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // 按行解析 SSE 数据
            const lines = buffer.split("\n");
            buffer = lines.pop() || "";  // 最后一行可能不完整，留到下次

            for (const line of lines) {
                if (!line.startsWith("data: ")) continue;
                const jsonStr = line.slice(6);

                try {
                    const data = JSON.parse(jsonStr);

                    if (data.type === "token") {
                        // 第一个 token 到达时，清除思考动画
                        if (fullReply === "") {
                            contentDiv.innerHTML = "";
                        }
                        fullReply += data.content;
                        contentDiv.innerHTML = formatContent(fullReply);
                        scrollToBottom();
                    } else if (data.type === "tool_start") {
                        // 显示搜索提示
                        if (fullReply === "") {
                            contentDiv.innerHTML = "";
                        }
                        const searchHint = `<span style="color:#10a37f;">🔍 正在搜索最新信息...</span><br>`;
                        contentDiv.innerHTML = searchHint;
                        scrollToBottom();
                    } else if (data.type === "tool_end") {
                        // 搜索完成，清空搜索提示，等待 AI 回复
                        if (fullReply === "") {
                            contentDiv.innerHTML = "";
                        }
                    } else if (data.type === "sources") {
                        collectedSources = data.sources;
                    } else if (data.type === "done") {
                        currentConversationId = data.conversation_id;
                        loadConversations();
                    } else if (data.type === "error") {
                        contentDiv.innerHTML = "抱歉，AI 服务暂时不可用：" + escapeHtml(data.content);
                    }
                } catch (e) {
                    // JSON 解析失败，跳过
                }
            }
        }

        // 如果没收到任何内容
        if (fullReply === "") {
            contentDiv.innerHTML = "抱歉，AI 未返回任何内容，请重试。";
        }

        // 渲染搜索来源链接
        if (collectedSources.length > 0) {
            let sourcesHtml = `<div class="sources-container">
                <div class="sources-header">
                    <i class="fas fa-globe"></i>
                    <span>${collectedSources.length} 个来源</span>
                </div>
                <div class="sources-list">`;
            collectedSources.forEach((s, i) => {
                const domain = new URL(s.url).hostname.replace("www.", "");
                sourcesHtml += `<a class="source-item" href="${s.url}" target="_blank" rel="noopener noreferrer">
                    <span class="source-index">${i + 1}</span>
                    <span class="source-title">${escapeHtml(s.title)}</span>
                    <span class="source-domain">${domain}</span>
                </a>`;
            });
            sourcesHtml += `</div></div>`;
            contentDiv.innerHTML += sourcesHtml;
        }

    } catch (err) {
        contentDiv.innerHTML = "网络错误，请检查服务器是否启动。";
        console.error(err);
    } finally {
        isStreaming = false;
        abortController = null;
        updateSendButton();
    }
}

// ====== 文件上传 ======
let selectedFiles = [];

function handleFileSelect(e) {
    const files = Array.from(e.target.files);
    const previewArea = document.getElementById("filePreviewArea");

    files.forEach((file) => {
        selectedFiles.push(file);
        const card = document.createElement("div");
        card.className = "file-card";
        card.innerHTML = `
            <i class="fas fa-file"></i>
            <span>${file.name}</span>
            <button class="remove-file" onclick="removeFile(this, '${file.name}')">
                <i class="fas fa-times"></i>
            </button>`;
        previewArea.appendChild(card);
    });

    if (selectedFiles.length > 0) {
        previewArea.style.display = "flex";
    }
    e.target.value = "";
}

function removeFile(btn, fileName) {
    selectedFiles = selectedFiles.filter((f) => f.name !== fileName);
    btn.parentElement.remove();
    if (selectedFiles.length === 0) {
        document.getElementById("filePreviewArea").style.display = "none";
    }
}

// ====== 工具函数 ======
function scrollToBottom() {
    const chatMessages = document.getElementById("chatMessages");
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function formatContent(text) {
    if (typeof marked !== "undefined") {
        marked.setOptions({
            breaks: true,
            gfm: true,
            highlight: function(code, lang) {
                if (typeof hljs !== "undefined" && lang && hljs.getLanguage(lang)) {
                    try {
                        return hljs.highlight(code, { language: lang }).value;
                    } catch (e) {}
                }
                return code;
            }
        });
        return marked.parse(text);
    }
    // 降级处理：如果没有加载 marked 库
    return text
        .replace(/\n/g, "<br>")
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
}

// ====== 导出功能 ======
function initExport() {
    const exportBtn = document.getElementById("exportBtn");
    const exportModal = document.getElementById("exportModal");
    const exportModalClose = document.getElementById("exportModalClose");
    const exportMarkdown = document.getElementById("exportMarkdown");

    exportBtn.addEventListener("click", () => {
        if (!currentConversationId) {
            alert("请先开始一段对话再导出");
            return;
        }
        exportModal.style.display = "flex";
    });

    exportModalClose.addEventListener("click", () => {
        exportModal.style.display = "none";
    });

    exportModal.addEventListener("click", (e) => {
        if (e.target === exportModal) exportModal.style.display = "none";
    });

    exportMarkdown.addEventListener("click", () => {
        exportModal.style.display = "none";
        exportAsMarkdown();
    });
}

async function getConversationMessages() {
    try {
        const res = await fetch(
            `${API_BASE}/api/chat/conversations/${currentConversationId}/messages`,
            { headers: { Authorization: `Bearer ${authToken}` } }
        );
        if (!res.ok) {
            const err = await res.json();
            alert("获取对话记录失败：" + (err.detail || res.status));
            return null;
        }
        return await res.json();
    } catch (e) {
        alert("网络错误，无法获取对话记录");
        console.error(e);
        return null;
    }
}

async function exportAsMarkdown() {
    const messages = await getConversationMessages();
    if (!messages) return;

    let md = `# 旅行专家 - 对话记录\n\n`;
    md += `> 导出时间：${new Date().toLocaleString("zh-CN")}\n\n---\n\n`;

    messages.forEach((msg) => {
        if (msg.role === "user") {
            md += `### 🧑 用户\n\n${msg.content}\n\n`;
        } else if (msg.role === "assistant") {
            md += `### 🤖 旅行专家\n\n${msg.content}\n\n`;
        }
    });

    md += `---\n*由旅行专家智能体导出*`;

    downloadFile(md, `旅行对话_${formatDate()}.md`, "text/markdown");
}

function downloadFile(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType + ";charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function formatDate() {
    const now = new Date();
    return `${now.getFullYear()}${String(now.getMonth()+1).padStart(2,"0")}${String(now.getDate()).padStart(2,"0")}_${String(now.getHours()).padStart(2,"0")}${String(now.getMinutes()).padStart(2,"0")}`;
}

function updateSendButton() {
    const sendBtn = document.getElementById("sendBtn");
    const messageInput = document.getElementById("messageInput");

    if (isStreaming) {
        sendBtn.classList.add("stopping");
        sendBtn.title = "停止生成";
        messageInput.placeholder = "AI 正在回复中，点击停止按钮中断...";
    } else {
        sendBtn.classList.remove("stopping");
        sendBtn.title = "发送";
        messageInput.placeholder = "输入你的旅行问题...";
    }
}