"""
Production AI Agent — Part 6 Final Project.

Kiểm tra: python check_production_ready.py
"""
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import redis
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import redis_healthy
from utils.mock_llm import ask as llm_ask


# ── Structured logging ────────────────────────────────────
class JsonFormatter(logging.Formatter):
    """Cả dòng log được tạo bằng json.dumps nên ký tự đặc biệt luôn được escape."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lvl": record.levelname,
            "event": record.getMessage(),
        }
        entry.update(getattr(record, "fields", {}))
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(JsonFormatter())
logger = logging.getLogger("agent")
logger.addHandler(_handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def log(event: str, level: int = logging.INFO, **fields) -> None:
    logger.log(level, event, extra={"fields": fields})


# ── Lifecycle / graceful shutdown ─────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    log("startup", environment=settings.environment, port=settings.port)
    if not settings.agent_api_key:
        log("agent_api_key_missing", level=logging.WARNING)
    yield
    # uvicorn tự xử lý SIGTERM: ngừng nhận kết nối mới, chờ request đang chạy,
    # rồi mới chạy phần này. Không đăng ký signal handler riêng để khỏi ghi đè.
    log("shutdown")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        # Chi tiết lỗi chỉ vào log, client không thấy stack trace
        logger.exception("unhandled_error", extra={"fields": {"path": request.url.path}})
        response = JSONResponse(status_code=500, content={"detail": "Internal server error"})
    log("request", method=request.method, path=request.url.path, status=response.status_code,
        ms=round((time.perf_counter() - started) * 1000, 1))
    return response


@app.exception_handler(redis.RedisError)
async def redis_unavailable(request: Request, exc: redis.RedisError):
    # Không có Redis thì không kiểm soát được rate limit và chi phí → từ chối request
    log("redis_error", level=logging.ERROR, error=type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "Service temporarily unavailable"})


# ── Endpoints ─────────────────────────────────────────────
class AskRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = Field(None, max_length=100)


@app.get("/health")
def health():
    """Liveness: không phụ thuộc Redis, để Redis lỗi không làm agent bị restart."""
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Readiness: chỉ nhận traffic khi kết nối được Redis."""
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis unavailable")
    return {"status": "ready"}


def _estimate_tokens(text: str) -> int:
    # Mock LLM không trả số token: ước lượng khoảng 4 ký tự mỗi token
    return max(1, len(text) // 4)


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)
    check_budget()
    answer = llm_ask(body.question)
    cost = record_cost(_estimate_tokens(body.question), _estimate_tokens(answer))
    return {"question": body.question, "answer": answer, "cost_usd": round(cost, 8)}
