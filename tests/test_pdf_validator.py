"""Tests for PDF Validator Service.
Verifies PDF header inspection, size limits, SHA-256 calculation, and rejection of fake/empty files.
"""
import hashlib
from app.services.pdf_validator import PDFValidator


def test_validate_valid_pdf(make_file_storage, valid_pdf_bytes):
    """Test that a valid PDF passes validation with correct SHA-256 and size."""
    file_storage = make_file_storage(valid_pdf_bytes, "whitepaper.pdf")
    max_size = 10 * 1024 * 1024

    result = PDFValidator.validate(file_storage, max_size)

    assert result.is_valid is True
    assert result.error_message is None
    assert result.safe_filename == "whitepaper.pdf"
    assert result.size_bytes == len(valid_pdf_bytes)
    assert result.sha256 == hashlib.sha256(valid_pdf_bytes).hexdigest()


def test_validate_rejects_none_file():
    """Test rejection when no file is supplied."""
    result = PDFValidator.validate(None, 1024 * 1024)
    assert result.is_valid is False
    assert "No file was selected" in result.error_message


def test_validate_rejects_empty_filename(make_file_storage, valid_pdf_bytes):
    """Test rejection when filename is empty or spaces."""
    file_storage = make_file_storage(valid_pdf_bytes, "   ")
    result = PDFValidator.validate(file_storage, 1024 * 1024)
    assert result.is_valid is False
    assert "cannot be empty" in result.error_message


def test_validate_rejects_non_pdf_extension(make_file_storage):
    """Test rejection of non-PDF file extensions."""
    file_storage = make_file_storage(b"not a pdf", "script.py")
    result = PDFValidator.validate(file_storage, 1024 * 1024)
    assert result.is_valid is False
    assert "Only .pdf files are permitted" in result.error_message


def test_validate_rejects_zero_byte_file(make_file_storage):
    """Test rejection of empty 0-byte PDF files."""
    file_storage = make_file_storage(b"", "empty.pdf")
    result = PDFValidator.validate(file_storage, 1024 * 1024)
    assert result.is_valid is False
    assert "is empty (0 bytes)" in result.error_message


def test_validate_rejects_fake_pdf_header(make_file_storage):
    """Test rejection when extension is .pdf but content has invalid magic bytes."""
    fake_content = b"This is just a plain text document masquerading as a PDF file."
    file_storage = make_file_storage(fake_content, "fake_doc.pdf")
    result = PDFValidator.validate(file_storage, 1024 * 1024)
    assert result.is_valid is False
    assert "File signature verification failed" in result.error_message


def test_validate_rejects_oversized_file(make_file_storage, valid_pdf_bytes):
    """Test rejection when file exceeds configured MAX_CONTENT_LENGTH."""
    max_size = 50  # Set tiny limit
    file_storage = make_file_storage(valid_pdf_bytes, "large.pdf")
    result = PDFValidator.validate(file_storage, max_size)
    assert result.is_valid is False
    assert "exceeds maximum size limit" in result.error_message


def test_validate_sanitizes_unsafe_filename(make_file_storage, valid_pdf_bytes):
    """Test that path traversal patterns in filenames are safely sanitized."""
    file_storage = make_file_storage(valid_pdf_bytes, "../../../etc/shadow.pdf")
    result = PDFValidator.validate(file_storage, 10 * 1024 * 1024)
    assert result.is_valid is True
    # werkzeug secure_filename turns ../../../etc/shadow.pdf into etc_shadow.pdf
    assert ".." not in result.safe_filename
    assert "/" not in result.safe_filename
    assert result.safe_filename.endswith(".pdf")
