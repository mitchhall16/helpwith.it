#!/bin/bash
echo "Installing PC Monitor Agent..."
echo

# Download agent
curl -s "http://192.168.12.125:8000/install/agent.py?key=5UmcdWxWlyER7snzbIbFlslNoapREZYh" -o ~/pc-monitor-agent.py

# Configure
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' 's|SERVER_URL = .*|SERVER_URL = "http://192.168.12.125:8000"|' ~/pc-monitor-agent.py
    sed -i '' 's|API_KEY = .*|API_KEY = "5UmcdWxWlyER7snzbIbFlslNoapREZYh"|' ~/pc-monitor-agent.py
else
    # Linux
    sed -i 's|SERVER_URL = .*|SERVER_URL = "http://192.168.12.125:8000"|' ~/pc-monitor-agent.py
    sed -i 's|API_KEY = .*|API_KEY = "5UmcdWxWlyER7snzbIbFlslNoapREZYh"|' ~/pc-monitor-agent.py
fi

# Install dependencies - try multiple methods for compatibility
echo "Installing dependencies..."
if pip3 install psutil websockets 2>/dev/null; then
    PYTHON_CMD="python3"
elif pip3 install --user psutil websockets 2>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python3 &>/dev/null; then
    # Create venv for externally managed environments (Ubuntu 23.04+, etc.)
    echo "Creating virtual environment..."
    python3 -m venv ~/.pc-monitor-venv
    ~/.pc-monitor-venv/bin/pip install psutil websockets
    PYTHON_CMD="$HOME/.pc-monitor-venv/bin/python"

    # Create launcher script
    cat > ~/pc-monitor-agent << 'LAUNCHER'
#!/bin/bash
~/.pc-monitor-venv/bin/python ~/pc-monitor-agent.py "$@"
LAUNCHER
    chmod +x ~/pc-monitor-agent
else
    echo "ERROR: Python3 not found. Please install Python 3."
    exit 1
fi

echo
echo "========================================"
echo "Installation complete!"
echo
if [ -f ~/pc-monitor-agent ]; then
    echo "To run the agent:"
    echo "  ~/pc-monitor-agent"
    echo
    echo "To run in background:"
    echo "  nohup ~/pc-monitor-agent &"
else
    echo "To run the agent:"
    echo "  $PYTHON_CMD ~/pc-monitor-agent.py"
    echo
    echo "To run in background:"
    echo "  nohup $PYTHON_CMD ~/pc-monitor-agent.py &"
fi
echo "========================================"
