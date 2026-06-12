from langchain_openai import ChatOpenAI
from backend.app.core.config import settings


def get_llm(streaming: bool = True):
    """获取通义千问 LLM 实例（文本模型）"""
    llm = ChatOpenAI(
        model=settings.DASHSCOPE_MODEL,
        base_url=settings.DASHSCOPE_BASE_URL,
        api_key=settings.DASHSCOPE_API_KEY,
        streaming=streaming,
        temperature=0.7,
        max_tokens=2048,
    )
    return llm


def get_vision_llm():
    """获取通义千问视觉模型实例（用于图片识别）"""
    llm = ChatOpenAI(
        model="qwen-vl-plus",
        base_url=settings.DASHSCOPE_BASE_URL,
        api_key=settings.DASHSCOPE_API_KEY,
        streaming=False,
        temperature=0.3,
        max_tokens=8196,
    )
    return llm