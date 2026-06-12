import os
import uuid
from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.models.user import User

router = APIRouter(tags=["文件上传"])

UPLOAD_DIR = os.path.join(os.path.dirname(__file__).replace("\\", "/").split("backend")[0], "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {
    "image": [".jpg", ".jpeg", ".png", ".gif", ".webp"],
    "document": [".pdf", ".doc", ".docx", ".txt"],
}


def get_file_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    for ftype, extensions in ALLOWED_EXTENSIONS.items():
        if ext in extensions:
            return ftype
    return "unknown"


@router.post("/api/chat/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """上传文件，返回文件信息"""
    # 检查文件类型
    ext = os.path.splitext(file.filename)[1].lower()
    all_allowed = []
    for exts in ALLOWED_EXTENSIONS.values():
        all_allowed.extend(exts)

    if ext not in all_allowed:
        return {"error": f"不支持的文件类型：{ext}"}

    # 生成唯一文件名
    file_id = uuid.uuid4().hex[:8]
    save_name = f"{file_id}_{file.filename}"
    save_path = os.path.join(UPLOAD_DIR, save_name)

    # 保存文件
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    file_type = get_file_type(file.filename)

    return {
        "file_id": file_id,
        "filename": file.filename,
        "save_name": save_name,
        "file_type": file_type,
        "size": len(content),
    }
