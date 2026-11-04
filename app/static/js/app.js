/**
 * Document Vault — Client Interaction Engine
 * Handles Drag & Drop, AJAX Uploads with Real Progress, Live Status Probes,
 * Search Filtering, Modals, and SHA-256 Checksum Copying.
 */

document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("file-input");
    const dropZoneIdle = document.getElementById("drop-zone-idle");
    const dropZoneSelected = document.getElementById("drop-zone-selected");
    const selectedFileName = document.getElementById("selected-file-name");
    const selectedFileSize = document.getElementById("selected-file-size");
    const btnClearFile = document.getElementById("btn-clear-file");
    const btnUploadSubmit = document.getElementById("btn-upload-submit");
    const uploadBtnText = document.getElementById("upload-btn-text");
    const uploadForm = document.getElementById("pdf-upload-form");
    const progressWrapper = document.getElementById("upload-progress-wrapper");
    const progressBarFill = document.getElementById("progress-bar-fill");
    const progressText = document.getElementById("progress-text");
    const searchInput = document.getElementById("document-search-input");
    const documentsTable = document.getElementById("documents-table");
    const documentsTableBody = document.getElementById("documents-table-body");
    const emptyVaultState = document.getElementById("empty-vault-state");
    const searchEmptyState = document.getElementById("search-empty-state");
    const notificationContainer = document.getElementById("notification-container");

    // Modals
    const infoModal = document.getElementById("info-modal");
    const infoModalBody = document.getElementById("info-modal-body");
    const infoModalClose = document.getElementById("info-modal-close");
    const infoModalDismiss = document.getElementById("info-modal-dismiss");

    const deleteModal = document.getElementById("delete-modal");
    const deleteDocumentName = document.getElementById("delete-document-name");
    const deleteModalForm = document.getElementById("delete-modal-form");
    const deleteModalClose = document.getElementById("delete-modal-close");
    const deleteModalCancel = document.getElementById("delete-modal-cancel");

    // CSRF Token Helper
    const getCsrfToken = () => {
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.getAttribute("content");
        const input = document.querySelector('input[name="csrf_token"]');
        return input ? input.value : "";
    };

    // Human Readable Size Formatter
    const formatBytes = (bytes) => {
        if (!bytes || bytes === 0) return "0 B";
        const k = 1024;
        const sizes = ["B", "KB", "MB", "GB", "TB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
    };

    // Toast Notification System
    const showToast = (message, type = "info") => {
        const toast = document.createElement("div");
        toast.className = `toast-message toast-${type}`;
        toast.setAttribute("role", "alert");

        const iconSvg = type === "success"
            ? '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>'
            : '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>';

        toast.innerHTML = `
            <div class="toast-icon">${iconSvg}</div>
            <span class="toast-body">${message}</span>
            <button type="button" class="toast-close" aria-label="Close notification">&times;</button>
        `;

        toast.querySelector(".toast-close").addEventListener("click", () => toast.remove());
        notificationContainer.appendChild(toast);

        // Auto remove after 5 seconds
        setTimeout(() => {
            if (toast.parentElement) {
                toast.style.opacity = "0";
                toast.style.transform = "translateX(40px)";
                setTimeout(() => toast.remove(), 300);
            }
        }, 5000);
    };

    // =========================================================================
    // FILE SELECTION & DRAG-AND-DROP HANDLERS
    // =========================================================================

    const setSelectedFile = (file) => {
        if (!file) return;

        // Verify PDF extension client-side before submission
        if (!file.name.toLowerCase().endsWith(".pdf")) {
            showToast("Invalid file type. Only PDF documents (*.pdf) are accepted.", "error");
            clearSelectedFile();
            return;
        }

        selectedFileName.textContent = file.name;
        selectedFileSize.textContent = formatBytes(file.size);
        dropZoneIdle.style.display = "none";
        dropZoneSelected.style.display = "block";
        btnUploadSubmit.disabled = false;
    };

    const clearSelectedFile = () => {
        fileInput.value = "";
        dropZoneIdle.style.display = "block";
        dropZoneSelected.style.display = "none";
        btnUploadSubmit.disabled = true;
        progressWrapper.style.display = "none";
        progressBarFill.style.width = "0%";
    };

    if (dropZone) {
        dropZone.addEventListener("click", (e) => {
            if (e.target !== btnClearFile && !btnClearFile.contains(e.target)) {
                fileInput.click();
            }
        });

        dropZone.addEventListener("keydown", (e) => {
            if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                fileInput.click();
            }
        });

        // Prevent default browser drag behaviors on whole document
        ["dragenter", "dragover", "dragleave", "drop"].forEach((eventName) => {
            document.body.addEventListener(eventName, (e) => e.preventDefault(), false);
        });

        // Highlight drop zone on drag over
        ["dragenter", "dragover"].forEach((eventName) => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.add("dragover");
            }, false);
        });

        ["dragleave", "drop"].forEach((eventName) => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.remove("dragover");
            }, false);
        });

        dropZone.addEventListener("drop", (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files && files.length > 0) {
                fileInput.files = files;
                setSelectedFile(files[0]);
            }
        });
    }

    if (fileInput) {
        fileInput.addEventListener("change", () => {
            if (fileInput.files && fileInput.files.length > 0) {
                setSelectedFile(fileInput.files[0]);
            }
        });
    }

    if (btnClearFile) {
        btnClearFile.addEventListener("click", (e) => {
            e.stopPropagation();
            clearSelectedFile();
        });
    }

    // =========================================================================
    // AJAX UPLOAD WITH REAL PROGRESS TRACKING
    // =========================================================================

    if (uploadForm) {
        uploadForm.addEventListener("submit", (e) => {
            e.preventDefault();

            if (!fileInput.files || fileInput.files.length === 0) {
                showToast("Please select a PDF document first.", "error");
                return;
            }

            const file = fileInput.files[0];
            const formData = new FormData();
            formData.append("file", file);
            formData.append("csrf_token", getCsrfToken());

            // Lock UI
            btnUploadSubmit.disabled = true;
            uploadBtnText.textContent = "Securing and Uploading...";
            progressWrapper.style.display = "block";
            progressBarFill.style.width = "0%";
            progressText.textContent = "Transferring: 0%";

            const xhr = new XMLHttpRequest();
            xhr.open("POST", uploadForm.action, true);
            xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
            xhr.setRequestHeader("X-CSRFToken", getCsrfToken());

            // Progress tracking
            xhr.upload.onprogress = (evt) => {
                if (evt.lengthComputable) {
                    const percent = Math.round((evt.loaded / evt.total) * 100);
                    progressBarFill.style.width = `${percent}%`;
                    progressText.textContent = `Writing to persistent volume: ${percent}%`;
                }
            };

            xhr.onload = () => {
                if (xhr.status === 201) {
                    try {
                        const response = JSON.parse(xhr.responseText);
                        showToast(response.message || "Document uploaded successfully!", "success");
                        clearSelectedFile();
                        // Refresh page or dynamic table update
                        setTimeout(() => window.location.reload(), 600);
                    } catch (err) {
                        window.location.reload();
                    }
                } else {
                    let errorMsg = "Upload failed. Please check the file and try again.";
                    try {
                        const errResponse = JSON.parse(xhr.responseText);
                        if (errResponse.error) errorMsg = errResponse.error;
                    } catch (err) {
                        if (xhr.statusText) errorMsg = `${xhr.status}: ${xhr.statusText}`;
                    }
                    showToast(errorMsg, "error");
                    btnUploadSubmit.disabled = false;
                    uploadBtnText.textContent = "Upload to Persistent Storage";
                    progressWrapper.style.display = "none";
                }
            };

            xhr.onerror = () => {
                showToast("Network connection error during upload. Please check Docker services.", "error");
                btnUploadSubmit.disabled = false;
                uploadBtnText.textContent = "Upload to Persistent Storage";
                progressWrapper.style.display = "none";
            };

            xhr.send(formData);
        });
    }

    // =========================================================================
    // SEARCH & FILTERING IN DOCUMENT INDEX
    // =========================================================================

    if (searchInput) {
        searchInput.addEventListener("input", () => {
            const query = searchInput.value.trim().toLowerCase();
            const rows = document.querySelectorAll(".document-row");
            let visibleCount = 0;

            rows.forEach((row) => {
                const name = row.getAttribute("data-name") || "";
                const hash = row.getAttribute("data-hash") || "";
                const id = row.getAttribute("data-id") || "";

                if (name.includes(query) || hash.includes(query) || id.includes(query)) {
                    row.style.display = "";
                    visibleCount++;
                } else {
                    row.style.display = "none";
                }
            });

            if (searchEmptyState) {
                searchEmptyState.style.display = (visibleCount === 0 && rows.length > 0) ? "block" : "none";
            }
        });
    }

    // =========================================================================
    // COPY SHA-256 CHECKSUM TO CLIPBOARD
    // =========================================================================

    document.addEventListener("click", (e) => {
        const copyBtn = e.target.closest(".btn-copy-hash");
        if (copyBtn) {
            const hashText = copyBtn.getAttribute("data-copy");
            if (hashText) {
                navigator.clipboard.writeText(hashText).then(() => {
                    showToast("SHA-256 checksum copied to clipboard!", "success");
                }).catch(() => {
                    showToast("Failed to copy checksum.", "error");
                });
            }
        }
    });

    // =========================================================================
    // DOCUMENT INSPECTION MODAL
    // =========================================================================

    const openInfoModal = (docId) => {
        infoModalBody.innerHTML = '<div style="text-align:center; padding: 1.5rem; color: #94A3B8;">Retrieving document metadata from PostgreSQL...</div>';
        infoModal.classList.add("active");
        infoModal.setAttribute("aria-hidden", "false");

        fetch(`/documents/${docId}`, {
            headers: { "X-Requested-With": "XMLHttpRequest" }
        })
        .then((res) => res.json())
        .then((data) => {
            if (data.success && data.document) {
                const doc = data.document;
                infoModalBody.innerHTML = `
                    <div class="inspect-grid">
                        <div class="inspect-item">
                            <span class="inspect-label">Database Record ID (UUID)</span>
                            <div class="inspect-value">${doc.id}</div>
                        </div>
                        <div class="inspect-item">
                            <span class="inspect-label">Original Filename</span>
                            <div class="inspect-value">${doc.original_filename}</div>
                        </div>
                        <div class="inspect-item">
                            <span class="inspect-label">Storage Target Name (Docker Volume)</span>
                            <div class="inspect-value">${doc.stored_filename}</div>
                        </div>
                        <div class="inspect-item">
                            <span class="inspect-label">Recorded Size / Physical Size</span>
                            <div class="inspect-value">${doc.human_readable_size} (${doc.size_bytes.toLocaleString()} bytes)</div>
                        </div>
                        <div class="inspect-item">
                            <span class="inspect-label">SHA-256 Cryptographic Digest</span>
                            <div class="inspect-value">${doc.sha256}</div>
                        </div>
                        <div class="inspect-item">
                            <span class="inspect-label">Volume Status</span>
                            <div class="inspect-value">${doc.is_available ? '✅ Physically Present in Volume (Mount: /app/uploads)' : '❌ Missing from Volume filesystem'}</div>
                        </div>
                        <div class="inspect-item">
                            <span class="inspect-label">Upload Timestamp (UTC)</span>
                            <div class="inspect-value">${doc.uploaded_at || 'N/A'}</div>
                        </div>
                    </div>
                `;
            } else {
                infoModalBody.innerHTML = `<div class="text-danger">Failed to retrieve metadata: ${data.error || "Unknown error"}</div>`;
            }
        })
        .catch((err) => {
            infoModalBody.innerHTML = `<div class="text-danger">Network error connecting to database API: ${err}</div>`;
        });
    };

    const closeInfoModal = () => {
        infoModal.classList.remove("active");
        infoModal.setAttribute("aria-hidden", "true");
    };

    if (infoModalClose) infoModalClose.addEventListener("click", closeInfoModal);
    if (infoModalDismiss) infoModalDismiss.addEventListener("click", closeInfoModal);
    if (infoModal) {
        infoModal.addEventListener("click", (e) => {
            if (e.target === infoModal) closeInfoModal();
        });
    }

    document.addEventListener("click", (e) => {
        const inspectBtn = e.target.closest("[data-inspect-id]");
        if (inspectBtn) {
            const docId = inspectBtn.getAttribute("data-inspect-id");
            openInfoModal(docId);
        }
    });

    // =========================================================================
    // DELETE CONFIRMATION MODAL & ACTION
    // =========================================================================

    let pendingDeleteId = null;

    const openDeleteModal = (docId, docName) => {
        pendingDeleteId = docId;
        deleteDocumentName.textContent = docName;
        deleteModalForm.action = `/documents/${docId}/delete`;
        deleteModal.classList.add("active");
        deleteModal.setAttribute("aria-hidden", "false");
    };

    const closeDeleteModal = () => {
        pendingDeleteId = null;
        deleteModal.classList.remove("active");
        deleteModal.setAttribute("aria-hidden", "true");
    };

    if (deleteModalClose) deleteModalClose.addEventListener("click", closeDeleteModal);
    if (deleteModalCancel) deleteModalCancel.addEventListener("click", closeDeleteModal);
    if (deleteModal) {
        deleteModal.addEventListener("click", (e) => {
            if (e.target === deleteModal) closeDeleteModal();
        });
    }

    document.addEventListener("click", (e) => {
        const deleteBtn = e.target.closest("[data-delete-id]");
        if (deleteBtn) {
            const docId = deleteBtn.getAttribute("data-delete-id");
            const docName = deleteBtn.getAttribute("data-delete-name") || "this document";
            openDeleteModal(docId, docName);
        }
    });

    if (deleteModalForm) {
        deleteModalForm.addEventListener("submit", (e) => {
            e.preventDefault();
            if (!pendingDeleteId) return;

            const confirmBtn = document.getElementById("delete-modal-confirm-btn");
            if (confirmBtn) confirmBtn.disabled = true;

            fetch(`/documents/${pendingDeleteId}`, {
                method: "DELETE",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": getCsrfToken(),
                }
            })
            .then((res) => res.json())
            .then((data) => {
                if (data.success) {
                    showToast(data.message || "Document deleted successfully", "success");
                    closeDeleteModal();
                    setTimeout(() => window.location.reload(), 400);
                } else {
                    showToast(data.error || "Failed to delete document", "error");
                    if (confirmBtn) confirmBtn.disabled = false;
                }
            })
            .catch((err) => {
                showToast(`Failed to communicate with server: ${err}`, "error");
                if (confirmBtn) confirmBtn.disabled = false;
            });
        });
    }

    // Keyboard ESC listener for modals
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeInfoModal();
            closeDeleteModal();
        }
    });

    // =========================================================================
    // SYSTEM HEALTH MONITORING PROBE
    // =========================================================================

    const healthPill = document.getElementById("system-health-pill");
    const healthText = document.getElementById("system-health-text");

    const probeHealth = () => {
        fetch("/health")
            .then((res) => {
                const isHealthy = res.status === 200;
                return res.json().then((data) => ({ isHealthy, data }));
            })
            .then(({ isHealthy, data }) => {
                if (healthPill && healthText) {
                    const dot = healthPill.querySelector(".status-indicator-dot");
                    if (isHealthy) {
                        dot.className = "status-indicator-dot online";
                        healthText.textContent = "Cluster Online";
                        healthPill.title = `Database: Connected | Storage Volume: ${data.checks?.storage?.status || 'Active'}`;
                    } else {
                        dot.className = "status-indicator-dot offline";
                        healthText.textContent = "Cluster Degraded";
                        healthPill.title = "Warning: Database or persistent volume is reporting errors.";
                    }
                }
            })
            .catch(() => {
                if (healthPill && healthText) {
                    const dot = healthPill.querySelector(".status-indicator-dot");
                    dot.className = "status-indicator-dot offline";
                    healthText.textContent = "Offline";
                    healthPill.title = "Cannot reach application backend.";
                }
            });
    };

    // Run health check on page load and every 30 seconds
    probeHealth();
    setInterval(probeHealth, 30000);
});
