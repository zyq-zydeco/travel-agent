import json
import asyncio
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, AIMessage

from backend.app.core.database import get_db
from backend.app.core.deps import get_current_user
from backend.app.models.user import User
from backend.app.models.conversation import Conversation
from backend.app.models.message import Message
from backend.app.schemas.chat import ChatRequest
from backend.app.services.agent import get_agent

router = APIRouter(prefix="/api/chat", tags=["流式聊天"])


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """流式聊天接口 - 使用 SSE 实时推送 AI 回复"""

    # 如果没有对话ID，创建新对话
    if not request.conversation_id:
        conversation = Conversation(user_id=current_user.id, title="新聊天")
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        request.conversation_id = conversation.id

    # ====== 在流式生成之前，先处理附件 ======
    enhanced_message = request.message
    has_image = False

    if request.files and len(request.files) > 0:
        from backend.app.services.file_processor import process_file
        from backend.app.services.image_recognizer import recognize_image

        for file_info in request.files:
            save_name = file_info.get("save_name", "")
            file_type = file_info.get("file_type", "")

            if file_type == "image":
                has_image = True
                image_desc = await asyncio.to_thread(recognize_image, save_name, request.message)
                enhanced_message += f"\n\n[用户上传了一张图片，图片识别结果如下：\n{image_desc}]"

            elif file_type == "document":
                result = await asyncio.to_thread(process_file, save_name, file_type)
                if result and result["type"] == "document":
                    doc_text = result["text"]
                    enhanced_message += f"\n\n[用户上传了文档，内容如下：\n{doc_text}]"

    # 保存用户消息
    files_to_save = request.files if request.files else []
    user_msg = Message(
        conversation_id=request.conversation_id,
        role="user",
        content=request.message,
        files=files_to_save,
    )
    db.add(user_msg)

    # 更新对话标题
    conversation = db.query(Conversation).filter(
        Conversation.id == request.conversation_id
    ).first()
    if conversation and conversation.title == "新聊天":
        conversation.title = request.message[:20] + ("..." if len(request.message) > 20 else "")
    db.commit()

    current_user_msg_id = user_msg.id

    async def generate():
        """生成 SSE 事件流"""
        agent = get_agent()

        # 构建消息上下文，只传最近10条
        db_messages = db.query(Message).filter(
            Message.conversation_id == request.conversation_id
        ).order_by(Message.id.desc()).limit(10).all()
        db_messages = list(reversed(db_messages))

        langchain_messages = []
        for msg in db_messages:
            if msg.role == "user":
                if msg.id == current_user_msg_id:
                    langchain_messages.append(HumanMessage(content=enhanced_message))
                else:
                    langchain_messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                langchain_messages.append(AIMessage(content=msg.content))

        # 如果有图片，先通知前端
        if has_image:
            img_hint = "📷 图片已识别，正在生成回答...\n\n"
            yield f"data: {json.dumps({'type': 'token', 'content': img_hint}, ensure_ascii=False)}\n\n"

        # ====== 逐 token 流式输出 ======
        full_reply = ""
        sources = []

        try:
            async for event in agent.astream_events(
                    {"messages": langchain_messages},
                    version="v2",
            ):
                kind = event.get("event")

                # AI 输出的文本 token
                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    token = chunk.content
                    if token:
                        full_reply += token
                        yield f"data: {json.dumps({'type': 'token', 'content': token}, ensure_ascii=False)}\n\n"

                # 工具调用开始
                elif kind == "on_tool_start":
                    tool_name = event.get("name", "搜索")
                    yield f"data: {json.dumps({'type': 'tool_start', 'tool': tool_name}, ensure_ascii=False)}\n\n"

                # 工具调用结束 - 提取搜索来源
                elif kind == "on_tool_end":
                    try:
                        tool_output = event["data"].get("output", "")
                        if isinstance(tool_output, str):
                            import ast
                            results = ast.literal_eval(tool_output)
                        elif isinstance(tool_output, list):
                            results = tool_output
                        else:
                            results = []
                        for item in results:
                            if isinstance(item, dict):
                                url = item.get("url", "")
                                title = item.get("title", "")
                                if url and title:
                                    sources.append({"title": title, "url": url})
                    except Exception:
                        pass

                    yield f"data: {json.dumps({'type': 'tool_end'}, ensure_ascii=False)}\n\n"

        except Exception as e:
            error_msg = str(e)
            yield f"data: {json.dumps({'type': 'error', 'content': error_msg}, ensure_ascii=False)}\n\n"
            if not full_reply:
                full_reply = "抱歉，AI 服务暂时不可用，请稍后再试。"

        # 保存 AI 回复到数据库
        if full_reply:
            ai_msg = Message(
                conversation_id=request.conversation_id,
                role="assistant",
                content=full_reply,
            )
            db.add(ai_msg)
            db.commit()

        # 发送搜索来源（去重）
        if sources:
            seen = set()
            unique_sources = []
            for s in sources:
                if s["url"] not in seen:
                    seen.add(s["url"])
                    unique_sources.append(s)
            yield f"data: {json.dumps({'type': 'sources', 'sources': unique_sources}, ensure_ascii=False)}\n\n"

        # 发送完成信号
        yield f"data: {json.dumps({'type': 'done', 'conversation_id': request.conversation_id}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
