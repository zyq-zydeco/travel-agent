from backend.app.core.config import settings


def get_search_tool():
    """获取 Tavily 联网搜索工具"""
    try:
        from langchain_tavily import TavilySearch
        search = TavilySearch(
            tavily_api_key=settings.TAVILY_API_KEY,
            max_results=5,
            topic="general",
            description="搜索互联网获取旅行相关信息，如景点介绍、天气预报、签证政策、机票酒店价格、美食推荐、交通攻略等",
        )
    except ImportError:
        from langchain_community.tools.tavily_search import TavilySearchResults
        search = TavilySearchResults(
            tavily_api_key=settings.TAVILY_API_KEY,
            max_results=5,
            search_depth="basic",
            description="搜索互联网获取旅行相关信息，如景点介绍、天气预报、签证政策、机票酒店价格、美食推荐、交通攻略等",
        )
    return search


def get_tools():
    """获取所有工具列表"""
    return [get_search_tool()]