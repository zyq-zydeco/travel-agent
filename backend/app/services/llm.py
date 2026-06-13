from langchain_openai import ChatOpenAI
from backend.app.core.config import settings


def get_llm(streaming: bool = True):
    """获取通义千问 LLM 实例（文本模型）

    注意：max_tokens 设置为 8192，以支持旅行规划等需要长回复的场景。
    之前设置为 2048 会导致输出被截断，影响用户体验。
    """
    llm = ChatOpenAI(
        model=settings.DASHSCOPE_MODEL,
        base_url=settings.DASHSCOPE_BASE_URL,
        api_key=settings.DASHSCOPE_API_KEY,
        streaming=streaming,
        temperature=0.7,
        max_tokens=8192,  # 提升到 8192，避免长回复被截断
    )
    return llm


def get_vision_llm():
    """获取通义千问视觉模型实例（用于图片识别）

    注意：max_tokens 设置为 4096，对于图片识别任务足够使用。
    """
    llm = ChatOpenAI(
        model="qwen-vl-plus",
        base_url=settings.DASHSCOPE_BASE_URL,
        api_key=settings.DASHSCOPE_API_KEY,
        streaming=False,
        temperature=0.3,
        max_tokens=4096,  # 图片识别任务通常不需要过长输出
    )
    return llm