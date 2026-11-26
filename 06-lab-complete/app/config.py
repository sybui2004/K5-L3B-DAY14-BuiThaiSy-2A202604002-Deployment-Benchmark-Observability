"""
Config — 12-Factor: mọi cấu hình đọc từ biến môi trường.
"""
import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    # default_factory: đọc env lúc tạo Settings, không phải lúc định nghĩa class
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    # Không có key mặc định: thiếu biến thì mọi request tới /ask bị từ chối
    agent_api_key: str = field(default_factory=lambda: os.getenv("AGENT_API_KEY", ""))
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    rate_limit_per_minute: int = field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "10")))
    daily_budget_usd: float = field(
        default_factory=lambda: float(os.getenv("DAILY_BUDGET_USD", "1.0")))


settings = Settings()
