"""
流式聊天接口 - 集成 StateGraph 工作流、动态上下文、长期记忆、可观测性
"""

import json
import time
import asyncio
import logging
from typing import Optional

from loguru import logger
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
from backend.app.services.memory import (
    get_or_create_profile,
    update_profile_from_conversation,
    analyze_and_save_experience,
    retrieve_relevant_experiences,
)
from backend.app.services.context import classify_intent, build_system_prompt, compress_long_context

router = APIRouter(prefix="/api/chat", tags=["流式聊天"])


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    流式聊天接口 — 使用 SSE 实时推送 AI 回复
    
    集成能力：
    - 意图分类 → 动态 Prompt 组装
    - 用户画像注入 → 个性化回答
    - 历史经验注入 → 自我改进
    - 长对话上下文压缩
    - 对话后异步学习（画像更新 + 经验记录）
    - 全链路可观测性日志
    """

    # ========== 1. 对话准备 ==========
    
    # 如果没有对话ID，创建新对话
    if not request.conversation_id:
        conversation = Conversation(user_id=current_user.id, title="新聊天")
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        request.conversation_id = conversation.id
    
    # 处理附件
    enhanced_message = request.message
    has_image = False
    tools_used_list = []  # 记录使用的工具名称
    
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
    request_start_time = time.time()
    
    # ========== 2. 构建增强上下文 ==========
    
    # 获取用户画像
    profile = get_or_create_profile(db, current_user.id)
    
    # 意图分类
    intent = classify_intent(request.message)
    logger.info(f"用户 {current_user.username} | 意图: {intent} | 消息: {request.message[:50]}...")
    
    # 检索相关历史经验
    experiences = retrieve_relevant_experiences(db, task_type=intent, limit=3)
    
    # 组装动态 System Prompt
    dynamic_prompt = build_system_prompt(profile, experiences, intent)
    
    # 获取历史消息并压缩
    db_messages = db.query(Message).filter(
        Message.conversation_id == request.conversation_id
    ).order_by(Message.id.asc()).all()
    
    compressed_messages, was_compressed = compress_long_context(db_messages, max_turns=10)
    if was_compressed:
        logger.info(f"上下文已压缩: {len(db_messages)} 条 → {len(compressed_messages)} 条")
    
    # 构建 LangChain messages（仅包含真实对话历史，dynamic_prompt 已通过 agent 注入为 System Prompt）
    langchain_messages = []
    
    for msg in compressed_messages:
        if msg.role == "user":
            if msg.id == current_user_msg_id:
                langchain_messages.append(HumanMessage(content=enhanced_message))
            else:
                langchain_messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            langchain_messages.append(AIMessage(content=msg.content))
        # system 类型的摘要消息也加入
        elif msg.role == "system":
            langchain_messages.append(HumanMessage(content=f"[摘要] {msg.content}"))
    
    # ========== 3. SSE 生成函数 ==========
    
    async def generate():
        """生成 SSE 事件流"""
        nonlocal tools_used_list
        
        agent = get_agent(system_prompt=dynamic_prompt)  # 注入动态 System Prompt（含日期+画像+经验）
        
        # 图片提示
        if has_image:
            img_hint = "📷 图片已识别，正在生成回答...\n\n"
            yield f"data: {json.dumps({'type': 'token', 'content': img_hint}, ensure_ascii=False)}\n\n"
        
        full_reply = ""
        sources = []
        first_token_time = None
        ttft = None
        
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
                        if first_token_time is None:
                            first_token_time = time.time()
                            ttft = first_token_time - request_start_time
                            logger.debug(f"TTFT: {ttft:.2f}s")
                        full_reply += token
                        yield f"data: {json.dumps({'type': 'token', 'content': token}, ensure_ascii=False)}\n\n"
                
                # 工具调用开始
                elif kind == "on_tool_start":
                    tool_name = event.get("name", "搜索")
                    tools_used_list.append(tool_name)
                    logger.info(f"Tool Call 开始: {tool_name}")
                    yield f"data: {json.dumps({'type': 'tool_start', 'tool': tool_name}, ensure_ascii=False)}\n\n"
                
                # 工具调用结束
                elif kind == "on_tool_end":
                    tool_end_time = time.time()
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
                    
                    logger.info(f"Tool Call 结束, 已收集 {len(sources)} 个来源")
                    yield f"data: {json.dumps({'type': 'tool_end'}, ensure_ascii=False)}\n\n"
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Agent 执行异常: {error_msg}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': error_msg}, ensure_ascii=False)}\n\n"
            if not full_reply:
                full_reply = "抱歉，AI 服务暂时不可用，请稍后再试。"
        
        total_time = time.time() - request_start_time
        logger.info(
            f"请求完成 | 用户={current_user.username} | "
            f"意图={intent} | 工具={tools_used_list} | "
            f"回复长度={len(full_reply)} | TTFT={ttft:.2f}s | 总耗时={total_time:.2f}s"
        )
        
        # ========== 4. 保存 AI 回复 ==========
        
        if full_reply:
            ai_msg = Message(
                conversation_id=request.conversation_id,
                role="assistant",
                content=full_reply,
            )
            db.add(ai_msg)
            db.commit()
        
        # ========== 5. 发送来源和完成信号 ==========
        
        # 搜索来源去重
        if sources:
            seen = set()
            unique_sources = []
            for s in sources:
                if s["url"] not in seen:
                    seen.add(s["url"])
                    unique_sources.append(s)
            yield f"data: {json.dumps({'type': 'sources', 'sources': unique_sources}, ensure_ascii=False)}\n\n"
        
        # 完成信号
        yield f"data: {json.dumps({'type': 'done', 'conversation_id': request.conversation_id}, ensure_ascii=False)}\n\n"
        
        # ========== 6. 异步后处理（不阻塞 SSE）==========
        
        if full_reply:
            # 异步更新用户画像
            try:
                await update_profile_from_conversation(db, current_user.id, request.conversation_id)
            except Exception as e:
                logger.warning(f"异步更新用户画像失败: {e}")
            
            # 异步分析并保存经验
            try:
                await analyze_and_save_experience(
                    db=db,
                    user_id=current_user.id,
                    task_type=intent,
                    query=request.message,
                    reply=full_reply,
                    tools_used=tools_used_list,
                )
            except Exception as e:
                logger.warning(f"异步保存经验日志失败: {e}")
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
