#!/bin/bash
# AI Doc Read Studio - Quick Start Script

echo "🚀 Starting AI Doc Read Studio..."
echo "   This will start both frontend and backend servers"
echo "   Press Ctrl+C to stop"
echo ""

# Check if uv is available
if ! command -v uv &> /dev/null; then
    echo "❌ UV is not installed. Please install UV first."
    echo "   Visit: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "config.json" ]; then
    echo "❌ Please run this script from the ai-doc-read-studio directory"
    echo "   cd ai-doc-read-studio && ./start.sh"
    exit 1
fi

# Run the Python startup script with UV environment
uv run python start_app.py