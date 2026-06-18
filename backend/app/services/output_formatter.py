"""
大模型稳定格式化输出核心模块。

提供输出 Schema 定义、思考-回答解析、格式修复、智能截断、结构校验和完整处理流水线。
"""

import logging
import re

from pydantic import BaseModel, Field
from typing import List, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 1. Pydantic 输出 Schema 模型族（用于结构校验，非强制 JSON 输出）
# ============================================================

class DayPlan(BaseModel):
    """每日行程安排"""
    date: str = Field(description="日期标识，如'Day 1'或'6月15日'")
    time_period: str = Field(description="时段，如'上午/下午/晚上'")
    location: str = Field(description="地点")
    activity: str = Field(description="活动描述")
    estimated_cost: Optional[str] = Field(default=None, description="预估费用")
    transport: Optional[str] = Field(default=None, description="交通方式")


class TravelPlanOutput(BaseModel):
    """行程规划输出 Schema"""
    total_days: int = Field(description="总天数")
    destination: str = Field(description="目的地")
    daily_plans: List[DayPlan] = Field(description="每日安排列表")
    total_budget_range: Optional[str] = Field(default=None, description="总预算范围")
    highlights: List[str] = Field(default_factory=list, description="行程亮点")


class WeatherDayInfo(BaseModel):
    """单日天气信息"""
    date: str = Field(description="日期")
    condition: str = Field(description="天气状况")
    temp_high: Optional[str] = Field(default=None, description="最高温度")
    temp_low: Optional[str] = Field(default=None, description="最低温度")
    humidity: Optional[str] = Field(default=None, description="湿度")


class WeatherOutput(BaseModel):
    """天气查询输出 Schema"""
    city: str = Field(description="城市名")
    forecast: List[WeatherDayInfo] = Field(description="天气预报列表")


class BudgetItem(BaseModel):
    """预算明细项"""
    category: str = Field(description="费用分类")
    amount: str = Field(description="金额")
    note: Optional[str] = Field(default=None, description="备注")


class BudgetOutput(BaseModel):
    """预算分析输出 Schema"""
    total_budget: str = Field(description="总预算")
    items: List[BudgetItem] = Field(description="费用明细列表")
    saving_tips: List[str] = Field(default_factory=list, description="省钱建议")


class SourceRef(BaseModel):
    """参考来源"""
    title: str = Field(description="来源标题")
    url: Optional[str] = Field(default=None, description="来源链接")


class GeneralQAOutput(BaseModel):
    """通用问答输出 Schema"""
    answer: str = Field(description="回答正文")
    sources: List[SourceRef] = Field(default_factory=list, description="参考来源")


# ============================================================
# 2. 思考-回答标签解析
# ============================================================

def extract_thinking_answer(text: str) -> tuple[str, str]:
    """
    健壮地解析【思考】【回答】标签。

    规则：
    - 正常情况：有【思考】...【回答】... → 返回 (thinking_content, answer_content)
    - 只有【思考】没有【回答】：将全部内容作为 answer，thinking 为空
    - 只有【回答】没有【思考】：直接返回 (空, 内容)
    - 完全没有标签：返回 (空, 原文)
    - 多重匹配：取第一个匹配
    - 标签内为空：返回对应空字符串
    """
    if not text:
        return ("", "")

    # 使用正则匹配【思考】...【回答】...
    pattern = r"【思考】([\s\S]*?)【回答】([\s\S]*)"
    match = re.search(pattern, text)

    if match:
        thinking = match.group(1).strip()
        answer = match.group(2).strip()
        return (thinking, answer)

    # 检查是否只有【回答】没有【思考】
    answer_only_pattern = r"【回答】([\s\S]*)"
    answer_match = re.search(answer_only_pattern, text)
    if answer_match:
        return ("", answer_match.group(1).strip())

    # 只有【思考】没有【回答】，或完全没有标签 → 全文作为 answer
    return ("", text.strip())


# ============================================================
# 3. Markdown 格式自动修复
# ============================================================

def format_repair(text: str) -> str:
    """
    自动修复常见 Markdown 格式错误：

    - 未闭合代码块：统计 ``` 数量，奇数个则在末尾补一个
    - 未闭合表格：检测 Markdown 表格语法，行数 < 3 时不自动补全（记录日志）
    - 连续空行：将 3 个及以上连续空行压缩为 2 个
    - 尾部空白清理：去除末尾多余空白字符
    - 缺失换行：在 --- 分隔线前后确保有空行
    """
    try:
        if not text:
            return ""

        result = text

        # 1) 未闭合代码块修复
        code_fence_count = result.count("```")
        if code_fence_count % 2 == 1:
            logger.warning("检测到未闭合的代码块，将在末尾补充闭合标记")
            result = result + "\n```"

        # 2) 未闭合表格检测（仅记录日志，不自动补全）
        lines = result.split("\n")
        table_lines = [i for i, line in enumerate(lines) if "|" in line and line.strip().startswith("|")]
        if len(table_lines) >= 1:
            has_separator = any(re.match(r"^\s*\|?\s*[-:\s|]+\s*\|?\s*$", lines[i]) for i in table_lines)
            if len(table_lines) >= 2 and not has_separator:
                logger.warning("检测到可能未闭合的 Markdown 表格（缺少表头分隔行），行号: %s", table_lines)

        # 3) 连续空行压缩（3 个及以上 → 2 个）
        result = re.sub(r"\n{4,}", "\n\n\n", result)

        # 4) 尾部空白清理
        result = result.rstrip()

        # 5) 分隔线前后确保有空行
        result = re.sub(r"(?<!\n)\n(---+)", "\n\\1", result)
        result = re.sub(r"(---+)(?!\n)", "\\1\n", result)

        return result
    except Exception as e:
        logger.warning("格式修复过程出错，返回原始文本: %s", str(e))
        return text


# ============================================================
# 4. 智能截断超长内容
# ============================================================

def truncate_respectfully(text: str, max_chars: int = 6000) -> str:
    """
    智能截断超长内容：

    - 文本长度 <= max_chars 时原样返回
    - 否则从后向前查找截断点：
      优先找双换行（段落边界）→ 单换行（行边界）→ 句号/感叹号/问号（句子边界）
    - 截断后追加提示信息
    - 最小保留长度不低于 max_chars 的 50%
    """
    if not text or len(text) <= max_chars:
        return text

    min_length = max_chars // 2
    search_text = text[:max_chars]

    # 优先找双换行（段落边界）
    last_double_newline = search_text.rfind("\n\n")
    if last_double_newline >= min_length:
        truncated = text[:last_double_newline].rstrip()
        return truncated + "\n\n...（内容过长，已截断）"

    # 其次找单换行（行边界）
    last_single_newline = search_text.rfind("\n")
    if last_single_newline >= min_length:
        truncated = text[:last_single_newline].rstrip()
        return truncated + "\n\n...（内容过长，已截断）"

    # 最后找句子边界（句号 / 感叹号 / 问号）
    for delimiter in ["。", "！", "？", ".", "!", "?"]:
        last_sentence = search_text.rfind(delimiter)
        if last_sentence >= min_length:
            truncated = text[:last_sentence + 1].rstrip()
            return truncated + "\n\n...（内容过长，已截断）"

    # 兜底：按 max_chars 硬截断
    return text[:max_chars].rstrip() + "\n\n...（内容过长，已截断）"


# ============================================================
# 5. 基于启发式规则的结构校验
# ============================================================

def validate_structure(text: str, intent_type: str = "qa") -> dict:
    """
    基于启发式规则的结构校验（不强制 Pydantic 解析，因为输出是自然语言+Markdown）。

    返回格式：{"is_valid": bool, "issues": list[str], "confidence": "high"|"medium"|"low"}
    """
    issues: list[str] = []

    # 空白检查
    if not text or not text.strip():
        return {"is_valid": False, "issues": ["输出内容为空"], "confidence": "low"}

    stripped = text.strip()

    # planning 类型校验
    if intent_type == "planning":
        has_date = bool(re.search(r"(?:Day\s*\d+|\d+\s*月\d+\s*日|第\d+天|日期)", stripped))
        has_structure = len(stripped) > 50  # 足够的结构化内容
        if not has_date:
            issues.append("缺少日期或天数标识")
        if not has_structure:
            issues.append("行程规划内容过短，结构可能不完整")

    # budget 类型校验
    elif intent_type == "budget":
        has_price = bool(re.search(r"[¥￥$]\s*[\d,]+|[\d,]+\s*元|\d+\s*块钱", stripped))
        has_table_or_list = bool(re.search(r"\|.*\||^[\s]*[-*+]\s", stripped, re.MULTILINE))
        if not has_price:
            issues.append("缺少价格/费用信息")
        if not has_table_or_list:
            issues.append("缺少表格或列表结构")

    # weather 类型校验
    elif intent_type == "weather":
        weather_keywords = ["温度", "°", "度", "晴", "阴", "雨", "雪", "湿度", "天气"]
        has_weather_info = any(kw in stripped for kw in weather_keywords)
        if not has_weather_info:
            issues.append("缺少温度或天气相关关键词")

    # 计算置信度
    if len(issues) == 0:
        confidence = "high"
    elif len(issues) == 1:
        confidence = "medium"
    else:
        confidence = "low"

    is_valid = confidence in ("high", "medium")

    return {
        "is_valid": is_valid,
        "issues": issues,
        "confidence": confidence,
    }


# ============================================================
# 6. 完整输出处理流水线
# ============================================================

def format_output_pipeline(text: str, intent_type: str = "qa") -> str:
    """
    完整的输出处理流水线（供 stream.py 调用）。

    处理步骤：
    1. truncate_respectfully() — 截断超长内容
    2. format_repair()          — 修复格式问题
    3. validate_structure()     — 结构校验（仅日志记录，不阻断）
    4. 返回处理后的文本
    """
    try:
        # Step 1: 截断超长内容
        text = truncate_respectfully(text)

        # Step 2: 格式修复
        text = format_repair(text)

        # Step 3: 结构校验（仅记录日志，不阻断）
        validate_structure(text, intent_type)

        return text
    except Exception as e:
        logger.warning("输出后处理流水线出错，返回原始文本: %s", str(e))
        return text
