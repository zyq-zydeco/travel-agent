"""聊天相关的请求/响应数据模型"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None
    files: Optional[List[dict]] = None

class ConversationResponse(BaseModel):
    """对话信息响应"""
    id: int
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """消息信息响应"""
    id: int
    role: str
    content: str
    files: list
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    """对话列表响应 - 按时间分组"""
    today: List[ConversationResponse] = []
    last_3_days: List[ConversationResponse] = []
    last_week: List[ConversationResponse] = []
    last_30_days: List[ConversationResponse] = []
