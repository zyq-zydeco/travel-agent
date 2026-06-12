import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import HTMLResponse

from backend.app.core.database import engine, Base
from backend.app.api.routers import auth, chat, stream, upload

# 创建数据库表
Base.metadata.create_all(bind=engine)

app = FastAPI(title="旅行专家智能体")

# CORS 跨域配置
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router, tags=["认证"])
app.include_router(chat.router, tags=["聊天"])
app.include_router(stream.router, tags=["流式聊天"])
app.include_router(upload.router, tags=["文件上传"])

# ====== 前端静态文件 ======
FRONTEND_DIR = PROJECT_ROOT / "frontend"

# 挂载静态资源（CSS/JS/图片）
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")

app.mount("/uploads", StaticFiles(directory=str(PROJECT_ROOT / "uploads")), name="uploads")

# 模板引擎
templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))


# 首页路由
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# 健康检查
@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "旅行专家智能体服务运行中"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
