#!/usr/bin/env python3
"""
Clean up script for AI Doc Read Studio
Removes generated files and directories that shouldn't be in version control.
"""

import os
import shutil
import glob


def clean_directory(path, description):
    """Clean a directory if it exists."""
    if os.path.exists(path):
        try:
            shutil.rmtree(path)
            print(f"✅ Cleaned {description}: {path}")
        except Exception as e:
            print(f"⚠️  Could not clean {description}: {e}")
    else:
        print(f"ℹ️  {description} not found: {path}")


def clean_files(pattern, description):
    """Clean files matching a pattern."""
    files = glob.glob(pattern, recursive=True)
    if files:
        for file in files:
            try:
                os.remove(file)
                print(f"✅ Removed {description}: {file}")
            except Exception as e:
                print(f"⚠️  Could not remove {file}: {e}")
    else:
        print(f"ℹ️  No {description} found")


def main():
    """Main cleanup function."""
    print("🧹 AI Doc Read Studio - Cleanup Script")
    print("=" * 50)
    
    # Clean uploaded files (keep directory structure)
    clean_directory("uploads", "uploaded documents")
    clean_directory("backend/uploads", "backend uploaded documents")
    
    # Clean session data
    clean_directory("sessions", "session data")
    clean_directory("backend/sessions", "backend session data")
    
    # Clean logs
    clean_directory("logs", "log directory")
    clean_directory("backend/logs", "backend log directory")
    clean_files("*.log", "root log files")
    clean_files("app.log", "app log files")
    clean_files("startup.log", "startup log files")
    
    # Clean test artifacts
    clean_directory(".pytest_cache", "pytest cache")
    clean_directory("htmlcov", "coverage reports")
    clean_files("test_report.json", "test reports")
    clean_files(".coverage", "coverage data")
    
    # Clean Python cache
    clean_directory("__pycache__", "Python cache")
    clean_files("**/__pycache__", "nested Python cache")
    clean_files("**/*.pyc", "compiled Python files")
    clean_files("**/*.pyo", "optimized Python files")
    
    # Recreate necessary directories
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("backend/uploads", exist_ok=True)
    os.makedirs("sessions", exist_ok=True)
    os.makedirs("backend/sessions", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.makedirs("backend/logs", exist_ok=True)
    
    print("\n✨ Cleanup complete!")
    print("📁 Necessary directories have been recreated.")
    print("🚀 Ready for fresh start!")


if __name__ == "__main__":
    main()