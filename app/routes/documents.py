"""Document management routes: Upload, list, download, inspect, and delete.
"""
import logging
from flask import (
    Blueprint,
    request,
    jsonify,
    current_app,
    send_from_directory,
    redirect,
    url_for,
    flash,
    abort,
)
from app.extensions import db
from app.models import Document
from app.services.pdf_validator import PDFValidator
from app.services.storage import StorageService

logger = logging.getLogger(__name__)

documents_bp = Blueprint("documents", __name__, url_prefix="/documents")


def _is_json_request() -> bool:
    """Detect if the incoming request expects a JSON response."""
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.is_json
        or "application/json" in request.headers.get("Accept", "")
    )


@documents_bp.route("/upload", methods=["POST"])
def upload():
    """Handle PDF upload, server-side validation, volume storage, and database persistence."""
    storage = StorageService(current_app.config["UPLOAD_FOLDER"])
    max_size = current_app.config["MAX_CONTENT_LENGTH"]

    # Check if a file was provided in the multipart form data
    if "file" not in request.files:
        error_msg = "No file field in upload request."
        if _is_json_request():
            return jsonify({"success": False, "error": error_msg}), 400
        flash(error_msg, "error")
        return redirect(url_for("main.index"))

    uploaded_file = request.files["file"]

    # 1. Rigorous PDF validation (mime, header, size, checksum)
    result = PDFValidator.validate(uploaded_file, max_size)
    if not result.is_valid:
        if _is_json_request():
            return jsonify({"success": False, "error": result.error_message}), 400
        flash(result.error_message, "error")
        return redirect(url_for("main.index"))

    stored_filename = storage.generate_stored_filename()

    # 2. Atomic write to persistent Docker volume
    try:
        storage.save_file(uploaded_file, stored_filename)
    except Exception as exc:
        logger.error("Failed to save file to volume: %s", exc)
        error_msg = f"Storage failure: Could not write file to persistent storage. ({str(exc)})"
        if _is_json_request():
            return jsonify({"success": False, "error": error_msg}), 500
        flash(error_msg, "error")
        return redirect(url_for("main.index"))

    # 3. Database metadata persistence
    document = Document(
        original_filename=result.safe_filename,
        stored_filename=stored_filename,
        size_bytes=result.size_bytes,
        sha256=result.sha256,
    )

    try:
        db.session.add(document)
        db.session.commit()
    except Exception as db_exc:
        # Consistency guarantee: Clean up orphaned file on disk if database insertion fails
        db.session.rollback()
        logger.critical("Database insertion failed for %s, cleaning up file: %s", stored_filename, db_exc)
        try:
            storage.delete_file(stored_filename)
        except Exception as cleanup_exc:
            logger.error("Failed to clean up orphaned file %s: %s", stored_filename, cleanup_exc)

        error_msg = f"Database failure: Could not record document metadata. Upload rolled back. ({str(db_exc)})"
        if _is_json_request():
            return jsonify({"success": False, "error": error_msg}), 500
        flash(error_msg, "error")
        return redirect(url_for("main.index"))

    success_msg = f"Successfully uploaded and secured '{document.original_filename}'."
    if _is_json_request():
        return jsonify({
            "success": True,
            "message": success_msg,
            "document": document.to_dict(is_available=True),
        }), 201

    flash(success_msg, "success")
    return redirect(url_for("main.index"))


@documents_bp.route("", methods=["GET"])
def list_documents():
    """API endpoint to list all documents with actual storage availability status."""
    storage = StorageService(current_app.config["UPLOAD_FOLDER"])
    documents = Document.query.order_by(Document.uploaded_at.desc()).all()

    docs_data = []
    total_size = 0
    available_count = 0
    missing_count = 0

    for doc in documents:
        available = storage.file_exists(doc.stored_filename)
        if available:
            available_count += 1
            total_size += doc.size_bytes
        else:
            missing_count += 1
        docs_data.append(doc.to_dict(is_available=available))

    return jsonify({
        "success": True,
        "documents": docs_data,
        "stats": {
            "total_documents": len(documents),
            "total_size_bytes": total_size,
            "available_documents": available_count,
            "missing_documents": missing_count,
        }
    }), 200


@documents_bp.route("/<string:document_id>", methods=["GET"])
def get_document(document_id: str):
    """Retrieve detailed metadata for a single document."""
    storage = StorageService(current_app.config["UPLOAD_FOLDER"])
    document = db.session.get(Document, document_id)

    if not document:
        return jsonify({"success": False, "error": "Document not found"}), 404

    available = storage.file_exists(document.stored_filename)
    doc_dict = document.to_dict(is_available=available)
    doc_dict["physical_size_bytes"] = storage.get_file_size(document.stored_filename) if available else None

    return jsonify({"success": True, "document": doc_dict}), 200


@documents_bp.route("/<string:document_id>/download", methods=["GET"])
def download(document_id: str):
    """Securely download a document by ID."""
    storage = StorageService(current_app.config["UPLOAD_FOLDER"])
    document = db.session.get(Document, document_id)

    if not document:
        abort(404, description="The requested document record does not exist in the database.")

    # Check physical existence in the persistent volume
    if not storage.file_exists(document.stored_filename):
        abort(404, description=f"Physical file '{document.original_filename}' is missing from the persistent storage volume.")

    # Send file safely using Flask's secure send_from_directory
    return send_from_directory(
        directory=str(storage.upload_folder),
        path=document.stored_filename,
        as_attachment=True,
        download_name=document.original_filename,
        mimetype="application/pdf"
    )


@documents_bp.route("/<string:document_id>", methods=["DELETE"])
@documents_bp.route("/<string:document_id>/delete", methods=["POST"])
def delete_document(document_id: str):
    """Delete a document from both persistent volume and database."""
    storage = StorageService(current_app.config["UPLOAD_FOLDER"])
    document = db.session.get(Document, document_id)

    if not document:
        error_msg = "Document record not found in database."
        if _is_json_request():
            return jsonify({"success": False, "error": error_msg}), 404
        flash(error_msg, "error")
        return redirect(url_for("main.index"))

    original_name = document.original_filename
    stored_name = document.stored_filename

    # Delete physical file from volume (if it exists)
    try:
        storage.delete_file(stored_name)
    except Exception as exc:
        logger.warning("Error deleting file %s from volume: %s", stored_name, exc)

    # Delete database record
    try:
        db.session.delete(document)
        db.session.commit()
    except Exception as db_exc:
        db.session.rollback()
        error_msg = f"Failed to delete document metadata from database: {str(db_exc)}"
        if _is_json_request():
            return jsonify({"success": False, "error": error_msg}), 500
        flash(error_msg, "error")
        return redirect(url_for("main.index"))

    success_msg = f"Document '{original_name}' was successfully deleted."
    if _is_json_request():
        return jsonify({"success": True, "message": success_msg}), 200

    flash(success_msg, "success")
    return redirect(url_for("main.index"))
