"""Tests for Persistent Storage Service.
Verifies safe path resolution, path traversal prevention, atomic saves, and deletion.
"""
import pytest
from app.services.storage import StorageService


def test_generate_unique_stored_filenames(storage):
    """Test that generated stored filenames are unique and end with .pdf."""
    name1 = storage.generate_stored_filename()
    name2 = storage.generate_stored_filename()
    assert name1 != name2
    assert name1.endswith(".pdf")
    assert name2.endswith(".pdf")


def test_save_and_verify_file(storage, make_file_storage, valid_pdf_bytes):
    """Test saving a file and confirming its physical presence and size."""
    filename = storage.generate_stored_filename()
    file_storage = make_file_storage(valid_pdf_bytes, "test.pdf")

    saved_path = storage.save_file(file_storage, filename)

    assert saved_path.exists()
    assert storage.file_exists(filename) is True
    assert storage.get_file_size(filename) == len(valid_pdf_bytes)


def test_delete_existing_file(storage, make_file_storage, valid_pdf_bytes):
    """Test deleting an existing file from the storage directory."""
    filename = storage.generate_stored_filename()
    file_storage = make_file_storage(valid_pdf_bytes, "delete_me.pdf")
    storage.save_file(file_storage, filename)

    assert storage.file_exists(filename) is True
    deleted = storage.delete_file(filename)
    assert deleted is True
    assert storage.file_exists(filename) is False


def test_delete_non_existent_file(storage):
    """Test that deleting a file that does not exist returns False cleanly."""
    deleted = storage.delete_file("non_existent_file.pdf")
    assert deleted is False


def test_path_traversal_detection(storage):
    """Test that path traversal attempts raise ValueError."""
    dangerous_names = [
        "../../etc/passwd",
        "..\\..\\windows\\system32",
        "/absolute/path/file.pdf",
        "subfolder/file.pdf",
        "..",
        "",
    ]
    for bad_name in dangerous_names:
        with pytest.raises(ValueError):
            storage.get_safe_path(bad_name)


def test_storage_health_check(storage):
    """Test that storage health check confirms accessibility and writability."""
    accessible, writable, msg = storage.check_health()
    assert accessible is True
    assert writable is True
    assert "accessible and writable" in msg
