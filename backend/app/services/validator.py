"""
输出验证模块
负责：AI 回复的事实核查、格式校验、一致性检查
验证失败时返回问题和修正建议
"""

import re
import logging
from typing import List, Tuple, Dict, Any
from dataclasses import dataclass, field
from backend.app.services.output_formatter import (
    format_repair,
    extract_thinking_answer,
    validate_structure as formatter_validate,
    TravelPlanOutput,
    WeatherOutput,
    BudgetOutput,
    GeneralQAOutput,
)

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """验证结果"""
    is_valid: bool = True
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)  # 不阻断但需关注的问题
    confidence: str = "high"  # high / medium / low


class OutputValidator:
    """AI 输出验证器"""
    
    def __init__(self):
        # 价格检测正则
        self.price_pattern = re.compile(
            r'[¥￥$€£]\s*[\d,]+\.?\d*\s*(?:元|块|USD|EUR|GBP| dollars?|euros?|pounds?)?|'
            r'[\d,]+\.?\d*\s*(?:元|RMB|CNY|USD|EUR|GBP)\b'
        )
        # 日期检测正则
        self.date_pattern = re.compile(
            r'\d{1,2}[月/.]\d{1,2}(?:日)?|\d{4}[-/年]\d{1,2}[-/月]\d{1,2}(?:日)?|'
            r'(?:第?\d+[天日]|Day\s*\d+|day\s*\d+)'
        )
        # 距离检测正则
        self.distance_pattern = re.compile(
            r'[\d.]+\s*(?:公里|千米|km|KM|miles?|米)'
        )
        # 时间段检测正则
        self.duration_pattern = re.compile(
            r'[\d.]+\s*(?:小时|分钟|hrs?|mins?|days?|天)'
        )
    
    def validate(self, response: str, intent_type: str = "qa") -> ValidationResult:
        """
        综合验证入口。
        
        参数:
            response: AI 生成的回复文本
            intent_type: 任务类型 (qa/planning/search/complex)
        
        返回:
            ValidationResult 对象
        """
        result = ValidationResult()
        
        # 执行各项检查
        fact_issues = self.fact_check(response)
        format_issues = self.format_check(response, intent_type)
        consistency_issues = self.consistency_check(response)
        schema_issues = self.schema_validate(response, intent_type)

        result.issues.extend(fact_issues)
        result.issues.extend(format_issues)
        result.issues.extend(consistency_issues)
        result.issues.extend(schema_issues)

        # 格式修复检测（仅记录，不阻断）
        repair_check = self.format_repair_check(response)
        if repair_check["has_issues"]:
            for issue in repair_check["repairable_issues"]:
                if issue["auto_fixable"]:
                    result.warnings.append(f"[可自动修复] {issue['description']}")
                else:
                    result.warnings.append(f"[需人工检查] {issue['description']}")

        # 判断整体有效性
        critical_issues = [i for i in result.issues if i.startswith("[严重]")]
        if critical_issues:
            result.is_valid = False
            result.confidence = "low"
        elif result.issues:
            result.is_valid = True  # 有警告但不阻断
            result.confidence = "medium"
        else:
            result.is_valid = True
            result.confidence = "high"
        
        return result
    
    def fact_check(self, response: str) -> List[str]:
        """
        事实核查：检查关键信息是否有来源标注或置信度说明。
        
        检测项：
        - 价格信息是否标注了时效性或数据来源
        - 日期敏感信息（签证、政策）是否有"请以官方为准"提示
        """
        issues = []
        
        prices = self.price_pattern.findall(response)
        if prices:
            # 检查价格附近是否有来源标注
            has_source_hint = any(hint in response for hint in [
                "参考", "大约", "大概", "约", "左右", "起步", "起",
                "以...为准", "官方", "实际", "仅供参考",
                "来源:", "资料", "数据",
            ])
            if not has_source_hint and len(prices) >= 2:
                issues.append("[提示] 回复中包含多个价格信息，建议标注数据来源或时效性")
        
        # 检查签证/政策类内容是否有免责声明
        visa_keywords = ["签证", "入境", "护照", "visa", "passport"]
        has_visa_content = any(kw in response for kw in visa_keywords)
        if has_visa_content:
            has_disclaimer = any(hint in response for hint in [
                "以官方为准", "请确认", "可能有变", "最新", "官方渠道",
                "大使馆", "领事馆",
            ])
            if not has_disclaimer:
                issues.append("[提示] 包含签证/政策信息，建议添加'请以官方最新公告为准'的免责声明")
        
        return issues
    
    def format_check(self, response: str, intent_type: str) -> List[str]:
        """
        格式校验：检查输出是否符合任务类型的格式要求。
        
        planning 类型要求：
        - 必须有日期/天数标识
        - 建议有时间分段（上午/下午/晚上）
        
        budget 相关要求：
        - 建议有明细结构
        """
        issues = []
        
        if intent_type in ("planning", "complex"):
            # 检查是否有日期或天数结构
            has_date_structure = bool(self.date_pattern.search(response))
            has_day_structure = bool(re.search(r'第?\d+[天日]|Day\s*\d+', response, re.IGNORECASE))
            
            if not has_date_structure and not has_day_structure:
                issues.append("[建议] 行程规划类回答建议按日期或天数组织（如'Day 1'、'第一天'、'6月15日'）")
            
            # 检查是否有足够的结构化内容
            lines = response.strip().split('\n')
            non_empty_lines = [l for l in lines if l.strip()]
            if len(non_empty_lines) < 5:
                issues.append("[建议] 回复内容偏短，行程规划建议提供更详细的每日安排")
        
        # 检查是否有预算相关信息时的格式
        if "预算" in response or "费用" in response or "花销" in response:
            has_table_like = "|" in response or "：" in response.replace("：", ":").count(":") >= 3
            if not has_table_like:
                issues.append("[提示] 包含预算/费用信息时，建议使用列表或表格形式展示明细")
        
        return issues
    
    def consistency_check(self, response: str) -> List[str]:
        """
        一致性检查：检测回复中的逻辑矛盾。
        
        检测项：
        - 距离 vs 时间不合理（如"100公里，步行30分钟"）
        - 预算超支矛盾
        - 时间冲突
        """
        issues = []
        
        distances = self.distance_pattern.findall(response)
        durations = self.duration_pattern.findall(response)
        
        # 简单的距离-时间合理性启发式
        if distances and durations:
            for dist in distances[:3]:
                dist_val = float(re.findall(r'[\d.]+', dist)[0])
                dist_unit = re.sub(r'[\d.]+', '', dist).strip()
                
                for dur in durations[:3]:
                    dur_val = float(re.findall(r'[\d.]+', dur)[0])
                    dur_unit = re.sub(r'[\d.]+', '', dur).strip()
                    
                    # 明显不合理的组合
                    if ("公里" in dist_unit or "km" in dist_unit.lower()) and dist_val > 50:
                        if "分钟" in dur_unit and dur_val < 60:
                            issues.append(
                                f"[提示] 距离-时间可能不合理: {dist} vs {dur}，"
                                f"远距离通常需要更长的时间"
                            )
                        break  # 只报告第一个矛盾
        
        # 检查预算自相矛盾
        budget_matches = re.findall(r'总[计共]?[预算费]?.*?([¥￥$\d,]+)', response)
        if len(budget_matches) >= 2:
            issues.append("[提示] 回复中出现多次预算汇总，请确认无重复计算")
        
        return issues

    def schema_validate(self, response: str, intent_type: str = "qa") -> List[str]:
        """
        基于 Pydantic Schema 的结构校验。

        尝试将文本输出与对应意图类型的 Schema 进行启发式匹配，
        检查是否包含 Schema 要求的关键字段/结构元素。

        参数:
            response: AI 生成的回复文本
            intent_type: 任务类型 (qa/planning/search/complex)

        返回:
            问题列表（空列表表示通过）
        """
        issues = []

        # 先调用 output_formatter 的通用结构校验
        fmt_result = formatter_validate(response, intent_type)
        if not fmt_result["is_valid"]:
            issues.extend(fmt_result["issues"])

        # 额外的 Schema 级别检查
        if intent_type in ("planning", "complex"):
            # 检查行程规划类输出是否包含必要结构元素
            has_day_marker = bool(re.search(r'(?:Day\s*\d+|第?\d+[天日]|\d+月\d+日)', response, re.IGNORECASE))
            has_cost_info = bool(self.price_pattern.search(response))

            if not has_day_marker:
                issues.append("[Schema] 行程规划输出缺少日期/天数标识（如 Day 1、第一天等）")
            if not has_cost_info:
                issues.append("[提示] 行程规划建议包含费用信息")

        if intent_type in ("search",) and "天气" in response[:50]:
            # 天气类查询检查
            has_temp = bool(re.search(r'\d+.*?[°Cc]', response))
            has_date = bool(self.date_pattern.search(response))
            if not has_temp:
                issues.append("[Schema] 天气查询输出缺少温度数据")
            if not has_date:
                issues.append("[Schema] 天气查询输出缺少日期信息")

        return issues

    def format_repair_check(self, response: str) -> dict:
        """
        检测可自动修复的格式问题。

        分析回复文本中的格式缺陷，返回可修复的问题清单和建议。
        此方法只做检测不执行修复，供调用方决定是否修复。

        参数:
            response: AI 生成的回复文本

        返回:
            {
                "has_issues": bool,
                "repairable_issues": list[dict],  # 每项含 {"type": str, "description": str, "auto_fixable": bool}
                "needs_truncate": bool,
            }
        """
        result = {
            "has_issues": False,
            "repairable_issues": [],
            "needs_truncate": len(response) > 8000,
        }

        issues = result["repairable_issues"]

        # 检测未闭合代码块
        code_block_count = response.count("```")
        if code_block_count % 2 == 1:
            issues.append({
                "type": "unclosed_code_block",
                "description": f"检测到 {code_block_count} 个代码块标记（奇数个），存在未闭合的代码块",
                "auto_fixable": True,
            })
            result["has_issues"] = True

        # 检测连续过多空行（3 个及以上）
        if "\n\n\n\n" in response:
            count = response.count("\n\n\n\n")
            issues.append({
                "type": "excessive_blank_lines",
                "description": f"检测到 {count} 处超过 3 个连续空行",
                "auto_fixable": True,
            })
            result["has_issues"] = True

        # 检测缺失【思考】或【回答】标签
        has_thinking = "【思考】" in response
        has_answer = "【回答】" in response
        if not has_answer and len(response) > 100:
            # 较长的回复应该有标签
            issues.append({
                "type": "missing_tags",
                "description": "回复内容较长但缺少【回答】标签",
                "auto_fixable": True,  # 可以自动补全【回答】包裹
            })
            result["has_issues"] = True

        # 检测表格格式问题（有 | 但可能缺分隔行）
        if "|" in response and "---" not in response:
            # 可能有表格但缺少表头分隔行
            lines_with_pipe = [l for l in response.split("\n") if "|" in l and l.strip().startswith("|")]
            if len(lines_with_pipe) >= 2:
                issues.append({
                    "type": "malformed_table",
                    "description": f"检测到 {len(lines_with_pipe)} 行表格内容但缺少 --- 分隔行",
                    "auto_fixable": False,  # 表格修复需要语义理解，不建议自动修
                })
                result["has_issues"] = True

        return result


def validate_response(response: str, intent_type: str = "qa") -> Tuple[bool, List[str]]:
    """
    便捷函数：验证回复并返回 (is_valid, issues) 元组。
    
    供外部调用的简化接口。
    """
    validator = OutputValidator()
    result = validator.validate(response, intent_type)
    return result.is_valid, result.issues
