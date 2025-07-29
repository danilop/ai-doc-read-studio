"""
Test that all imports work correctly after recent changes
"""

import pytest
import sys
import os


class TestImports:
    """Test module imports after recent refactoring."""
    
    def test_backend_main_imports(self):
        """Test that backend.main can be imported without errors."""
        try:
            from backend import main
            assert hasattr(main, 'app')
            assert hasattr(main, 'logger')
        except ImportError as e:
            pytest.fail(f"Failed to import backend.main: {e}")
    
    def test_cost_tracker_imports(self):
        """Test that cost_tracker module imports correctly."""
        try:
            from backend.cost_tracker import cost_tracker, CostTracker
            assert cost_tracker is not None
            assert isinstance(cost_tracker, CostTracker)
        except ImportError as e:
            pytest.fail(f"Failed to import cost_tracker: {e}")
    
    def test_agents_module_imports(self):
        """Test that agents module imports correctly."""
        try:
            from backend.agents import (
                get_bedrock_model_id, 
                MODEL_MAPPING,
                create_agent,
                run_discussion_round
            )
            assert callable(get_bedrock_model_id)
            assert isinstance(MODEL_MAPPING, dict)
            assert callable(create_agent)
            assert callable(run_discussion_round)
        except ImportError as e:
            pytest.fail(f"Failed to import from agents module: {e}")
    
    def test_document_parser_imports(self):
        """Test that document_parser imports correctly."""
        try:
            from backend.document_parser import parse_document
            assert callable(parse_document)
        except ImportError as e:
            pytest.fail(f"Failed to import document_parser: {e}")
    
    def test_structlog_logger_usage(self):
        """Test that modules use structlog correctly."""
        from backend.cost_tracker import logger as cost_logger
        from backend.agents import logger as agents_logger
        
        # Both should be structlog loggers
        assert hasattr(cost_logger, 'info')
        assert hasattr(cost_logger, 'error')
        assert hasattr(agents_logger, 'info')
        assert hasattr(agents_logger, 'error')
    
    def test_circular_imports(self):
        """Test that there are no circular import issues."""
        # This would fail if there were circular imports
        try:
            from backend.main import app
            from backend.agents import run_discussion_round
            from backend.cost_tracker import cost_tracker
            from backend.document_parser import parse_document
            
            # All imports should succeed
            assert app is not None
            assert run_discussion_round is not None
            assert cost_tracker is not None
            assert parse_document is not None
        except ImportError as e:
            pytest.fail(f"Circular import detected: {e}")