"""
记忆管理模块 - 用户画像与经验日志管理
负责：用户画像的读写、对话后的偏好提取、经验日志的存储与检索
"""

import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from backend.app.models.user import User
from backend.app.models.user_profile import UserProfile
from backend.app.models.experience_log import ExperienceLog
from backend.app.models.message import Message

logger = logging.getLogger(__name__)


def get_or_create_profile(db: Session, user_id: int) -> UserProfile:
    """获取用户画像，不存在则创建默认的"""
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile:
        profile = UserProfile(user_id=user_id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
        logger.info(f"为用户 {user_id} 创建了默认画像")
    return profile


def format_profile_for_prompt(profile: UserProfile) -> str:
    """将用户画像格式化为可注入 System Prompt 的文本片段"""
    if not profile:
        return ""
    
    parts = ["## 用户画像（根据历史对话自动学习）"]
    
    preferences = profile.preferences or {}
    if preferences:
        pref_items = []
        for key, value in preferences.items():
            if value:
                label_map = {
                    "budget_range": "预算范围",
                    "travel_style": "出行风格",
                    "diet": "饮食偏好",
                    "companions": "常同行人",
                    "interests": "兴趣爱好",
                }
                label = label_map.get(key, key)
                pref_items.append(f"- {label}: {value}")
        if pref_items:
            parts.append("\n偏好设置:\n" + "\n".join(pref_items))
    
    visited = profile.visited_destinations or []
    if visited:
        parts.append(f"\n去过的地方: {', '.join(visited)}")
    
    history = profile.travel_history or []
    if history:
        recent = history[-3:]  # 最近 3 条
        parts.append("\n最近旅行记录:")
        for h in recent:
            dest = h.get("destination", "?")
            duration = h.get("duration", "?")
            rating = h.get("rating", "?")
            parts.append(f"  - {dest}: {duration}天, 评价: {rating}")
    
    return "\n".join(parts)


async def update_profile_from_conversation(db: Session, user_id: int, conversation_id: int) -> None:
    """
    对话结束后，调用 LLM 分析对话内容，提取用户偏好更新画像。
    此函数应在 AI 回复完成后异步调用。
    """
    try:
        # 获取该对话的所有消息
        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.id.asc()).all()
        
        if len(messages) < 2:
            return
        
        # 构建对话文本供 LLM 分析
        conversation_text = ""
        for msg in messages:
            role_label = "用户" if msg.role == "user" else "助手"
            conversation_text += f"{role_label}: {msg.content}\n"
        
        # 调用 LLM 提取偏好
        extraction_prompt = f"""你是一个用户偏好提取助手。请从以下旅行规划对话中提取用户的旅行偏好信息。

对话内容：
{conversation_text}

请以 JSON 格式输出提取到的信息（只输出 JSON，不要其他文字）：
{{
    "preferences": {{
        "budget_range": "预算范围（如 3000-5000 元）",
        "travel_style": "出行风格（如 深度游/休闲游/特种兵式）",
        "diet": "饮食偏好（如有提及）",
        "companions": "常同行人（如有提及）"
    }},
    "visited_destinations": ["去过的目的地1", "去过的目的地2"],
    "new_travel_entry": {{
        "destination": "本次讨论的目的地",
        "duration": 计划天数,
        "budget": 预算金额,
        "notes": "其他备注"
    }}
}}

如果某项信息在对话中未提及，对应字段设为 null 或空列表。
"""
        
        from backend.app.services.llm import get_llm
        llm = get_llm(streaming=False)
        response = llm.invoke(extraction_prompt)
        response_text = response.content.strip()
        
        # 解析 JSON
        # 尝试提取 JSON（可能在 markdown 代码块中）
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0].strip()
        else:
            json_str = response_text
        
        extracted = json.loads(json_str)
        
        # 更新画像
        profile = get_or_create_profile(db, user_id)
        
        # 合并 preferences（新值覆盖旧值，但保留旧值中独有的字段）
        new_prefs = extracted.get("preferences") or {}
        current_prefs = profile.preferences or {}
        for key, value in new_prefs.items():
            if value and value != "null":
                current_prefs[key] = value
        profile.preferences = current_prefs
        
        # 合并 visited_destinations
        new_visited = extracted.get("visited_destinations") or []
        current_visited = list(set((profile.visited_destinations or []) + [v for v in new_visited if v]))
        profile.visited_destinations = current_visited
        
        # 追加 travel_history
        new_entry = extracted.get("new_travel_entry") or {}
        if new_entry.get("destination"):
            current_history = profile.travel_history or []
            current_history.append({
                "destination": new_entry["destination"],
                "duration": new_entry.get("duration"),
                "budget": new_entry.get("budget"),
                "date": datetime.now().strftime("%Y-%m"),
            })
            profile.travel_history = current_history[-10:]  # 只保留最近 10 条
        
        db.commit()
        logger.info(f"用户 {user_id} 的画像已更新")
        
    except json.JSONDecodeError as e:
        logger.warning(f"解析 LLM 偏好提取结果失败: {e}")
    except Exception as e:
        logger.error(f"更新用户画像失败: {e}", exc_info=True)


def save_experience_log(
    db: Session,
    user_id: int,
    task_type: str,
    query_summary: str,
    tools_used: list = None,
    lesson: str = None,
) -> ExperienceLog:
    """写入一条经验日志"""
    log = ExperienceLog(
        user_id=user_id,
        task_type=task_type,
        query_summary=query_summary,
        tools_used=tools_used or [],
        lesson_learned=lesson,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    logger.info(f"经验日志已保存: user={user_id}, type={task_type}, id={log.id}")
    return log


async def analyze_and_save_experience(db: Session, user_id: int, task_type: str, query: str, reply: str, tools_used: list = None) -> None:
    """
    对话结束后，调用 LLM 分析本次回答质量，提取经验教训。
    异步执行，不影响用户体验。
    """
    try:
        analysis_prompt = f"""你是一个旅行专家 AI 的自我评估助手。请分析以下对话的质量，并总结可改进的经验。

用户需求: {query}

AI 回复: {reply[:2000]}

请以 JSON 格式输出（只输出 JSON）：
{{
    "lesson_learned": "一条具体的经验教训或改进建议（如果本次回复质量良好则写'本次表现良好，继续保持'）",
    "quality_score": 1-5 的整数评分
}}
"""
        
        from backend.app.services.llm import get_llm
        llm = get_llm(streaming=False)
        response = llm.invoke(analysis_prompt)
        response_text = response.content.strip()
        
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0].strip()
        else:
            json_str = response_text
        
        result = json.loads(json_str)
        
        save_experience_log(
            db=db,
            user_id=user_id,
            task_type=task_type,
            query_summary=query[:200],
            tools_used=tools_used,
            lesson=result.get("lesson_learned"),
        )
        
    except Exception as e:
        logger.error(f"分析并保存经验失败: {e}", exc_info=True)


def retrieve_relevant_experiences(db: Session, task_type: str, limit: int = 5) -> list:
    """检索与给定任务类型相关的历史经验"""
    logs = db.query(ExperienceLog).filter(
        ExperienceLog.user_id.isnot(None),  # 全局经验（暂不做用户隔离）
        ExperienceLog.task_type == task_type,
        ExperienceLog.lesson_learned.isnot(None),
    ).order_by(ExperienceLog.created_at.desc()).limit(limit).all()
    
    return [
        {
            "lesson": log.lesson_learned,
            "rating": log.result_rating,
            "date": log.created_at.strftime("%Y-%m-%d") if log.created_at else None,
        }
        for log in logs if log.lesson_learned
    ]
