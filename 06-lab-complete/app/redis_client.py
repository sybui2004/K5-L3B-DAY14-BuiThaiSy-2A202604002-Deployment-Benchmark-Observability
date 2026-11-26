"""
Kết nối Redis dùng chung cho rate limiter và cost guard.
"""
import redis

from app.config import settings

# from_url chưa mở kết nối, nên app vẫn khởi động được khi Redis chưa sẵn sàng.
# Timeout ngắn để request và /ready không treo khi Redis mất mạng.
r = redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)


def redis_healthy() -> bool:
    try:
        return bool(r.ping())
    except redis.RedisError:
        return False
