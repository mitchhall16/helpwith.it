#!/bin/bash
echo "============================================"
echo "  PC Monitor - macOS Build Script"
echo "============================================"
echo

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 not found. Please install Python first."
    echo "  Install with: brew install python3"
    exit 1
fi

# Install PyInstaller if needed
echo "Installing/updating PyInstaller..."
pip3 install pyinstaller --quiet

# Create dist directory
mkdir -p dist/mac

echo
echo "Building Server..."
pyinstaller --onefile --name pc-monitor-server \
    --add-data "dashboard:dashboard" \
    --distpath dist/mac \
    --workpath build/server \
    --specpath build \
    server/server.py

echo
echo "Building Agent..."
pyinstaller --onefile --name pc-monitor-agent \
    --distpath dist/mac \
    --workpath build/agent \
    --specpath build \
    agent/agent.py

# Copy config
if [ -f "server/config.json" ]; then
    cp "server/config.json" "dist/mac/config.json"
fi

# Make executable
chmod +x dist/mac/pc-monitor-server
chmod +x dist/mac/pc-monitor-agent

echo
echo "============================================"
echo "  Build Complete!"
echo "============================================"
echo
echo "Files created in dist/mac/:"
ls -la dist/mac/
echo
echo "To use:"
echo "  1. Copy pc-monitor-server to your server computer"
echo "  2. Copy pc-monitor-agent to computers you want to monitor"
echo "  3. Run the server first, then agents"
echo
echo "To run: ./pc-monitor-server or ./pc-monitor-agent"
