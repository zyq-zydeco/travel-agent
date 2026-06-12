"""测试 MySQL 数据库连接"""
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv(os.path.join(os.path.dirname(__file__), "config", ".env"))

DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "travel_agent")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("✅ 数据库连接成功！")
        print(f"✅ 数据库名称: {DB_NAME}")
        print(f"✅ 连接地址: {DB_HOST}:{DB_PORT}")
except Exception as e:
    print(f"❌ 数据库连接失败: {e}")
finally:
    engine.dispose()
