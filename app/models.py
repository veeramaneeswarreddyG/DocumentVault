"""Database models for Document Vault.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy.sql import func
from app.extensions import db


class Document(db.Model):
    """Document metadata model stored in PostgreSQL.
    Stores metadata for documents whose actual PDF binary is preserved in the Docker Volume.
    """
    __tablename__ = "documents"

    # UUID primary key represented as 36-character string for universal compatibility
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), unique=True, nullable=False, index=True)
    size_bytes = db.Column(db.BigInteger, nullable=False)
    sha256 = db.Column(db.String(64), nullable=False, index=True)
    uploaded_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Document {self.id} - {self.original_filename}>"

    @property
    def human_readable_size(self) -> str:
        """Format size_bytes into a human-readable string (B, KB, MB, GB)."""
        bytes_val = float(self.size_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_val < 1024.0 or unit == "TB":
                return f"{bytes_val:.2f} {unit}" if unit != "B" else f"{int(bytes_val)} B"
            bytes_val /= 1024.0
        return f"{bytes_val:.2f} TB"

    def to_dict(self, is_available: bool = True) -> dict:
        """Convert model instance to JSON-serializable dictionary."""
        return {
            "id": self.id,
            "original_filename": self.original_filename,
            "stored_filename": self.stored_filename,
            "size_bytes": self.size_bytes,
            "human_readable_size": self.human_readable_size,
            "sha256": self.sha256,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
            "is_available": is_available,
        }
