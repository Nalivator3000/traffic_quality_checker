"""
Lead ingestion via JSON API.

POST /leads        — batch upsert (simulates CRM push)
PATCH /leads/{id}  — update status and/or comment for one lead
"""

import datetime
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_api_key
from app.crud import delete_lead, patch_lead, upsert_leads_json
from app.db import get_db

logger = logging.getLogger("leads")
router = APIRouter(prefix="/leads", tags=["leads"])

_DATE_FMTS = ("%d.%m.%Y %H:%M", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y", "%Y-%m-%d")


class LeadIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id_custom: int
    status: int
    date: datetime.date
    webmaster: str
    sum: float = 0.0
    comment: str | None = None

    @field_validator("date", mode="before")
    @classmethod
    def parse_date(cls, v: Any) -> datetime.date:
        if isinstance(v, datetime.date):
            return v
        s = str(v).strip()
        for fmt in _DATE_FMTS:
            try:
                return datetime.datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Unrecognised date format: {v!r}")

    @field_validator("sum", mode="before")
    @classmethod
    def parse_sum(cls, v: Any) -> float:
        if isinstance(v, (int, float)):
            return float(v)
        return float(str(v).replace(",", "."))


class LeadPatch(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: int | None = Field(default=None, description="New CRM status code")
    comment: str | None = Field(default=None, description="Free-text comment")


@router.post("", status_code=status.HTTP_200_OK)
async def ingest_leads(
    request: Request,
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
      {"id_custom": 124, "status": 3, "date": "09.03.2025 14:32", "webmaster": "abc123", "sum": "1500,00"}
    ]
    ```
    """
    client = request.client.host if request.client else "unknown"
    logger.info("POST /leads from %s — %d leads received", client, len(leads))

    if not leads:
        logger.info("Empty payload, nothing to upsert")
        return {"status": "ok", "rows_upserted": 0}

    records = [lead.model_dump() for lead in leads]

    # Log first lead as sample
    logger.debug("Sample lead: %s", records[0])

    try:
        count = await upsert_leads_json(session, records)
    except Exception as exc:
        logger.exception("DB upsert failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"DB error: {exc}") from exc

    logger.info("Upserted %d rows", count)
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
    logger.info("PATCH /leads/%d — status=%s comment=%s", id_custom, body.status, body.comment)

    if body.status is None and body.comment is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one of: status, comment",
        )
    found = await patch_lead(session, id_custom, status=body.status, comment=body.comment)
    if not found:
        logger.warning("Lead %d not found", id_custom)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead {id_custom} not found",
        )
    logger.info("Lead %d updated", id_custom)
    return {"status": "ok", "id_custom": id_custom}


@router.delete("/{id_custom}", status_code=status.HTTP_200_OK)
async def remove_lead(
    id_custom: int,
    session: AsyncSession = Depends(get_db),
    _key: str = Depends(require_api_key),
) -> dict[str, Any]:
    """Delete a single lead by id_custom."""
    logger.info("DELETE /leads/%d", id_custom)
    found = await delete_lead(session, id_custom)
    if not found:
        logger.warning("Lead %d not found", id_custom)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead {id_custom} not found",
        )
    logger.info("Lead %d deleted", id_custom)
    return {"status": "deleted", "id_custom": id_custom}
