"""
Test document parsing functionality
"""

import pytest
import tempfile
import os
from backend.document_parser import parse_document, parse_txt, parse_markdown


class TestDocumentParser:
    """Test document parsing utilities."""
    
    def test_parse_markdown_file(self, sample_document_path):
        """Test parsing a markdown file."""
        content = parse_document(sample_document_path)
        
        assert isinstance(content, str)
        assert len(content) > 0
        assert "Smart Garden System" in content
        assert "Market Analysis" in content
        assert "Technical Requirements" in content
        assert "$15.3 billion" in content
    
    def test_parse_txt_file(self):
        """Test parsing a text file."""
        test_content = "This is a test document about smart agriculture.\nIt has multiple lines."
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(test_content)
            f.flush()
            
            try:
                content = parse_document(f.name)
                assert content == test_content
            finally:
                os.unlink(f.name)
    
    def test_parse_unsupported_file_type(self):
        """Test parsing an unsupported file type."""
        with tempfile.NamedTemporaryFile(suffix='.xyz', delete=False) as f:
            try:
                with pytest.raises(Exception, match="Error parsing document.*Unsupported file extension"):
                    parse_document(f.name)
            finally:
                os.unlink(f.name)
    
    def test_parse_nonexistent_file(self):
        """Test parsing a file that doesn't exist."""
        with pytest.raises(Exception):
            parse_document("/nonexistent/file.txt")
    
    def test_parse_txt_direct(self):
        """Test the parse_txt function directly."""
        test_content = "Direct text parsing test\nWith multiple lines\nAnd various content."
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(test_content)
            f.flush()
            
            try:
                content = parse_txt(f.name)
                assert content == test_content
            finally:
                os.unlink(f.name)
    
    def test_parse_markdown_direct(self):
        """Test the parse_markdown function directly."""
        test_content = "# Test Markdown\n\nThis is **bold** text with *italic* and `code`."
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(test_content)
            f.flush()
            
            try:
                content = parse_markdown(f.name)
                # Should return the raw markdown content
                assert content == test_content
                assert "# Test Markdown" in content
                assert "**bold**" in content
            finally:
                os.unlink(f.name)
    
    def test_parse_empty_file(self):
        """Test parsing an empty file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("")
            f.flush()
            
            try:
                content = parse_document(f.name)
                assert content == ""
            finally:
                os.unlink(f.name)
    
    def test_parse_large_file(self):
        """Test parsing a reasonably large file."""
        # Create a file with repeated content
        test_line = "This is line number {}\n"
        large_content = "".join(test_line.format(i) for i in range(1000))
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(large_content)
            f.flush()
            
            try:
                content = parse_document(f.name)
                assert len(content) > 10000  # Should be substantial
                assert "This is line number 1" in content
                assert "This is line number 999" in content
            finally:
                os.unlink(f.name)