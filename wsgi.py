"""WSGI Entrypoint for Document Vault.
Used by Gunicorn in production containers and direct execution for testing.
"""
import os
from app import create_app, db

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        # Ensure database tables exist if running locally outside migrations
        db.create_all()
    port = int(os.getenv("APP_PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
