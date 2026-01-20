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

# Install dependencies
pip3 install psutil websockets

echo
echo "========================================"
echo "Installation complete!"
echo
echo "To run the agent:"
echo "  python3 ~/pc-monitor-agent.py"
echo
echo "To run in background:"
echo "  nohup python3 ~/pc-monitor-agent.py &"
echo "========================================"
