#!/bin/bash
set -e

echo "========================================="
echo "=== Superset Startup Script"
echo "=== $(date)"
echo "========================================="

echo ""
echo "--- Environment Check ---"
echo "PORT:                  ${PORT:-NOT SET}"
echo "DATABASE_URL set:      $([ -n "$DATABASE_URL" ] && echo YES || echo NO)"
echo "SUPERSET_SECRET_KEY:   $([ -n "$SUPERSET_SECRET_KEY" ] && echo YES || echo NO)"
echo "SUPERSET_ADMIN_PASSWORD: $([ -n "$SUPERSET_ADMIN_PASSWORD" ] && echo YES || echo NO)"

if [ -z "$DATABASE_URL" ]; then
    echo "FATAL: DATABASE_URL is not set. Exiting."
    exit 1
fi

if [ -z "$SUPERSET_SECRET_KEY" ]; then
    echo "FATAL: SUPERSET_SECRET_KEY is not set. Exiting."
    exit 1
fi

echo ""
echo "--- Creating superset_config.py ---"
mkdir -p /app/pythonpath

/app/.venv/bin/python3 << 'PYEOF'
import os, psycopg2, urllib.parse

db_url = os.environ['DATABASE_URL']
sk = os.environ['SUPERSET_SECRET_KEY']

# Normalize postgres:// -> postgresql://
if db_url.startswith('postgres://'):
    db_url = 'postgresql://' + db_url[len('postgres://'):]

p = urllib.parse.urlparse(db_url)
host = p.hostname
port = p.port or 5432
user = p.username
password = p.password
main_db = p.path.lstrip('/')

print(f"DB host: {host}:{port}/{main_db}")

# Create a dedicated 'superset_db' database so Superset's alembic_version
# is fully isolated from our FastAPI app's database. No shared tables at all.
print("Ensuring 'superset_db' database exists...")
superset_db_url = urllib.parse.urlunparse(p._replace(path='/superset_db', query=''))
try:
    conn = psycopg2.connect(host=host, port=port, user=user, password=password, dbname=main_db)
    conn.autocommit = True  # CREATE DATABASE requires autocommit
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = 'superset_db'")
    if not cur.fetchone():
        cur.execute("CREATE DATABASE superset_db")
        print("Created 'superset_db'.")
    else:
        print("'superset_db' already exists.")
    cur.close()
    conn.close()
    print(f"Superset will use: {host}:{port}/superset_db")
except Exception as e:
    print(f"WARNING: Could not create superset_db ({e}), falling back to main db")
    superset_db_url = urllib.parse.urlunparse(p._replace(query=''))

config = f"""import os

SQLALCHEMY_DATABASE_URI = "{superset_db_url}"
SECRET_KEY = "{sk}"

WTF_CSRF_ENABLED = False
ENABLE_CORS = True
HTTP_HEADERS = {{}}
"""

with open('/app/pythonpath/superset_config.py', 'w') as f:
    f.write(config)
print("superset_config.py written OK")
PYEOF

echo ""
echo "--- superset db upgrade ---"
superset db upgrade

echo ""
echo "--- Creating admin user ---"
superset fab create-admin \
    --username admin \
    --firstname Admin \
    --lastname User \
    --email admin@admin.com \
    --password "${SUPERSET_ADMIN_PASSWORD:-admin123}" 2>&1 || echo "Admin user already exists, skipping."

echo ""
echo "--- superset init ---"
superset init

echo ""
echo "--- Starting gunicorn on 0.0.0.0:${PORT} ---"
exec gunicorn \
    --bind "0.0.0.0:${PORT:-8088}" \
    --workers 2 \
    --timeout 120 \
    --log-level info \
    --access-logfile - \
    --error-logfile - \
    "superset.app:create_app()"
