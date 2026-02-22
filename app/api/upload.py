import os
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import parser
from app.api.deps import require_api_key
from app.crud import upsert_leads
from app.db import get_db

router = APIRouter(prefix="/upload", tags=["ingest"])

_ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv"}


@router.post("", status_code=status.HTTP_200_OK)
async def upload_file(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    _key: str = Depends(require_api_key),
):
    """
    Upload an Excel (.xlsx/.xls) or CSV file with leads.
    Parses and upserts into the database. Re-uploading the same file is safe (idempotent).
    """
    suffix = ""
    if file.filename and "." in file.filename:
        suffix = "." + file.filename.rsplit(".", 1)[-1].lower()

    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type {suffix!r}. Use .xlsx or .csv",
        )

    contents = await file.read()

    # parser.load() needs a real file path with the correct extension
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        os.write(tmp_fd, contents)
        os.close(tmp_fd)
        df = parser.load(tmp_path)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Parse error: {exc}") from exc
    finally:
        os.unlink(tmp_path)

    count = await upsert_leads(session, df)
    return {"status": "ok", "rows_parsed": len(df), "rows_upserted": count}
