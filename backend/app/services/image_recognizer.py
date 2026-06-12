from langchain_core.messages import HumanMessage
from backend.app.services.llm import get_vision_llm
from backend.app.services.file_processor import process_file


def recognize_image(save_name: str, user_question: str = "请描述这张图片的内容") -> str:
    """使用视觉模型识别图片内容"""
    result = process_file(save_name, "image")
    if not result or result["type"] != "image":
        return "[图片处理失败]"

    # 构建多模态消息
    content = [
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:{result['mime_type']};base64,{result['base64']}"
            }
        },
        {
            "type": "text",
            "text": f"""你是一个旅行图片分析专家。请仔细分析这张图片，回答用户的问题：{user_question}

请从以下角度分析（如果图片中有相关内容）：
1. 这是什么地方/景点/建筑？
2. 在哪个城市/国家？
3. 有什么特色或值得注意的细节？
4. 如果是美食，是什么菜系/特色？
5. 如果是酒店/住宿，是什么风格？

请尽量详细、准确地描述，如果不确定请说明。"""
        }
    ]

    try:
        vl_llm = get_vision_llm()
        response = vl_llm.invoke([HumanMessage(content=content)])
        return response.content
    except Exception as e:
        return f"[图片识别失败：{str(e)}]"