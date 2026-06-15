"""
LangGraph 工作流编排 + 多 Agent Supervisor 架构
实现：意图分类 → 分支处理 → 输出验证 → 自我修正 的完整流水线
"""

import json
import logging
from typing import TypedDict, Annotated, List, Optional, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from backend.app.services.agent import (
    get_agent,
    create_route_agent,
    create_weather_agent,
    create_budget_agent,
    create_local_guide_agent,
)
from backend.app.services.context import (
    classify_intent,
    build_system_prompt,
    compress_long_context,
    INTENT_QA,
    INTENT_PLANNING,
    INTENT_SEARCH,
    INTENT_COMPLEX,
)
from backend.app.services.validator import OutputValidator, ValidationResult
from backend.app.services.memory import get_or_create_profile, retrieve_relevant_experiences

logger = logging.getLogger(__name__)


# ============================================================
# Graph State 定义
# ============================================================

class AgentState(TypedDict):
    """工作流状态定义"""
    messages: List[dict]          # 对话消息 [{role, content}, ...]
    intent: str                   # 分类后的意图类型
    user_profile: Optional[dict]  # 用户画像信息
    experiences: Optional[list]   # 相关历史经验
    raw_response: str             # AI 原始回复文本
    validation_result: Optional[dict]  # 验证结果
    final_response: str           # 最终回复
    error: Optional[str]          # 错误信息
    retry_count: int              # 重试次数


# ============================================================
# 图节点函数
# ============================================================

def classify_intent_node(state: AgentState) -> dict:
    """节点1：意图分类"""
    # 取最后一条用户消息
    last_user_msg = ""
    for msg in reversed(state["messages"]):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break
    
    intent = classify_intent(last_user_msg)
    logger.info(f"意图分类结果: '{last_user_msg[:50]}...' → {intent}")
    
    return {"intent": intent}


def qa_node(state: AgentState) -> dict:
    """节点：简单问答 — 直接用主 Agent 回答"""
    try:
        agent = get_agent()
        
        # 构建带上下文的消息
        system_prompt = _build_contextual_prompt(state)
        messages = [SystemMessage(content=system_prompt)]
        for msg in state["messages"]:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        
        # 流式收集完整响应
        response_text = ""
        async for event in agent.astream_events(
            {"messages": messages},
            version="v2",
        ):
            kind = event.get("event")
            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    response_text += chunk.content
        
        return {"raw_response": response_text, "final_response": response_text}
    except Exception as e:
        logger.error(f"QA 节点执行失败: {e}", exc_info=True)
        return {"error": str(e), "raw_response": "", "final_response": f"抱歉，回答时出错: {str(e)}"}


def planning_node(state: AgentState) -> dict:
    """节点：行程规划 — 使用 RouteAgent"""
    try:
        # 行程规划使用专用 Agent
        agent = create_route_agent()
        
        system_prompt = _build_contextual_prompt(state)
        messages = [SystemMessage(content=system_prompt)]
        for msg in state["messages"]:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        
        response_text = ""
        async for event in agent.astream_events(
            {"messages": messages},
            version="v2",
        ):
            kind = event.get("event")
            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if chunk.content:
                    response_text += chunk.content
        
        return {"raw_response": response_text, "final_response": response_text}
    except Exception as e:
        logger.error(f"Planning 节点执行失败: {e}", exc_info=True)
        return {"error": str(e), "raw_response": "", "final_response": f"抱歉，规划时出错: {str(e)}"}


def search_node(state: AgentState) -> dict:
    """节点：搜索整合 — 用主 Agent 处理实时查询"""
    # 搜索类请求和 QA 类似，但使用强调检索的 prompt
    return qa_node(state)


def complex_node(state: AgentState) -> dict:
    """节点：复杂任务 — Supervisor 多 Agent 协作"""
    try:
        last_user_msg = ""
        for msg in reversed(state["messages"]):
            if msg.get("role") == "user":
                last_user_msg = msg.get("content", "")
                break
        
        # 判断需要哪些子 Agent 参与
        sub_results = {}
        
        # 天气相关 → WeatherAgent
        weather_keywords = ["天气", "气温", "下雨", "温度", "预报", "weather", "穿衣"]
        if any(kw in last_user_msg.lower() for kw in weather_keywords):
            sub_results["weather"] = await _call_sub_agent(
                create_weather_agent(), 
                state, 
                "请重点回答天气相关问题。"
            )
        
        # 预算/费用/汇率 → BudgetAgent
        budget_keywords = ["预算", "费用", "多少钱", "价格", "汇率", "换算", "花销", "cost", "price"]
        if any(kw in last_user_msg.lower() for kw in budget_keywords):
            sub_results["budget"] = await _call_sub_agent(
                create_budget_agent(),
                state,
                "请重点回答预算和费用相关问题，给出明细分析。"
            )
        
        # 行程/路线/景点 → RouteAgent
        route_keywords = ["规划", "行程", "路线", "几天", "日游", "安排", "itinerary"]
        if any(kw in last_user_msg.lower() for kw in route_keywords):
            sub_results["route"] = await _call_sub_agent(
                create_route_agent(),
                state,
                "请给出详细的行程规划方案。"
            )
        
        # 美食/当地特色 → LocalGuideAgent
        guide_keywords = ["美食", "吃", "餐厅", "当地", "特色", "推荐", "攻略", "避坑"]
        if any(kw in last_user_msg.lower() for kw in guide_keywords):
            sub_results["local_guide"] = await _call_sub_agent(
                create_local_guide_agent(),
                state,
                "请分享地道的当地建议。"
            )
        
        # 如果没有匹配到任何子 Agent，使用主 Agent
        if not sub_results:
            return qa_node(state)
        
        # 聚合子 Agent 结果
        aggregated = _aggregate_sub_agent_results(sub_results, last_user_msg)
        
        return {
            "raw_response": aggregated,
            "final_response": aggregated,
        }
    except Exception as e:
        logger.error(f"Complex/Supervisor 节点执行失败: {e}", exc_info=True)
        return {"error": str(e), "raw_response": "", "final_response": f"抱歉，处理复杂任务时出错: {str(e)}"}


async def _call_sub_agent(agent_factory_func, state: AgentState, extra_instruction: str) -> str:
    """调用子 Agent 并返回其回复文本"""
    agent = agent_factory_func()
    
    system_prompt = _build_contextual_prompt(state)
    if extra_instruction:
        system_prompt += f"\n\n{extra_instruction}"
    
    messages = [SystemMessage(content=system_prompt)]
    for msg in state["messages"]:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))
    
    response_text = ""
    async for event in agent.astream_events(
        {"messages": messages},
        version="v2",
    ):
        kind = event.get("event")
        if kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if chunk.content:
                response_text += chunk.content
    
    return response_text


def _aggregate_sub_agent_results(sub_results: Dict[str, str], original_query: str) -> str:
    """聚合多个子 Agent 的结果为统一回复"""
    parts = [f"根据您的问题「{original_query}」，我从多个专业维度为您整理如下：\n"]
    
    order_map = {
        "route": ("🗺️ 行程规划", "route"),
        "weather": ("🌤️ 天气情况", "weather"),
        "budget": ("💰 预算分析", "budget"),
        "local_guide": ("🏮 当地向导", "local_guide"),
    }
    
    for label, key in order_map.values():
        if key in sub_results:
            parts.append(f"### {label}\n{sub_results[key]}\n")
    
    # 如果还有未覆盖的通用问题，补充说明
    covered = set(sub_results.keys())
    all_needed = set(order_map.keys())
    missing = all_needed - covered
    
    if not parts or len(parts) <= 1:
        # 子 Agent 结果不够好，直接返回主 Agent 的回答
        return list(sub_results.values())[0] if sub_results else "抱歉，无法完成分析。"
    
    return "\n".join(parts)


def validate_output_node(state: AgentState) -> dict:
    """节点：输出验证"""
    response = state.get("raw_response") or state.get("final_response") or ""
    intent = state.get("intent", INTENT_QA)
    
    validator = OutputValidator()
    result: ValidationResult = validator.validate(response, intent)
    
    validation_dict = {
        "is_valid": result.is_valid,
        "issues": result.issues,
        "warnings": result.warnings,
        "confidence": result.confidence,
    }
    
    if result.issues:
        logger.info(f"输出验证发现 {len(result.issues)} 个问题: {result.issues}")
    else:
        logger.info("输出验证通过")
    
    return {"validation_result": validation_dict}


def self_correct_node(state: AgentState) -> dict:
    """节点：自我修正（当验证不通过时触发）"""
    try:
        from backend.app.services.llm import get_llm
        
        issues = state.get("validation_result", {}).get("issues", [])
        original_response = state.get("raw_response", "")
        
        correction_prompt = f"""你是一位旅行专家 AI 的自我修正助手。

原始回复：
{original_response[:2000]}

验证发现以下问题：
{chr(10).join('- ' + issue for issue in issues)}

请基于以上反馈，修正你的回答。
要求：
1. 解决所有被指出的问题
2. 保持原有信息的完整性
3. 不要编造不存在的信息
4. 直接输出修正后的回答，不要解释你做了什么修改
"""
        
        llm = get_llm(streaming=False)
        response = llm.invoke(correction_prompt)
        corrected = response.content.strip()
        
        logger.info(f"自我修正完成，原文长度={len(original_response)}, 修正后长度={len(corrected)}")
        
        return {
            "final_response": corrected,
            "retry_count": state.get("retry_count", 0) + 1,
        }
    except Exception as e:
        logger.error(f"自我修正失败: {e}", exc_info=True)
        # 修正失败则保留原回复
        return {
            "final_response": state.get("raw_response", ""),
            "retry_count": state.get("retry_count", 0) + 1,
        }


# ============================================================
# 条件边路由函数
# ============================================================

def route_by_intent(state: AgentState) -> str:
    """根据意图路由到不同处理节点"""
    intent = state.get("intent", INTENT_QA)
    routing = {
        INTENT_QA: "qa",
        INTENT_PLANNING: "planning",
        INTENT_SEARCH: "search",
        INTENT_COMPLEX: "complex",
    }
    return routing.get(intent, "qa")


def route_after_validation(state: AgentState) -> str:
    """验证后决定：通过则结束，否则尝试自我修正"""
    validation = state.get("validation_result", {})
    is_valid = validation.get("is_valid", True)
    retry_count = state.get("retry_count", 0)
    
    if is_valid or retry_count >= 1:
        # 验证通过 或 已经重试过一次了 → 结束
        return "end"
    else:
        # 验证不通过 且 还没重试过 → 自我修正
        return "self_correct"


# ============================================================
# 辅助函数
# ============================================================

def _build_contextual_prompt(state: AgentState) -> str:
    """构建注入了画像和经验的动态 System Prompt"""
    intent = state.get("intent", INTENT_QA)
    profile_data = state.get("user_profile")
    experiences = state.get("experiences")
    
    # 将 dict 格式的 profile 转回对象（如果有的话）
    # 这里简化处理：直接传 None 让 build_system_prompt 处理空值
    profile_obj = None
    exp_list = experiences or []
    
    return build_system_prompt(profile_obj, exp_list, intent)


# ============================================================
# Graph 构建
# ============================================================

def create_travel_graph():
    """
    创建并编译完整的旅行专家工作流图。
    
    工作流程：
    用户输入 → [classify_intent] → 路由到对应处理节点
                                    ↓
                              [validate_output]
                                    ↓
                          ┌─── 通过 → END
                          │
                          └─── 不通过 → [self_correct] → END
    """
    graph = StateGraph(AgentState)
    
    # 添加节点
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("qa", qa_node)
    graph.add_node("planning", planning_node)
    graph.add_node("search", search_node)
    graph.add_node("complex", complex_node)
    graph.add_node("validate_output", validate_output_node)
    graph.add_node("self_correct", self_correct_node)
    
    # 设置入口
    graph.set_entry_point("classify_intent")
    
    # 意图分类 → 路由分发
    graph.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "qa": "qa",
            "planning": "planning",
            "search": "search",
            "complex": "complex",
        },
    )
    
    # 各处理节点 → 验证
    graph.add_edge("qa", "validate_output")
    graph.add_edge("planning", "validate_output")
    graph.add_edge("search", "validate_output")
    graph.add_edge("complex", "validate_output")
    
    # 验证 → 通过/修正
    graph.add_conditional_edges(
        "validate_output",
        route_after_validation,
        {
            "end": END,
            "self_correct": "self_correct",
        },
    )
    
    # 自我修正后结束
    graph.add_edge("self_correct", END)
    
    # 编译图
    compiled_graph = graph.compile(checkpointer=MemorySaver())
    
    logger.info("旅行专家工作流图已编译完成")
    logger.info("节点: classify_intent → [qa|planning|search|complex] → validate_output → [END|self_correct] → END")
    
    return compiled_graph


# ============================================================
# 兼容性接口：保持与旧 stream.py 的调用方式兼容
# ============================================================

def get_graph_agent():
    """
    获取编译后的工作流图 Agent。
    这是新的默认入口，替代原来的 get_agent()。
    """
    return create_travel_graph()


# 保持向后兼容：get_agent 也返回图模式
# （在 stream.py 中会优先使用 get_graph_agent）
