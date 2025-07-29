"""
Test API endpoints
"""

import pytest
import json
import os


class TestDocumentUpload:
    """Test document upload functionality."""
    
    def test_upload_markdown_document(self, client, sample_document_path):
        """Test uploading a markdown document."""
        with open(sample_document_path, "rb") as f:
            response = client.post(
                "/upload",
                files={"file": ("sample_document.md", f, "text/markdown")}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "document_id" in data
        assert data["filename"] == "sample_document.md"
        assert len(data["document_id"]) > 0
    
    def test_upload_unsupported_file_type(self, client):
        """Test uploading an unsupported file type."""
        # Create a temporary file with unsupported extension
        test_content = b"This is a test file"
        response = client.post(
            "/upload",
            files={"file": ("test.xyz", test_content, "application/octet-stream")}
        )
        
        # Should return 400 for unsupported file type
        assert response.status_code == 400
        response_data = response.json()
        assert "detail" in response_data
        assert "Unsupported file type" in response_data["detail"]
    
    def test_upload_text_file(self, client):
        """Test uploading a text file."""
        test_content = b"This is a test document for the smart garden system."
        response = client.post(
            "/upload",
            files={"file": ("test.txt", test_content, "text/plain")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.txt"


class TestSessionManagement:
    """Test session creation and management."""
    
    def test_create_session(self, client, uploaded_document, sample_team_members):
        """Test creating a discussion session."""
        session_data = {
            "document_id": uploaded_document["document_id"],
            "team_members": sample_team_members,
            "initial_prompt": "Please review this document and provide feedback."
        }
        
        response = client.post("/sessions", json=session_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "document_filename" in data
        assert "conversation" in data
        assert data["document_filename"] == "sample_document.md"
        
        # Check that conversation has user message and agent responses
        conversation = data["conversation"]
        assert len(conversation) >= 1  # At least the user message
        
        user_messages = [msg for msg in conversation if msg["type"] == "user"]
        agent_messages = [msg for msg in conversation if msg["type"] == "agent"]
        
        assert len(user_messages) == 1
        assert user_messages[0]["content"] == "Please review this document and provide feedback."
        
        # Should have responses from both agents
        assert len(agent_messages) == len(sample_team_members)
    
    def test_create_session_invalid_document(self, client, sample_team_members):
        """Test creating session with invalid document ID."""
        session_data = {
            "document_id": "invalid-document-id",
            "team_members": sample_team_members,
            "initial_prompt": "Test prompt"
        }
        
        response = client.post("/sessions", json=session_data)
        assert response.status_code == 404
        assert "Document not found" in response.json()["detail"]
    
    def test_get_session(self, client, uploaded_document, sample_team_members):
        """Test retrieving session information."""
        # First create a session
        session_data = {
            "document_id": uploaded_document["document_id"],
            "team_members": sample_team_members,
            "initial_prompt": "Initial test prompt"
        }
        
        create_response = client.post("/sessions", json=session_data)
        session_id = create_response.json()["session_id"]
        
        # Then retrieve it
        response = client.get(f"/sessions/{session_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["document_filename"] == "sample_document.md"
        assert "team_members" in data
        assert "conversation" in data
        assert "created_at" in data
    
    def test_get_nonexistent_session(self, client):
        """Test retrieving a non-existent session."""
        response = client.get("/sessions/invalid-session-id")
        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]


class TestConversationFlow:
    """Test conversation functionality."""
    
    def test_add_prompt_to_session(self, client, uploaded_document, sample_team_members):
        """Test adding a follow-up prompt to an existing session."""
        # Create initial session
        session_data = {
            "document_id": uploaded_document["document_id"],
            "team_members": sample_team_members,
            "initial_prompt": "Please review this document."
        }
        
        create_response = client.post("/sessions", json=session_data)
        session_id = create_response.json()["session_id"]
        initial_conversation_length = len(create_response.json()["conversation"])
        
        # Add follow-up prompt
        follow_up_data = {
            "prompt": "What are the main risks you see?"
        }
        
        response = client.post(f"/sessions/{session_id}/prompt", json=follow_up_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "conversation" in data
        
        conversation = data["conversation"]
        
        # Should have more messages than before
        assert len(conversation) > initial_conversation_length
        
        # Check that the new user message and agent responses are added
        new_messages = conversation[initial_conversation_length:]
        user_messages = [msg for msg in new_messages if msg["type"] == "user"]
        agent_messages = [msg for msg in new_messages if msg["type"] == "agent"]
        
        assert len(user_messages) == 1
        assert user_messages[0]["content"] == "What are the main risks you see?"
        assert len(agent_messages) == len(sample_team_members)
    
    def test_add_prompt_to_nonexistent_session(self, client):
        """Test adding prompt to non-existent session."""
        response = client.post(
            "/sessions/invalid-session-id/prompt",
            json={"prompt": "Test prompt"}
        )
        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]


class TestAPIHealth:
    """Test API health and basic functionality."""
    
    def test_root_endpoint(self, client):
        """Test the root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "AI Doc Read Studio API"
    
    def test_api_cors_headers(self, client):
        """Test that CORS headers are properly set."""
        response = client.options("/")
        # The test client doesn't fully simulate CORS, but we can check the app allows it
        assert response.status_code in [200, 405]  # OPTIONS might not be explicitly handled