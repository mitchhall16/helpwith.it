# PC Monitor - Quick Start Guide

## 5-Minute Setup

### Step 1: Install Dependencies (one time)

```bash
pip install fastapi uvicorn psutil
```

### Step 2: Start the Server (on your main PC)

```bash
cd pc-monitor
python server/server.py
```

Open http://localhost:8000 - you should see an empty dashboard.

### Step 3: Install Agent on Other Computers

1. Copy the `agent/` folder to each computer
2. Edit `agent.py` and change this line:
   ```python
   SERVER_URL = "http://YOUR_SERVER_IP:8000"
   ```
   Replace `YOUR_SERVER_IP` with your main PC's IP address (e.g., `192.168.1.100`)

3. Run the agent:
   ```bash
   pip install psutil  # optional but recommended
   python agent.py
   ```

4. Check your dashboard - the computer should appear!

---

## Remote Access Setup

### Option A: RustDesk (Recommended - Free & Easy)

1. Download RustDesk from https://rustdesk.com (free, open source)
2. Install on ALL your computers
3. The agent will auto-detect RustDesk IDs
4. Click "Connect" in the dashboard to remote in

### Option B: Windows RDP

1. Enable Remote Desktop on target PCs:
   - Settings > System > Remote Desktop > Enable
2. Click "Connect" in dashboard, use the RDP option

### Option C: SSH (Linux/Mac)

1. Enable SSH on target: `sudo systemctl enable --now sshd`
2. Click "Connect" in dashboard, copy the SSH command

---

## Optional: Grafana for Historical Graphs

If you want pretty graphs showing CPU/memory over time:

```bash
cd grafana
docker-compose up -d
```

Then open:
- Grafana: http://localhost:3000 (admin/admin)
- Add Prometheus data source: http://prometheus:9090

---

## Running as a Background Service

### Windows (Server)

Create a scheduled task:
1. Open Task Scheduler
2. Create Basic Task > "PC Monitor Server"
3. Trigger: At startup
4. Action: Start program > `pythonw.exe`
5. Arguments: `C:\path\to\pc-monitor\server\server.py`

### Windows (Agent)

Same process, but for `agent.py`

### Linux

```bash
# Create service file
sudo nano /etc/systemd/system/pc-monitor-agent.service
```

```ini
[Unit]
Description=PC Monitor Agent
After=network.target

[Service]
ExecStart=/usr/bin/python3 /path/to/agent.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now pc-monitor-agent
```

---

## Troubleshooting

**Agent can't connect to server?**
- Check firewall allows port 8000
- Verify SERVER_URL in agent.py is correct
- Make sure server is running

**No CPU/memory stats?**
- Install psutil: `pip install psutil`

**Dashboard not updating?**
- Check agent is running (look for heartbeat messages)
- Refresh the page
