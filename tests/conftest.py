"""
Test configuration and fixtures for AI Doc Read Studio
"""

import pytest
import asyncio
import sys
import os
from pathlib import Path

# Add backend directory to Python path for imports
backend_dir = Path(__file__).parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from backend.main import app
import tempfile
import shutil

@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)

@pytest.fixture
def sample_document_path():
    """Path to the sample test document."""
    return os.path.join(os.path.dirname(__file__), "sample_document.md")

@pytest.fixture
def sample_team_members():
    """Standard team configuration for tests."""
    return [
        {
            "id": "pm",
            "name": "Product Manager",
            "role": "Product Strategy and Market Analysis",
            "model": "nova-lite"
        },
        {
            "id": "tech",
            "name": "Tech Lead",
            "role": "Technical Architecture and Implementation", 
            "model": "nova-lite"
        }
    ]

@pytest.fixture
def uploaded_document(client, sample_document_path):
    """Upload a document and return the document ID."""
    with open(sample_document_path, "rb") as f:
        response = client.post(
            "/upload",
            files={"file": ("sample_document.md", f, "text/markdown")}
        )
    assert response.status_code == 200
    return response.json()

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up and clean up test environment."""
    # Create temporary directories for uploads and sessions
    upload_dir = "uploads"
    session_dir = "sessions"
    
    # Create directories if they don't exist
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(session_dir, exist_ok=True)
    
    yield
    
    # Cleanup is handled by the application's normal flow
    # We don't want to delete all uploads as other tests might be running