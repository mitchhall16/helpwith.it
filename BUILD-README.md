# PC Monitor - Build & Deploy Guide

## Quick Start (Without Building)

Just run with Python:
```bash
# Server (on your main computer)
cd server
python server.py

# Agent (on computers to monitor)
cd agent
python agent.py
```

---

## Building Standalone Executables

Build on each platform to get native executables:

### Windows
```batch
build-windows.bat
```
Creates: `dist/windows/pc-monitor-server.exe` and `pc-monitor-agent.exe`

### Linux/Ubuntu
```bash
chmod +x build-linux.sh
./build-linux.sh
```
Creates: `dist/linux/pc-monitor-server` and `pc-monitor-agent`

### macOS
```bash
chmod +x build-mac.sh
./build-mac.sh
```
Creates: `dist/mac/pc-monitor-server` and `pc-monitor-agent`

---

## Deploying the Server

### Option 1: Choose Any Computer as Server

1. Copy the built `pc-monitor-server` executable to that computer
2. Run it - dashboard available at `http://[computer-ip]:8000`
3. Update agents with the new server IP

### Option 2: Install as Service (Auto-Start)

**Windows (as Administrator):**
```batch
install-service-windows.bat
```

**Linux:**
```bash
sudo ./install-service-linux.sh
```

---

## Deploying Agents

### Easy Way (From Dashboard)
1. Go to Settings in the dashboard
2. Copy the one-liner for your platform
3. Run it on the new computer

### Manual Way
1. Copy `pc-monitor-agent` executable to the computer
2. Edit `config.json` or set environment variables:
   - `SERVER_URL` - your server's address
   - `API_KEY` - from your server's config.json
3. Run the agent

---

## Switching Server to a Different Computer

1. Stop the old server
2. Copy these files to the new computer:
   - `pc-monitor-server` (executable)
   - `config.json` (keeps your credentials)
   - `pc_monitor.db` (optional - keeps history)
   - `dashboard/` folder
3. Run the server on the new computer
4. Update `SERVER_URL` in all agents (they'll auto-update on next push)

---

## File Locations

| File | Purpose |
|------|---------|
| `config.json` | Server credentials & API key |
| `pc_monitor.db` | Database (history, alerts, etc.) |
| `dashboard/` | Web interface files |

---

## Troubleshooting

**Port already in use:**
```bash
# Find what's using port 8000
netstat -ano | findstr :8000  # Windows
lsof -i :8000                  # Linux/Mac
```

**Can't connect from other computers:**
- Check firewall allows port 8000
- Use the computer's actual IP, not localhost

**Agents not connecting:**
- Verify SERVER_URL is correct
- Check API_KEY matches server's config.json
- Ensure server is reachable (try curl/wget)
