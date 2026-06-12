import os
import base64


UPLOAD_DIR = os.path.join(os.path.dirname(__file__).replace("\\", "/").split("backend")[0], "uploads")


def process_image(save_name: str) -> dict:
    """处理图片：转为 base64，用于多模态 AI 识别"""
    filepath = os.path.join(UPLOAD_DIR, save_name)
    if not os.path.exists(filepath):
        return None

    with open(filepath, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    # 判断图片格式
    ext = os.path.splitext(save_name)[1].lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    mime_type = mime_map.get(ext, "image/jpeg")

    return {
        "type": "image",
        "base64": image_data,
        "mime_type": mime_type,
    }


def process_document(save_name: str) -> dict:
    """处理文档：提取文本内容"""
    filepath = os.path.join(UPLOAD_DIR, save_name)
    if not os.path.exists(filepath):
        return None

    ext = os.path.splitext(save_name)[1].lower()
    text = ""

    try:
        if ext == ".pdf":
            import fitz
            doc = fitz.open(filepath)
            for page in doc:
                text += page.get_text()
            doc.close()

        elif ext in (".docx", ".doc"):
            from docx import Document
            doc = Document(filepath)
            for para in doc.paragraphs:
                text += para.text + "\n"

        elif ext == ".txt":
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()
    except Exception as e:
        text = f"[文件读取失败：{str(e)}]"

    return {
        "type": "document",
        "text": text[:5000],  # 限制文本长度，避免 token 过多
    }


def process_file(save_name: str, file_type: str) -> dict:
    """根据文件类型选择处理方式"""
    if file_type == "image":
        return process_image(save_name)
    elif file_type == "document":
        return process_document(save_name)
    return None
