"""聊天路由 - 对话管理和消息"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
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
import logging

logger = logging.getLogger(__name__)

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
    try:
        logger.info(f"用户 {current_user.username}(id={current_user.id}) 请求删除对话 {conversation_id}")

        # 查询对话
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

        # 先删除关联的所有消息
        msg_count = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).delete(synchronize_session=False)
        logger.info(f"已删除对话 {conversation_id} 下的 {msg_count} 条消息")

        # 再删除对话本身
        db.delete(conversation)
        db.commit()

        logger.info(f"对话 {conversation_id} 删除成功")
        return {"message": "对话已删除", "deleted_messages": msg_count}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除对话 {conversation_id} 失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


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


# ====== 用户画像 API ======

@router.get("/profile")
def get_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前用户的旅行画像"""
    from backend.app.services.memory import get_or_create_profile, format_profile_for_prompt
    import logging
    logger = logging.getLogger(__name__)
    
    profile = get_or_create_profile(db, current_user.id)
    
    return {
        "user_id": profile.user_id,
        "preferences": profile.preferences or {},
        "visited_destinations": profile.visited_destinations or [],
        "travel_history": profile.travel_history or [],
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        "formatted_for_prompt": format_profile_for_prompt(profile),
    }


@router.put("/profile")
def update_user_profile(
    preferences: dict = None,
    visited_destinations: list = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """手动编辑用户画像"""
    from backend.app.services.memory import get_or_create_profile
    import logging
    logger = logging.getLogger(__name__)
    
    profile = get_or_create_profile(db, current_user.id)
    
    if preferences is not None:
        current_prefs = profile.preferences or {}
        current_prefs.update(preferences)
        profile.preferences = current_prefs
    
    if visited_destinations is not None:
        current_visited = list(set((profile.visited_destinations or []) + visited_destinations))
        profile.visited_destinations = current_visited
    
    db.commit()
    logger.info(f"用户 {current_user.username} 手动更新了画像")
    
    return {
        "message": "画像已更新",
        "preferences": profile.preferences,
        "visited_destinations": profile.visited_destinations,
    }


# ====== 反馈 API ======

class FeedbackRequest(BaseModel):
    message_id: Optional[int] = None
    rating: int  # 1=点赞, -1=点踩
    feedback_text: Optional[str] = None


@router.post("/feedback")
def submit_feedback(
    request: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    提交对 AI 回复的反馈。
    
    rating: 1 表示点赞（正面反馈），-1 表示点踩（负面反馈）
    反馈将用于 Self-Improvement 经验积累。
    """
    from backend.app.models.experience_log import ExperienceLog
    import logging
    logger = logging.getLogger(__name__)
    
    if request.rating not in (1, -1, 0):
        raise HTTPException(status_code=400, detail="rating 必须为 1（点赞）、-1（点踩）或 0（中立）")
    
    # 如果提供了 message_id，尝试找到对应的 experience log 并更新评分
    if request.message_id:
        # 尝试查找最近的匹配 experience log（通过关联方式）
        # 这里简化处理：直接创建一条新的反馈记录
        pass
    
    # 创建或更新反馈记录
    feedback_record = ExperienceLog(
        user_id=current_user.id,
        task_type="user_feedback",
        query_summary=f"用户反馈: rating={request.rating}",
        result_rating=max(0, (request.rating + 1) * 2 + 1) if request.rating != 0 else 3,  # 转换为 1-5 分
        feedback=request.feedback_text,
        lesson_learned=(
            f"用户{'点赞' if request.rating == 1 else '点踩'}了本次回复。"
            f"{f'反馈内容: {request.feedback_text}' if request.feedback_text else ''}"
        ),
    )
    db.add(feedback_record)
    db.commit()
    
    action = "点赞 👍" if request.rating == 1 else "点踩 👎" if request.rating == -1 else "中立"
    logger.info(f"用户 {current_user.username} 提交反馈: {action}")
    
    return {
        "message": f"感谢您的{action}！",
        "feedback_id": feedback_record.id,
    }
