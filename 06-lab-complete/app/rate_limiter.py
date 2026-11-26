"""
Rate limiting: sliding window 60 giây bằng Redis sorted set.

Mỗi API key có một sorted set, mỗi request là một phần tử với score = thời điểm gọi.
State nằm trong Redis nên mọi worker / instance dùng chung và còn sau khi restart.
"""
import hashlib
import time
import uuid

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

WINDOW_SECONDS = 60


def check_rate_limit(key: str) -> None:
    # Không lưu API key gốc vào Redis, chỉ lưu bản băm
    bucket = "ratelimit:" + hashlib.sha256(key.encode()).hexdigest()[:16]
    now = time.time()
    member = uuid.uuid4().hex

    # pipeline mặc định chạy trong MULTI/EXEC: 4 lệnh chạy liền nhau,
    # nên 2 worker không thể cùng đếm một giá trị cũ rồi cùng cho qua
    pipe = r.pipeline()
    pipe.zremrangebyscore(bucket, 0, now - WINDOW_SECONDS)  # xoá request ngoài cửa sổ
    pipe.zadd(bucket, {member: now})
    pipe.zcard(bucket)
    pipe.expire(bucket, WINDOW_SECONDS)
    count = pipe.execute()[2]

    if count > settings.rate_limit_per_minute:
        r.zrem(bucket, member)  # request bị từ chối không tính vào giới hạn
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(WINDOW_SECONDS)},
        )
