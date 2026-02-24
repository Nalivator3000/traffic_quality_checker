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
import os, sys

db_url = os.environ['DATABASE_URL']
sk = os.environ['SUPERSET_SECRET_KEY']

# Normalize postgres:// -> postgresql://
if db_url.startswith('postgres://'):
    db_url = 'postgresql://' + db_url[len('postgres://'):]

masked = db_url.split('@')[-1] if '@' in db_url else db_url
print(f"DB URL host/db: {masked}")

config = f"""import os

SQLALCHEMY_DATABASE_URI = "{db_url}"
SECRET_KEY = "{sk}"

# Disable CSRF for API
WTF_CSRF_ENABLED = False

# Allow all hosts
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
