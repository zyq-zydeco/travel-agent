"""消息表模型"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, comment="所属对话ID")
    role = Column(String(20), nullable=False, comment="角色：user 或 assistant")
    content = Column(Text, nullable=False, default="", comment="消息内容")
    files = Column(JSON, default=list, comment="附件文件信息JSON列表")
    created_at = Column(DateTime, server_default=func.now(), comment="发送时间")

    # 关联关系
    conversation = relationship("Conversation", back_populates="messages")
