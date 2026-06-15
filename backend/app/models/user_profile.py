"""用户画像表模型"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..core.database import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, comment="关联用户ID")
    
    # 用户偏好（JSON 格式存储）
    # 示例: {"budget_range": "3000-5000", "travel_style": "深度游", "diet": "素食", "companions": "独自/家庭/情侣"}
    preferences = Column(JSON, default=dict, comment="用户旅行偏好")
    
    # 去过的目的地列表
    # 示例: ["成都", "东京", "巴厘岛"]
    visited_destinations = Column(JSON, default=list, comment="已访问的目的地")
    
    # 旅行历史记录
    # 示例: [{"destination": "云南", "duration": 7, "budget": 5000, "rating": "满意", "date": "2025-01"}]
    travel_history = Column(JSON, default=list, comment="旅行历史记录")
    
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="最后更新时间")

    # 关联关系
    user = relationship("User", back_populates="profile", uselist=False)
