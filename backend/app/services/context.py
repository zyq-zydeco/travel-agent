"""
动态上下文组装模块
负责：意图分类、Prompt 模板选择与组装、长对话上下文压缩
"""

import re
import logging
from typing import List, Optional, Tuple

from langchain_core.messages import HumanMessage, AIMessage

from backend.app.models.message import Message
from backend.app.models.user_profile import UserProfile
from backend.app.services.memory import format_profile_for_prompt, retrieve_relevant_experiences

logger = logging.getLogger(__name__)

from datetime import datetime

# 生成中文格式的当前日期字符串
def _get_current_date_str() -> str:
    now = datetime.now()
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday = weekdays[now.weekday()]
    return f"{now.year}年{now.month}月{now.day}日 {weekday}"


# ====== 意图分类 ======

INTENT_QA = "qa"           # 简单问答（事实性问题、常识问题）
INTENT_PLANNING = "planning"  # 行程规划（多天行程安排）
INTENT_SEARCH = "search"     # 实时查询（天气、价格、政策等需要最新信息的）
INTENT_COMPLEX = "complex"   # 复杂任务（涉及多个维度的综合请求）

# 意图关键词规则
INTENT_RULES = {
    INTENT_PLANNING: [
        "规划", "行程", "路线", "几天", "日游", " itinerary", "安排",
        "第1天", "第一天", "第2天", "第二天", "每天", "逐日",
        "自由行", "跟团", "深度游", "攻略",
    ],
    INTENT_SEARCH: [
        # 天气类
        "天气", "气温", "下雨", "温度", "预报", "weather",
        # 价格费用类
        "多少钱", "价格", "费用", "预算", "花费", "cost", "price",
        "汇率", "换算", "exchange",
        # 签证入境类
        "签证", "passport", "visa", "入境",
        # 交通住宿类
        "机票", "航班", "flight", "飞机票",
        "酒店", "住宿", "hotel",
        # === 新增：赛事/活动/时间相关 ===
        "大奖赛", "赛事", "比赛", "活动", "节庆", "节日",
        "展览", "演出", "音乐会", "开幕", "闭幕","演唱会",
        "奥运会","世界杯",
        "什么时候", "几号", "几点",
        "今年", "明年", "最近", "最新",
        "schedule", "event", "festival", "concert", "exhibition",
        "开放时间", "营业时间", "门票", "票价",
    ],
}


def classify_intent(user_message: str) -> str:
    """
    对用户消息进行意图分类。
    使用关键词规则快速匹配，支持后续扩展为 LLM 分类。
    
    返回值: qa / planning / search / complex
    """
    msg_lower = user_message.lower()
    
    # 检查是否同时涉及多个维度 → complex
    hit_count = 0
    for intent, keywords in INTENT_RULES.items():
        for kw in keywords:
            if kw.lower() in msg_lower:
                hit_count += 1
                break
    
    # 如果命中 2 种以上意图类型，判定为复杂任务
    if hit_count >= 2:
        return INTENT_COMPLEX
    
    # 检查是否是行程规划类
    for kw in INTENT_RULES[INTENT_PLANNING]:
        if kw.lower() in msg_lower:
            # 行程规划+搜索混合也是 complex
            for search_kw in INTENT_RULES[INTENT_SEARCH]:
                if search_kw.lower() in msg_lower:
                    return INTENT_COMPLEX
            return INTENT_PLANNING
    
    # 检查是否是搜索类
    for kw in INTENT_RULES[INTENT_SEARCH]:
        if kw.lower() in msg_lower:
            return INTENT_SEARCH
    
    # 默认为简单问答
    return INTENT_QA


# ====== Prompt 模板 =====

BASE_PERSONA = """你是一位专业的旅行专家助手，名叫"旅行专家"，拥有丰富的旅行规划经验。

你的核心能力：
1. 🗺️ 根据用户需求规划旅行路线和行程安排
2. 🏖️ 推荐景点、美食、住宿和当地特色体验
3. 💰 提供预算建议和省钱攻略
4. 🔍 搜索最新的旅行信息、签证政策、优惠活动
5. 🌤️ 查询目的地天气、交通、注意事项
6. 💱 提供汇率换算和出境游财务建议
"""

SELF_RAG_GUIDE = """
## Self-RAG 检索决策指引（非常重要）

在回答每个问题之前，请先进行自我评估：

**第一步：判断是否需要检索**

🔴 **必须检索（强制，不可跳过）：**
- 涉及任何具体日期、时间、年份的事件、活动或安排
- 涉及赛事、活动、节庆、展览、演出、会议的时间/地点/票价
- 涉及"明年""今年""最近""什么时候""几号"等相对时间表述的内容
- 涉及某个地方"现在怎么样""目前是否开放"等实时状态查询
- 任何你无法100%确定当前状态的事实性信息

✅ **建议检索**的情况：
- 问题涉及最新信息（天气、价格、政策）、具体地点的详细信息、你不确定的事实

❌ **无需检索**的情况（仅限以下场景，其他一律检索）：
- 纯粹的通用旅行建议（打包清单、旅行保险建议）
- 行程组织方式和方法论框架

**第二步：选择检索策略**
- 如果需要检索，优先使用最匹配的工具：
  - 天气相关 → weather_search
  - 汇率/换算 → exchange_rate
  - 签证政策 → visa_policy_search
  - 地点/景点/路线 → amap_poi_search / amap_route_planning / amap_geocode
  - 其他通用信息 → web_search

**第三步：评估检索结果质量**
- 检索到的信息是否充分回答了用户问题？
- 信息是否过时或不相关？（特别注意日期是否合理）
- 如果不够充分 → 用更精确的关键词再次检索（最多 3 轮）
- 如果足够 → 基于结果组织回答

**第四步：停止条件**
- 已获得足够的信息来给出高质量回答
- 或者已达到最大检索轮次（3轮），此时基于已有信息尽力回答

⚠️ **关键提醒：你的训练数据有截止日期！你不知道现在是哪一年。
   对于任何涉及时间、日期、事件的问题，必须调用搜索工具获取最新信息，
   绝对不能仅凭记忆回答！如果你的回答中出现了具体日期但没调过搜索工具，说明你犯错了。**
"""

OUTPUT_REQUIREMENTS = """
## 输出格式要求

- 用友好、专业的语气交流
- 推荐行程时 **必须按天规划**，每条包含：日期/时间段、地点、活动、预计费用、交通方式
- 预算分析必须包含明细表格
- 所有来自搜索的信息必须标注来源
- 参考来源格式：在正文结束后另起一行写"---"，然后"**参考资料：**"，再列出编号. [标题](URL)

## ⚠️ 思考过程与回答格式（重要）

你的输出必须严格区分**思考过程**和**正式回答**，使用以下标签：

```
【思考】
（这里写你的推理步骤、搜索意图说明、中间分析过程等）
例如：我需要搜索... / 让我先确认... / 根据搜索结果...

【回答】
（这里写给用户的正式回答内容，包括推荐结果、具体信息等）
```

**规则：**
1. 所有"我需要搜索"、"让我开始"、"根据我的分析"等推理性文字放在【思考】内
2. 正式的推荐、答案、规划内容放在【回答】内
3. 如果没有明显的思考过程（如简单问答），可以直接输出【回答】内容
4. 【思考】和【回答】各占一个独立段落，不要嵌套
"""

QA_TEMPLATE = BASE_PERSONA + """
📅 **当前日期：{current_date}**

{profile_section}
{experience_section}

## 当前任务：简单问答
用户的问题是简单的事实性或咨询性问题，直接给出准确、简洁的回答即可。

""" + SELF_RAG_GUIDE + OUTPUT_REQUIREMENTS

PLANNING_TEMPLATE = BASE_PERSONA + """
📅 **当前日期：{current_date}**

{profile_section}
{experience_section}

## 当前任务：行程规划
这是一个复杂的行程规划请求，请按以下步骤进行：

1. **先思考**：明确目的地、天数、预算、人数、特殊需求
2. **必要时搜索**：查找目的地最新信息（景点开放情况、交通变化等）
3. **详细规划**：按每日上午/下午/晚上组织行程
4. **预算拆分**：列出交通、住宿、餐饮、门票的大致费用
5. **实用提示**：添加避坑指南、省钱技巧、必备物品清单

""" + SELF_RAG_GUIDE + OUTPUT_REQUIREMENTS

SEARCH_TEMPLATE = BASE_PERSONA + """
📅 **当前日期：{current_date}**

{profile_section}
{experience_section}

## 当前任务：实时信息查询
用户需要最新的实时信息，请使用合适的工具查询后给出准确答案。

""" + SELF_RAG_GUIDE + OUTPUT_REQUIREMENTS

COMPLEX_TEMPLATE = BASE_PERSONA + """
📅 **当前日期：{current_date}**

{profile_section}
{experience_section}

## 当前任务：综合旅行规划
这是一个涉及多个维度的复杂请求（如行程+预算+天气+签证），请系统性地处理：

1. **分解需求**：识别用户提到的所有维度
2. **逐一处理**：对每个维度分别收集信息
3. **整合输出**：将各维度信息整合成一份完整的旅行方案
4. **交叉验证**：检查各部分之间是否有矛盾（如预算vs行程强度）

""" + SELF_RAG_GUIDE + OUTPUT_REQUIREMENTS

TEMPLATE_MAP = {
    INTENT_QA: QA_TEMPLATE,
    INTENT_PLANNING: PLANNING_TEMPLATE,
    INTENT_SEARCH: SEARCH_TEMPLATE,
    INTENT_COMPLEX: COMPLEX_TEMPLATE,
}


def get_prompt_template(intent_type: str) -> str:
    """根据意图类型返回对应的 prompt 模板"""
    return TEMPLATE_MAP.get(intent_type, QA_TEMPLATE)


def build_system_prompt(
    user_profile: Optional[UserProfile] = None,
    experiences: Optional[list] = None,
    intent_type: str = INTENT_QA,
) -> str:
    """
    组装完整的 System Prompt。
    
    参数:
        user_profile: 用户画像对象（可为 None）
        experiences: 相关历史经验列表（可为 None）
        intent_type: 意图类型（qa/planning/search/complex）
    
    返回:
        组装好的完整 System Prompt 字符串
    """
    current_date = _get_current_date_str()
    template = get_prompt_template(intent_type)
    
    # 注入用户画像
    profile_section = ""
    if user_profile:
        profile_section = format_profile_for_prompt(user_profile)
    
    # 注入历史经验
    experience_section = ""
    if experiences:
        exp_items = []
        for exp in experiences[:3]:  # 最多 3 条经验
            lesson = exp.get("lesson", "")
            if lesson and lesson != "本次表现良好，继续保持":
                exp_items.append(f"- {lesson}")
        if exp_items:
            experience_section = "\n## 历史经验参考（来自以往类似任务的教训）\n" + "\n".join(exp_items)
    
    # 注入当前日期到所有模板中
    result = template.format(
        profile_section=profile_section or "（暂无用户画像信息）",
        experience_section=experience_section or "（暂无相关经验）",
        current_date=current_date,
    )
    return result


# ====== 上下文压缩 =====

def compress_long_context(messages: List[Message], max_turns: int = 10) -> Tuple[List[Message], bool]:
    """
    压缩过长对话的上下文。
    
    当对话超过 max_turns 轮时，将早期消息摘要化，
    保留最近的消息原文以保证细节准确性。
    
    参数:
        messages: 按 ID 升序排列的消息列表
        max_turns: 最大保留轮数（一轮 = 一问一答）
    
    返回:
        (压缩后的消息列表, 是否进行了压缩)
    """
    total_messages = len(messages)
    
    if total_messages <= max_turns:
        return messages, False
    
    # 计算需要保留的消息数（最近 N 轮）
    keep_count = min(max_turns, total_messages)
    kept_messages = messages[-keep_count:]
    
    # 早期消息生成摘要
    early_messages = messages[:-keep_count]
    summary_texts = []
    for msg in early_messages:
        role_label = "用户" if msg.role == "user" else "助手"
        # 截断过长内容
        content = msg.content[:200] + ("..." if len(msg.content) > 200 else "")
        summary_texts.append(f"{role_label}: {content}")
    
    summary_content = "[早期对话摘要]\n" + "\n".join(summary_texts)
    
    # 创建摘要消息
    from backend.app.models.message import Message
    summary_msg = Message(
        conversation_id=early_messages[0].conversation_id if early_messages else 0,
        role="system",
        content=summary_content,
    )
    
    # 将摘要插入到保留消息之前
    compressed = [summary_msg] + kept_messages
    
    logger.info(f"上下文压缩: {total_messages} 条 → {len(compressed)} 条（含摘要）")
    return compressed, True
