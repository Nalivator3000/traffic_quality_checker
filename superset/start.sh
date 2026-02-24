#!/bin/bash
set -e

echo "=== Superset start: $(date) ==="
echo "PORT=${PORT:-NOT SET}"
echo "DATABASE_URL set: $([ -n "$DATABASE_URL" ] && echo YES || echo NO)"
echo "SUPERSET_SECRET_KEY set: $([ -n "$SUPERSET_SECRET_KEY" ] && echo YES || echo NO)"

if [ -z "$DATABASE_URL" ] || [ -z "$SUPERSET_SECRET_KEY" ]; then
    echo "FATAL: DATABASE_URL and SUPERSET_SECRET_KEY are required"
    exit 1
fi

# Write config — reads env vars at Python runtime, no string-escaping issues
mkdir -p /app/pythonpath
cat > /app/pythonpath/superset_config.py << 'PYCFG'
import os

_db = os.environ['DATABASE_URL']
if _db.startswith('postgres://'):
    _db = 'postgresql://' + _db[len('postgres://'):]

SQLALCHEMY_DATABASE_URI = _db
SECRET_KEY = os.environ['SUPERSET_SECRET_KEY']
WTF_CSRF_ENABLED = False
ENABLE_CORS = True
HTTP_HEADERS = {}

_CACHE = {'CACHE_TYPE': 'SimpleCache', 'CACHE_DEFAULT_TIMEOUT': 300}
CACHE_CONFIG = _CACHE
DATA_CACHE_CONFIG = _CACHE
FILTER_STATE_CACHE_CONFIG = _CACHE
EXPLORE_FORM_DATA_CACHE_CONFIG = _CACHE
THUMBNAIL_CACHE_CONFIG = _CACHE

RATELIMIT_STORAGE_URI = "memory://"
SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True, 'pool_recycle': 300}
TALISMAN_ENABLED = False
PYCFG

echo "superset_config.py written"

echo "=== /app/gunicorn.conf.py ==="
cat /app/gunicorn.conf.py 2>/dev/null || echo "(not found)"

echo "=== superset db upgrade ==="
superset db upgrade

echo "=== Creating admin user ==="
superset fab create-admin \
    --username admin \
    --firstname Admin \
    --lastname User \
    --email admin@admin.com \
    --password "${SUPERSET_ADMIN_PASSWORD:-admin}" 2>&1 || true

echo "=== superset init ==="
superset init

echo "=== Starting gunicorn on 0.0.0.0:${PORT:-8088} ==="
exec gunicorn \
    --bind "[::]:${PORT:-8088}" \
    --forwarded-allow-ips "*" \
    --workers 1 \
    --threads 4 \
    --worker-class gthread \
    --timeout 120 \
    --log-level debug \
    --access-logfile - \
    --error-logfile - \
    "superset.app:create_app()"
