"""
API Key authentication.

Client gửi header X-API-Key; thiếu hoặc sai → 401.
"""
import hmac

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import settings

# auto_error=False để tự trả 401 cho cả trường hợp thiếu header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Dependency cho FastAPI. Trả về key đã xác thực."""
    expected = settings.agent_api_key
    # compare_digest: thời gian so sánh không phụ thuộc vị trí ký tự sai
    if not expected or not api_key or not hmac.compare_digest(api_key.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key
