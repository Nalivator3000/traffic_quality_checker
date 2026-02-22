import os

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

_API_KEY_HEADER = APIKeyHeader(name="Authorization", auto_error=False)
_EXPECTED_KEY = os.environ.get("API_KEY", "")


async def require_api_key(key: str | None = Security(_API_KEY_HEADER)) -> str:
    if not key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")
    actual = key.removeprefix("Bearer ").strip()
    if not _EXPECTED_KEY or actual != _EXPECTED_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")
    return actual
