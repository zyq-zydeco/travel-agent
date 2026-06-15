"""导入所有模型，确保 Base.metadata.create_all() 能发现所有表"""
from .user import User
from .conversation import Conversation
from .message import Message
from .user_profile import UserProfile
from .experience_log import ExperienceLog

__all__ = ["User", "Conversation", "Message", "UserProfile", "ExperienceLog"]
