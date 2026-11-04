# Document Vault — Persistent PDF Storage Engine

An enterprise-grade document upload system built with **Flask**, **PostgreSQL**, and **Docker Compose**, featuring persistent storage across Docker containers via **Docker Named Volumes** and a futuristic, glassmorphic dark user interface with continuous CSS gradient motion.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Core Architecture & Storage Model](#2-core-architecture--storage-model)
3. [Deep Dive: Docker Concepts Explained](#3-deep-dive-docker-concepts-explained)
   - [What is a Docker Image?](#what-is-a-docker-image)
   - [What is a Docker Container?](#what-is-a-docker-container)
   - [What is a Docker Volume?](#what-is-a-docker-volume)
   - [Why are Docker Volumes Essential for this Project?](#why-are-docker-volumes-essential-for-this-project)
4. [Database & Backend Architecture](#4-database--backend-architecture)
   - [Why PostgreSQL is Used](#why-postgresql-is-used)
   - [How Flask Operates in this System](#how-flask-operates-in-this-system)
   - [How PDF Uploads are Handled and Stored](#how-pdf-uploads-are-handled-and-stored)
   - [How Docker Compose Connects the Services](#how-docker-compose-connects-the-services)
5. [Prerequisites & System Setup on Windows 11](#5-prerequisites--system-setup-on-windows-11)
6. [Environment Configuration (`.env`)](#6-environment-configuration-env)
7. [Running the Application with Docker Compose](#7-running-the-application-with-docker-compose)
   - [Building the Application](#building-the-application)
   - [Starting the Containers](#starting-the-containers)
   - [Stopping the Containers](#stopping-the-containers)
   - [Viewing Container Logs](#viewing-container-logs)
8. [Persistence Verification: Step-by-Step Testing Guide](#8-persistence-verification-step-by-step-testing-guide)
   - [Test 1: Initial PDF Upload](#test-1-initial-pdf-upload)
   - [Test 2: Recreate Flask Container (`--force-recreate`)](#test-2-recreate-flask-container---force-recreate)
   - [Test 3: Recreate the Entire Multi-Container Application](#test-3-recreate-the-entire-multi-container-application)
   - [CRITICAL WARNING: `docker compose down` vs `docker compose down -v`](#critical-warning-docker-compose-down-vs-docker-compose-down--v)
9. [Inspecting Docker Volumes](#9-inspecting-docker-volumes)
10. [Local Development & Automated Testing (Outside Docker)](#10-local-development--automated-testing-outside-docker)
11. [Troubleshooting & FAQ](#11-troubleshooting--faq)

---

## 1. Project Overview

**Document Vault** solves the classic Docker ephemeral storage dilemma: when a container stops or is recreated, its internal writable filesystem layer is destroyed.

In Document Vault:
- **Actual PDF binaries** are preserved in an independent named volume: `pdf_uploads` (mounted at `/app/uploads` in the Flask container).
- **Document metadata** (UUID, original filename, SHA-256 checksum, size, timestamp) is indexed in PostgreSQL, persisted through its own named volume: `postgres_data` (mounted at `/var/lib/postgresql/data`).
- **Binary validation** strictly verifies genuine `%PDF-` file signatures, preventing renamed executables or corrupted uploads.
- **Continuous UI animations** provide a futuristic, dark-mode glassmorphic control center with ambient orbs, real database statistics, drag-and-drop uploads, live SHA-256 copy, and deletion safeguards.

---

## 2. Core Architecture & Storage Model

```
                    ┌──────────────────────────────────────────────┐
                    │               User Web Browser               │
                    │   (Futuristic Glassmorphic Web Dashboard)    │
                    └──────────────────────┬───────────────────────┘
                                           │ HTTP Port 5000
                                           ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│ Docker Network (bridge)                                                          │
│                                                                                  │
│   ┌───────────────────────────────────┐     TCP 5432     ┌───────────────────┐   │
│   │   Web Service (Flask + Gunicorn)   ├─────────────────►   Database Service│   │
│   │   - PDF Magic Header Validation   │                  │   (PostgreSQL 16) │   │
│   │   - SHA-256 Checksum Streaming    │                  │   - Document meta │   │
│   │   - Atomic File Write & Deletion  │                  │   - UUID indexing │   │
│   └─────────────────┬─────────────────┘                  └─────────┬─────────┘   │
└─────────────────────┼──────────────────────────────────────────────┼─────────────┘
                      │ Mounted at /app/uploads                      │ Mounted at /var/lib/postgresql/data
                      ▼                                              ▼
          ┌───────────────────────┐                      ┌───────────────────────┐
          │  Named Docker Volume  │                      │  Named Docker Volume  │
          │     `pdf_uploads`     │                      │    `postgres_data`    │
          │ (Survives container   │                      │ (Survives container   │
          │  restarts & rebuilds) │                      │  restarts & rebuilds) │
          └───────────────────────┘                      └───────────────────────┘
```

---

## 3. Deep Dive: Docker Concepts Explained

### What is a Docker Image?
A **Docker Image** is an immutable, read-only blueprint containing the source code, libraries, runtime (Python 3.11), system tools, and dependencies required to run the application. Think of an image as a read-only recipe or template.

### What is a Docker Container?
A **Docker Container** is a running instance created from a Docker Image. Containers add a thin, temporary **read-write layer** on top of the image. **Crucial fact:** when a container is stopped and deleted (or rebuilt), everything written inside this temporary read-write layer is permanently destroyed.

### What is a Docker Volume?
A **Docker Volume** is a storage mechanism managed directly by Docker on the host machine's physical storage, **completely outside the container's lifecycle**. Volumes are independent entities:
- Deleting or recreating a container **does not delete** the volume.
- Multiple containers can mount the same volume simultaneously.
- Volumes bypass the container union filesystem for maximum I/O performance.

### Why are Docker Volumes Essential for this Project?
Without Docker Volumes, any PDF uploaded to `/app/uploads` would reside in the container's temporary read-write layer. As soon as you run `docker compose up --build -d` or recreate the container, all uploaded documents would vanish instantly!

By mapping the named volume `pdf_uploads` to `/app/uploads`, Docker ensures the physical PDF files remain safely on host storage across all container recreation operations.

---

## 4. Database & Backend Architecture

### Why PostgreSQL is Used
PostgreSQL was chosen for its reliability, ACID transaction compliance, robust indexing capabilities, and high-performance querying:
- **No Binary Bloat**: Storing raw PDF binary data (BLOBs) inside a relational database drastically degrades query performance, inflates memory cache usage, and complicates database backups. Instead, Document Vault stores only rich metadata (UUID, filename, byte size, SHA-256 hash, timestamps) in PostgreSQL, while the raw files live on the volume filesystem.
- **Relational Integrity**: If database insertion fails during an upload, SQLAlchemy automatically rolls back the transaction, and the backend cleans up the orphaned file on disk.

### How Flask Operates in this System
The Flask application is packaged as a modular application factory with clean blueprint routing:
- `app/routes/main.py`: Serves the dashboard, performs live checks on disk for every database record, and calculates actual aggregate metrics.
- `app/routes/documents.py`: Handles streaming uploads, secure downloads via `send_from_directory`, and atomic deletions.
- `app/routes/health.py`: Healthcheck endpoint verifying PostgreSQL connectivity (`SELECT 1`) and volume filesystem writability.

### How PDF Uploads are Handled and Stored
1. **Selection & Sanitization**: Filename is secured with `secure_filename`.
2. **Signature Verification**: First 1024 bytes are scanned for the mandatory PDF magic signature: `b'%PDF-'`. Plaintext, images, or executables renamed to `.pdf` are rejected.
3. **SHA-256 Generation**: The file stream is read in memory-efficient 64 KB chunks to generate an exact cryptographic digest.
4. **UUID Stored Filename**: The file is assigned a random UUID filename (e.g. `c7f18b32...pdf`). This prevents filename collisions when two different users upload files with the exact same name (e.g. `resume.pdf`).
5. **Atomic Write**: The file is written to a temporary hidden file in `/app/uploads` and atomically moved into place using `os.replace`.
6. **Transaction Commit**: Metadata is inserted into PostgreSQL. If the database commit fails, the uploaded file is purged immediately.

### How Docker Compose Connects the Services
Docker Compose orchestrates both services on a private bridge network:
- The `web` service depends on `db` with `condition: service_healthy`.
- Gunicorn does not accept traffic until PostgreSQL passes its internal `pg_isready` health check.
- Environment variables are injected from `.env`.

---

## 5. Prerequisites & System Setup on Windows 11

To run this application locally on Windows 11:

1. **Install Docker Desktop**:
   - Download and install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/).
   - During installation, ensure the **Use WSL 2 instead of Hyper-V** option is selected (recommended by Microsoft and Docker).
2. **Start Docker Desktop**:
   - Open Docker Desktop from the Start Menu.
   - Wait until the status icon in the bottom-left turns green: **"Engine running"**.
3. **Verify in Windows PowerShell**:
   Open Windows 11 PowerShell and run:
   ```powershell
   docker --version
   docker compose version
   ```

---

## 6. Environment Configuration (`.env`)

A default, ready-to-run `.env` file is included in the project root. For custom deployments:

1. Copy `.env.example` to `.env`:
   ```powershell
   Copy-Item .env.example .env
   ```
2. Inspect or modify key parameters:
   - `POSTGRES_DB`: Name of the database (default: `document_vault`)
   - `POSTGRES_USER`: Database username (default: `vault_user`)
   - `POSTGRES_PASSWORD`: Strong password (default: `vault_secure_password_9872`)
   - `APP_PORT`: Local Windows port mapped to the web interface (default: `5000`)
   - `MAX_CONTENT_LENGTH`: Maximum allowed file size in bytes (default: `16777216` = 16 MB)
   - `SECRET_KEY`: Cryptographic key for CSRF tokens and session security.

> **Security Note:** The `.env` file contains sensitive database passwords and is ignored by `.gitignore`. Never commit `.env` into public Git repositories.

---

## 7. Running the Application with Docker Compose

Open Windows PowerShell in the project directory:

### Building the Application
Build the production Docker image using pinned dependencies:
```powershell
docker compose build
```

### Starting the Containers
Start all services in detached mode:
```powershell
docker compose up -d
```
Docker Compose will:
1. Create named volumes `pdf_uploads` and `postgres_data`.
2. Start the PostgreSQL container and wait for the health probe.
3. Apply database migrations / schema initialization.
4. Launch the Gunicorn production server.

### Verifying Service Status
```powershell
docker compose ps
```
Both `document_vault_web` and `document_vault_db` should display status `Up (healthy)`.

Open your browser and navigate to:
```
http://localhost:5000
```

### Stopping the Containers
To stop containers safely:
```powershell
docker compose stop
```
Or to stop and remove containers (while **preserving** all uploaded PDFs and database data):
```powershell
docker compose down
```

### Viewing Container Logs
To follow live application and database logs:
```powershell
docker compose logs -f
```
To view web container logs specifically:
```powershell
docker compose logs -f web
```

---

## 8. Persistence Verification: Step-by-Step Testing Guide

This is the core objective of the system: proving that uploaded PDF files and PostgreSQL records survive complete container destruction.

### Test 1: Initial PDF Upload
1. Generate a valid sample PDF or use any real PDF on your computer:
   ```powershell
   python scripts\generate_sample_pdf.py test_whitepaper.pdf
   ```
2. Open `http://localhost:5000` in your web browser.
3. Drag and drop `test_whitepaper.pdf` into the upload zone and click **Upload to Persistent Storage**.
4. Confirm:
   - The file appears in the **Persistent Document Index** table.
   - Volume status displays a green badge: **"In Volume"**.
   - Note the **UUID** and **SHA-256 Checksum**.

### Test 2: Recreate Flask Container (`--force-recreate`)
Recreate only the web application container:
```powershell
docker compose up -d --force-recreate web
```
Then:
1. Refresh `http://localhost:5000`.
2. Confirm the document remains listed in the table.
3. Click the **Download** button.
4. Verify the downloaded PDF opens perfectly and the content matches.

### Test 3: Recreate the Entire Multi-Container Application
Destroy both containers and recreate everything from scratch:
```powershell
docker compose down
docker compose up --build -d
```
Then:
1. Refresh `http://localhost:5000`.
2. Verify:
   - PostgreSQL retained all metadata records.
   - `pdf_uploads` volume retained all physical PDF binaries.
   - All documents show green **"In Volume"** status.
   - Download the file again and verify its SHA-256 checksum matches the original.

---

### CRITICAL WARNING: `docker compose down` vs `docker compose down -v`

> [!CAUTION]
> ### UNDERSTANDING THE DESTRUCTIVE `-v` FLAG
>
> - **`docker compose down` (SAFE)**:
>   Stops and removes containers and the virtual network. **Named Docker Volumes are completely preserved.** Your uploaded PDFs and database records remain safe and ready for the next container launch.
>
> - **`docker compose down -v` (PERMANENT DATA LOSS)**:
>   The `-v` (or `--volumes`) flag instructs Docker to **permanently delete all named volumes** (`pdf_uploads` and `postgres_data`).
>   All uploaded PDF files and database records will be erased irrevocably.
>
> **NEVER use `docker compose down -v` during standard maintenance or container restarts!**

---

## 9. Inspecting Docker Volumes

You can directly inspect the named volumes managed by Docker on Windows:

### List All Docker Volumes
```powershell
docker volume ls
```
You will see:
```
DRIVER    VOLUME NAME
local     pdf_uploads
local     postgres_data
```

### Inspect Volume Details
```powershell
docker volume inspect pdf_uploads
docker volume inspect postgres_data
```

### View Files Inside the `pdf_uploads` Volume
To see the actual files stored in the volume without opening a shell:
```powershell
docker compose exec web ls -lah /app/uploads
```

---

## 10. Local Development & Automated Testing (Outside Docker)

The project includes a comprehensive Pytest test suite (27 automated unit and integration tests) verifying PDF header inspection, size limits, SHA-256 calculation, atomic storage rollbacks, and route security.

To run the automated tests directly on Windows using Python:
```powershell
python -m pytest tests -v
```

All 27 tests run in an isolated in-memory testing environment without modifying production volumes or databases.

---

## 11. Troubleshooting & FAQ

### 1. `docker: The term 'docker' is not recognized`
**Cause:** Docker Desktop is not installed, or its executable directory is not added to your system `PATH`.  
**Solution:** Install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/), start Docker Desktop, and restart PowerShell.

### 2. Port 5000 is Already in Use
**Cause:** Another local service is using port 5000.  
**Solution:** Change `APP_PORT` in your `.env` file (e.g. `APP_PORT=8080`) and restart with `docker compose up -d`. Access the web app at `http://localhost:8080`.

### 3. "File signature verification failed" During Upload
**Cause:** The uploaded file has a `.pdf` extension, but does not start with the standard `%PDF-` binary magic bytes.  
**Solution:** Upload a genuine PDF document created by a PDF generator or viewer.

### 4. Health Check Returns "Degraded" or Status 503
**Cause:** The upload directory permissions are read-only or PostgreSQL is not accepting queries.  
**Solution:** Inspect logs using `docker compose logs -f web` and check database readiness.
