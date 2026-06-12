"""聊天路由 - 对话管理和消息"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.models.user import User
from backend.app.models.conversation import Conversation
from backend.app.models.message import Message
from backend.app.schemas.chat import (
    ChatRequest,
    ConversationResponse,
    MessageResponse,
    ConversationListResponse,
)

router = APIRouter(prefix="/api/chat", tags=["聊天"])


@router.get("/conversations", response_model=ConversationListResponse)
def get_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前用户的对话列表，按时间分类返回"""
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    three_days_ago = today_start - timedelta(days=3)
    seven_days_ago = today_start - timedelta(days=7)
    thirty_days_ago = today_start - timedelta(days=30)

    return ConversationListResponse(
        today=[c for c in conversations if c.updated_at >= today_start],
        last_3_days=[c for c in conversations if three_days_ago <= c.updated_at < today_start],
        last_week=[c for c in conversations if seven_days_ago <= c.updated_at < three_days_ago],
        last_30_days=[c for c in conversations if thirty_days_ago <= c.updated_at < seven_days_ago],
    )


@router.post("/conversations", response_model=ConversationResponse)
def create_conversation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建新对话"""
    conversation = Conversation(user_id=current_user.id, title="新聊天")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
def get_messages(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取某个对话的所有消息"""
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")
    return conversation.messages


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除对话及其所有消息"""
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")
    db.delete(conversation)
    db.commit()
    return {"message": "对话已删除"}


@router.put("/conversations/{conversation_id}/title")
def update_conversation_title(
    conversation_id: int,
    title: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新对话标题"""
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")
    conversation.title = title
    db.commit()
    return {"message": "标题已更新"}

@router.post("/send")
def send_message(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """发送消息（临时版本，后续替换为 LangGraph 流式输出）"""

    # 如果没有对话ID，创建新对话
    if not request.conversation_id:
        conversation = Conversation(user_id=current_user.id, title="新聊天")
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        request.conversation_id = conversation.id

    # 保存用户消息
    user_msg = Message(
        conversation_id=request.conversation_id,
        role="user",
        content=request.message,
        files=request.files or [],
    )
    db.add(user_msg)

    # 生成临时回复（后续替换为 AI 回复）
    reply = f"收到你的消息：「{request.message}」\n\n这是临时回复，AI 功能将在第五步接入。"
    ai_msg = Message(
        conversation_id=request.conversation_id,
        role="assistant",
        content=reply,
    )
    db.add(ai_msg)

    # 用用户第一条消息的前20个字作为对话标题
    conversation = db.query(Conversation).filter(Conversation.id == request.conversation_id).first()
    if conversation and conversation.title == "新聊天":
        conversation.title = request.message[:20] + ("..." if len(request.message) > 20 else "")

    db.commit()

    return {
        "conversation_id": request.conversation_id,
        "reply": reply,
    }
