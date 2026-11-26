"""
Cost guard: cộng dồn chi phí LLM theo ngày (UTC) trong Redis.

Giới hạn: kiểm tra trước, ghi chi phí sau, nên các request đang chạy đồng thời
có thể làm tổng vượt ngân sách một chút.
"""
from datetime import datetime, timezone

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006

KEY_TTL_SECONDS = 2 * 24 * 3600


def _today_key() -> str:
    # Key có ngày: sang ngày mới dùng key mới, ngân sách tự reset
    return "cost:" + datetime.now(timezone.utc).strftime("%Y-%m-%d")


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → 402."""
    spent = float(r.get(_today_key()) or 0)
    if spent >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail="Daily budget exceeded")


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí vào tổng, trả về chi phí của request."""
    cost = (input_tokens * PRICE_INPUT_PER_1K + output_tokens * PRICE_OUTPUT_PER_1K) / 1000
    key = _today_key()
    pipe = r.pipeline()
    pipe.incrbyfloat(key, cost)
    pipe.expire(key, KEY_TTL_SECONDS)
    pipe.execute()
    return cost
