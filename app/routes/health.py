"""Health check endpoint for Docker container and orchestrator monitoring.
Verifies:
1. Flask web application responsiveness
2. PostgreSQL database connection
3. Persistent upload volume accessibility and writability
"""
import time
from flask import Blueprint, jsonify, current_app
from sqlalchemy import text
from app.extensions import db
from app.services.storage import StorageService

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health_check():
    """Evaluate full application health: Database connectivity and persistent volume writability."""
    start_time = time.time()
    checks = {}
    is_healthy = True

    # 1. Flask application is active (implicit if handling this request)
    checks["application"] = {
        "status": "up",
        "service": "Flask / Gunicorn"
    }

    # 2. Check PostgreSQL connectivity
    try:
        db.session.execute(text("SELECT 1"))
        checks["database"] = {
            "status": "connected",
            "type": "PostgreSQL",
        }
    except Exception as exc:
        is_healthy = False
        checks["database"] = {
            "status": "error",
            "error": str(exc),
        }

    # 3. Check persistent volume storage (mounted at /app/uploads)
    try:
        storage = StorageService(current_app.config["UPLOAD_FOLDER"])
        accessible, writable, msg = storage.check_health()
        if accessible and writable:
            checks["storage"] = {
                "status": "available",
                "path": str(storage.upload_folder),
                "accessible": True,
                "writable": True,
                "message": msg,
            }
        else:
            is_healthy = False
            checks["storage"] = {
                "status": "degraded",
                "path": str(storage.upload_folder),
                "accessible": accessible,
                "writable": writable,
                "error": msg,
            }
    except Exception as exc:
        is_healthy = False
        checks["storage"] = {
            "status": "error",
            "error": str(exc),
        }

    latency_ms = round((time.time() - start_time) * 1000, 2)
    status_code = 200 if is_healthy else 503

    return jsonify({
        "status": "healthy" if is_healthy else "unhealthy",
        "timestamp": time.time(),
        "latency_ms": latency_ms,
        "checks": checks,
    }), status_code
