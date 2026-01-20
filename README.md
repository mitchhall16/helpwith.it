# PC Monitor

A self-hosted PC monitoring dashboard with remote desktop integration. Monitor all your computers from one place.

## Features

- **Real-time Monitoring** - CPU, RAM, Disk, Network stats updated live via WebSocket
- **Multi-Computer Support** - Monitor unlimited computers from one dashboard
- **Remote Desktop** - One-click RustDesk integration for remote access
- **Remote Terminal** - Execute commands on any computer from the dashboard
- **File Browser** - Browse, upload, and download files from remote computers
- **Speed Tests** - Run network speed tests using speedtest.net
- **Alerts** - Get notified (Discord) when CPU/RAM/Disk exceed thresholds
- **Wake-on-LAN** - Wake up sleeping computers remotely
- **Auto-Updates** - Agents automatically update themselves
- **Cross-Platform** - Windows, Linux, macOS support
- **Self-Hosted** - Your data stays on your network

## Quick Start

### Download Installers

Download from [Releases](../../releases):

| Platform | Server | Agent |
|----------|--------|-------|
| Windows | `PCMonitorServer-Setup.exe` | `PCMonitorAgent-Setup.exe` |
| Linux | `pc-monitor-server` | `pc-monitor-agent` |
| macOS | `pc-monitor-server` | `pc-monitor-agent` |

### Install Server

1. Download and run `PCMonitorServer-Setup.exe` on your chosen server computer
2. Open `http://localhost:8000` in your browser
3. Login credentials are shown in the terminal (and saved to `config.json`)

### Install Agents

**Option 1: Installer**
- Run `PCMonitorAgent-Setup.exe`
- Enter your server URL when prompted

**Option 2: One-Liner (from Dashboard)**
1. Open Settings in the dashboard
2. Copy the install command for your platform
3. Paste and run on the new computer

## Run from Source

```bash
# Clone
git clone https://github.com/mitchhall16/helpwith.it.git
cd pc-monitor

# Server
cd server
pip install fastapi uvicorn websockets
python server.py

# Agent (on other computers)
cd agent
pip install psutil websockets speedtest-cli
# Edit agent.py: set SERVER_URL and API_KEY
python agent.py
```

## Build Executables

```bash
# Windows
build-windows.bat

# Linux
chmod +x build-linux.sh && ./build-linux.sh

# macOS
chmod +x build-mac.sh && ./build-mac.sh
```

Output in `dist/` folder.

## Remote Desktop (RustDesk)

PC Monitor integrates with [RustDesk](https://rustdesk.com) for free remote desktop:

1. Install RustDesk on computers you want to access
2. Dashboard auto-detects RustDesk installation
3. Click **"Remote"** for one-click connection
4. Set up **permanent password** in Connect tab for unattended access

## Configuration

### Server (`config.json`)
Auto-generated on first run:
```json
{
  "admin_username": "admin",
  "admin_password": "auto-generated",
  "agent_api_key": "auto-generated"
}
```

### Agent (`agent.py`)
```python
SERVER_URL = "http://YOUR_SERVER_IP:8000"
API_KEY = "copy-from-server-config"
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/computers` | List all computers |
| `POST /api/exec/{id}` | Run shell command |
| `POST /api/files/{id}/browse` | Browse directory |
| `POST /api/speedtest/{id}` | Run speed test |
| `GET /metrics` | Prometheus metrics |
| `WS /ws/{id}` | WebSocket for real-time |

## License

MIT License - see [LICENSE](LICENSE)
