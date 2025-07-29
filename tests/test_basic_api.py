"""
Test basic API functionality
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
import json
import os

client = TestClient(app)


class TestBasicAPI:
    """Test basic API endpoints."""
    
    def test_root_endpoint(self):
        """Test the root endpoint returns expected message."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "AI Doc Read Studio API"}
    
    def test_file_upload(self):
        """Test file upload functionality."""
        test_content = b"# Test Document\n\nThis is a test document for upload."
        files = {"file": ("test.md", test_content, "text/markdown")}
        
        response = client.post("/upload", files=files)
        assert response.status_code == 200
        
        data = response.json()
        assert "document_id" in data
        assert "filename" in data
        assert data["filename"] == "test.md"
        # Note: The API doesn't return content_type or size in the response
    
    def test_upload_file_size_limit(self):
        """Test file size limit enforcement."""
        # Create a file larger than 10MB
        large_content = b"x" * (11 * 1024 * 1024)  # 11MB
        files = {"file": ("large.txt", large_content, "text/plain")}
        
        response = client.post("/upload", files=files)
        assert response.status_code == 413
        assert "too large" in response.json()["detail"].lower()
    
    def test_upload_invalid_file_type(self):
        """Test rejection of invalid file types."""
        test_content = b"fake executable content"
        files = {"file": ("test.exe", test_content, "application/x-msdownload")}
        
        response = client.post("/upload", files=files)
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]
    
    def test_create_session(self):
        """Test session creation."""
        # First upload a document
        test_content = b"Test document for session"
        files = {"file": ("session_test.txt", test_content, "text/plain")}
        upload_response = client.post("/upload", files=files)
        document_id = upload_response.json()["document_id"]
        
        # Create session
        session_data = {
            "document_ids": [document_id],
            "team_members": [
                {
                    "id": "pm",
                    "name": "Product Manager",
                    "role": "Product strategy",
                    "model": "nova-lite"
                }
            ],
            "initial_prompt": "Please review this document and provide feedback."
        }
        
        response = client.post("/sessions", json=session_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "session_id" in data
        # The API returns the actual session response with agent responses
    
    def test_get_session(self):
        """Test retrieving session information."""
        # Create a session first
        test_content = b"Test document"
        files = {"file": ("test.txt", test_content, "text/plain")}
        upload_response = client.post("/upload", files=files)
        document_id = upload_response.json()["document_id"]
        
        session_data = {
            "document_ids": [document_id],
            "team_members": [
                {
                    "id": "dev",
                    "name": "Developer",
                    "role": "Technical implementation",
                    "model": "nova-lite"
                }
            ],
            "initial_prompt": "Please analyze this document for technical issues."
        }
        
        create_response = client.post("/sessions", json=session_data)
        session_id = create_response.json()["session_id"]
        
        # Get session
        response = client.get(f"/sessions/{session_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["session_id"] == session_id
        assert "conversation" in data
        assert "team_members" in data
        assert len(data["team_members"]) == 1
        assert data["team_members"][0]["name"] == "Developer"
    
    def test_get_nonexistent_session(self):
        """Test getting a non-existent session returns 404."""
        response = client.get("/sessions/nonexistent-session-id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_agent_templates_endpoint(self):
        """Test agent templates endpoint."""
        response = client.get("/agent-templates")
        assert response.status_code == 200
        
        data = response.json()
        assert "categories" in data or "templates" in data
        # The API structure may vary, but it should return template data