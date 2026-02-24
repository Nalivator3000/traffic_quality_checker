web: python scripts/migrate_version_table.py && alembic upgrade head && uvicorn app.api.main:app --host 0.0.0.0 --port $PORT
