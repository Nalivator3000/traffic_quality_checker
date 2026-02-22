"""
Lead ingestion via JSON API.

POST /leads        — batch upsert (simulates CRM push)
PATCH /leads/{id}  — update status and/or comment for one lead
"""

import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_api_key
from app.crud import patch_lead, upsert_leads_json
from app.db import get_db

router = APIRouter(prefix="/leads", tags=["leads"])


class LeadIn(BaseModel):
    id_custom: int
    status: int
    date: datetime.date
    webmaster: str
    sum: float = 0.0
    comment: str | None = None


class LeadPatch(BaseModel):
    status: int | None = Field(default=None, description="New CRM status code")
    comment: str | None = Field(default=None, description="Free-text comment")


@router.post("", status_code=status.HTTP_200_OK)
async def ingest_leads(
    leads: list[LeadIn],
    session: AsyncSession = Depends(get_db),
    _key: str = Depends(require_api_key),
) -> dict[str, Any]:
    """
    Batch upsert leads from JSON.
    Idempotent: re-sending the same id_custom updates the row.

    Example body:
    ```json
    [
      {"id_custom": 123, "status": 2, "date": "2025-03-10", "webmaster": "abc123", "sum": 500.0},
      {"id_custom": 124, "status": 3, "date": "2025-03-10", "webmaster": "abc123", "sum": 450.0, "comment": "доставлен"}
    ]
    ```
    """
    if not leads:
        return {"status": "ok", "rows_upserted": 0}
    records = [lead.model_dump() for lead in leads]
    count = await upsert_leads_json(session, records)
    return {"status": "ok", "rows_upserted": count}


@router.patch("/{id_custom}", status_code=status.HTTP_200_OK)
async def update_lead(
    id_custom: int,
    body: LeadPatch,
    session: AsyncSession = Depends(get_db),
    _key: str = Depends(require_api_key),
) -> dict[str, Any]:
    """
    Update status and/or comment for a single lead.

    Example body:
    ```json
    {"status": 3, "comment": "выкуплен на почте"}
    ```
    """
    if body.status is None and body.comment is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one of: status, comment",
        )
    found = await patch_lead(session, id_custom, status=body.status, comment=body.comment)
    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead {id_custom} not found",
        )
    return {"status": "ok", "id_custom": id_custom}
