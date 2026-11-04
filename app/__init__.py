"""Document Vault Application Factory.
"""
import os
import logging
from flask import Flask, render_template, request, jsonify
from app.config import config_by_name
from app.extensions import db, migrate, csrf
from app.routes.main import main_bp
from app.routes.documents import documents_bp
from app.routes.health import health_bp

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
)


def create_app(config_name: str = None) -> Flask:
    """Create and configure an instance of the Flask application."""
    if config_name is None:
        env = os.getenv("FLASK_ENV", "production").lower()
        config_name = "development" if env in ["dev", "development"] else "production"

    app = Flask(__name__)
    config_obj = config_by_name.get(config_name, config_by_name["default"])
    app.config.from_object(config_obj)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Exempt health check route from CSRF
    csrf.exempt(health_bp)

    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(health_bp)

    # Ensure upload directory exists
    upload_path = app.config.get("UPLOAD_FOLDER")
    if upload_path:
        os.makedirs(upload_path, exist_ok=True)

    # Register error handlers
    register_error_handlers(app)

    # Add security headers
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    return app


def register_error_handlers(app: Flask):
    """Register custom error handlers for standard HTTP error codes."""

    def is_json():
        return (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or request.is_json
            or "application/json" in request.headers.get("Accept", "")
        )

    @app.errorhandler(400)
    def bad_request(error):
        msg = getattr(error, "description", "Bad Request")
        if is_json():
            return jsonify({"success": False, "error": msg}), 400
        return render_template("errors/400.html", error=msg), 400

    @app.errorhandler(404)
    def not_found(error):
        msg = getattr(error, "description", "Resource Not Found")
        if is_json():
            return jsonify({"success": False, "error": msg}), 404
        return render_template("errors/404.html", error=msg), 404

    @app.errorhandler(413)
    def request_entity_too_large(error):
        max_mb = app.config["MAX_CONTENT_LENGTH"] / (1024 * 1024)
        msg = f"The uploaded file exceeds the maximum allowed payload size of {max_mb:.0f} MB."
        if is_json():
            return jsonify({"success": False, "error": msg}), 413
        return render_template("errors/413.html", error=msg), 413

    @app.errorhandler(500)
    def internal_error(error):
        msg = "An unexpected internal server error occurred."
        if is_json():
            return jsonify({"success": False, "error": msg}), 500
        return render_template("errors/500.html", error=msg), 500
