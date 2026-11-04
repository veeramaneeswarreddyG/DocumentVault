"""Application configuration module.
Loads settings from environment variables with safe defaults and specific environments.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root if present
basedir = Path(__file__).resolve().parent.parent
load_dotenv(basedir / ".env")


class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-key-change-in-production")
    
    # Database Settings
    POSTGRES_USER = os.getenv("POSTGRES_USER", "vault_user")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "vault_secure_password_9872")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB = os.getenv("POSTGRES_DB", "document_vault")
    
    # Build default PostgreSQL URI
    DEFAULT_DB_URI = (
        f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", DEFAULT_DB_URI)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
    
    # Upload Settings
    # Inside Docker container, mapped to /app/uploads
    # In local development outside Docker, falls back to ./uploads
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(basedir / "uploads"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))  # 16 MB default
    
    # Security
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    # In local development outside Docker, default to SQLite database for instant local operation
    sqlite_db = (basedir / "document_vault.db").as_posix()
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{sqlite_db}")
    SQLALCHEMY_ENGINE_OPTIONS = {}


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False


class TestingConfig(Config):
    """Testing configuration with SQLite in-memory or temporary disk."""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    UPLOAD_FOLDER = str(basedir / "tests" / "test_uploads")


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": ProductionConfig,
}
