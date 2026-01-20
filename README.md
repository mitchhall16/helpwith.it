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
1. Download `PCMonitorServer-Setup.exe` from [Releases](../../releases)
2. Run it and click Next through the installer
3. Open your browser to `http://localhost:8000`
4. Done! You'll see your login info in the window

**On Linux/Mac:**
1. Download `pc-monitor-server` from [Releases](../../releases)
2. Open terminal and run:
   ```
   chmod +x pc-monitor-server
   ./pc-monitor-server
   ```
3. Open browser to `http://localhost:8000`

---

### Step 2: Add Computers to Monitor

On each computer you want to monitor:

**Easiest Way:**
1. Open the dashboard (from Step 1)
2. Click **Settings** (gear icon)
3. Find "Add New Computer" section
4. Copy the command for your system (Windows/Linux/Mac)
5. Paste and run it on the computer you want to add
6. That's it! The computer will appear in your dashboard

**Or Download Installer:**
1. Download `PCMonitorAgent-Setup.exe` from [Releases](../../releases)
2. Run it
3. Enter your server's address when asked (like `http://192.168.1.100:8000`)
4. Done!

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
