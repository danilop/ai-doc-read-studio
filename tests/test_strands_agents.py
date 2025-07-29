"""
Test Strands Agents integration
"""
import pytest
import asyncio
import os
import json
import sys

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strands import Agent

# Load configuration
def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load config file: {e}")
        return {}

config = load_config()

def get_test_model_id():
    """Get a model ID from config for testing."""
    models = config.get("models", {}).get("available", [])
    if models:
        # Use the first available model for testing
        return models[0]["bedrock_id"]
    return "us.amazon.nova-lite-v1:0"  # Fallback

@pytest.mark.asyncio
async def test_single_agent():
    """Test a single Strands Agent with Amazon Bedrock using Amazon Nova"""
    
    try:
        print("🔍 Testing single Strands Agent...")
        
        # Create agent with model from config
        agent = Agent(
            name="Test Agent",
            system_prompt="You are a Product Manager analyzing documents for strategic insights.",
            model=get_test_model_id()
        )
        
        # Test prompt
        prompt = "What are the key benefits of using AI in document review processes?"
        
        print(f"📝 Sending prompt: {prompt}")
        
        # Get response
        response = await agent.invoke_async(prompt)
        
        print(f"✅ Agent Response: {response}")
        # Fix the length check for AgentResult objects
        response_text = str(response)
        print(f"📊 Response length: {len(response_text)} characters")
        assert len(response_text) > 0
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing agent: {e}")
        return False

@pytest.mark.asyncio
async def test_agent_with_context():
    """Test agent with document context"""
    
    try:
        print("\n🔍 Testing agent with document context...")
        
        document_content = """
        # Smart Garden System Proposal
        
        ## Market Analysis
        The smart gardening market is valued at $15.3 billion and growing at 12% annually.
        
        ## Technical Requirements
        - IoT sensors for soil moisture, temperature, and light
        - Mobile app for remote monitoring
        - Automated watering system
        """
        
        # Create agent with context
        agent = Agent(
            name="Tech Lead",
            system_prompt="You are a Tech Lead responsible for technical architecture and implementation. Analyze documents for technical feasibility and implementation challenges.",
            model=get_test_model_id()
        )
        
        # Test prompt with context
        prompt = f"""
        Document Content:
        {document_content}
        
        Question: What are the main technical challenges in implementing this smart garden system?
        """
        
        print(f"📝 Sending contextual prompt...")
        
        # Get response
        response = await agent.invoke_async(prompt)
        
        print(f"✅ Agent Response: {response}")
        # Fix the length check for AgentResult objects
        response_text = str(response)
        print(f"📊 Response length: {len(response_text)} characters")
        assert len(response_text) > 0
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing agent with context: {e}")
        return False

class TestStrandsAgents:
    """Test Strands Agents integration with Amazon Bedrock using Amazon Nova models"""
    
    @pytest.mark.asyncio
    async def test_agent_basic_functionality(self):
        """Test basic agent functionality"""
        result = await test_single_agent()
        assert result == True
    
    @pytest.mark.asyncio  
    async def test_agent_with_document_context(self):
        """Test agent with document context"""
        result = await test_agent_with_context()
        assert result == True