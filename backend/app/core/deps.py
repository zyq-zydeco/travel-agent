"""FastAPI 依赖项 - 获取当前登录用户"""
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from ..models.user import User
from .database import get_db
from .security import decode_access_token


def get_current_user(
    authorization: str = Header(..., description="Bearer Token"),
    db: Session = Depends(get_db),
) -> User:
    """从请求头中提取 Token，验证并返回当前用户"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="无效的认证格式，请使用 Bearer Token")

    token = authorization[7:]  # 去掉 "Bearer " 前缀
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")

    user_id = int(payload.get("sub", 0))
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

    return user
