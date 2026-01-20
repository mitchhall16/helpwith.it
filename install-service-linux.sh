#!/bin/bash
echo "============================================"
echo "  PC Monitor - Linux Service Installer"
echo "============================================"
echo
echo "This will install PC Monitor as a systemd service"
echo "that starts automatically on boot."
echo

# Check for root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./install-service-linux.sh)"
    exit 1
fi

read -p "Install (S)erver or (A)gent service? [S/A]: " CHOICE

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${CHOICE,,}" == "s" ]]; then
    echo
    echo "Installing Server service..."

    # Copy binary to /opt
    mkdir -p /opt/pc-monitor
    cp "$SCRIPT_DIR/dist/linux/pc-monitor-server" /opt/pc-monitor/
    cp -r "$SCRIPT_DIR/dashboard" /opt/pc-monitor/
    if [ -f "$SCRIPT_DIR/dist/linux/config.json" ]; then
        cp "$SCRIPT_DIR/dist/linux/config.json" /opt/pc-monitor/
    fi
    chmod +x /opt/pc-monitor/pc-monitor-server

    # Create systemd service
    cat > /etc/systemd/system/pc-monitor-server.service << EOF
[Unit]
Description=PC Monitor Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/pc-monitor
ExecStart=/opt/pc-monitor/pc-monitor-server
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Enable and start service
    systemctl daemon-reload
    systemctl enable pc-monitor-server
    systemctl start pc-monitor-server

    echo
    echo "Server service installed!"
    echo "Dashboard available at: http://$(hostname -I | awk '{print $1}'):8000"
    echo
    echo "Commands:"
    echo "  sudo systemctl status pc-monitor-server"
    echo "  sudo systemctl stop pc-monitor-server"
    echo "  sudo systemctl restart pc-monitor-server"
    echo "  sudo journalctl -u pc-monitor-server -f"

elif [[ "${CHOICE,,}" == "a" ]]; then
    echo
    echo "Installing Agent service..."

    # Copy binary to /opt
    mkdir -p /opt/pc-monitor
    cp "$SCRIPT_DIR/dist/linux/pc-monitor-agent" /opt/pc-monitor/
    chmod +x /opt/pc-monitor/pc-monitor-agent

    # Create systemd service
    cat > /etc/systemd/system/pc-monitor-agent.service << EOF
[Unit]
Description=PC Monitor Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/pc-monitor
ExecStart=/opt/pc-monitor/pc-monitor-agent
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Enable and start service
    systemctl daemon-reload
    systemctl enable pc-monitor-agent
    systemctl start pc-monitor-agent

    echo
    echo "Agent service installed!"
    echo
    echo "Commands:"
    echo "  sudo systemctl status pc-monitor-agent"
    echo "  sudo systemctl stop pc-monitor-agent"
    echo "  sudo systemctl restart pc-monitor-agent"
    echo "  sudo journalctl -u pc-monitor-agent -f"

else
    echo "Invalid choice. Please run again and enter S or A."
fi
