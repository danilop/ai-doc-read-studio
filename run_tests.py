#!/usr/bin/env python3
"""
Test runner script for AI Doc Read Studio
"""

import subprocess
import sys
import os

def run_tests():
    """Run the complete test suite."""
    
    print("🧪 AI Doc Read Studio - Test Suite")
    print("=" * 50)
    
    # Ensure we're in the right directory
    if not os.path.exists("tests"):
        print("❌ Tests directory not found. Please run from project root.")
        return 1
    
    # Run pytest with coverage if available
    try:
        # Try to run with coverage first
        result = subprocess.run([
            "uv", "run", "pytest", 
            "tests/",
            "-v",
            "--tb=short",
            "-x"  # Stop on first failure
        ], capture_output=False)
        
        if result.returncode == 0:
            print("\n✅ All tests passed!")
            print("\n🚀 Application is ready for use!")
            print("Start with: python start_app.py")
        else:
            print(f"\n❌ Tests failed with exit code {result.returncode}")
            print("Check the output above for details.")
        
        return result.returncode
        
    except FileNotFoundError:
        print("❌ pytest not found. Make sure you've installed test dependencies:")
        print("   uv add pytest pytest-asyncio")
        return 1
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return 1

def run_specific_test_file(test_file):
    """Run a specific test file."""
    
    if not test_file.startswith("test_"):
        test_file = f"test_{test_file}"
    if not test_file.endswith(".py"):
        test_file = f"{test_file}.py"
    
    test_path = f"tests/{test_file}"
    
    if not os.path.exists(test_path):
        print(f"❌ Test file not found: {test_path}")
        return 1
    
    print(f"🧪 Running specific test: {test_file}")
    print("=" * 50)
    
    try:
        result = subprocess.run([
            "uv", "run", "pytest",
            test_path,
            "-v",
            "--tb=short"
        ], capture_output=False)
        
        return result.returncode
        
    except Exception as e:
        print(f"❌ Error running test: {e}")
        return 1

def main():
    """Main entry point for test runner."""
    
    if len(sys.argv) > 1:
        # Run specific test file
        test_file = sys.argv[1]
        return run_specific_test_file(test_file)
    else:
        # Run all tests
        return run_tests()

if __name__ == "__main__":
    sys.exit(main())