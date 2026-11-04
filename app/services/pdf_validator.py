"""PDF Validation Service.
Performs rigorous server-side validation of uploaded files:
- Safe filename sanitization
- Extension verification
- PDF magic signature verification (%PDF-)
- Size bounds checking (non-empty and <= MAX_CONTENT_LENGTH)
- Incremental SHA-256 calculation
"""
import hashlib
import os
from dataclasses import dataclass
from typing import Optional
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


@dataclass
class ValidationResult:
    """Encapsulates the result of a PDF validation attempt."""
    is_valid: bool
    error_message: Optional[str] = None
    safe_filename: Optional[str] = None
    size_bytes: int = 0
    sha256: Optional[str] = None


class PDFValidator:
    """Service to validate uploaded PDF files."""

    PDF_MAGIC_BYTES = b"%PDF-"
    MAX_MAGIC_SEARCH_OFFSET = 1024  # PDF spec allows header within first 1024 bytes
    CHUNK_SIZE = 64 * 1024  # 64 KB chunks for memory-efficient hashing

    @classmethod
    def validate(cls, file_obj: Optional[FileStorage], max_size_bytes: int) -> ValidationResult:
        """Validate an uploaded file storage object.
        
        Args:
            file_obj: The Werkzeug FileStorage object from request.files
            max_size_bytes: Maximum allowed file size in bytes
            
        Returns:
            ValidationResult with validation status, metadata, and error details.
        """
        if file_obj is None or not file_obj.filename:
            return ValidationResult(
                is_valid=False,
                error_message="No file was selected for upload."
            )

        raw_filename = file_obj.filename.strip()
        if not raw_filename:
            return ValidationResult(
                is_valid=False,
                error_message="Uploaded file name cannot be empty."
            )

        # Sanitize filename
        safe_name = secure_filename(raw_filename)
        if not safe_name:
            # Fallback if filename consisted entirely of unsafe characters
            safe_name = "document.pdf"

        # Check extension
        _, ext = os.path.splitext(safe_name)
        if ext.lower() != ".pdf":
            return ValidationResult(
                is_valid=False,
                error_message=f"Invalid file extension '{ext}'. Only .pdf files are permitted."
            )

        # Inspect stream signature and size
        stream = file_obj.stream
        stream.seek(0, os.SEEK_END)
        total_size = stream.tell()
        stream.seek(0)

        # Validate non-empty
        if total_size <= 0:
            return ValidationResult(
                is_valid=False,
                error_message="The selected PDF file is empty (0 bytes)."
            )

        # Validate maximum size limit
        if total_size > max_size_bytes:
            max_mb = max_size_bytes / (1024 * 1024)
            actual_mb = total_size / (1024 * 1024)
            return ValidationResult(
                is_valid=False,
                error_message=f"File exceeds maximum size limit of {max_mb:.1f} MB (uploaded: {actual_mb:.2f} MB)."
            )

        # Inspect magic header bytes (%PDF-)
        header_sample = stream.read(cls.MAX_MAGIC_SEARCH_OFFSET)
        if cls.PDF_MAGIC_BYTES not in header_sample:
            stream.seek(0)
            return ValidationResult(
                is_valid=False,
                error_message="File signature verification failed. The file is not a valid PDF document."
            )

        # Calculate SHA-256 hash incrementally across entire file
        stream.seek(0)
        hasher = hashlib.sha256()
        bytes_read = 0

        while True:
            chunk = stream.read(cls.CHUNK_SIZE)
            if not chunk:
                break
            hasher.update(chunk)
            bytes_read += len(chunk)

        # Reset stream pointer back to start so subsequent operations can read it
        stream.seek(0)

        calculated_sha256 = hasher.hexdigest()

        return ValidationResult(
            is_valid=True,
            error_message=None,
            safe_filename=safe_name,
            size_bytes=bytes_read,
            sha256=calculated_sha256
        )
