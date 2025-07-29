"""
Integration tests for the complete application flow
"""

import pytest
import time
from unittest.mock import patch


class TestCompleteWorkflow:
    """Test the complete document review workflow."""
    
    def test_full_document_review_workflow(self, client, sample_document_path, sample_team_members):
        """Test the complete workflow from document upload to discussion."""
        
        # Step 1: Upload document
        with open(sample_document_path, "rb") as f:
            upload_response = client.post(
                "/upload",
                files={"file": ("sample_document.md", f, "text/markdown")}
            )
        
        assert upload_response.status_code == 200
        document_data = upload_response.json()
        document_id = document_data["document_id"]
        
        # Step 2: Create discussion session
        session_data = {
            "document_id": document_id,
            "team_members": sample_team_members,
            "initial_prompt": "Please analyze this smart garden system proposal from your expertise areas."
        }
        
        session_response = client.post("/sessions", json=session_data)
        assert session_response.status_code == 200
        
        session_data = session_response.json()
        session_id = session_data["session_id"]
        
        # Verify session was created properly
        assert "conversation" in session_data
        assert session_data["document_filename"] == "sample_document.md"
        
        conversation = session_data["conversation"]
        
        # Should have user message + responses from both team members
        user_messages = [msg for msg in conversation if msg["type"] == "user"]
        agent_messages = [msg for msg in conversation if msg["type"] == "agent"]
        
        assert len(user_messages) == 1
        assert len(agent_messages) == 2  # Two team members
        
        # Step 3: Add follow-up questions
        follow_up_prompts = [
            "What are the biggest technical risks?",
            "How should we price this product?",
            "What's the competitive landscape like?"
        ]
        
        for prompt in follow_up_prompts:
            follow_up_response = client.post(
                f"/sessions/{session_id}/prompt",
                json={"prompt": prompt}
            )
            
            assert follow_up_response.status_code == 200
            
            updated_conversation = follow_up_response.json()["conversation"]
            
            # Should have new user message and agent responses
            new_user_messages = [msg for msg in updated_conversation if msg["type"] == "user" and msg["content"] == prompt]
            assert len(new_user_messages) == 1
        
        # Step 4: Verify final session state
        final_session_response = client.get(f"/sessions/{session_id}")
        assert final_session_response.status_code == 200
        
        final_session_data = final_session_response.json()
        final_conversation = final_session_data["conversation"]
        
        # Should have initial prompt + 3 follow-ups = 4 user messages
        # Plus 2 agent responses per round = 8 agent messages total
        final_user_messages = [msg for msg in final_conversation if msg["type"] == "user"]
        final_agent_messages = [msg for msg in final_conversation if msg["type"] == "agent"]
        
        assert len(final_user_messages) == 4  # Initial + 3 follow-ups
        assert len(final_agent_messages) == 8  # 2 agents × 4 rounds
    
    def test_multiple_sessions_same_document(self, client, sample_document_path, sample_team_members):
        """Test creating multiple sessions for the same document."""
        
        # Upload document once
        with open(sample_document_path, "rb") as f:
            upload_response = client.post(
                "/upload",
                files={"file": ("sample_document.md", f, "text/markdown")}
            )
        
        document_id = upload_response.json()["document_id"]
        
        # Create multiple sessions with different initial prompts
        prompts = [
            "Focus on the market opportunity",
            "Analyze the technical feasibility",
            "Evaluate the financial projections"
        ]
        
        session_ids = []
        
        for prompt in prompts:
            session_data = {
                "document_id": document_id,
                "team_members": sample_team_members,
                "initial_prompt": prompt
            }
            
            response = client.post("/sessions", json=session_data)
            assert response.status_code == 200
            
            session_id = response.json()["session_id"]
            session_ids.append(session_id)
        
        # Verify all sessions are independent
        assert len(set(session_ids)) == 3  # All unique session IDs
        
        # Verify each session has the correct initial prompt
        for i, session_id in enumerate(session_ids):
            session_response = client.get(f"/sessions/{session_id}")
            conversation = session_response.json()["conversation"]
            
            user_messages = [msg for msg in conversation if msg["type"] == "user"]
            assert len(user_messages) == 1
            assert user_messages[0]["content"] == prompts[i]
    
    def test_session_conversation_context_preservation(self, client, sample_document_path, sample_team_members):
        """Test that conversation context is preserved across multiple rounds."""
        
        # Upload and create session
        with open(sample_document_path, "rb") as f:
            upload_response = client.post(
                "/upload",
                files={"file": ("sample_document.md", f, "text/markdown")}
            )
        
        document_id = upload_response.json()["document_id"]
        
        session_data = {
            "document_id": document_id,
            "team_members": sample_team_members,
            "initial_prompt": "What do you think about the market size mentioned in this document?"
        }
        
        session_response = client.post("/sessions", json=session_data)
        session_id = session_response.json()["session_id"]
        
        # Add a follow-up that references previous discussion
        follow_up_response = client.post(
            f"/sessions/{session_id}/prompt",
            json={"prompt": "Based on your previous analysis, what would you recommend as next steps?"}
        )
        
        assert follow_up_response.status_code == 200
        
        conversation = follow_up_response.json()["conversation"]
        
        # Get the latest agent responses (should reference previous discussion)
        latest_agent_messages = [msg for msg in conversation if msg["type"] == "agent"][-2:]  # Last 2 agent responses
        
        # In follow-up rounds, agents should include contextual phrases
        for msg in latest_agent_messages:
            content = str(msg["content"]).lower()  # Convert to string in case it's not
            # Should show some indication of building on previous discussion
            assert any(phrase in content for phrase in [
                "building on", "following up", "considering", "previous", "mentioned", "based on", "analysis",
                "earlier", "initially", "first", "continuing", "addition", "further", "also", "moreover",
                "furthermore", "recommend", "suggest", "next steps", "moving forward", "approach"
            ])
    
    def test_error_handling_workflow(self, client, sample_team_members):
        """Test error handling in the workflow."""
        
        # Test session creation with invalid document
        invalid_session_data = {
            "document_id": "nonexistent-document-id",
            "team_members": sample_team_members,
            "initial_prompt": "Test prompt"
        }
        
        response = client.post("/sessions", json=invalid_session_data)
        assert response.status_code == 404
        
        # Test adding prompt to nonexistent session
        response = client.post(
            "/sessions/nonexistent-session-id/prompt",
            json={"prompt": "Test prompt"}
        )
        assert response.status_code == 404
    
    def test_document_content_in_agent_responses(self, client, sample_document_path, sample_team_members):
        """Test that agents actually reference document content in their responses."""
        
        # Upload document
        with open(sample_document_path, "rb") as f:
            upload_response = client.post(
                "/upload",
                files={"file": ("sample_document.md", f, "text/markdown")}
            )
        
        document_id = upload_response.json()["document_id"]
        
        # Create session with specific prompt about document content
        session_data = {
            "document_id": document_id,
            "team_members": sample_team_members,
            "initial_prompt": "What do you think about the $15.3 billion market size mentioned in this document?"
        }
        
        session_response = client.post("/sessions", json=session_data)
        conversation = session_response.json()["conversation"]
        
        agent_messages = [msg for msg in conversation if msg["type"] == "agent"]
        
        # At least one agent should reference the market size or related concepts
        market_references = 0
        for msg in agent_messages:
            content_lower = str(msg["content"]).lower()  # Convert to string in case it's not
            if any(term in content_lower for term in ["market", "billion", "revenue", "financial"]):
                market_references += 1
        
        assert market_references > 0, "Agents should reference document content in their responses"