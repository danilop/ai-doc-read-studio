# AI Doc Read Studio - Test Suite

## Overview

This test suite provides comprehensive coverage of the AI Doc Read Studio application, focusing on recent changes and core functionality.

## Test Files

### Core Tests
- **test_imports.py** - Tests module imports and fixes for recent import path changes
- **test_basic_api.py** - Tests basic API functionality including uploads, sessions, and endpoints
- **test_cache_control.py** - Tests cache-busting features and version endpoint
- **test_logging.py** - Tests structlog integration and cost tracking functionality

### Legacy Tests
- **test_agents.py** - Tests agent functionality and model mapping
- **test_api.py** - Additional API tests
- **test_document_parser.py** - Document parsing functionality
- **test_integration.py** - Integration tests
- **test_strands_agents.py** - Strands Agents integration with Amazon Bedrock

## Recent Changes Tested

### 1. Import Path Fixes ✅
- Fixed relative imports to use absolute backend paths
- All modules now properly import without circular dependencies
- Tests: `test_imports.py`

### 2. Cache-Busting Implementation ✅
- Added cache control headers to all API responses
- Implemented version endpoint for frontend cache detection
- Enhanced frontend with automatic update notifications
- Tests: `test_cache_control.py`

### 3. Logging System Updates ✅
- Fixed Logger.log() error by migrating to structlog
- All backend modules now use structured logging
- Cost tracking properly logs with keyword arguments
- Tests: `test_logging.py`

### 4. API Functionality ✅
- Basic endpoints working correctly
- File upload with size and type validation
- Session creation and management
- Agent templates endpoint
- Tests: `test_basic_api.py`

## Running Tests

### Run All Tests
```bash
uv run pytest tests/ -v
```

### Run Specific Test Categories
```bash
# Test recent changes
uv run pytest tests/test_imports.py tests/test_cache_control.py tests/test_logging.py -v

# Test basic API functionality
uv run pytest tests/test_basic_api.py -v

# Quick smoke test
uv run pytest tests/test_imports.py -v
```

### Using the Test Runner
```bash
# Run all tests
python run_tests.py

# Run specific test file
python run_tests.py test_basic_api
```

## Test Results Summary

✅ **22 tests passing**  
⚠️ **14 warnings** (mostly deprecation warnings)  
❌ **0 failures**

## Warnings to Address (Future Work)

1. **Pydantic V1 to V2 Migration**: Update validators to use `@field_validator`
2. **PyPDF2 Deprecation**: Migrate to `pypdf` library
3. **datetime.utcnow() Deprecation**: Use timezone-aware datetime objects

## Test Coverage

The test suite covers:

- ✅ Module imports and dependency resolution
- ✅ API endpoint functionality
- ✅ File upload and validation
- ✅ Session management
- ✅ Cache control headers
- ✅ Version endpoint for updates
- ✅ Cost tracking and logging
- ✅ Error handling
- ✅ Basic integration flows

## Configuration

Tests use:
- FastAPI TestClient for API testing
- pytest-asyncio for async test support
- Structured logging verification
- Mock objects where appropriate
- Temporary test data cleanup

## Notes

- Tests run against the actual backend API using TestClient
- No external services required for basic test suite
- AWS credentials not needed for core functionality tests
- All tests are designed to be independent and can run in any order