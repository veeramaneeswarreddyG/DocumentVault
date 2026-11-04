"""Routes blueprint module for Document Vault.
"""
from app.routes.main import main_bp
from app.routes.documents import documents_bp
from app.routes.health import health_bp

__all__ = ["main_bp", "documents_bp", "health_bp"]
