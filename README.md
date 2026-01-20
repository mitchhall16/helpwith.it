# HelpWith.IT - PC Monitor

**Monitor and control all your computers from one place.** See what's running, check performance, browse files, run commands, and remote desktop into any of your machines.

---

## What Can It Do?

| Feature | Description |
|---------|-------------|
| **Dashboard** | See all your computers at a glance - CPU, RAM, disk usage |
| **Remote Desktop** | One-click to control any computer (via RustDesk) |
| **Remote Terminal** | Run commands on any computer from your browser |
| **File Browser** | Browse and download files from any computer |
| **Speed Test** | Test internet speed on any computer |
| **Alerts** | Get notified when something's wrong |
| **Wake-on-LAN** | Turn on sleeping computers remotely |

---

## How To Install

### Step 1: Pick a "Server" Computer

This is the computer that runs the dashboard. Can be any computer that stays on.

**On Windows:**
1. Go to [Releases](../../releases) and download `pc-monitor-server.exe`
2. Double-click to run it
3. Open your browser to `http://localhost:8000`
4. Done!

**On Linux:**
1. Go to [Releases](../../releases) and download `pc-monitor-server-linux`
2. Open terminal and run:
   ```
   cd ~/Downloads
   chmod +x pc-monitor-server-linux
   ./pc-monitor-server-linux
   ```
3. Open browser to `http://localhost:8000`

**On Mac:**
1. Go to [Releases](../../releases) and download `pc-monitor-server-mac`
2. Open terminal and run:
   ```
   cd ~/Downloads
   chmod +x pc-monitor-server-mac
   ./pc-monitor-server-mac
   ```
3. Open browser to `http://localhost:8000`

---

### Step 2: Add Computers to Monitor

On each computer you want to monitor:

**On Windows:**
1. Go to [Releases](../../releases) and download `pc-monitor-agent.exe`
2. Double-click to run it
3. Enter your server's address when asked (like `http://192.168.1.100:8000`)
4. Done! The computer will appear in your dashboard

**On Linux:**
1. Go to [Releases](../../releases) and download `pc-monitor-agent-linux`
2. Open terminal and run:
   ```
   cd ~/Downloads
   chmod +x pc-monitor-agent-linux
   ./pc-monitor-agent-linux http://YOUR_SERVER_IP:8000
   ```

**On Mac:**
1. Go to [Releases](../../releases) and download `pc-monitor-agent-mac`
2. Open terminal and run:
   ```
   cd ~/Downloads
   chmod +x pc-monitor-agent-mac
   ./pc-monitor-agent-mac http://YOUR_SERVER_IP:8000
   ```

---

### Step 3: Set Up Remote Desktop (Optional)

To remotely control your computers:

1. Download [RustDesk](https://rustdesk.com) on each computer
2. Install and open it once
3. In the dashboard, click on a computer → **Connect** tab
4. Click **"Setup One-Click Password"**
5. Now you can click **"Remote"** to instantly connect!

---

## FAQ

**Q: What's the server address?**
Look at the computer running the server. It shows the address like:
```
Dashboard: http://192.168.1.100:8000
```
Use that address.

**Q: I can't connect from another computer**
- Make sure both computers are on the same network
- Check Windows Firewall isn't blocking it
- Try the IP address, not "localhost"

**Q: How do I find my server's IP address?**
- Windows: Open CMD, type `ipconfig`, look for "IPv4 Address"
- Linux/Mac: Open terminal, type `ip addr` or `ifconfig`

**Q: Can I access this from outside my home?**
Yes! Use [Tailscale](https://tailscale.com) (free) to connect your computers. Then use the Tailscale IP address.

**Q: How do I make it start automatically?**
The installer has an option "Start automatically on Windows startup" - check that box.

---

## Screenshots

*Coming soon*

---

## Need Help?

- [Report a bug](../../issues)
- [Ask a question](../../discussions)

---

## For Developers

<details>
<summary>Click to expand technical details</summary>

### Run from Source
```bash
# Server
cd server
pip install fastapi uvicorn websockets
python server.py

# Agent
cd agent
pip install psutil websockets speedtest-cli
python agent.py
```

### Build Executables
```bash
# Windows
build-windows.bat

# Linux
./build-linux.sh

# Mac
./build-mac.sh
```

### Tech Stack
- **Server:** Python, FastAPI, WebSockets, SQLite
- **Dashboard:** Vanilla HTML/CSS/JS
- **Agent:** Python, psutil

</details>

---

**License:** MIT (free to use and modify)
