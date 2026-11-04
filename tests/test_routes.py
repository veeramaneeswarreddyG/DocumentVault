"""Tests for Flask HTTP routes: Upload, list, download, delete, and statistics.
"""
import io
from app.extensions import db
from app.models import Document


def test_index_route_empty(client):
    """Test that the index dashboard loads with zero initial documents."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Document Vault" in html
    assert "Vault is Currently Empty" in html


def test_upload_valid_pdf_json(client, valid_pdf_bytes):
    """Test uploading a valid PDF document via JSON/AJAX returns 201 and stores record."""
    data = {
        "file": (io.BytesIO(valid_pdf_bytes), "quarterly_report.pdf", "application/pdf")
    }
    response = client.post(
        "/documents/upload",
        data=data,
        content_type="multipart/form-data",
        headers={"X-Requested-With": "XMLHttpRequest"}
    )
    assert response.status_code == 201
    res_json = response.get_json()
    assert res_json["success"] is True
    assert "quarterly_report.pdf" in res_json["message"]

    doc_info = res_json["document"]
    assert doc_info["original_filename"] == "quarterly_report.pdf"
    assert doc_info["size_bytes"] == len(valid_pdf_bytes)
    assert doc_info["is_available"] is True

    # Verify database entry exists
    db_doc = db.session.get(Document, doc_info["id"])
    assert db_doc is not None
    assert db_doc.sha256 == doc_info["sha256"]


def test_upload_invalid_file_rejected(client):
    """Test that non-PDF file upload returns 400 error."""
    data = {
        "file": (io.BytesIO(b"Hello world"), "notes.txt", "text/plain")
    }
    response = client.post(
        "/documents/upload",
        data=data,
        content_type="multipart/form-data",
        headers={"X-Requested-With": "XMLHttpRequest"}
    )
    assert response.status_code == 400
    res_json = response.get_json()
    assert res_json["success"] is False
    assert "Only .pdf files are permitted" in res_json["error"]


def test_upload_no_file_rejected(client):
    """Test upload request without file returns 400."""
    response = client.post(
        "/documents/upload",
        data={},
        content_type="multipart/form-data",
        headers={"X-Requested-With": "XMLHttpRequest"}
    )
    assert response.status_code == 400
    res_json = response.get_json()
    assert "No file field" in res_json["error"]


def test_download_document(client, valid_pdf_bytes):
    """Test downloading a previously uploaded document."""
    # First upload
    upload_res = client.post(
        "/documents/upload",
        data={"file": (io.BytesIO(valid_pdf_bytes), "contract.pdf", "application/pdf")},
        content_type="multipart/form-data",
        headers={"X-Requested-With": "XMLHttpRequest"}
    )
    doc_id = upload_res.get_json()["document"]["id"]

    # Now download
    download_res = client.get(f"/documents/{doc_id}/download")
    assert download_res.status_code == 200
    assert download_res.data == valid_pdf_bytes
    assert "attachment; filename=contract.pdf" in download_res.headers.get("Content-Disposition", "")


def test_download_nonexistent_document(client):
    """Test downloading an unknown document ID returns 404."""
    response = client.get("/documents/non-existent-uuid/download")
    assert response.status_code == 404


def test_delete_document(client, valid_pdf_bytes, storage):
    """Test deleting a document removes both the file on disk and the database record."""
    # 1. Upload
    upload_res = client.post(
        "/documents/upload",
        data={"file": (io.BytesIO(valid_pdf_bytes), "receipt.pdf", "application/pdf")},
        content_type="multipart/form-data",
        headers={"X-Requested-With": "XMLHttpRequest"}
    )
    doc_data = upload_res.get_json()["document"]
    doc_id = doc_data["id"]
    stored_name = doc_data["stored_filename"]

    assert storage.file_exists(stored_name) is True
    assert db.session.get(Document, doc_id) is not None

    # 2. Delete
    delete_res = client.delete(
        f"/documents/{doc_id}",
        headers={"X-Requested-With": "XMLHttpRequest"}
    )
    assert delete_res.status_code == 200
    assert delete_res.get_json()["success"] is True

    # 3. Verify gone from database and storage
    assert db.session.get(Document, doc_id) is None
    assert storage.file_exists(stored_name) is False


def test_list_documents_api(client, valid_pdf_bytes):
    """Test documents list API returns proper statistics and document models."""
    client.post(
        "/documents/upload",
        data={"file": (io.BytesIO(valid_pdf_bytes), "doc1.pdf", "application/pdf")},
        content_type="multipart/form-data",
        headers={"X-Requested-With": "XMLHttpRequest"}
    )

    list_res = client.get("/documents")
    assert list_res.status_code == 200
    data = list_res.get_json()
    assert data["success"] is True
    assert len(data["documents"]) == 1
    assert data["stats"]["total_documents"] == 1
    assert data["stats"]["available_documents"] == 1
    assert data["stats"]["missing_documents"] == 0


def test_missing_file_detection(client, valid_pdf_bytes, storage):
    """Test that when a physical file is removed from storage, it is detected and reported as missing."""
    # 1. Upload
    upload_res = client.post(
        "/documents/upload",
        data={"file": (io.BytesIO(valid_pdf_bytes), "disappearing.pdf", "application/pdf")},
        content_type="multipart/form-data",
        headers={"X-Requested-With": "XMLHttpRequest"}
    )
    doc_data = upload_res.get_json()["document"]
    doc_id = doc_data["id"]
    stored_name = doc_data["stored_filename"]

    # 2. Simulate external deletion from volume
    storage.delete_file(stored_name)
    assert storage.file_exists(stored_name) is False

    # 3. Check dashboard API returns is_available: False and missing_documents: 1
    list_res = client.get("/documents")
    data = list_res.get_json()
    assert data["stats"]["missing_documents"] == 1
    assert data["documents"][0]["is_available"] is False

    # 4. Check download attempt returns 404 with missing file error
    dl_res = client.get(f"/documents/{doc_id}/download")
    assert dl_res.status_code == 404
    assert "missing" in dl_res.get_data(as_text=True).lower()


def test_upload_db_failure_cleans_up_orphaned_file(client, valid_pdf_bytes, storage):
    """Test that if the database fails during upload, the saved file on disk is cleaned up."""
    from unittest.mock import patch

    with patch("app.routes.documents.db.session.commit") as mock_commit:
        mock_commit.side_effect = Exception("Simulated PostgreSQL connection drop")

        data = {
            "file": (io.BytesIO(valid_pdf_bytes), "test_cleanup.pdf", "application/pdf")
        }
        res = client.post(
            "/documents/upload",
            data=data,
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest"}
        )

        assert res.status_code == 500
        assert "Database failure" in res.get_json()["error"]

        # Ensure no orphaned files remain in storage directory
        remaining_files = [f for f in storage.upload_folder.iterdir() if f.is_file() and not f.name.startswith(".")]
        assert len(remaining_files) == 0
