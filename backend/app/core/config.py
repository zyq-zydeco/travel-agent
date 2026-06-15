from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # 数据库配置
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "travel_agent"

    # JWT 配置
    SECRET_KEY: str = "travel-agent-secret-key-2024"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24小时

    # 通义千问 API
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DASHSCOPE_MODEL: str = "qwen-plus"

    # Tavily 搜索 API
    TAVILY_API_KEY: str = ""

    # 天气 API（OpenWeatherMap）
    WEATHER_API_KEY: str = ""

    # 汇率 API（Open Exchange Rates，留空则使用内置固定汇率）
    OPEN_EXCHANGE_KEY: str = ""

    # 高德地图 API（Web 服务类型）
    AMAP_API_KEY: str = ""

    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    class Config:
        env_file = str(Path(__file__).resolve().parent.parent.parent.parent / "config" / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

def get_settings():
    return settings