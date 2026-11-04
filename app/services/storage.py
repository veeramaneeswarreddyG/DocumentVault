"""Persistent Storage Service.
Manages file operations within the mounted persistent Docker Volume:
- Safe path resolution without directory traversal
- Atomic writes with chunking and cleanup on failure
- Safe file deletion
- Physical file existence checks
- Upload directory health and writability checks
"""
import os
import uuid
from pathlib import Path
from typing import Optional, Tuple
from werkzeug.datastructures import FileStorage


class StorageService:
    """Service to safely interact with the persistent volume filesystem."""

    def __init__(self, upload_folder: str):
        self.upload_folder = Path(upload_folder).resolve()
        # Ensure upload folder exists with appropriate permissions
        self.upload_folder.mkdir(parents=True, exist_ok=True)

    def generate_stored_filename(self) -> str:
        """Generate a cryptographically secure, unique UUID filename."""
        return f"{uuid.uuid4().hex}.pdf"

    def get_safe_path(self, stored_filename: str) -> Path:
        """Resolve a filename to a secure absolute path within the upload directory.
        Strictly prevents directory traversal attacks.
        
        Raises:
            ValueError: If the filename contains traversal characters or resolves outside upload_folder.
        """
        # Reject obvious path traversal patterns
        if not stored_filename or "/" in stored_filename or "\\" in stored_filename or ".." in stored_filename:
            raise ValueError(f"Invalid or unsafe stored filename: {stored_filename}")

        candidate_path = (self.upload_folder / stored_filename).resolve()

        # Strict boundary check: candidate must be within self.upload_folder
        try:
            candidate_path.relative_to(self.upload_folder)
        except ValueError as exc:
            raise ValueError(f"Path traversal detected: {stored_filename}") from exc

        return candidate_path

    def file_exists(self, stored_filename: str) -> bool:
        """Check whether a stored file physically exists in the volume."""
        try:
            file_path = self.get_safe_path(stored_filename)
            return file_path.is_file()
        except ValueError:
            return False

    def get_file_size(self, stored_filename: str) -> Optional[int]:
        """Return the physical size of a stored file in bytes."""
        try:
            file_path = self.get_safe_path(stored_filename)
            if file_path.is_file():
                return file_path.stat().st_size
        except (ValueError, OSError):
            pass
        return None

    def save_file(self, file_obj: FileStorage, stored_filename: str) -> Path:
        """Save an uploaded file stream atomically to the persistent volume.
        Writes to a temporary file first, then atomically replaces/renames to prevent partial files.
        
        Args:
            file_obj: Uploaded file storage
            stored_filename: Target unique filename
            
        Returns:
            Path of the stored file
        """
        target_path = self.get_safe_path(stored_filename)
        temp_filename = f".tmp_{uuid.uuid4().hex}_{stored_filename}"
        temp_path = self.upload_folder / temp_filename

        try:
            # Write stream to temporary file in chunks
            file_obj.stream.seek(0)
            with open(temp_path, "wb") as f_out:
                while True:
                    chunk = file_obj.stream.read(64 * 1024)
                    if not chunk:
                        break
                    f_out.write(chunk)
                f_out.flush()
                os.fsync(f_out.fileno())

            # Atomic replace
            os.replace(temp_path, target_path)
            return target_path

        except Exception as exc:
            # Clean up temporary file on failure
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            raise IOError(f"Failed to save file to persistent volume: {str(exc)}") from exc

    def delete_file(self, stored_filename: str) -> bool:
        """Safely delete a stored file from the persistent volume.
        
        Returns:
            True if file existed and was deleted, False if file did not exist.
        """
        target_path = self.get_safe_path(stored_filename)
        if target_path.is_file():
            try:
                target_path.unlink()
                return True
            except OSError as exc:
                raise IOError(f"Failed to delete file from volume: {str(exc)}") from exc
        return False

    def check_health(self) -> Tuple[bool, bool, str]:
        """Inspect upload directory accessibility and writability.
        
        Returns:
            (is_accessible, is_writable, status_message)
        """
        if not self.upload_folder.exists() or not self.upload_folder.is_dir():
            return False, False, f"Upload directory does not exist: {self.upload_folder}"

        test_file = self.upload_folder / f".health_check_{uuid.uuid4().hex}"
        try:
            # Test writability
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("healthcheck")
            # Test readability & cleanup
            if test_file.exists():
                test_file.unlink()
            return True, True, "Upload directory is accessible and writable."
        except Exception as exc:
            if test_file.exists():
                try:
                    test_file.unlink()
                except OSError:
                    pass
            return True, False, f"Upload directory is not writable: {str(exc)}"
