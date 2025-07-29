"""
Test cache control and version endpoint functionality
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
import time

client = TestClient(app)


class TestCacheControl:
    """Test cache control headers and functionality."""
    
    def test_cache_control_headers_on_api_endpoints(self):
        """Test that all API endpoints return proper cache control headers."""
        response = client.get("/")
        
        # Check cache control headers
        assert "Cache-Control" in response.headers
        assert response.headers["Cache-Control"] == "no-cache, no-store, must-revalidate, max-age=0"
        assert response.headers["Pragma"] == "no-cache"
        assert response.headers["Expires"] == "0"
        assert "X-Response-Time" in response.headers
    
    def test_version_endpoint(self):
        """Test the version endpoint returns proper data."""
        response = client.get("/version")
        assert response.status_code == 200
        
        data = response.json()
        assert "version" in data
        assert "timestamp" in data
        assert "cache_buster" in data
        
        # Check cache headers are present
        assert response.headers["Cache-Control"] == "no-cache, no-store, must-revalidate, max-age=0"
    
    def test_version_endpoint_unique_cache_buster(self):
        """Test that version endpoint returns unique cache busters."""
        response1 = client.get("/version")
        time.sleep(0.1)  # Small delay to ensure different timestamp
        response2 = client.get("/version")
        
        data1 = response1.json()
        data2 = response2.json()
        
        # Cache busters should be different
        assert data1["cache_buster"] != data2["cache_buster"]
        assert data1["timestamp"] != data2["timestamp"]
    
    def test_upload_endpoint_cache_headers(self):
        """Test cache headers on upload endpoint."""
        # Create a test file
        test_content = b"Test document content"
        files = {"file": ("test.txt", test_content, "text/plain")}
        
        response = client.post("/upload", files=files)
        
        # Even POST endpoints should have cache control headers
        assert "Cache-Control" in response.headers
        assert response.headers["Cache-Control"] == "no-cache, no-store, must-revalidate, max-age=0"