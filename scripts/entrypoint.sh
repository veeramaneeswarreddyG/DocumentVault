#!/bin/sh
set -e

echo "=== Document Vault Container Startup ==="

# 1. Wait for PostgreSQL readiness
python scripts/wait_for_db.py

# 2. Run Database Migrations or ensure schema is initialized
echo "[Startup] Applying database migrations..."
if [ -d "migrations/versions" ] && [ "$(ls -A migrations/versions)" ]; then
    flask db upgrade
else
    echo "[Startup] Initializing database tables..."
    python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
fi

# 3. Verify upload directory permissions
echo "[Startup] Verifying upload directory at ${UPLOAD_FOLDER:-/app/uploads}..."
mkdir -p "${UPLOAD_FOLDER:-/app/uploads}"

# 4. Launch Production Gunicorn Server
echo "[Startup] Launching Gunicorn WSGI server on 0.0.0.0:5000..."
exec gunicorn \
    --bind 0.0.0.0:5000 \
    --workers 3 \
    --worker-class sync \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    wsgi:app
