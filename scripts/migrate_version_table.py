"""
Ensure our app's alembic revisions live in tqc_alembic_version (not the
shared alembic_version table that Superset uses). Idempotent on every startup.
"""
import os
from sqlalchemy import create_engine, text

url = os.environ["DATABASE_URL"]
url = url.replace("postgres://", "postgresql://", 1)
url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

HEAD = "c7f2a1d8e345"  # only the current head goes in the version table
all_revs = ["b589e261f68f", "a1c3e9f72b44", "c7f2a1d8e345"]

engine = create_engine(url)
with engine.begin() as conn:
    # Create our version table if missing
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS tqc_alembic_version (
            version_num VARCHAR(32) NOT NULL,
            CONSTRAINT tqc_alembic_version_pkc PRIMARY KEY (version_num)
        )
    """))

    # Remove stale intermediate revisions left by a previous bad seed
    for rev in all_revs:
        if rev != HEAD:
            conn.execute(text("DELETE FROM tqc_alembic_version WHERE version_num = :r"), {"r": rev})

    # Ensure only HEAD is present
    conn.execute(
        text("INSERT INTO tqc_alembic_version (version_num) VALUES (:r) ON CONFLICT DO NOTHING"),
        {"r": HEAD},
    )

    # Remove our revisions from alembic_version only if that table exists
    av_exists = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM pg_tables
            WHERE schemaname = 'public' AND tablename = 'alembic_version'
        )
    """)).scalar()

    if av_exists:
        for rev in all_revs:
            conn.execute(
                text("DELETE FROM alembic_version WHERE version_num = :r"),
                {"r": rev},
            )

engine.dispose()
print("tqc_alembic_version seeded OK")
