"""旅行专家智能体 - 工具集
包含：联网搜索、天气查询、汇率换算、签证政策查询、高德地图(POI/路线/地理编码)
"""
import json
import requests
from langchain_core.tools import BaseTool, StructuredTool
from typing import Optional
from pydantic import BaseModel, Field

from backend.app.core.config import settings


# ====== 1. 联网搜索工具（已有，保持不变）======

def get_search_tool():
    """获取 Tavily 联网搜索工具"""
    try:
        from langchain_tavily import TavilySearch
        search = TavilySearch(
            tavily_api_key=settings.TAVILY_API_KEY,
            max_results=5,
            topic="general",
            description=(
                "搜索互联网获取旅行相关信息。"
                "适用于：景点介绍、美食推荐、交通攻略、酒店评价、旅游注意事项等通用信息查询。"
                "不要用于：天气查询（请用 weather_search）、汇率换算（请用 exchange_rate）。"
            ),
        )
    except ImportError:
        from langchain_community.tools.tavily_search import TavilySearchResults
        search = TavilySearchResults(
            tavily_api_key=settings.TAVILY_API_KEY,
            max_results=5,
            search_depth="basic",
            description=(
                "搜索互联网获取旅行相关信息。"
                "适用于：景点介绍、美食推荐、交通攻略、酒店评价等通用信息查询。"
            ),
        )
    return search


# ====== 2. 天气查询工具 ======

# 内置固定汇率表（当 API Key 未配置时使用）
FALLBACK_EXCHANGE_RATES = {
    "USD": 7.25,   # 美元 → 人民币
    "EUR": 7.80,   # 欧元 → 人民币
    "JPY": 0.048,  # 日元 → 人民币 (100日元 ≈ 4.8人民币)
    "KRW": 0.0053, # 韩元 → 人民币
    "GBP": 9.20,   # 英镑 → 人民币
    "HKD": 0.93,   # 港币 → 人民币
    "TWD": 0.22,   # 台币 → 人民币
    "THB": 0.20,   # 泰铢 → 人民币
    "SGD": 5.30,   # 新加坡元 → 人民币
    "MYR": 1.53,   # 马来西亚林吉特 → 人民币
    "AUD": 4.65,   # 澳元 → 人民币
    "CAD": 5.30,   # 加拿大元 → 人民币
}


class WeatherInput(BaseModel):
    city: str = Field(description="要查询天气的城市名称，如'杭州'、'Tokyo'、'Paris'")


def _search_weather_fallback(city: str) -> str:
    """降级方案：通过搜索工具查询天气信息"""
    try:
        from langchain_tavily import TavilySearch
        search = TavilySearch(
            tavily_api_key=settings.TAVILY_API_KEY,
            max_results=3,
            topic="general",
        )
        results = search.invoke(f"{city} 未来一周天气预报 今天天气")
        output = []
        for r in results:
            if isinstance(r, dict):
                output.append(r.get("content", ""))
            else:
                output.append(str(r))
        return f"[降级模式] 通过搜索获取的 {city} 天气信息：\n" + "\n\n".join(output)
    except Exception as e:
        return f"抱歉，无法获取 {city} 的天气信息：{str(e)}"


def _call_weather_api(city: str) -> str:
    """调用 OpenWeatherMap 查询天气"""
    api_key = getattr(settings, 'WEATHER_API_KEY', '')

    if not api_key:
        return _search_weather_fallback(city)

    try:
        # 直接调用 OpenWeatherMap Forecast API
        url = "https://api.openweathermap.org/data/2.5/forecast"
        params = {
            "q": city,
            "appid": api_key,
            "units": "metric",
            "lang": "zh_cn",
        }
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            data = res.json()
            lines = [f"📍 {city} 天气预报（数据来源：OpenWeatherMap）"]
            seen_dates = set()
            for item in data.get("list", [])[:8]:
                dt = item.get("dt_txt", "")[:10]
                if dt not in seen_dates:
                    seen_dates.add(dt)
                    desc = item["weather"][0]["description"] if item.get("weather") else ""
                    temp = item["main"].get("temp", "?")
                    humidity = item["main"].get("humidity", "?")
                    lines.append(f"📅 {dt}: {desc}，约{temp}°C，湿度{humidity}%")
            return "\n".join(lines)

        # API 返回非 200 则降级到搜索
        return _search_weather_fallback(city)

    except Exception as e:
        return _search_weather_fallback(city)


# 创建天气工具
weather_tool = StructuredTool.from_function(
    func=_call_weather_api,
    name="weather_search",
    description=(
        "查询指定城市当前及未来几天的天气预报。"
        "输入：城市名称（中文或英文均可）。"
        "输出：未来3-7天的天气详情，包括温度范围、天气状况、湿度、风向等。"
        "适用场景：用户询问目的地天气、穿衣建议、最佳出行时间等。"
        "示例输入: city='杭州'"
    ),
    args_schema=WeatherInput,
)


# ====== 3. 汇率换算工具 ======

class ExchangeInput(BaseModel):
    amount: float = Field(description="要换算的金额")
    from_currency: str = Field(description="源货币代码，如 CNY/USD/EUR/JPY/GBP/HKD/TWD/KRW/THB 等 ISO 4217 代码")
    to_currency: str = Field(description="目标货币代码")


def _convert_exchange(amount: float, from_currency: str, to_currency: str) -> str:
    """汇率换算"""
    from_upper = from_currency.upper().strip()
    to_upper = to_currency.upper().strip()

    api_key = getattr(settings, 'OPEN_EXCHANGE_KEY', '')

    # 尝试调用实时汇率 API
    if api_key:
        try:
            url = f"https://openexchangerates.org/api/latest.json?app_id={api_key}"
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                rates = res.json().get("rates", {})
                if from_upper == "USD":
                    usd_amount = amount
                elif from_upper in rates:
                    usd_amount = amount / rates[from_upper]
                else:
                    return f"不支持的货币: {from_upper}"

                if to_upper == "USD":
                    result = usd_amount
                elif to_upper in rates:
                    result = usd_amount * rates[to_upper]
                else:
                    return f"不支持的货币: {to_upper}"

                return (
                    f"💱 汇率换算结果（实时数据）：\n"
                    f"{amount:.2f} {from_upper} = {result:.2f} {to_upper}\n"
                    f"数据来源: Open Exchange Rates，仅供参考，实际以银行汇率为准"
                )
        except Exception:
            pass

    # 使用内置固定汇率（基于人民币为基准）
    fallback_rates = FALLBACK_EXCHANGE_RATES.copy()

    # CNY 作为基准
    cny_rates = {"CNY": 1.0}
    cny_rates.update(fallback_rates)

    # 反向汇率（外币→人民币已有，需要人民币→外币）
    reverse_rates = {}
    for code, rate_to_cny in cny_rates.items():
        if rate_to_cny > 0:
            reverse_rates[code] = 1.0 / rate_to_cny

    # 先统一转为人民币
    if from_upper in cny_rates:
        amount_in_cny = amount * cny_rates[from_upper]
    elif from_upper in reverse_rates:
        amount_in_cny = amount * reverse_rates[from_upper]
    else:
        return f"❌ 不支持的货币代码: {from_upper}。支持的常见货币: USD/EUR/JPY/GBP/HKD/TWD/KRW/THB/MYR/AUD/CAD"

    # 再从人民币转为目标货币
    if to_upper == "CNY":
        final_amount = amount_in_cny
    elif to_upper in reverse_rates:
        final_amount = amount_in_cny * reverse_rates[to_upper]
    else:
        return f"❌ 不支持的货币代码: {to_upper}。支持的常见货币: USD/EUR/JPY/GBP/HKD/TWD/KRW/THB/MYR/AUD/CAD"

    return (
        f"💱 汇率换算结果（参考汇率）：\n"
        f"{amount:.2f} {from_upper} ≈ {final_amount:.2f} {to_upper}\n"
        f"⚠️ 使用的是参考汇率，实际交易请以银行实时汇率为准"
    )


exchange_tool = StructuredTool.from_function(
    func=_convert_exchange,
    name="exchange_rate",
    description=(
        "货币汇率换算工具。支持主要国际货币之间的汇率换算。"
        "输入：金额、源货币代码、目标货币代码（ISO 4217 标准）。"
        "输出：换算结果和参考汇率说明。"
        "适用场景：出境游预算估算、费用对比、购物换算等。"
        "支持货币: CNY(人民币), USD(美元), EUR(欧元), JPY(日元), GBP(英镑), "
        "HKD(港币), TWD(台币), KRW(韩元), THB(泰铢), MYR(林吉特), AUD(澳元), CAD(加元)"
        "示例输入: amount=10000, from_currency='CNY', to_currency='JPY'"
    ),
    args_schema=ExchangeInput,
)


# ====== 4. 签证政策查询工具 ======

class VisaPolicyInput(BaseModel):
    destination: str = Field(description="目的地国家或地区名称")
    nationality: str = Field(default="中国", description="持签人国籍，默认为中国")


def _search_visa_policy(destination: str, nationality: str = "中国") -> str:
    """
    通过联网搜索查询签证政策，并尝试结构化提取关键信息。
    由于没有专门的签证 API，使用 Tavily 搜索后返回原始结果。
    """
    query = f"{nationality}公民去{destination}签证要求 2025 最新政策 免签 落地签 电子签"

    try:
        from langchain_tavily import TavilySearch
        search = TavilySearch(
            tavily_api_key=settings.TAVILY_API_KEY,
            max_results=5,
            topic="general",
        )
        results = search.invoke(query)

        output_parts = [f"📋 {nationality}公民前往 {destination} 的签证政策信息：\n"]

        for i, r in enumerate(results, 1):
            if isinstance(r, dict):
                content = r.get("content", "")
                url = r.get("url", "")
                title = r.get("title", "来源")
                output_parts.append(f"--- 来源{i}: {title} ---")
                output_parts.append(content[:800])  # 截断过长内容
                if url:
                    output_parts.append(f"链接: {url}")
            else:
                output_parts.append(str(r)[:500])
            output_parts.append("")

        output_parts.append("\n⚠️ 以上信息来自网络搜索，签证政策可能随时变化，请以官方渠道最新公告为准。")

        return "\n".join(output_parts)

    except ImportError:
        # 降级处理
        return (
            f"⚠️ 无法查询 {destination} 的签证政策信息。\n"
            f"建议访问以下官方渠道确认：\n"
            f"- 目的地国家驻华大使馆官网\n"
            f"- 外交部领事服务网: cs.mfa.gov.cn"
        )
    except Exception as e:
        return f"查询签证政策时出错: {str(e)}"


visa_policy_tool = StructuredTool.from_function(
    func=_search_visa_policy,
    name="visa_policy_search",
    description=(
        "查询前往特定目的地的签证政策信息。"
        "输入：目的地国家/地区名称、持签人国籍（默认中国）。"
        "输出：签证类型（免签/落地签/电子签/贴纸签）、所需材料、办理时间、费用等。"
        "适用场景：用户询问出国签证要求、免签国家列表、落地签条件等。"
        "注意：此工具依赖网络搜索，信息可能存在滞后，请提醒用户以官方渠道为准。"
        "示例输入: destination='日本', nationality='中国'"
    ),
    args_schema=VisaPolicyInput,
)


# ====== 5. 高德地图 POI 搜索工具 ======

class AmapPOISearchInput(BaseModel):
    city: str = Field(description="查询的城市名称，如'成都'、'杭州'、'Tokyo'")
    keywords: str = Field(description="搜索关键词，如'景点'、'川菜'、'酒店'、'地铁站'")
    types: str = Field(
        default="",
        description=(
            "POI 分类代码，可限制搜索范围。"
            "常用值: scenic_spot(景点), hotel(酒店), restaurant(餐厅), "
            "subway_station(地铁), bus_station(公交站), scenic_spot_2a~5a(A级以上景点)。"
            "留空则搜索全部类型"
        )
    )
    offset: int = Field(default=8, description="返回结果数量，默认8条")


# 高德 POI 类型中文映射表
AMAP_TYPE_LABELS = {
    "scenic_spot": "景点",
    "hotel": "酒店",
    "restaurant": "餐厅",
    "subway_station": "地铁",
    "bus_station": "公交",
}


def _amap_poi_fallback(city: str, keywords: str) -> str:
    """降级方案：通过 Tavily 搜索 POI 信息"""
    try:
        from langchain_tavily import TavilySearch
        search = TavilySearch(
            tavily_api_key=settings.TAVILY_API_KEY,
            max_results=5,
            topic="general",
        )
        results = search.invoke(f"{city} {keywords} 推荐 地址 评价")
        output = [f"[降级模式] 通过搜索获取 {city} 的{keywords}信息："]
        for i, r in enumerate(results, 1):
            if isinstance(r, dict):
                content = r.get("content", "")
                url = r.get("url", "")
                output.append(f"\n{i}. {content[:300]}")
                if url:
                    output.append(f"   来源: {url}")
            else:
                output.append(f"\n{i}. {str(r)[:300]}")
        return "\n".join(output)
    except Exception as e:
        return f"抱歉，无法搜索 {keywords} 信息：{str(e)}"


def _call_amap_poi(city: str, keywords: str, types: str = "", offset: int = 8) -> str:
    """调用高德 POI 搜索 API"""
    api_key = getattr(settings, 'AMAP_API_KEY', '')
    
    if not api_key:
        return (
            "⚠️ 高德地图 API Key 未配置。\n"
            "请在 .env 文件中设置 AMAP_API_KEY 以启用精确的地点搜索功能。\n"
            "注册地址: https://lbs.amap.com/\n\n"
            + _amap_poi_fallback(city, keywords)
        )
    
    try:
        url = "https://restapi.amap.com/v3/place/text"
        params = {
            "key": api_key,
            "city": city,
            "keywords": keywords,
            "output": "json",
            "offset": min(offset, 25),  # 高德上限 25
            "extensions": "all",  # 返回详细信息
        }
        if types:
            params["types"] = types
        
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        
        if data.get("status") != "1":
            error_info = data.get("info", "未知错误")
            return f"⚠️ 高德地图搜索失败: {error_info}\n" + _amap_poi_fallback(city, keywords)
        
        pois = data.get("pois", [])
        if not pois:
            return f"📍 在 {city} 未找到与「{keywords}」相关的结果。建议换个关键词试试。"
        
        type_label = AMAP_TYPE_LABELS.get(types, types or "地点")
        lines = [f"📍 {city} · {keywords}相关{type_label}（数据来源：高德地图）\n"]
        
        for i, poi in enumerate(pois[:offset], 1):
            name = poi.get("name", "未知")
            address = poi.get("address", "") or poi.get("pname", "") + poi.get("adname", "")
            location = poi.get("location", "")
            ptype = poi.get("type", "").replace("|", " / ")
            
            info_parts = [f"📌 {i}. **{name}**"]
            if address:
                info_parts.append(f"   🏠 地址: {address}")
            if location:
                lng, lat = location.split(",") if "," in location else ("?", "?")
                info_parts.append(f"   🗺️ 坐标: 经度{lng}, 纬度{lat}")
            if ptype and ptype != name:
                info_parts.append(f"   📂 类型: {ptype}")
            
            # 额外字段
            tel = poi.get("tel", "")
            if tel:
                info_parts.append(f"   ☎️ 电话: {tel}")
            
            cost = poi.get("cost", "")
            if cost:
                info_parts.append(f"   💰 人均/价格: {cost}")
            
            rating = poi.get("rating", "")
            if rating:
                info_parts.append(f"   ⭐ 评分: {rating}")
            
            lines.append("\n".join(info_parts))
        
        total = data.get("count", len(pois))
        if int(total) > offset:
            lines.append(f"\n📊 共找到 {total} 个结果，显示前 {offset} 条。")
        
        return "\n\n".join(lines)
    
    except requests.exceptions.Timeout:
        return "⚠️ 高德地图请求超时，已自动切换为搜索模式\n" + _amap_poi_fallback(city, keywords)
    except Exception as e:
        return f"⚠️ 高德地图搜索出错: {str(e)}\n" + _amap_poi_fallback(city, keywords)


amap_poi_tool = StructuredTool.from_function(
    func=_call_amap_poi,
    name="amap_poi_search",
    description=(
        "高德地图 POI（兴趣点）搜索工具。用于查找指定城市的真实地点信息。"
        "输入：城市名称和搜索关键词。"
        "输出：结构化的地点列表，包含名称、地址、坐标、类型、电话、评分、人均消费等。"
        "适用场景：用户询问某个城市有什么好玩的景点、推荐的餐厅/酒店、"
        "附近的地铁站/公交站等具体地理位置相关的需求。"
        "注意：这是精确的地理数据搜索，不是普通网页搜索。"
        "示例输入: city='成都', keywords='景点'"
    ),
    args_schema=AmapPOISearchInput,
)


# ====== 6. 高德地图路线规划工具 ======

class AmapRouteInput(BaseModel):
    origin: str = Field(description="起点名称或经纬度坐标（如'春熙路'或'104.065735,30.659462'）")
    destination: str = Field(description="终点名称或经纬度坐标（如'熊猫基地'或'104.1465,30.7350'）")
    mode: str = Field(
        default="driving",
        description=(
            "出行方式: "
            "driving=驾车（默认）, walking=步行, transit=公交/地铁, bicycling=骑行"
        ),
    )

# 出行方式中文标签
MODE_LABELS = {
    "driving": "🚗 驾车",
    "walking": "🚶 步行",
    "transit": "🚇 公交/地铁",
    "bicycling": "🚴 骑行",
}

MODE_TIME_HINTS = {
    "driving": "（路况良好时）",
    "walking": "",
    "transit": "（含等车时间）",
    "bicycling": "（平路匀速骑行）",
}


def _amap_route_fallback(origin: str, destination: str, mode: str) -> str:
    """路线规划降级方案"""
    mode_label = MODE_LABELS.get(mode, "导航")
    try:
        from langchain_tavily import TavilySearch
        search = TavilySearch(
            tavily_api_key=settings.TAVILY_API_KEY,
            max_results=3,
            topic="general",
        )
        results = search.invoke(f"{origin} 到 {destination} {mode_label.replace(' ', '')} 路线 怎么走")
        output = [f"[降级模式] {mode_label}: {origin} → {destination}\n"]
        for r in results:
            if isinstance(r, dict):
                output.append(r.get("content", "")[:400])
            else:
                output.append(str(r)[:400])
        return "\n".join(output)
    except Exception as e:
        return f"抱歉，无法获取路线信息: {e}"


def _call_amap_route(origin: str, destination: str, mode: str = "driving") -> str:
    """调用高德路线规划 API"""
    api_key = getattr(settings, 'AMAP_API_KEY', '')
    
    if not api_key:
        return (
            "⚠️ 高德地图 API Key 未配置。\n"
            "请在 .env 中设置 AMAP_API_KEY 以启用路线规划功能。\n"
            "注册地址: https://lbs.amap.com/\n\n"
            + _amap_route_fallback(origin, destination, mode)
        )
    
    # 验证 mode 合法性
    valid_modes = ["driving", "walking", "transit", "bicycling"]
    if mode not in valid_modes:
        mode = "driving"
    
    try:
        url = f"https://restapi.amap.com/v3/direction/{mode}"
        params = {
            "key": api_key,
            "origin": origin,
            "destination": destination,
            "extensions": "all",
            "strategy": "0",  # 最短距离策略（驾车）/推荐策略（公交）
            "output": "json",
        }
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        
        if data.get("status") != "1":
            error_info = data.get("info", "未知错误")
            return f"⚠️ 路线规划失败: {error_info}\n" + _amap_route_fallback(origin, destination, mode)
        
        routes = data.get("route", {}).get("routes", [])
        if not routes:
            return f"❌ 无法规划从「{origin}」到「{destination}」的{MODE_LABELS.get(mode, '')}路线。请检查地名是否正确。"
        
        route = routes[0]  # 取最佳路线
        distance_m = route.get("distance", 0)
        duration_s = route.get("duration", 0)
        tolls = route.get("tolls", "0")
        taxi_cost = route.get("taxi_cost", "")
        
        # 格式化距离和时间
        if distance_m >= 1000:
            dist_display = f"{distance_m / 1000:.1f} 公里"
        else:
            dist_display = f"{distance_m} 米"
        
        hours = int(duration_s) // 3600
        minutes = (int(duration_s) % 3600) // 60
        if hours > 0:
            time_display = f"{hours}小时{minutes}分钟"
        else:
            time_display = f"{minutes}分钟"
        
        mode_label = MODE_LABELS.get(mode, "导航")
        time_hint = MODE_TIME_HINTS.get(mode, "")
        
        lines = [
            f"{mode_label}路线: **{origin}** → **{destination}**",
            f"📏 总距离: {dist_display}",
            f"⏱️ 预计用时: {time_display} {time_hint}",
        ]
        
        if tolls and tolls != "0":
            lines.append(f"💰 过路费: 约 ¥{tolls}")
        if taxi_cost:
            lines.append(f"🚕 参考打车费: 约 ¥{taxi_cost}")
        
        # 解析分步路径
        steps = route.get("steps", [])
        if steps:
            lines.append(f"\n--- 详细路线 ({len(steps)} 段) ---")
            for i, step in enumerate(steps, 1):
                instruction = step.get("instruction", "").strip()
                step_dist = step.get("distance", 0)
                step_dur = step.get("duration", 0)
                road = step.get("road", "")
                
                if step_dist >= 1000:
                    step_dist_str = f"{step_dist / 1000:.1f}km"
                else:
                    step_dist_str = f"{step_dist}m"
                
                step_min = int(step_dur) // 60
                
                step_line = f"  {i}. {instruction}"
                if road:
                    step_line += f" [{road}]"
                step_line += f" ({step_dist_str}, 约{step_min}分)"
                lines.append(step_line)
        
        # 公交特有信息
        if mode == "transit":
            transits = route.get("transits", [])
            if transits:
                transit = transits[0]
                lines.append(f"\n--- 推荐公交方案 ---")
                segments = transit.get("segments", [])
                for seg in segments:
                    bus_lines = seg.get("bus", {}).get("buslines", [])
                    if bus_lines:
                        for bl in bus_lines[:3]:
                            bl_name = bl.get("name", "")
                            via_stops = bl.get("via_stops", [])
                            arrival_stop = bl.get("arrival_stop", {}).get("name", "")
                            lines.append(f"  🚌 {bl_name} → {arrival_stop}")
                    walking = seg.get("walking")
                    if walking:
                        w_dist = walking.get("distance", 0)
                        if w_dist > 0:
                            lines.append(f"  🚶 步行 {w_dist}米")
        
        return "\n".join(lines)
    
    except requests.exceptions.Timeout:
        return "⚠️ 高德地图请求超时\n" + _amap_route_fallback(origin, destination, mode)
    except Exception as e:
        return f"⚠️ 路线规划出错: {str(e)}\n" + _amap_route_fallback(origin, destination, mode)


amap_route_tool = StructuredTool.from_function(
    func=_call_amap_route,
    name="amap_route_planning",
    description=(
        "高德地图路线规划工具。用于计算两点间的出行路线。"
        "输入：起点、终点、出行方式（驾车/步行/公交/骑行）。"
        "输出：总距离、预计时间、过路费、详细分段导航指引。"
        "适用场景：用户询问从A到B怎么走、交通方式对比、"
        "通勤时间估算、打车费用预估等。"
        "支持驾车(driving)、步行(walking)、公交(transit)、骑行(bicycling) 四种模式。"
        "示例输入: origin='春熙路', destination='熊猫基地', mode='transit'"
    ),
    args_schema=AmapRouteInput,
)


# ====== 7. 高德地图地理编码工具 ======

class AmapGeocodeInput(BaseModel):
    address: Optional[str] = Field(default=None, description="要编码的地址或地名（地理编码时使用）")
    location: Optional[str] = Field(default=None, description="经纬度坐标，格式'经度,纬度'（逆地理编码时使用）")


def _call_amap_geocode(address: str = None, location: str = None) -> str:
    """调用高德地理编码/逆地理编码 API"""
    api_key = getattr(settings, 'AMAP_API_KEY', '')
    
    if not api_key:
        return (
            "⚠️ 高德地图 API Key 未配置。\n"
            "请在 .env 中设置 AMAP_API_KEY 以启用地理编码功能。\n"
            "注册地址: https://lbs.amap.com/"
        )
    
    try:
        # 地理编码：地址 → 坐标
        if address and not location:
            url = "https://restapi.amap.com/v3/geocode/geo"
            params = {
                "key": api_key,
                "address": address,
                "output": "json",
            }
            res = requests.get(url, params=params, timeout=10)
            data = res.json()
            
            if data.get("status") != "1":
                return f"⚠️ 地理编码失败: {data.get('info', '未知错误')}"
            
            geocodes = data.get("geocodes", [])
            if not geocodes:
                return f"❌ 未找到地址「{address}」对应的坐标。请检查地址是否正确。"
            
            geo = geocodes[0]
            formatted_addr = geo.get("formatted_address", address)
            coords = geo.get("location", "")
            adcode = geo.get("adcode", "")
            city = geo.get("city", "")
            district = geo.get("district", "")
            
            lng, lat = (coords.split(",") if coords else ("?", "?"))
            
            lines = [
                f"📍 地理编码结果",
                f"📌 输入地址: {address}",
                f"✅ 标准化地址: {formatted_addr}",
                f"🗺️ 坐标: 经度 {lng}, 纬度 {lat}",
            ]
            if city:
                lines.append(f"🏙️ 城市: {city}")
            if district:
                lines.append(f"📋 区县: {district}")
            if adcode:
                lines.append(f"🔢 行政区划码: {adcode}")
            
            return "\n".join(lines)
        
        # 逆地理编码：坐标 → 地址
        elif location and not address:
            url = "https://restapi.amap.com/v3/geocode/regeo"
            params = {
                "key": api_key,
                "location": location,
                "output": "json",
                "extensions": "all",  # 返回详细信息
            }
            res = requests.get(url, params=params, timeout=10)
            data = res.json()
            
            if data.get("status") != "1":
                return f"⚠️ 逆地理编码失败: {data.get('info', '未知错误')}"
            
            regeocode = data.get("regeocode", {})
            formatted_addr = regeocode.get("formatted_address", location)
            
            address_component = regeocode.get("addressComponent", {})
            province = address_component.get("province", "")
            city = address_component.get("city", "")
            district = address_component.get("district", "")
            township = address_component.get("township", "")
            street = address_component.get("streetNumber", {})
            street_name = street.get("street", "")
            street_number = street.get("number", "")
            
            # 周边道路/地标
            aois = regeocode.get("aois", [])  # 兴趣点
            streets = regeocode.get("streets", [])  # 道路
            crossroads = regeocode.get("crossroads", [])  # 路口
            
            lines = [
                f"📍 逆地理编码结果",
                f"📌 输入坐标: {location}",
                f"✅ 标准化地址: {formatted_addr}",
                f"🏛️ 行政区划: {province} {city} {district}",
            ]
            if township:
                lines.append(f"🏘️ 街道/乡镇: {township}")
            if street_name:
                addr_detail = street_name
                if street_number:
                    addr_detail += f" {street_number}号"
                lines.append(f"🛣️ 门牌: {addr_detail}")
            
            if aois:
                nearby_pois = [aoi.get("name", "") for aoi in aois[:3]]
                lines.append(f"🏢 附近: {', '.join(nearby_pois)}")
            if crossroads:
                cr = crossroads[0] if crossroads else {}
                cr_name = cr.get("name", "")
                if cr_name:
                    lines.append(f"🔀 附近路口: {cr_name}")
            
            return "\n".join(lines)
        
        else:
            return "❌ 请提供 address（地址）或 location（坐标）其中之一，不能同时为空或同时填写。"
    
    except requests.exceptions.Timeout:
        return "⚠️ 高德地图请求超时"
    except Exception as e:
        return f"⚠️ 地理编码出错: {str(e)}"


amap_geocode_tool = StructuredTool.from_function(
    func=_call_amap_geocode,
    name="amap_geocode",
    description=(
        "高德地图地理编码工具。支持两种模式："
        "1. 地理编码：传入地址 → 返回经纬度坐标和标准化地址"
        "2. 逆地理编码：传入坐标 → 返回详细地址和周边信息"
        "适用场景：将地名转为坐标用于路线计算、确认某坐标对应的具体位置、"
        "了解坐标周边的道路/建筑/兴趣点。"
        "示例输入(地理编码): address='成都市天府广场'"
        "示例输入(逆编码): location='104.065735,30.659462'"
    ),
    args_schema=AmapGeocodeInput,
)


# ====== 工具集入口 ======

def get_tools():
    """获取所有可用工具列表（共 7 个工具）"""
    return [
        get_search_tool(),          # 1. 联网搜索
        weather_tool,               # 2. 天气查询
        exchange_tool,              # 3. 汇率换算
        visa_policy_tool,           # 4. 签证政策
        amap_poi_tool,              # 5. 高德地图 POI 搜索 ⬅️ 新增
        amap_route_tool,            # 6. 高德地图路线规划 ⬅️ 新增
        amap_geocode_tool,          # 7. 高德地图地理编码 ⬅️ 新增
    ]
