"""Main route serving the dashboard user interface.
"""
from flask import Blueprint, render_template, current_app
from app.models import Document
from app.services.storage import StorageService

main_bp = Blueprint("main", __name__)


def format_bytes(bytes_val: int) -> str:
    """Format bytes into readable string."""
    b = float(bytes_val)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024.0 or unit == "TB":
            return f"{b:.2f} {unit}" if unit != "B" else f"{int(b)} B"
        b /= 1024.0
    return f"{b:.2f} TB"


@main_bp.route("/", methods=["GET"])
def index():
    """Render the dashboard interface with live PostgreSQL document records and volume statistics."""
    storage = StorageService(current_app.config["UPLOAD_FOLDER"])
    
    # Query all documents from PostgreSQL ordered by most recent first
    documents = Document.query.order_by(Document.uploaded_at.desc()).all()
    
    # Check physical file presence for each record in the persistent volume
    documents_with_status = []
    total_size_bytes = 0
    available_count = 0
    missing_count = 0

    for doc in documents:
        is_physically_available = storage.file_exists(doc.stored_filename)
        if is_physically_available:
            available_count += 1
            total_size_bytes += doc.size_bytes
        else:
            missing_count += 1
            
        documents_with_status.append({
            "model": doc,
            "is_available": is_physically_available,
        })

    stats = {
        "total_documents": len(documents),
        "total_size": format_bytes(total_size_bytes),
        "total_size_bytes": total_size_bytes,
        "available_documents": available_count,
        "missing_documents": missing_count,
    }

    max_mb = current_app.config["MAX_CONTENT_LENGTH"] / (1024 * 1024)

    return render_template(
        "index.html",
        documents=documents_with_status,
        stats=stats,
        max_file_size_mb=f"{max_mb:.0f}",
    )
