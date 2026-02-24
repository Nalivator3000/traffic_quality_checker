"""
One-time migration: copy app's alembic revisions from alembic_version →
tqc_alembic_version so Superset can own alembic_version exclusively.
Idempotent — safe to run on every startup.
"""
import os
from sqlalchemy import create_engine, text

url = os.environ["DATABASE_URL"]
url = url.replace("postgres://", "postgresql://", 1)
url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

our_revs = ["b589e261f68f", "a1c3e9f72b44", "c7f2a1d8e345"]

engine = create_engine(url)
with engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS tqc_alembic_version (
            version_num VARCHAR(32) NOT NULL,
            CONSTRAINT tqc_alembic_version_pkc PRIMARY KEY (version_num)
        )
    """))
    for rev in our_revs:
        conn.execute(
            text("INSERT INTO tqc_alembic_version (version_num) VALUES (:r) ON CONFLICT DO NOTHING"),
            {"r": rev},
        )
        conn.execute(
            text("DELETE FROM alembic_version WHERE version_num = :r"),
            {"r": rev},
        )
engine.dispose()
print("tqc_alembic_version seeded OK")
