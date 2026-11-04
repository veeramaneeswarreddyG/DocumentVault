"""Pytest configuration and shared fixtures for Document Vault tests.
"""
import io
import os
import shutil
import tempfile
import pytest
from app import create_app, db as _db
from app.services.storage import StorageService

# Valid minimal PDF file bytes compliant with ISO 32000-1
MINIMAL_VALID_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj\n"
    b"<< /Type /Catalog /Pages 2 0 R >>\n"
    b"endobj\n"
    b"2 0 obj\n"
    b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>\n"
    b"endobj\n"
    b"3 0 obj\n"
    b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\n"
    b"endobj\n"
    b"4 0 obj\n"
    b"<< /Length 44 >>\n"
    b"stream\n"
    b"BT /F1 24 Tf 100 700 Td (Document Vault Test) Tj ET\n"
    b"endstream\n"
    b"endobj\n"
    b"xref\n"
    b"0 5\n"
    b"0000000000 65535 f \n"
    b"0000000010 00000 n \n"
    b"0000000060 00000 n \n"
    b"0000000117 00000 n \n"
    b"0000000202 00000 n \n"
    b"trailer\n"
    b"<< /Size 5 /Root 1 0 R >>\n"
    b"startxref\n"
    b"296\n"
    b"%%EOF\n"
)


@pytest.fixture(scope="session")
def test_temp_dir():
    """Create a temporary directory for test file uploads."""
    temp_dir = tempfile.mkdtemp(prefix="doc_vault_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def app(test_temp_dir):
    """Instantiate application configured for isolated testing."""
    os.environ["FLASK_ENV"] = "testing"
    os.environ["UPLOAD_FOLDER"] = test_temp_dir
    os.environ["MAX_CONTENT_LENGTH"] = str(5 * 1024 * 1024)  # 5 MB limit for test
    
    flask_app = create_app("testing")
    flask_app.config["UPLOAD_FOLDER"] = test_temp_dir
    flask_app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
    flask_app.config["WTF_CSRF_ENABLED"] = False

    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.session.remove()
        _db.drop_all()

    # Clean temporary upload directory contents between tests
    for item in os.listdir(test_temp_dir):
        item_path = os.path.join(test_temp_dir, item)
        if os.path.isfile(item_path):
            os.remove(item_path)


@pytest.fixture
def client(app):
    """Test HTTP client."""
    return app.test_client()


@pytest.fixture
def db(app):
    """Database instance fixture."""
    return _db


@pytest.fixture
def storage(app):
    """StorageService configured for test upload directory."""
    return StorageService(app.config["UPLOAD_FOLDER"])


@pytest.fixture
def valid_pdf_bytes():
    """Valid PDF byte content fixture."""
    return MINIMAL_VALID_PDF_BYTES


@pytest.fixture
def make_file_storage():
    """Helper factory to create Werkzeug FileStorage objects."""
    from werkzeug.datastructures import FileStorage

    def _maker(content: bytes, filename: str, content_type: str = "application/pdf"):
        return FileStorage(
            stream=io.BytesIO(content),
            filename=filename,
            content_type=content_type
        )
    return _maker
