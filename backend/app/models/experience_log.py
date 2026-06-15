"""经验日志表模型"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, SmallInteger
from sqlalchemy.sql import func
from ..core.database import Base


class ExperienceLog(Base):
    __tablename__ = "experience_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="关联用户ID")
    
    # 任务类型
    task_type = Column(String(50), nullable=False, comment="任务类型: 行程规划/酒店推荐/机票查询/天气查询/预算分析")
    
    # 用户需求摘要
    query_summary = Column(Text, comment="用户需求的摘要")
    
    # 使用的工具列表
    tools_used = Column(JSON, default=list, comment="本次使用的工具列表")
    
    # 结果评分（可选，来自用户反馈）
    result_rating = Column(SmallInteger, nullable=True, comment="用户评分 1-5，NULL表示未评分")
    
    # 用户反馈内容
    feedback = Column(Text, nullable=True, comment="用户反馈文本")
    
    # AI 总结的经验教训
    lesson_learned = Column(Text, nullable=True, comment="AI总结的经验教训")
    
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
