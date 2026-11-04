"""PostgreSQL readiness probe.
Polls PostgreSQL until it is ready to accept connections before running migrations or starting Gunicorn.
"""
import os
import sys
import time
from sqlalchemy import create_engine, text

def wait_for_database():
    user = os.getenv("POSTGRES_USER", "vault_user")
    password = os.getenv("POSTGRES_PASSWORD", "vault_secure_password_9872")
    host = os.getenv("POSTGRES_HOST", "db")
    port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "document_vault")

    db_url = os.getenv(
        "DATABASE_URL",
        f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
    )

    print(f"[Wait-For-DB] Checking database connectivity at {host}:{port}/{db_name}...")
    max_retries = 30
    retry_delay = 2

    for attempt in range(1, max_retries + 1):
        try:
            engine = create_engine(db_url, connect_args={"connect_timeout": 3})
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("[Wait-For-DB] Database is healthy and ready to accept connections.")
            sys.exit(0)
        except Exception as exc:
            print(f"[Wait-For-DB] Attempt {attempt}/{max_retries} failed: {exc}. Retrying in {retry_delay}s...")
            time.sleep(retry_delay)

    print("[Wait-For-DB] ERROR: Database did not become available in time. Exiting.", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    wait_for_database()
