"""
Test agent functionality and responses
"""

import pytest
from unittest.mock import Mock, patch
from backend.agents import get_bedrock_model_id, MODEL_MAPPING
# Remove mock_agents import - will use mocking instead


class TestModelMapping:
    """Test model ID mapping functionality."""
    
    def test_get_bedrock_model_id_valid_models(self):
        """Test getting Bedrock model IDs for valid models."""
        assert get_bedrock_model_id("nova-micro") == "amazon.nova-micro-v1:0"
        assert get_bedrock_model_id("nova-lite") == "amazon.nova-lite-v1:0"
        assert get_bedrock_model_id("nova-pro") == "amazon.nova-pro-v1:0"
        assert get_bedrock_model_id("nova-premier") == "amazon.nova-premier-v1:0"
    
    def test_get_bedrock_model_id_invalid_model(self):
        """Test getting model ID for invalid model name (should default to nova-pro)."""
        assert get_bedrock_model_id("invalid-model") == "amazon.nova-pro-v1:0"
        assert get_bedrock_model_id("") == "amazon.nova-pro-v1:0"
        assert get_bedrock_model_id(None) == "amazon.nova-pro-v1:0"
    
    def test_model_mapping_completeness(self):
        """Test that all expected models are in the mapping."""
        expected_models = ["nova-micro", "nova-lite", "nova-pro", "nova-premier"]
        for model in expected_models:
            assert model in MODEL_MAPPING
            assert MODEL_MAPPING[model].startswith("amazon.nova")
            assert MODEL_MAPPING[model].endswith("-v1:0")


class TestMockAgents:
    """Test mock agent functionality."""
    
    def test_generate_contextual_response_product_manager(self):
        """Test contextual response generation for Product Manager role."""
        document_content = """
        # Product Proposal
        This document outlines a market opportunity worth $50M in revenue.
        The competitive landscape includes several key players.
        """
        
        response = generate_contextual_response(
            "Product Manager",
            document_content,
            "What do you think about this proposal?",
            ""
        )
        
        assert isinstance(response, str)
        assert len(response) > 50
        assert any(word in response.lower() for word in ["market", "revenue", "competitive"])
    
    def test_generate_contextual_response_tech_lead(self):
        """Test contextual response generation for Tech Lead role."""
        document_content = """
        # Technical Architecture
        The system requires REST APIs and cloud architecture.
        We need to consider scalability and security protocols.
        """
        
        response = generate_contextual_response(
            "Tech Lead",
            document_content,
            "What are your technical concerns?",
            ""
        )
        
        assert isinstance(response, str)
        assert len(response) > 50
        assert any(word in response.lower() for word in ["technical", "architecture", "scalability"])
    
    def test_generate_contextual_response_ux_designer(self):
        """Test contextual response generation for UX Designer role."""
        response = generate_contextual_response(
            "UX Designer",
            "Any document content",
            "How's the user experience?",
            ""
        )
        
        assert isinstance(response, str)
        assert "user experience" in response.lower()
        assert len(response) > 50
    
    def test_generate_contextual_response_default_role(self):
        """Test contextual response generation for unknown role."""
        response = generate_contextual_response(
            "Marketing Specialist",
            "Document content here",
            "What do you think?",
            ""
        )
        
        assert isinstance(response, str)
        assert "marketing specialist" in response.lower()
        assert len(response) > 30
    
    @pytest.mark.asyncio
    async def test_run_discussion_round_basic(self):
        """Test basic discussion round functionality."""
        # Create mock session and document
        mock_session = Mock()
        mock_session.conversation = []
        
        # Create mock team members
        mock_member1 = Mock()
        mock_member1.id = "pm"
        mock_member1.name = "Product Manager"
        mock_member1.role = "Product Strategy"
        mock_member1.model = "nova-lite"
        
        mock_member2 = Mock()
        mock_member2.id = "tech"
        mock_member2.name = "Tech Lead"
        mock_member2.role = "Technical Architecture"
        mock_member2.model = "nova-lite"
        
        mock_session.team_members = [mock_member1, mock_member2]
        
        mock_document = {
            "path": "tests/sample_document.md"
        }
        
        responses = await run_discussion_round(
            mock_session,
            mock_document,
            "Please review this document."
        )
        
        assert isinstance(responses, list)
        assert len(responses) == 2  # One response per team member
        
        for response in responses:
            assert response["type"] == "agent"
            assert "agent_id" in response
            assert "agent_name" in response
            assert "role" in response
            assert "model" in response
            assert "content" in response
            assert "timestamp" in response
            assert len(response["content"]) > 0
    
    @pytest.mark.asyncio
    async def test_run_discussion_round_with_conversation_history(self):
        """Test discussion round with existing conversation history."""
        # Create mock session with conversation history
        mock_session = Mock()
        mock_session.conversation = [
            {
                "type": "user",
                "content": "Previous user message"
            },
            {
                "type": "agent",
                "agent_name": "Product Manager",
                "role": "Product Strategy",
                "content": "Previous agent response"
            }
        ]
        
        mock_member = Mock()
        mock_member.id = "pm"
        mock_member.name = "Product Manager"
        mock_member.role = "Product Strategy"
        mock_member.model = "nova-lite"
        
        mock_session.team_members = [mock_member]
        
        mock_document = {
            "path": "tests/sample_document.md"
        }
        
        responses = await run_discussion_round(
            mock_session,
            mock_document,
            "Follow-up question"
        )
        
        assert len(responses) == 1
        response = responses[0]
        
        # Should include contextual intro for follow-up discussions
        content_lower = response["content"].lower()
        assert any(phrase in content_lower for phrase in [
            "building on", "following up", "considering", "to add"
        ])
    
    def test_mock_agent_document_content_analysis(self):
        """Test that mock agents actually analyze document content."""
        # Test with document containing market information
        market_doc = "This proposal shows a $10M market opportunity with strong revenue potential."
        pm_response = generate_contextual_response(
            "Product Manager",
            market_doc,
            "What do you think?",
            ""
        )
        assert "market opportunity" in pm_response.lower()
        
        # Test with document containing technical information
        tech_doc = "The technical architecture requires scalable APIs and robust security protocols."
        tech_response = generate_contextual_response(
            "Tech Lead",
            tech_doc,
            "Technical thoughts?",
            ""
        )
        assert "technical architecture" in tech_response.lower()