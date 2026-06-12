"""用户相关的请求/响应数据模型"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserRegister(BaseModel):
    """注册请求"""
    username: str
    email: str
    password: str


class UserLogin(BaseModel):
    """登录请求"""
    username: str
    password: str


class UserResponse(BaseModel):
    """用户信息响应"""
    id: int
    username: str
    email: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """登录/注册成功后的 Token 响应"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
