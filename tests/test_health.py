"""Tests for Health Check Endpoint.
Verifies response codes, JSON structure, and error reporting.
"""
from unittest.mock import patch


def test_health_check_healthy(client):
    """Test health check returns 200 and healthy JSON when DB and storage are operating normally."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"
    assert data["checks"]["application"]["status"] == "up"
    assert data["checks"]["database"]["status"] == "connected"
    assert data["checks"]["storage"]["accessible"] is True
    assert data["checks"]["storage"]["writable"] is True


def test_health_check_database_failure(client):
    """Test health check returns 503 when the database fails to respond."""
    with patch("app.routes.health.db.session.execute") as mock_exec:
        mock_exec.side_effect = Exception("Database connection refused")
        response = client.get("/health")
        assert response.status_code == 503
        data = response.get_json()
        assert data["status"] == "unhealthy"
        assert data["checks"]["database"]["status"] == "error"
        assert "Database connection refused" in data["checks"]["database"]["error"]


def test_health_check_storage_failure(client):
    """Test health check returns 503 when storage directory is not writable."""
    with patch("app.services.storage.StorageService.check_health") as mock_storage_health:
        mock_storage_health.return_value = (True, False, "Read-only filesystem")
        response = client.get("/health")
        assert response.status_code == 503
        data = response.get_json()
        assert data["status"] == "unhealthy"
        assert data["checks"]["storage"]["status"] == "degraded"
