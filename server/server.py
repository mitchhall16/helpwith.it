"""
PC Monitor Server
Simple FastAPI server that receives heartbeats from agents and serves a dashboard.
"""
import sys
import os

# Determine base path (works for both script and PyInstaller bundle)
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    BASE_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = sys._MEIPASS  # PyInstaller temp folder with bundled files
else:
    # Running as script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = os.path.dirname(BASE_DIR)

# Auto-install dependencies if missing (only when running as script)
def _ensure_dependencies():
    if getattr(sys, 'frozen', False):
        return  # Skip when running as executable
    import subprocess
    required = ["fastapi", "uvicorn", "websockets"]
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            print(f"Installing {pkg}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "--quiet"])

_ensure_dependencies()

from fastapi import FastAPI, Request, HTTPException, Depends, status, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from datetime import datetime, timedelta
import json
import sqlite3
import os
import secrets
import hashlib
import asyncio

app = FastAPI(title="PC Monitor")

# Store active WebSocket connections for each computer
active_connections: dict[str, WebSocket] = {}
# Store pending commands to send via WebSocket
pending_websocket_commands: dict[str, list] = {}
security = HTTPBasic()

# ============================================
# CONFIGURATION (auto-generated on first run)
# ============================================
import secrets as secrets_module

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

def load_or_create_config():
    """Load config or create with auto-generated secrets"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)

    # Generate new config with random secrets
    config = {
        "admin_username": "admin",
        "admin_password": secrets_module.token_urlsafe(12),
        "agent_api_key": secrets_module.token_urlsafe(24)
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\n{'='*50}")
    print("FIRST RUN - Generated new credentials:")
    print(f"  Dashboard Login: admin / {config['admin_password']}")
    print(f"  Agent API Key: {config['agent_api_key']}")
    print(f"  Saved to: {CONFIG_FILE}")
    print(f"{'='*50}\n")

    return config

CONFIG = load_or_create_config()

# Support multiple admin users - can be a list of {username, password} objects
# or the legacy single admin_username/admin_password format
ADMIN_USERS = CONFIG.get("admin_users", [])
if not ADMIN_USERS:
    # Fallback to legacy single user format
    ADMIN_USERS = [{"username": CONFIG["admin_username"], "password": CONFIG["admin_password"]}]

AGENT_API_KEY = CONFIG["agent_api_key"]

# Optional InfluxDB support
INFLUXDB_URL = CONFIG.get("influxdb_url", "")  # e.g., "http://localhost:8086"
INFLUXDB_TOKEN = CONFIG.get("influxdb_token", "")
INFLUXDB_ORG = CONFIG.get("influxdb_org", "pc-monitor")
INFLUXDB_BUCKET = CONFIG.get("influxdb_bucket", "pc-metrics")

def _send_to_influxdb_sync(computer_name: str, computer_id: str, metrics: dict):
    """Send metrics to InfluxDB (sync version for threading)"""
    try:
        import urllib.request
        # Format as InfluxDB line protocol
        timestamp = int(datetime.now().timestamp() * 1_000_000_000)  # nanoseconds
        # Escape spaces in computer name for InfluxDB line protocol
        safe_name = computer_name.replace(" ", "\\ ").replace(",", "\\,")
        lines = [
            f'pc_metrics,host={safe_name},id={computer_id} cpu={metrics.get("cpu_percent", 0)},memory={metrics.get("memory_percent", 0)},disk={metrics.get("disk_percent", 0)} {timestamp}'
        ]

        data = "\n".join(lines).encode("utf-8")
        url = f"{INFLUXDB_URL}/api/v2/write?org={INFLUXDB_ORG}&bucket={INFLUXDB_BUCKET}&precision=ns"

        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Token {INFLUXDB_TOKEN}",
                "Content-Type": "text/plain; charset=utf-8"
            }
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"[InfluxDB] Failed to send metrics: {e}")

async def send_to_influxdb(computer_name: str, computer_id: str, metrics: dict):
    """Send metrics to InfluxDB if configured (async wrapper)"""
    if not INFLUXDB_URL or not INFLUXDB_TOKEN:
        return
    # Run in thread to not block
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _send_to_influxdb_sync, computer_name, computer_id, metrics)

def generate_install_scripts():
    """Generate install script files for easy distribution"""
    scripts_dir = os.path.join(BUNDLE_DIR, "install-scripts")
    os.makedirs(scripts_dir, exist_ok=True)

    # Get local IP for default server URL
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        local_ip = "YOUR_SERVER_IP"

    server_url = f"http://{local_ip}:8000"

    # Windows batch script
    win_script = f'''@echo off
echo Installing PC Monitor Agent...
echo.

:: Create directory
mkdir "%USERPROFILE%\\pc-monitor-agent" 2>nul
cd /d "%USERPROFILE%\\pc-monitor-agent"

:: Download agent
echo Downloading agent...
powershell -Command "Invoke-WebRequest -Uri '{server_url}/install/agent.py?key={AGENT_API_KEY}' -OutFile 'agent.py'"

:: Configure
echo Configuring...
powershell -Command "(Get-Content agent.py) -replace 'SERVER_URL = .*', 'SERVER_URL = \\\"{server_url}\\\"' -replace 'API_KEY = .*', 'API_KEY = \\\"{AGENT_API_KEY}\\\"' | Set-Content agent.py"

:: Install dependencies
echo Installing dependencies...
pip install psutil websockets

echo.
echo ========================================
echo Installation complete!
echo.
echo To run the agent:
echo   python "%USERPROFILE%\\pc-monitor-agent\\agent.py"
echo.
echo To run at startup, use install-agent-autostart.bat
echo ========================================
pause
'''
    with open(os.path.join(scripts_dir, "install-windows.bat"), "w") as f:
        f.write(win_script)

    # Mac/Linux shell script
    unix_script = f'''#!/bin/bash
echo "Installing PC Monitor Agent..."
echo

# Download agent
curl -s "{server_url}/install/agent.py?key={AGENT_API_KEY}" -o ~/pc-monitor-agent.py

# Configure
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' 's|SERVER_URL = .*|SERVER_URL = "{server_url}"|' ~/pc-monitor-agent.py
    sed -i '' 's|API_KEY = .*|API_KEY = "{AGENT_API_KEY}"|' ~/pc-monitor-agent.py
else
    # Linux
    sed -i 's|SERVER_URL = .*|SERVER_URL = "{server_url}"|' ~/pc-monitor-agent.py
    sed -i 's|API_KEY = .*|API_KEY = "{AGENT_API_KEY}"|' ~/pc-monitor-agent.py
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
'''
    with open(os.path.join(scripts_dir, "install-mac-linux.sh"), "w") as f:
        f.write(unix_script)

    # Also create a simple README
    first_username = ADMIN_USERS[0]["username"]
    first_password = ADMIN_USERS[0]["password"]
    readme = f'''PC Monitor - Install Scripts
============================

Server URL: {server_url}
API Key: {AGENT_API_KEY}

Dashboard Login:
  Username: {first_username}
  Password: {first_password}

WINDOWS:
  Run install-windows.bat on the target computer

MAC/LINUX:
  Copy install-mac-linux.sh to the target computer and run:
    chmod +x install-mac-linux.sh
    ./install-mac-linux.sh

Or manually:
  1. Copy the agent folder to the target computer
  2. Edit agent.py and set:
     SERVER_URL = "{server_url}"
     API_KEY = "{AGENT_API_KEY}"
  3. Run: pip install psutil websockets
  4. Run: python agent.py
'''
    with open(os.path.join(scripts_dir, "README.txt"), "w") as f:
        f.write(readme)

    print(f"  Install scripts saved to: {scripts_dir}")

generate_install_scripts()
# ============================================

# Allow CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
DB_PATH = "pc_monitor.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)

    # Create tables
    conn.execute("""
        CREATE TABLE IF NOT EXISTS computers (
            id TEXT PRIMARY KEY,
            name TEXT,
            ip TEXT,
            os TEXT,
            cpu_percent REAL,
            memory_percent REAL,
            disk_percent REAL,
            last_seen TEXT,
            extra_info TEXT
        )
    """)

    # Auto-add missing columns (for upgrades)
    def add_column_if_missing(table, column, col_type, default="''"):
        try:
            conn.execute(f"SELECT {column} FROM {table} LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type} DEFAULT {default}")
            print(f"[DB] Added missing column: {table}.{column}")

    add_column_if_missing("computers", "group_name", "TEXT", "'Ungrouped'")
    add_column_if_missing("computers", "notes", "TEXT", "''")
    add_column_if_missing("computers", "mac_address", "TEXT", "''")
    add_column_if_missing("computers", "latitude", "REAL", "0")
    add_column_if_missing("computers", "longitude", "REAL", "0")
    add_column_if_missing("computers", "location_name", "TEXT", "''")
    add_column_if_missing("computers", "agent_version", "TEXT", "''")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            computer_id TEXT,
            alert_type TEXT,
            message TEXT,
            created_at TEXT,
            acknowledged INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS diagnostic_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            computer_id TEXT,
            trigger_type TEXT,
            trigger_value REAL,
            threshold REAL,
            processes TEXT,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS speed_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            computer_id TEXT,
            download_mbps REAL,
            upload_mbps REAL,
            test_time_sec REAL,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pending_commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            computer_id TEXT,
            command TEXT,
            payload TEXT,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS command_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            computer_id TEXT,
            command TEXT,
            output TEXT,
            exit_code INTEGER,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS metrics_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            computer_id TEXT,
            cpu_percent REAL,
            memory_percent REAL,
            disk_percent REAL,
            recorded_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    # Insert default settings if not exist
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('discord_webhook', '')")
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('email_alerts', '')")
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('alert_cpu_threshold', '90')")
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('alert_memory_threshold', '90')")
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('alert_disk_threshold', '90')")
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('auto_speedtest_enabled', 'false')")
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('auto_speedtest_interval_hours', '6')")
    conn.commit()
    conn.close()

init_db()

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify login credentials against all admin users"""
    for user in ADMIN_USERS:
        correct_username = secrets.compare_digest(credentials.username, user["username"])
        correct_password = secrets.compare_digest(credentials.password, user["password"])
        if correct_username and correct_password:
            return credentials.username

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Basic"},
    )

def send_discord_notification(message):
    """Send notification to Discord webhook"""
    try:
        conn = sqlite3.connect(DB_PATH)
        webhook_url = conn.execute("SELECT value FROM settings WHERE key = 'discord_webhook'").fetchone()
        conn.close()

        if webhook_url and webhook_url[0]:
            import urllib.request
            data = json.dumps({"content": message}).encode("utf-8")
            req = urllib.request.Request(
                webhook_url[0],
                data=data,
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=10)
    except:
        pass

def get_alert_thresholds():
    """Get alert thresholds from settings"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT key, value FROM settings WHERE key LIKE 'alert_%'")
    thresholds = {row["key"]: row["value"] for row in cursor}
    conn.close()
    return {
        "cpu": int(thresholds.get("alert_cpu_threshold", 90)),
        "memory": int(thresholds.get("alert_memory_threshold", 90)),
        "disk": int(thresholds.get("alert_disk_threshold", 90))
    }

def check_threshold_alerts(computer_id, computer_name, cpu, memory, disk, extra_info=None):
    """Check if metrics exceed thresholds and create alerts + diagnostic logs"""
    thresholds = get_alert_thresholds()
    conn = sqlite3.connect(DB_PATH)

    def create_alert_if_needed(alert_type, current_value, threshold, metric_name):
        if current_value >= threshold:
            existing = conn.execute(
                "SELECT * FROM alerts WHERE computer_id = ? AND alert_type = ? AND acknowledged = 0",
                (computer_id, alert_type)
            ).fetchone()
            if not existing:
                message = f"{computer_name}: {metric_name} at {current_value}% (threshold: {threshold}%)"
                conn.execute(
                    "INSERT INTO alerts (computer_id, alert_type, message, created_at) VALUES (?, ?, ?, ?)",
                    (computer_id, alert_type, message, datetime.now().isoformat())
                )
                send_discord_notification(f"**PC Monitor Alert:** {message}")

                # Capture diagnostic log with process snapshot
                if extra_info:
                    processes = extra_info.get("top_processes", [])
                    # Only log if we haven't logged in the last 5 minutes for this trigger
                    recent_log = conn.execute(
                        "SELECT * FROM diagnostic_logs WHERE computer_id = ? AND trigger_type = ? AND created_at > datetime('now', '-5 minutes')",
                        (computer_id, alert_type)
                    ).fetchone()
                    if not recent_log:
                        conn.execute(
                            "INSERT INTO diagnostic_logs (computer_id, trigger_type, trigger_value, threshold, processes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                            (computer_id, alert_type, current_value, threshold, json.dumps(processes), datetime.now().isoformat())
                        )
                        print(f"[Diagnostics] Captured log for {computer_name}: {metric_name} at {current_value}%")

    create_alert_if_needed("high_cpu", cpu, thresholds["cpu"], "CPU")
    create_alert_if_needed("high_memory", memory, thresholds["memory"], "Memory")
    create_alert_if_needed("high_disk", disk, thresholds["disk"], "Disk")

    conn.commit()
    conn.close()

def check_offline_computers():
    """Check for newly offline computers and create alerts"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM computers")

    for row in cursor:
        last_seen = datetime.fromisoformat(row["last_seen"])
        is_offline = datetime.now() - last_seen > timedelta(minutes=2)

        if is_offline:
            # Check if we already alerted for this
            existing = conn.execute(
                "SELECT * FROM alerts WHERE computer_id = ? AND alert_type = 'offline' AND acknowledged = 0",
                (row["id"],)
            ).fetchone()

            if not existing:
                conn.execute(
                    "INSERT INTO alerts (computer_id, alert_type, message, created_at) VALUES (?, ?, ?, ?)",
                    (row["id"], "offline", f"{row['name']} went offline", datetime.now().isoformat())
                )
                # Send Discord notification
                send_discord_notification(f"**PC Monitor Alert:** {row['name']} went offline!")

    conn.commit()
    conn.close()

def verify_agent_key(api_key: str) -> bool:
    """Verify the agent API key"""
    return api_key == AGENT_API_KEY

@app.post("/heartbeat")
async def receive_heartbeat(request: Request):
    """Receive heartbeat from an agent"""
    data = await request.json()

    # Verify API key
    agent_key = data.get("api_key") or request.headers.get("X-API-Key")
    if not verify_agent_key(agent_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    conn = sqlite3.connect(DB_PATH)

    # Check if computer exists to preserve group/notes and custom name
    existing = conn.execute("SELECT group_name, notes, name FROM computers WHERE id = ?", (data.get("id"),)).fetchone()
    group_name = existing[0] if existing else "Ungrouped"
    notes = existing[1] if existing else ""
    # Keep custom name if set, otherwise use reported name
    display_name = existing[2] if existing else data.get("name")

    conn.execute("""
        INSERT OR REPLACE INTO computers
        (id, name, ip, os, cpu_percent, memory_percent, disk_percent, last_seen, extra_info, group_name, notes, mac_address, agent_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("id"),
        display_name,
        data.get("ip"),
        data.get("os"),
        data.get("cpu_percent", 0),
        data.get("memory_percent", 0),
        data.get("disk_percent", 0),
        datetime.now().isoformat(),
        json.dumps(data.get("extra", {})),
        group_name,
        notes,
        data.get("extra", {}).get("mac_address", ""),
        data.get("agent_version", "")
    ))

    # Store metrics for history graphs (keep last 7 days worth)
    conn.execute(
        "INSERT INTO metrics_history (computer_id, cpu_percent, memory_percent, disk_percent, recorded_at) VALUES (?, ?, ?, ?, ?)",
        (data.get("id"), data.get("cpu_percent", 0), data.get("memory_percent", 0), data.get("disk_percent", 0), datetime.now().isoformat())
    )
    # Clean old metrics (older than 7 days)
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    conn.execute("DELETE FROM metrics_history WHERE recorded_at < ?", (week_ago,))

    # Clear any offline alerts for this computer
    conn.execute("DELETE FROM alerts WHERE computer_id = ? AND alert_type = 'offline'", (data.get("id"),))

    conn.commit()
    conn.close()

    # Check threshold alerts and capture diagnostic logs
    check_threshold_alerts(
        data.get("id"),
        display_name,
        data.get("cpu_percent", 0),
        data.get("memory_percent", 0),
        data.get("disk_percent", 0),
        data.get("extra", {})
    )

    # Send to InfluxDB if configured
    if INFLUXDB_URL:
        await send_to_influxdb(
            display_name,
            data.get("id"),
            {
                "cpu_percent": data.get("cpu_percent", 0),
                "memory_percent": data.get("memory_percent", 0),
                "disk_percent": data.get("disk_percent", 0)
            }
        )

    return {"status": "ok", "received": datetime.now().isoformat()}

@app.get("/api/computers")
async def get_computers(username: str = Depends(verify_credentials)):
    """Get all computers and their status"""
    check_offline_computers()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM computers ORDER BY group_name, name")
    computers = []

    for row in cursor:
        last_seen = datetime.fromisoformat(row["last_seen"])
        is_online = datetime.now() - last_seen < timedelta(minutes=2)

        # Get latest speed test for this computer
        speed_test = conn.execute(
            "SELECT download_mbps, upload_mbps FROM speed_tests WHERE computer_id = ? ORDER BY created_at DESC LIMIT 1",
            (row["id"],)
        ).fetchone()

        computers.append({
            "id": row["id"],
            "name": row["name"],
            "ip": row["ip"],
            "os": row["os"],
            "cpu_percent": row["cpu_percent"],
            "memory_percent": row["memory_percent"],
            "disk_percent": row["disk_percent"],
            "last_seen": row["last_seen"],
            "is_online": is_online,
            "extra": json.loads(row["extra_info"] or "{}"),
            "group_name": row["group_name"] or "Ungrouped",
            "notes": row["notes"] or "",
            "mac_address": row["mac_address"] or "",
            "agent_version": row["agent_version"] if "agent_version" in row.keys() else "",
            "last_speed": {
                "download": speed_test["download_mbps"] if speed_test else None,
                "upload": speed_test["upload_mbps"] if speed_test else None
            } if speed_test else None
        })

    conn.close()
    return {"computers": computers}

@app.put("/api/computers/{computer_id}")
async def update_computer(computer_id: str, request: Request, username: str = Depends(verify_credentials)):
    """Update computer group or notes"""
    data = await request.json()
    conn = sqlite3.connect(DB_PATH)

    if "group_name" in data:
        conn.execute("UPDATE computers SET group_name = ? WHERE id = ?", (data["group_name"], computer_id))
    if "notes" in data:
        conn.execute("UPDATE computers SET notes = ? WHERE id = ?", (data["notes"], computer_id))

    conn.commit()
    conn.close()
    return {"status": "updated"}

@app.delete("/api/computers/{computer_id}")
async def delete_computer(computer_id: str, username: str = Depends(verify_credentials)):
    """Remove a computer from monitoring"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM computers WHERE id = ?", (computer_id,))
    conn.execute("DELETE FROM alerts WHERE computer_id = ?", (computer_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}

@app.get("/api/alerts")
async def get_alerts(username: str = Depends(verify_credentials)):
    """Get all unacknowledged alerts"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM alerts WHERE acknowledged = 0 ORDER BY created_at DESC")
    alerts = [dict(row) for row in cursor]
    conn.close()
    return {"alerts": alerts}

@app.post("/api/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int, username: str = Depends(verify_credentials)):
    """Acknowledge an alert"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE alerts SET acknowledged = 1 WHERE id = ?", (alert_id,))
    conn.commit()
    conn.close()
    return {"status": "acknowledged"}

@app.get("/api/diagnostics/{computer_id}")
async def get_diagnostic_logs(computer_id: str, username: str = Depends(verify_credentials)):
    """Get diagnostic logs for a computer (captured when thresholds exceeded)"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT * FROM diagnostic_logs WHERE computer_id = ? ORDER BY created_at DESC LIMIT 50",
        (computer_id,)
    )
    logs = []
    for row in cursor:
        logs.append({
            "id": row["id"],
            "trigger_type": row["trigger_type"],
            "trigger_value": row["trigger_value"],
            "threshold": row["threshold"],
            "processes": json.loads(row["processes"]) if row["processes"] else [],
            "created_at": row["created_at"]
        })
    conn.close()
    return {"logs": logs}

@app.get("/api/diagnostics")
async def get_all_diagnostic_logs(username: str = Depends(verify_credentials)):
    """Get all recent diagnostic logs across all computers"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT d.*, c.name as computer_name
        FROM diagnostic_logs d
        LEFT JOIN computers c ON d.computer_id = c.id
        ORDER BY d.created_at DESC LIMIT 100
    """)
    logs = []
    for row in cursor:
        logs.append({
            "id": row["id"],
            "computer_id": row["computer_id"],
            "computer_name": row["computer_name"],
            "trigger_type": row["trigger_type"],
            "trigger_value": row["trigger_value"],
            "threshold": row["threshold"],
            "processes": json.loads(row["processes"]) if row["processes"] else [],
            "created_at": row["created_at"]
        })
    conn.close()
    return {"logs": logs}

@app.post("/api/speedtest/{computer_id}")
async def request_speedtest(computer_id: str, username: str = Depends(verify_credentials)):
    """Queue a speed test request for a computer"""
    command_data = {"command": "speedtest", "payload": ""}

    # Try WebSocket first
    if computer_id in active_connections:
        try:
            await active_connections[computer_id].send_json(command_data)
            return {"status": "sent", "message": "Speed test started", "delivery": "instant"}
        except:
            pass

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO pending_commands (computer_id, command, created_at) VALUES (?, ?, ?)",
        (computer_id, "speedtest", datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    return {"status": "queued", "message": "Speed test requested", "delivery": "polling"}

@app.get("/api/speedtest/{computer_id}/history")
async def get_speedtest_history(computer_id: str, username: str = Depends(verify_credentials)):
    """Get speed test history for a computer"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT * FROM speed_tests WHERE computer_id = ? ORDER BY created_at DESC LIMIT 20",
        (computer_id,)
    )
    tests = [dict(row) for row in cursor]
    conn.close()
    return {"tests": tests}

@app.get("/api/speedtest/auto/status")
async def get_auto_speedtest_status(username: str = Depends(verify_credentials)):
    """Get auto speed test schedule status for all computers"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Get settings
    settings = {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM settings WHERE key LIKE 'auto_speedtest%'")}
    enabled = settings.get("auto_speedtest_enabled", "false") == "true"
    interval_hours = int(settings.get("auto_speedtest_interval_hours", "6"))

    # Get last speed test time for each online computer
    computers_status = []
    for row in conn.execute("SELECT id, name, last_seen FROM computers"):
        last_seen = datetime.fromisoformat(row["last_seen"])
        is_online = datetime.now() - last_seen < timedelta(minutes=2)

        # Get last speed test for this computer
        last_test = conn.execute(
            "SELECT created_at FROM speed_tests WHERE computer_id = ? ORDER BY created_at DESC LIMIT 1",
            (row["id"],)
        ).fetchone()

        needs_test = False
        if is_online:
            if last_test:
                last_test_time = datetime.fromisoformat(last_test["created_at"])
                hours_since = (datetime.now() - last_test_time).total_seconds() / 3600
                needs_test = hours_since >= interval_hours
            else:
                needs_test = True  # Never tested

        computers_status.append({
            "id": row["id"],
            "name": row["name"],
            "is_online": is_online,
            "last_test": last_test["created_at"] if last_test else None,
            "needs_test": needs_test
        })

    conn.close()
    return {
        "enabled": enabled,
        "interval_hours": interval_hours,
        "computers": computers_status
    }

@app.post("/api/speedtest/auto/run")
async def run_auto_speedtests(request: Request, username: str = Depends(verify_credentials)):
    """Trigger speed tests - either scheduled (needs_test only) or manual (all online)"""
    # Check if this is a manual run (force all) or scheduled run
    try:
        body = await request.json()
        force_all = body.get("force_all", False)
    except:
        force_all = False

    # Get all online computers
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    computers = []
    for row in conn.execute("SELECT id, name, last_seen FROM computers"):
        last_seen = datetime.fromisoformat(row["last_seen"])
        is_online = datetime.now() - last_seen < timedelta(minutes=2)
        if is_online:
            computers.append({"id": row["id"], "name": row["name"]})
    conn.close()

    if not force_all:
        # Check if auto speedtest is enabled for scheduled runs
        status = await get_auto_speedtest_status(username)
        if not status["enabled"]:
            return {"status": "disabled", "message": "Auto speed tests are disabled"}
        # Filter to only computers that need a test
        needs_test_ids = {pc["id"] for pc in status["computers"] if pc["needs_test"]}
        computers = [c for c in computers if c["id"] in needs_test_ids]

    triggered = []
    for pc in computers:
        # Queue speed test
        command_data = {"command": "speedtest", "payload": ""}
        if pc["id"] in active_connections:
            try:
                await active_connections[pc["id"]].send_json(command_data)
                triggered.append(pc["name"])
            except:
                pass
        else:
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "INSERT INTO pending_commands (computer_id, command, created_at) VALUES (?, ?, ?)",
                (pc["id"], "speedtest", datetime.now().isoformat())
            )
            conn.commit()
            conn.close()
            triggered.append(pc["name"])

    return {"status": "ok", "triggered": triggered, "count": len(triggered)}

@app.post("/api/speedtest/{computer_id}/result")
async def submit_speedtest_result(computer_id: str, request: Request):
    """Agent submits speed test result"""
    data = await request.json()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO speed_tests (computer_id, download_mbps, upload_mbps, test_time_sec, network_name, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (computer_id, data.get("download_mbps"), data.get("upload_mbps", 0), data.get("test_time_sec"), data.get("network_name", ""), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    return {"status": "recorded"}

@app.get("/api/commands/{computer_id}")
async def get_pending_commands(computer_id: str):
    """Agent polls for pending commands"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT * FROM pending_commands WHERE computer_id = ?",
        (computer_id,)
    )
    commands = [dict(row) for row in cursor]
    # Delete retrieved commands
    conn.execute("DELETE FROM pending_commands WHERE computer_id = ?", (computer_id,))
    conn.commit()
    conn.close()
    return {"commands": commands}

# ============================================
# Remote Command Execution
# ============================================
@app.post("/api/exec/{computer_id}")
async def queue_command(computer_id: str, request: Request, username: str = Depends(verify_credentials)):
    """Queue a shell command to run on a computer"""
    data = await request.json()
    cmd = data.get("command", "").strip()
    if not cmd:
        raise HTTPException(status_code=400, detail="No command provided")

    command_data = {"command": "shell", "payload": cmd}

    # Try to send via WebSocket for instant delivery
    if computer_id in active_connections:
        try:
            await active_connections[computer_id].send_json(command_data)
            return {"status": "sent", "command": cmd, "delivery": "instant"}
        except:
            pass

    # Fallback to database queue if WebSocket not available
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO pending_commands (computer_id, command, payload, created_at) VALUES (?, ?, ?, ?)",
        (computer_id, "shell", cmd, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    return {"status": "queued", "command": cmd, "delivery": "polling"}

@app.post("/api/exec/{computer_id}/result")
async def submit_command_result(computer_id: str, request: Request):
    """Agent submits command execution result"""
    data = await request.json()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO command_results (computer_id, command, output, exit_code, created_at) VALUES (?, ?, ?, ?, ?)",
        (computer_id, data.get("command"), data.get("output"), data.get("exit_code"), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    return {"status": "recorded"}

@app.get("/api/exec/{computer_id}/history")
async def get_command_history(computer_id: str, username: str = Depends(verify_credentials)):
    """Get command execution history"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(
        "SELECT * FROM command_results WHERE computer_id = ? ORDER BY created_at DESC LIMIT 50",
        (computer_id,)
    )
    results = [dict(row) for row in cursor]
    conn.close()
    return {"results": results}

# ============================================
# Metrics History (for graphs)
# ============================================
@app.get("/api/metrics/{computer_id}/history")
async def get_metrics_history(computer_id: str, hours: int = 24, username: str = Depends(verify_credentials)):
    """Get metrics history for graphs"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    cursor = conn.execute(
        "SELECT * FROM metrics_history WHERE computer_id = ? AND recorded_at > ? ORDER BY recorded_at",
        (computer_id, since)
    )
    metrics = [dict(row) for row in cursor]
    conn.close()
    return {"metrics": metrics}

# ============================================
# File Browser
# ============================================
@app.post("/api/files/{computer_id}/browse")
async def queue_file_browse(computer_id: str, request: Request, username: str = Depends(verify_credentials)):
    """Queue a file browse request"""
    data = await request.json()
    path = data.get("path", "")
    command_data = {"command": "browse", "payload": path}

    # Try WebSocket first
    if computer_id in active_connections:
        try:
            await active_connections[computer_id].send_json(command_data)
            return {"status": "sent", "path": path, "delivery": "instant"}
        except:
            pass

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO pending_commands (computer_id, command, payload, created_at) VALUES (?, ?, ?, ?)",
        (computer_id, "browse", path, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    return {"status": "queued", "path": path, "delivery": "polling"}

@app.post("/api/files/{computer_id}/download")
async def queue_file_download(computer_id: str, request: Request, username: str = Depends(verify_credentials)):
    """Queue a file download request"""
    data = await request.json()
    path = data.get("path", "")
    command_data = {"command": "download", "payload": path}

    # Try WebSocket first
    if computer_id in active_connections:
        try:
            await active_connections[computer_id].send_json(command_data)
            return {"status": "sent", "path": path, "delivery": "instant"}
        except:
            pass

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO pending_commands (computer_id, command, payload, created_at) VALUES (?, ?, ?, ?)",
        (computer_id, "download", path, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    return {"status": "queued", "path": path, "delivery": "polling"}


@app.post("/api/files/{computer_id}/upload")
async def upload_file(computer_id: str, request: Request, username: str = Depends(verify_credentials)):
    """Upload a file to a remote computer"""
    data = await request.json()
    path = data.get("path", "")
    content = data.get("content", "")  # base64 encoded
    filename = data.get("filename", "")

    if not path or not content:
        raise HTTPException(status_code=400, detail="Missing path or content")

    # Send via WebSocket
    command_data = {"command": "upload", "payload": json.dumps({"path": path, "content": content})}

    if computer_id in active_connections:
        try:
            await active_connections[computer_id].send_json(command_data)
            return {"status": "sent", "path": path, "delivery": "instant"}
        except:
            pass

    # Queue for polling (not ideal for large files but works)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO pending_commands (computer_id, command, payload, created_at) VALUES (?, ?, ?, ?)",
        (computer_id, "upload", json.dumps({"path": path, "content": content}), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    return {"status": "queued", "path": path, "delivery": "polling"}


# ============================================
# Settings (Discord/Email alerts)
# ============================================
@app.get("/api/settings")
async def get_settings(username: str = Depends(verify_credentials)):
    """Get all settings"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM settings")
    settings = {row["key"]: row["value"] for row in cursor}
    conn.close()
    return {"settings": settings}

@app.put("/api/settings")
async def update_settings(request: Request, username: str = Depends(verify_credentials)):
    """Update settings"""
    data = await request.json()
    conn = sqlite3.connect(DB_PATH)
    for key, value in data.items():
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()
    return {"status": "updated"}

@app.get("/api/config")
async def get_config(username: str = Depends(verify_credentials)):
    """Get server configuration (for displaying in UI)"""
    return {
        "admin_username": ADMIN_USERS[0]["username"],
        "agent_api_key": AGENT_API_KEY,
        # Don't expose password
    }

@app.put("/api/config/password")
async def change_password(request: Request, username: str = Depends(verify_credentials)):
    """Change password for the logged-in user"""
    global ADMIN_USERS, CONFIG
    data = await request.json()
    new_password = data.get("password", "").strip()

    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    # Update password for the current user
    for user in ADMIN_USERS:
        if user["username"] == username:
            user["password"] = new_password
            break

    CONFIG["admin_users"] = ADMIN_USERS
    with open(CONFIG_FILE, "w") as f:
        json.dump(CONFIG, f, indent=2)

    return {"status": "updated"}

@app.put("/api/config/regenerate-key")
async def regenerate_api_key(username: str = Depends(verify_credentials)):
    """Regenerate agent API key"""
    global AGENT_API_KEY, CONFIG

    CONFIG["agent_api_key"] = secrets_module.token_urlsafe(24)
    AGENT_API_KEY = CONFIG["agent_api_key"]

    with open(CONFIG_FILE, "w") as f:
        json.dump(CONFIG, f, indent=2)

    return {"status": "updated", "new_key": AGENT_API_KEY}

# ============================================
# Computer rename
# ============================================
@app.put("/api/computers/{computer_id}/rename")
async def rename_computer(computer_id: str, request: Request, username: str = Depends(verify_credentials)):
    """Rename a computer's display name"""
    data = await request.json()
    new_name = data.get("name", "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="Name required")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE computers SET name = ? WHERE id = ?", (new_name, computer_id))
    conn.commit()
    conn.close()
    return {"status": "renamed", "name": new_name}

@app.put("/api/computers/{computer_id}/location")
async def update_computer_location(computer_id: str, request: Request, username: str = Depends(verify_credentials)):
    """Update computer's location (manual or from geolocation)"""
    data = await request.json()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE computers SET latitude = ?, longitude = ?, location_name = ? WHERE id = ?",
        (data.get("latitude", 0), data.get("longitude", 0), data.get("location_name", ""), computer_id)
    )
    conn.commit()
    conn.close()
    return {"status": "updated"}

@app.get("/api/computers/locations")
async def get_all_locations(username: str = Depends(verify_credentials)):
    """Get all computers with their locations for map view"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT id, name, ip, latitude, longitude, location_name, cpu_percent, memory_percent, disk_percent, last_seen FROM computers")
    locations = []
    for row in cursor:
        last_seen = datetime.fromisoformat(row["last_seen"])
        is_online = datetime.now() - last_seen < timedelta(minutes=2)
        locations.append({
            "id": row["id"],
            "name": row["name"],
            "ip": row["ip"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "location_name": row["location_name"],
            "cpu_percent": row["cpu_percent"],
            "memory_percent": row["memory_percent"],
            "disk_percent": row["disk_percent"],
            "is_online": is_online
        })
    conn.close()
    return {"locations": locations}

@app.get("/api/geolocate/{computer_id}")
async def geolocate_computer(computer_id: str, username: str = Depends(verify_credentials)):
    """Get geolocation from IP address"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT ip FROM computers WHERE id = ?", (computer_id,)).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Computer not found")

    try:
        import urllib.request
        ip = row['ip']

        # Check if it's a local/private IP - if so, get public IP instead
        is_local = (
            ip.startswith('192.168.') or
            ip.startswith('10.') or
            ip.startswith('172.16.') or ip.startswith('172.17.') or ip.startswith('172.18.') or
            ip.startswith('172.19.') or ip.startswith('172.2') or ip.startswith('172.30.') or ip.startswith('172.31.') or
            ip.startswith('127.') or
            ip == 'localhost'
        )

        if is_local:
            # For local IPs, query without IP to get server's public IP location
            # (assumes computers on same network have same public IP)
            url = "http://ip-api.com/json/?fields=status,lat,lon,city,regionName,country,query"
        else:
            url = f"http://ip-api.com/json/{ip}?fields=status,lat,lon,city,regionName,country,query"

        req = urllib.request.Request(url, headers={'User-Agent': 'PC-Monitor/1.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            print(f"[Geolocation] Response for {ip}: {data}")
            if data.get("status") == "success":
                return {
                    "latitude": data.get("lat", 0),
                    "longitude": data.get("lon", 0),
                    "location_name": f"{data.get('city', '')}, {data.get('regionName', '')}, {data.get('country', '')}".strip(", "),
                    "public_ip": data.get("query", "")
                }
            else:
                print(f"[Geolocation] API returned failure: {data}")
    except Exception as e:
        print(f"[Geolocation] Failed: {e}")

    raise HTTPException(status_code=500, detail="Could not geolocate IP - check server logs")

@app.post("/api/wake/{computer_id}")
async def wake_computer(computer_id: str, username: str = Depends(verify_credentials)):
    """Send Wake-on-LAN packet to a computer"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT mac_address, name FROM computers WHERE id = ?", (computer_id,)).fetchone()
    conn.close()

    if not row or not row["mac_address"]:
        raise HTTPException(status_code=400, detail="No MAC address stored for this computer")

    mac = row["mac_address"]
    try:
        # Send WoL magic packet
        mac_bytes = bytes.fromhex(mac.replace(":", "").replace("-", ""))
        magic_packet = b'\xff' * 6 + mac_bytes * 16

        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(magic_packet, ('255.255.255.255', 9))
        sock.close()

        return {"status": "sent", "message": f"Wake-on-LAN packet sent to {row['name']}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# WebSocket for Real-Time Communication
# ============================================
@app.websocket("/ws/{computer_id}")
async def websocket_endpoint(websocket: WebSocket, computer_id: str):
    """Real-time WebSocket connection for instant command delivery"""
    # Get API key from query params
    api_key = websocket.query_params.get("key", "")
    if api_key != AGENT_API_KEY:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    active_connections[computer_id] = websocket
    print(f"[WebSocket] Agent connected: {computer_id}")

    try:
        while True:
            # Receive results from agent
            data = await websocket.receive_json()

            if data.get("type") == "command_result":
                # Store command result
                conn = sqlite3.connect(DB_PATH)
                conn.execute(
                    "INSERT INTO command_results (computer_id, command, output, exit_code, created_at) VALUES (?, ?, ?, ?, ?)",
                    (computer_id, data.get("command"), data.get("output"), data.get("exit_code"), datetime.now().isoformat())
                )
                conn.commit()
                conn.close()

            elif data.get("type") == "speedtest_result":
                # Store speed test result
                conn = sqlite3.connect(DB_PATH)
                conn.execute(
                    "INSERT INTO speed_tests (computer_id, download_mbps, upload_mbps, test_time_sec, network_name, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (computer_id, data.get("download_mbps"), data.get("upload_mbps", 0), data.get("test_time_sec"), data.get("network_name", ""), datetime.now().isoformat())
                )
                conn.commit()
                conn.close()

            elif data.get("type") == "heartbeat":
                # Handle heartbeat via WebSocket (optional, for efficiency)
                pass

    except WebSocketDisconnect:
        print(f"[WebSocket] Agent disconnected: {computer_id}")
    except Exception as e:
        print(f"[WebSocket] Error for {computer_id}: {e}")
    finally:
        if computer_id in active_connections:
            del active_connections[computer_id]

# ============================================
# Prometheus Metrics Endpoint (for Grafana)
# ============================================
@app.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    """Expose metrics in Prometheus format for Grafana"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM computers")

    lines = [
        "# HELP pc_monitor_cpu_percent CPU usage percentage",
        "# TYPE pc_monitor_cpu_percent gauge",
        "# HELP pc_monitor_memory_percent Memory usage percentage",
        "# TYPE pc_monitor_memory_percent gauge",
        "# HELP pc_monitor_disk_percent Disk usage percentage",
        "# TYPE pc_monitor_disk_percent gauge",
        "# HELP pc_monitor_online Whether the computer is online",
        "# TYPE pc_monitor_online gauge",
    ]

    for row in cursor:
        last_seen = datetime.fromisoformat(row["last_seen"])
        is_online = 1 if datetime.now() - last_seen < timedelta(minutes=2) else 0
        labels = f'computer="{row["name"]}",id="{row["id"]}"'

        lines.append(f'pc_monitor_cpu_percent{{{labels}}} {row["cpu_percent"]}')
        lines.append(f'pc_monitor_memory_percent{{{labels}}} {row["memory_percent"]}')
        lines.append(f'pc_monitor_disk_percent{{{labels}}} {row["disk_percent"]}')
        lines.append(f'pc_monitor_online{{{labels}}} {is_online}')

    conn.close()
    return "\n".join(lines) + "\n"

# ============================================
# Serve the dashboard
# ============================================
@app.get("/", response_class=HTMLResponse)
async def dashboard(username: str = Depends(verify_credentials)):
    """Serve the main dashboard with credentials injected"""
    dashboard_path = os.path.join(BUNDLE_DIR, "dashboard", "index.html")
    with open(dashboard_path, "r") as f:
        html = f.read()

    # Inject actual credentials into the dashboard
    first_user = ADMIN_USERS[0]["username"]
    first_pass = ADMIN_USERS[0]["password"]
    html = html.replace(
        "const authHeader = 'Basic ' + btoa('admin:admin');",
        f"const authHeader = 'Basic ' + btoa('{first_user}:{first_pass}');"
    )
    # Update the refresh info line
    html = html.replace(
        'Login: admin/admin',
        f'Login: {first_user} / (see config.json)'
    )
    return html

@app.get("/api/agent/version")
async def get_agent_version(username: str = Depends(verify_credentials)):
    """Get the latest agent version available on the server"""
    import re
    agent_path = os.path.join(BUNDLE_DIR, "agent", "agent.py")
    with open(agent_path, "r", encoding="utf-8") as f:
        content = f.read()

    version_match = re.search(r'AGENT_VERSION\s*=\s*["\']([^"\']+)["\']', content)
    version = version_match.group(1) if version_match else "unknown"

    return {"version": version}


@app.post("/api/agent/update/{computer_id}")
async def trigger_agent_update(computer_id: str, username: str = Depends(verify_credentials)):
    """Trigger an update on a specific agent"""
    if computer_id in active_connections:
        try:
            ws = active_connections[computer_id]
            await ws.send_json({"command": "update", "payload": ""})
            return {"status": "update_sent", "computer_id": computer_id}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    else:
        return {"status": "offline", "message": "Computer is not connected via WebSocket"}


@app.post("/api/agent/update-all")
async def trigger_update_all(username: str = Depends(verify_credentials)):
    """Trigger an update on all connected agents"""
    results = {"updated": [], "offline": [], "errors": []}

    # Get all computers
    conn = sqlite3.connect(DB_PATH)
    computers = conn.execute("SELECT id, name FROM computers").fetchall()
    conn.close()

    for computer_id, name in computers:
        if computer_id in active_connections:
            try:
                ws = active_connections[computer_id]
                await ws.send_json({"command": "update", "payload": ""})
                results["updated"].append({"id": computer_id, "name": name})
            except Exception as e:
                results["errors"].append({"id": computer_id, "name": name, "error": str(e)})
        else:
            results["offline"].append({"id": computer_id, "name": name})

    return results


@app.post("/api/rustdesk/{computer_id}/set-password")
async def set_rustdesk_password(computer_id: str, request: Request, username: str = Depends(verify_credentials)):
    """Set RustDesk permanent password on a remote computer"""
    data = await request.json()
    password = data.get("password", "")

    if not password:
        raise HTTPException(status_code=400, detail="Password required")

    if computer_id in active_connections:
        try:
            ws = active_connections[computer_id]
            await ws.send_json({"command": "rustdesk_set_password", "payload": password})
            return {"status": "sent", "message": "Password set command sent"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    else:
        return {"status": "offline", "message": "Computer is not connected"}


@app.get("/api/rustdesk/{computer_id}/connect")
async def get_rustdesk_connect_url(computer_id: str, username: str = Depends(verify_credentials)):
    """Get RustDesk connection URL for one-click connect"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT extra_info FROM computers WHERE id = ?", (computer_id,)).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Computer not found")

    extra = json.loads(row["extra_info"] or "{}")
    rustdesk_id = extra.get("rustdesk_id")
    rustdesk_password = extra.get("rustdesk_password")

    if not rustdesk_id:
        return {"status": "not_installed", "message": "RustDesk not installed or ID not found"}

    # Build connection URL
    # Format: rustdesk://connection/new/ID?password=PASSWORD
    if rustdesk_password:
        connect_url = f"rustdesk://connection/new/{rustdesk_id}?password={rustdesk_password}"
    else:
        connect_url = f"rustdesk://connection/new/{rustdesk_id}"

    return {
        "status": "ok",
        "rustdesk_id": rustdesk_id,
        "has_password": bool(rustdesk_password),
        "connect_url": connect_url
    }


@app.get("/install/agent.py")
async def get_agent_script(request: Request, key: str = ""):
    """Serve the agent script with configuration pre-filled"""
    if key != AGENT_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid key")

    agent_path = os.path.join(BUNDLE_DIR, "agent", "agent.py")
    with open(agent_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Get server URL from request
    host = request.headers.get("host", "localhost:8000")
    server_url = f"http://{host}"

    # Pre-configure the agent with server URL and API key
    content = content.replace('SERVER_URL = "CONFIGURE_ME"', f'SERVER_URL = "{server_url}"')
    content = content.replace('API_KEY = "CONFIGURE_ME"', f'API_KEY = "{AGENT_API_KEY}"')

    return PlainTextResponse(content, media_type="text/plain; charset=utf-8")

@app.get("/install/agent-config.json")
async def get_agent_config(request: Request, key: str = ""):
    """Serve a config file for the agent"""
    if key != AGENT_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid key")

    host = request.headers.get("host", "localhost:8000")
    server_url = f"http://{host}"

    config = {
        "server_url": server_url,
        "api_key": AGENT_API_KEY,
        "heartbeat_interval": 60,
        "auto_update": True
    }

    return JSONResponse(config)

@app.get("/i")
async def quick_install_script(request: Request):
    """Super short URL for quick install: curl http://server:8000/i | bash"""
    host = request.headers.get("host", "localhost:8000")
    server_url = f"http://{host}"

    script = f'''#!/bin/bash
# PC Monitor Agent - Quick Install
# Usage: curl -sL {server_url}/i | bash

echo "Installing PC Monitor Agent..."
mkdir -p ~/pc-monitor
cd ~/pc-monitor

# Download pre-configured agent
curl -s "{server_url}/install/agent.py?key={AGENT_API_KEY}" -o agent.py

# Download config file
curl -s "{server_url}/install/agent-config.json?key={AGENT_API_KEY}" -o agent-config.json

# Install dependencies
if pip3 install psutil websockets 2>/dev/null; then
    PYTHON="python3"
elif pip3 install --user psutil websockets 2>/dev/null; then
    PYTHON="python3"
else
    echo "Creating virtual environment..."
    python3 -m venv venv
    venv/bin/pip install psutil websockets
    PYTHON="venv/bin/python"
fi

echo ""
echo "========================================"
echo "  Installation complete!"
echo "========================================"
echo ""
echo "To run: $PYTHON ~/pc-monitor/agent.py"
echo ""
echo "Starting agent now..."
exec $PYTHON ~/pc-monitor/agent.py
'''
    return PlainTextResponse(script, media_type="text/plain")

@app.get("/i.ps1")
async def quick_install_powershell(request: Request):
    """PowerShell install: iwr http://server:8000/i.ps1 | iex"""
    host = request.headers.get("host", "localhost:8000")
    server_url = f"http://{host}"

    script = f'''# PC Monitor Agent - Quick Install (PowerShell)
# Usage: iwr {server_url}/i.ps1 | iex

Write-Host "Installing PC Monitor Agent..."
$dir = "$env:USERPROFILE\\pc-monitor"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
Set-Location $dir

# Download pre-configured agent
Invoke-WebRequest -Uri "{server_url}/install/agent.py?key={AGENT_API_KEY}" -OutFile "agent.py"

# Download config file
Invoke-WebRequest -Uri "{server_url}/install/agent-config.json?key={AGENT_API_KEY}" -OutFile "agent-config.json"

# Install dependencies
pip install psutil websockets 2>$null

Write-Host ""
Write-Host "========================================"
Write-Host "  Installation complete!"
Write-Host "========================================"
Write-Host ""
Write-Host "To run: python $dir\\agent.py"
Write-Host ""
Write-Host "Starting agent now..."
python agent.py
'''
    return PlainTextResponse(script, media_type="text/plain")

@app.get("/api/install-commands")
async def get_install_commands(request: Request, username: str = Depends(verify_credentials)):
    """Generate install commands for each platform"""
    # Get the server's URL from the request
    host = request.headers.get("host", "localhost:8000")
    scheme = "http"  # Assume http for local network
    server_url = f"{scheme}://{host}"

    # SIMPLE ONE-LINER for Linux/Mac - just pipe to bash
    linux_simple = f'''curl -sL {server_url}/i | bash'''
    mac_simple = f'''curl -sL {server_url}/i | bash'''
    windows_simple = f'''powershell -c "iwr {server_url}/i.ps1 | iex"'''

    # Windows PowerShell - Full setup (Agent + RustDesk)
    windows_full = f'''powershell -ExecutionPolicy Bypass -Command "iwr {server_url}/i.ps1 | iex; Write-Host 'Installing RustDesk...'; Invoke-WebRequest -Uri 'https://github.com/rustdesk/rustdesk/releases/download/1.4.5/rustdesk-1.4.5-x86_64.exe' -OutFile $env:TEMP\\rustdesk.exe; Start-Process $env:TEMP\\rustdesk.exe -ArgumentList '--silent-install' -Wait"'''

    # Windows - Agent only (simple)
    windows_agent = windows_simple

    # Linux/Ubuntu - Full setup (Agent + RustDesk)
    linux_full = f'''curl -sL {server_url}/i | bash; wget -qO /tmp/rustdesk.deb https://github.com/rustdesk/rustdesk/releases/download/1.4.5/rustdesk-1.4.5-x86_64.deb && sudo dpkg -i /tmp/rustdesk.deb; sudo apt install -f -y'''

    # Linux/Ubuntu - Agent only (simple)
    linux_agent = linux_simple

    # Mac - Full setup (Agent + RustDesk)
    mac_full = f'''curl -sL {server_url}/i | bash; curl -L -o /tmp/rustdesk.dmg https://github.com/rustdesk/rustdesk/releases/download/1.4.5/rustdesk-1.4.5-x86_64.dmg && hdiutil attach /tmp/rustdesk.dmg && cp -R "/Volumes/RustDesk/RustDesk.app" /Applications/ && hdiutil detach "/Volumes/RustDesk"'''

    # Mac - Agent only (simple)
    mac_agent = mac_simple

    return {
        "server_url": server_url,
        "api_key": AGENT_API_KEY,
        "windows_full": windows_full,
        "windows_agent": windows_agent,
        "linux_full": linux_full,
        "linux_agent": linux_agent,
        "mac_full": mac_full,
        "mac_agent": mac_agent,
        # Backwards compatibility
        "windows": windows_agent,
        "linux": linux_agent,
        "mac": mac_agent
    }

if __name__ == "__main__":
    import uvicorn
    import socket

    def find_available_port(start_port=8000, max_attempts=10):
        """Find an available port, starting from start_port"""
        for port in range(start_port, start_port + max_attempts):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("0.0.0.0", port))
                sock.close()
                return port
            except OSError:
                continue
        return None

    # Get local IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        local_ip = "localhost"

    # Find available port
    port = find_available_port(8000)
    if port is None:
        print("ERROR: Could not find an available port (tried 8000-8009)")
        sys.exit(1)

    if port != 8000:
        print(f"Note: Port 8000 was in use, using port {port} instead")

    scripts_dir = os.path.join(BUNDLE_DIR, "install-scripts")

    # Show all admin users
    users_str = ", ".join([f"{u['username']}" for u in ADMIN_USERS])

    print(f"""
    ╔════════════════════════════════════════════════════════════════╗
    ║                      PC Monitor Server                         ║
    ╠════════════════════════════════════════════════════════════════╣
    ║  Dashboard:      http://{local_ip}:{port}
    ║  Users:          {users_str}
    ║  (passwords in config.json)
    ╠════════════════════════════════════════════════════════════════╣
    ║  TO ADD COMPUTERS:                                             ║
    ║  Copy files from: install-scripts/                             ║
    ║    - Windows: Run install-windows.bat                          ║
    ║    - Mac/Linux: Run install-mac-linux.sh                       ║
    ║    - Or see README.txt for credentials                         ║
    ╚════════════════════════════════════════════════════════════════╝
    """)
    uvicorn.run(app, host="0.0.0.0", port=port)
