"""
PC Monitor Agent
Install this on each computer you want to monitor.
Sends heartbeats with system info to the central server.
Uses WebSockets for instant command response!
"""

AGENT_VERSION = "1.5.1"  # Increment this when updating the agent

import platform
import socket
import time
import uuid
import json
import os
import sys
import urllib.request
import urllib.error
import subprocess
import threading

# Hide console windows for subprocess on Windows
SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0

# ============================================
# CONFIGURATION - Set by server when downloaded
# ============================================
SERVER_URL = "CONFIGURE_ME"
API_KEY = "CONFIGURE_ME"
HEARTBEAT_INTERVAL = 60  # seconds
COMMAND_POLL_INTERVAL = 5  # seconds - fallback if WebSocket unavailable
COMPUTER_NAME = platform.node()
AUTO_UPDATE = True
AUTO_UPDATE_INTERVAL = 300  # Check for updates every 5 minutes
# ============================================

# WebSocket connection state
ws_connected = False
ws_connection = None

# Generate a unique ID for this computer (persisted to file)
ID_FILE = os.path.join(os.path.expanduser("~"), ".pc_monitor_id")

# Speed test cache (only run every 10 minutes)
_speed_test_cache = {"result": None, "timestamp": 0}
SPEED_TEST_INTERVAL = 600  # 10 minutes

def get_computer_id():
    """Get or create a unique ID for this computer"""
    if os.path.exists(ID_FILE):
        with open(ID_FILE, "r") as f:
            return f.read().strip()

    new_id = str(uuid.uuid4())[:8]
    with open(ID_FILE, "w") as f:
        f.write(new_id)
    return new_id

def get_mac_address():
    """Get the MAC address of the primary network interface"""
    try:
        import psutil
        for iface, addrs in psutil.net_if_addrs().items():
            # Skip loopback
            if iface.lower() in ['lo', 'loopback']:
                continue
            for addr in addrs:
                # AF_LINK on Mac, AF_PACKET on Linux, -1 on Windows
                if addr.family in [psutil.AF_LINK, -1] or (hasattr(psutil, 'AF_PACKET') and addr.family == psutil.AF_PACKET):
                    if addr.address and addr.address != '00:00:00:00:00:00':
                        return addr.address
    except:
        pass

    # Fallback for Windows
    try:
        import uuid as uuid_mod
        mac = ':'.join(['{:02x}'.format((uuid_mod.getnode() >> i) & 0xff) for i in range(0, 48, 8)][::-1])
        return mac
    except:
        pass

    return None

def get_rustdesk_info():
    """Get RustDesk ID and permanent password if installed"""
    info = {"id": None, "password": None, "installed": False}

    try:
        # Determine config paths based on OS
        if platform.system() == "Windows":
            config_paths = [
                os.path.join(os.environ.get("APPDATA", ""), "RustDesk", "config")
            ]
        elif platform.system() == "Darwin":  # macOS
            config_paths = [
                os.path.expanduser("~/Library/Application Support/rustdesk/config"),
                os.path.expanduser("~/.config/rustdesk")  # Fallback for older versions
            ]
        else:  # Linux
            config_paths = [
                os.path.expanduser("~/.config/rustdesk")
            ]

        rustdesk_conf = None
        rustdesk_conf2 = None

        # Find config files
        for config_dir in config_paths:
            conf = os.path.join(config_dir, "RustDesk.toml")
            conf2 = os.path.join(config_dir, "RustDesk2.toml")
            if os.path.exists(conf):
                rustdesk_conf = conf
                info["installed"] = True
            if os.path.exists(conf2):
                rustdesk_conf2 = conf2
                info["installed"] = True
            if rustdesk_conf or rustdesk_conf2:
                break

        # Also check if RustDesk app exists on Mac
        if platform.system() == "Darwin" and not info["installed"]:
            if os.path.exists("/Applications/RustDesk.app"):
                info["installed"] = True

        # Get ID from RustDesk.toml (try plain 'id' first, then use --get-id command)
        if rustdesk_conf and os.path.exists(rustdesk_conf):
            with open(rustdesk_conf, "r") as f:
                for line in f:
                    # Old format: id = '123456789'
                    if line.strip().startswith("id =") and not line.strip().startswith("id_"):
                        info["id"] = line.split("=")[1].strip().strip("'\"")
                        break

        # If no plain ID found, try to get it via command line (works with newer RustDesk)
        if not info["id"] and info["installed"]:
            rustdesk_paths = ["rustdesk"]
            if platform.system() == "Windows":
                rustdesk_paths.extend([
                    r"C:\Program Files\RustDesk\rustdesk.exe",
                    os.path.expandvars(r"%LOCALAPPDATA%\RustDesk\rustdesk.exe"),
                ])
            elif platform.system() == "Darwin":
                rustdesk_paths.extend([
                    "/Applications/RustDesk.app/Contents/MacOS/RustDesk",
                ])

            for rustdesk_exe in rustdesk_paths:
                try:
                    result = subprocess.run(
                        [rustdesk_exe, "--get-id"],
                        capture_output=True, text=True, timeout=5,
                        creationflags=SUBPROCESS_FLAGS
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        info["id"] = result.stdout.strip()
                        break
                except:
                    continue

        # Get permanent password from RustDesk2.toml
        if rustdesk_conf2 and os.path.exists(rustdesk_conf2):
            with open(rustdesk_conf2, "r") as f:
                for line in f:
                    if line.strip().startswith("password"):
                        pwd = line.split("=")[1].strip().strip("'\"")
                        if pwd:  # Only set if not empty
                            info["password"] = pwd
                        break
    except:
        pass

    return info


def get_rustdesk_id():
    """Try to get RustDesk ID if installed (backwards compatible)"""
    return get_rustdesk_info()["id"]


def set_rustdesk_password(password):
    """Set RustDesk permanent password for unattended access"""
    try:
        if platform.system() == "Windows":
            rustdesk_conf2 = os.path.join(os.environ.get("APPDATA", ""), "RustDesk", "config", "RustDesk2.toml")
        elif platform.system() == "Darwin":  # macOS
            rustdesk_conf2 = os.path.expanduser("~/Library/Application Support/rustdesk/config/RustDesk2.toml")
            # Fallback to old path if new path doesn't exist
            if not os.path.exists(os.path.dirname(rustdesk_conf2)):
                rustdesk_conf2 = os.path.expanduser("~/.config/rustdesk/RustDesk2.toml")
        else:
            rustdesk_conf2 = os.path.expanduser("~/.config/rustdesk/RustDesk2.toml")

        # Read existing config
        config_lines = []
        password_found = False

        if os.path.exists(rustdesk_conf2):
            with open(rustdesk_conf2, "r") as f:
                for line in f:
                    if line.strip().startswith("password"):
                        config_lines.append(f'password = "{password}"\n')
                        password_found = True
                    else:
                        config_lines.append(line)

        if not password_found:
            config_lines.append(f'password = "{password}"\n')

        # Ensure directory exists
        os.makedirs(os.path.dirname(rustdesk_conf2), exist_ok=True)

        # Write config
        with open(rustdesk_conf2, "w") as f:
            f.writelines(config_lines)

        return {"output": f"RustDesk password set successfully", "exit_code": 0}
    except Exception as e:
        return {"output": str(e), "exit_code": -1}

def get_gpu_info():
    """Try to get GPU information"""
    gpus = []

    # Try Windows WMI
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ['wmic', 'path', 'win32_videocontroller', 'get', 'name,adapterram'],
                capture_output=True, text=True, timeout=10, creationflags=SUBPROCESS_FLAGS
            )
            lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip() and 'Name' not in l]
            for line in lines:
                if line:
                    gpus.append(line.split('  ')[0].strip())
        except:
            pass

    # Try nvidia-smi
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=name,temperature.gpu,utilization.gpu', '--format=csv,noheader'],
                              capture_output=True, text=True, timeout=10, creationflags=SUBPROCESS_FLAGS)
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                parts = line.split(', ')
                if len(parts) >= 3:
                    gpus.append({
                        "name": parts[0],
                        "temp": parts[1],
                        "utilization": parts[2]
                    })
    except:
        pass

    return gpus if gpus else None

def get_network_info():
    """Get network speed/stats"""
    try:
        import psutil
        net = psutil.net_io_counters()
        return {
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
            "packets_sent": net.packets_sent,
            "packets_recv": net.packets_recv
        }
    except:
        return None

def get_connected_network():
    """Get the name of the connected network (WiFi SSID or Ethernet)"""
    try:
        if platform.system() == "Windows":
            # Try to get WiFi SSID
            result = subprocess.run(
                ['netsh', 'wlan', 'show', 'interfaces'],
                capture_output=True, text=True, timeout=5, creationflags=SUBPROCESS_FLAGS
            )
            for line in result.stdout.split('\n'):
                if 'SSID' in line and 'BSSID' not in line:
                    ssid = line.split(':')[1].strip()
                    if ssid:
                        return {"type": "WiFi", "name": ssid}

            # If no WiFi, check for Ethernet
            import psutil
            for iface, addrs in psutil.net_if_stats().items():
                if addrs.isup and 'ethernet' in iface.lower():
                    return {"type": "Ethernet", "name": iface}

        elif platform.system() == "Darwin":  # macOS
            result = subprocess.run(
                ['/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport', '-I'],
                capture_output=True, text=True, timeout=5, creationflags=SUBPROCESS_FLAGS
            )
            for line in result.stdout.split('\n'):
                if ' SSID:' in line:
                    return {"type": "WiFi", "name": line.split(':')[1].strip()}

        else:  # Linux
            result = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True, timeout=5, creationflags=SUBPROCESS_FLAGS)
            if result.returncode == 0 and result.stdout.strip():
                return {"type": "WiFi", "name": result.stdout.strip()}

            # Check for ethernet
            result = subprocess.run(['ip', 'route', 'get', '1'], capture_output=True, text=True, timeout=5, creationflags=SUBPROCESS_FLAGS)
            if 'eth' in result.stdout or 'enp' in result.stdout:
                return {"type": "Ethernet", "name": "Wired Connection"}
    except:
        pass
    return None

def get_wifi_signal_strength():
    """Get WiFi signal strength percentage"""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ['netsh', 'wlan', 'show', 'interfaces'],
                capture_output=True, text=True, timeout=5, creationflags=SUBPROCESS_FLAGS
            )
            for line in result.stdout.split('\n'):
                if 'Signal' in line:
                    # Extract percentage like "Signal : 85%"
                    signal = line.split(':')[1].strip().replace('%', '')
                    return int(signal)
        elif platform.system() == "Darwin":  # macOS
            result = subprocess.run(
                ['/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport', '-I'],
                capture_output=True, text=True, timeout=5, creationflags=SUBPROCESS_FLAGS
            )
            for line in result.stdout.split('\n'):
                if 'agrCtlRSSI' in line:
                    rssi = int(line.split(':')[1].strip())
                    # Convert RSSI to percentage (rough approximation)
                    return max(0, min(100, 2 * (rssi + 100)))
        else:  # Linux
            result = subprocess.run(['iwconfig'], capture_output=True, text=True, timeout=5, creationflags=SUBPROCESS_FLAGS)
            import re
            match = re.search(r'Signal level[=:](-?\d+)', result.stdout)
            if match:
                rssi = int(match.group(1))
                return max(0, min(100, 2 * (rssi + 100)))
    except:
        pass
    return None

def run_speed_test():
    """Run a speed test (download and upload) using speedtest-cli for accuracy"""
    # Get network name before test
    network = get_connected_network()
    network_name = f"{network['name']} ({network['type']})" if network else ""

    result = {
        "download_mbps": 0,
        "upload_mbps": 0,
        "test_time_sec": 0,
        "network_name": network_name,
        "method": "basic"  # Will be updated to "speedtest-cli" if successful
    }

    # Try speedtest-cli first (accurate results)
    try:
        import speedtest
        print("    Using speedtest-cli (accurate)...")
        start_time = time.time()

        st = speedtest.Speedtest()
        print("    Finding best server...")
        st.get_best_server()

        print("    Download test...")
        download_speed = st.download()
        result["download_mbps"] = round(download_speed / 1_000_000, 2)
        print(f"    Download: {result['download_mbps']} Mbps")

        print("    Upload test...")
        upload_speed = st.upload()
        result["upload_mbps"] = round(upload_speed / 1_000_000, 2)
        print(f"    Upload: {result['upload_mbps']} Mbps")

        result["test_time_sec"] = round(time.time() - start_time, 2)
        result["method"] = "speedtest-cli"  # Mark as accurate

        # Add server info to network name
        server = st.results.server
        if server and result["network_name"]:
            result["network_name"] += f" -> {server['sponsor']}"
        elif server:
            result["network_name"] = server['sponsor']

        return result
    except ImportError:
        print("    speedtest-cli not installed, using basic test...")
        print("    (Install with: pip install speedtest-cli)")
    except Exception as e:
        print(f"    speedtest-cli failed: {e}, using basic test...")

    # Fallback to basic test if speedtest-cli unavailable
    download_urls = [
        "http://speedtest.tele2.net/1MB.zip",
        "http://proof.ovh.net/files/1Mb.dat",
        "http://ipv4.download.thinkbroadband.com/1MB.zip",
    ]

    print("    Download test (basic)...")
    for url in download_urls:
        try:
            start_time = time.time()
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req, timeout=30)
            data = response.read()
            elapsed = time.time() - start_time

            size_bits = len(data) * 8
            result["download_mbps"] = round((size_bits / elapsed) / 1_000_000, 2)
            result["test_time_sec"] += round(elapsed, 2)
            print(f"    Download: {result['download_mbps']} Mbps")
            break
        except Exception as e:
            continue

    upload_urls = [
        "http://speedtest.tele2.net/upload.php",
        "https://httpbin.org/post",
    ]

    print("    Upload test (basic)...")
    upload_data = b'0' * (500 * 1024)

    for url in upload_urls:
        try:
            start_time = time.time()
            req = urllib.request.Request(
                url,
                data=upload_data,
                headers={'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/octet-stream'}
            )
            response = urllib.request.urlopen(req, timeout=30)
            response.read()
            elapsed = time.time() - start_time

            size_bits = len(upload_data) * 8
            result["upload_mbps"] = round((size_bits / elapsed) / 1_000_000, 2)
            result["test_time_sec"] += round(elapsed, 2)
            print(f"    Upload: {result['upload_mbps']} Mbps")
            break
        except Exception as e:
            continue

    if result["download_mbps"] > 0:
        return result
    return None

def get_all_disks():
    """Get info about all disks"""
    disks = []
    try:
        import psutil
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disks.append({
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype,
                    "total_gb": round(usage.total / (1024**3), 1),
                    "used_gb": round(usage.used / (1024**3), 1),
                    "free_gb": round(usage.free / (1024**3), 1),
                    "percent": usage.percent
                })
            except:
                pass
    except:
        pass
    return disks

def get_top_processes(limit=10):
    """Get top processes by CPU and memory usage"""
    processes = []
    # Processes to ignore (system pseudo-processes that don't represent real usage)
    ignore_names = {
        'system idle process', 'idle', 'system', 'registry',
        'memory compression', 'secure system', 'kernel_task'
    }
    try:
        import psutil

        # Get CPU count to normalize percentages
        cpu_count = psutil.cpu_count() or 1

        # First pass: initialize CPU measurement for all processes
        proc_list = []
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                proc.cpu_percent()  # First call initializes measurement
                proc_list.append(proc)
            except:
                pass

        # Wait a bit for CPU measurement
        time.sleep(0.1)

        # Second pass: get actual CPU and memory percentages
        for proc in proc_list:
            try:
                name = proc.info['name'] or ''

                # Skip system pseudo-processes
                if name.lower() in ignore_names:
                    continue

                # Get CPU and normalize to total CPU (not per-core)
                cpu_val = proc.cpu_percent() / cpu_count
                mem_val = proc.memory_percent()

                # Skip negligible processes
                if cpu_val < 0.1 and mem_val < 0.1:
                    continue

                processes.append({
                    "pid": proc.info['pid'],
                    "name": name,
                    "cpu": round(cpu_val, 1),
                    "memory": round(mem_val, 1)
                })
            except:
                pass

        # Sort by CPU usage and return top N
        processes.sort(key=lambda x: x['cpu'], reverse=True)
        return processes[:limit]
    except:
        return []

def get_temperatures():
    """Try to get CPU/system temperatures"""
    temps = {}
    try:
        import psutil
        if hasattr(psutil, 'sensors_temperatures'):
            sensor_temps = psutil.sensors_temperatures()
            for name, entries in sensor_temps.items():
                for entry in entries:
                    if entry.current:
                        temps[f"{name}_{entry.label or 'temp'}"] = round(entry.current, 1)
    except:
        pass
    return temps if temps else None

def get_system_info():
    """Collect system information"""
    info = {
        "id": get_computer_id(),
        "name": COMPUTER_NAME,
        "ip": get_local_ip(),
        "os": f"{platform.system()} {platform.release()}",
        "agent_version": AGENT_VERSION,
        "cpu_percent": 0,
        "memory_percent": 0,
        "disk_percent": 0,
        "extra": {
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "architecture": platform.machine(),
        }
    }

    # Add MAC address for Wake-on-LAN
    mac = get_mac_address()
    if mac:
        info["extra"]["mac_address"] = mac

    # Add RustDesk info if available
    rustdesk_info = get_rustdesk_info()
    if rustdesk_info["installed"]:
        info["extra"]["rustdesk_installed"] = True
        if rustdesk_info["id"]:
            info["extra"]["rustdesk_id"] = rustdesk_info["id"]
        if rustdesk_info["password"]:
            info["extra"]["rustdesk_password"] = rustdesk_info["password"]

    # Try to get detailed stats if psutil is available
    try:
        import psutil
        info["cpu_percent"] = psutil.cpu_percent(interval=1)
        info["memory_percent"] = psutil.virtual_memory().percent

        # Primary disk
        if platform.system() == "Windows":
            info["disk_percent"] = psutil.disk_usage("C:\\").percent
        else:
            info["disk_percent"] = psutil.disk_usage("/").percent

        # Extra info
        info["extra"]["cpu_count"] = psutil.cpu_count()
        info["extra"]["cpu_count_physical"] = psutil.cpu_count(logical=False)
        info["extra"]["memory_total_gb"] = round(psutil.virtual_memory().total / (1024**3), 1)
        info["extra"]["memory_available_gb"] = round(psutil.virtual_memory().available / (1024**3), 1)

        # Uptime
        info["extra"]["uptime_seconds"] = int(time.time() - psutil.boot_time())

        # Process count
        info["extra"]["process_count"] = len(psutil.pids())

        # All disks
        info["extra"]["disks"] = get_all_disks()

        # Network stats
        network = get_network_info()
        if network:
            info["extra"]["network"] = network

        # Connected network name (WiFi/Ethernet)
        connected_net = get_connected_network()
        if connected_net:
            info["extra"]["connected_network"] = connected_net

        # WiFi signal strength
        wifi_signal = get_wifi_signal_strength()
        if wifi_signal is not None:
            info["extra"]["wifi_signal"] = wifi_signal

        # Top processes
        info["extra"]["top_processes"] = get_top_processes(10)

        # Check for duplicate agents
        instance_count, duplicate_pids = count_agent_instances()
        if instance_count > 1:
            info["extra"]["duplicate_agents"] = instance_count
            info["extra"]["duplicate_pids"] = duplicate_pids

    except ImportError:
        print("Note: Install psutil for detailed metrics: pip install psutil")

    # GPU info (works without psutil)
    gpu = get_gpu_info()
    if gpu:
        info["extra"]["gpu"] = gpu

    # Temperatures
    temps = get_temperatures()
    if temps:
        info["extra"]["temperatures"] = temps

    return info

def get_local_ip():
    """Get the local IP address"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "unknown"

def send_heartbeat():
    """Send heartbeat to the server"""
    info = get_system_info()
    info["api_key"] = API_KEY
    data = json.dumps(info).encode("utf-8")

    try:
        req = urllib.request.Request(
            f"{SERVER_URL}/heartbeat",
            data=data,
            headers={"Content-Type": "application/json", "X-API-Key": API_KEY}
        )
        response = urllib.request.urlopen(req, timeout=10)
        return True
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print(f"Authentication failed - check API_KEY matches server!")
        else:
            print(f"Failed to send heartbeat: {e}")
        return False
    except urllib.error.URLError as e:
        print(f"Failed to send heartbeat: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False

def check_for_commands():
    """Poll server for pending commands and execute them"""
    computer_id = get_computer_id()
    try:
        req = urllib.request.Request(f"{SERVER_URL}/api/commands/{computer_id}")
        response = urllib.request.urlopen(req, timeout=10)
        data = json.loads(response.read().decode("utf-8"))

        commands = data.get("commands", [])
        if commands:
            print(f"[{time.strftime('%H:%M:%S')}] Received {len(commands)} command(s)")

        for cmd in commands:
            cmd_type = cmd.get("command")
            payload = cmd.get("payload", "")

            if cmd_type == "speedtest":
                print(f"[{time.strftime('%H:%M:%S')}] Running speed test...")
                result = run_speed_test()
                if result:
                    submit_speedtest_result(computer_id, result)
                    print(f"[{time.strftime('%H:%M:%S')}] Speed test complete: {result['download_mbps']} Mbps")
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] Speed test failed")

            elif cmd_type == "shell":
                print(f"[{time.strftime('%H:%M:%S')}] Executing: {payload}")
                result = execute_shell_command(payload)
                submit_command_result(computer_id, payload, result)
                print(f"[{time.strftime('%H:%M:%S')}] Command completed (exit code: {result['exit_code']})")

            elif cmd_type == "browse":
                print(f"[{time.strftime('%H:%M:%S')}] Browsing: {payload}")
                result = browse_directory(payload)
                submit_command_result(computer_id, f"browse:{payload}", result)

            elif cmd_type == "download":
                print(f"[{time.strftime('%H:%M:%S')}] Reading file: {payload}")
                result = read_file_for_transfer(payload)
                submit_command_result(computer_id, f"download:{payload}", result)

    except Exception as e:
        pass

def execute_shell_command(command):
    """Execute a shell command and return output"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=SUBPROCESS_FLAGS
        )
        return {
            "output": result.stdout + result.stderr,
            "exit_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"output": "Command timed out after 60 seconds", "exit_code": -1}
    except Exception as e:
        return {"output": str(e), "exit_code": -1}

def browse_directory(path):
    """List contents of a directory"""
    try:
        if not path:
            # Return drives on Windows, root on Linux
            if platform.system() == "Windows":
                import string
                drives = []
                for letter in string.ascii_uppercase:
                    if os.path.exists(f"{letter}:"):
                        drives.append({"name": f"{letter}:", "type": "drive", "size": 0})
                return {"output": json.dumps(drives), "exit_code": 0}
            else:
                path = "/"

        # On Windows, ensure drive letters have trailing backslash (C: -> C:\)
        if platform.system() == "Windows" and len(path) == 2 and path[1] == ':':
            path = path + "\\"

        items = []
        for item in os.listdir(path):
            full_path = os.path.join(path, item)
            try:
                stat = os.stat(full_path)
                items.append({
                    "name": item,
                    "type": "dir" if os.path.isdir(full_path) else "file",
                    "size": stat.st_size,
                    "modified": stat.st_mtime
                })
            except:
                items.append({"name": item, "type": "unknown", "size": 0})

        items.sort(key=lambda x: (x["type"] != "dir", x["name"].lower()))
        return {"output": json.dumps(items), "exit_code": 0}
    except Exception as e:
        return {"output": str(e), "exit_code": -1}

def read_file_for_transfer(path):
    """Read a file and return base64 encoded content"""
    try:
        import base64
        with open(path, "rb") as f:
            content = f.read()
            # Limit to 100MB
            if len(content) > 100 * 1024 * 1024:
                return {"output": "File too large (max 100MB)", "exit_code": -1}
            encoded = base64.b64encode(content).decode("utf-8")
            return {"output": encoded, "exit_code": 0}
    except Exception as e:
        return {"output": str(e), "exit_code": -1}


def write_file_from_transfer(payload):
    """Write a file from base64 encoded content"""
    try:
        import base64
        data = json.loads(payload)
        path = data.get("path", "")
        content_b64 = data.get("content", "")

        if not path or not content_b64:
            return {"output": "Missing path or content", "exit_code": -1}

        # Decode base64
        content = base64.b64decode(content_b64)

        # Create directory if needed
        dir_path = os.path.dirname(path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path)

        # Write file
        with open(path, "wb") as f:
            f.write(content)

        print(f"    Saved to: {path} ({len(content)} bytes)")
        return {"output": f"File saved: {path}", "exit_code": 0}
    except Exception as e:
        return {"output": str(e), "exit_code": -1}

def submit_command_result(computer_id, command, result):
    """Submit command result to server"""
    try:
        data = json.dumps({
            "command": command,
            "output": result["output"],
            "exit_code": result["exit_code"]
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{SERVER_URL}/api/exec/{computer_id}/result",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=10)
    except:
        pass

def submit_speedtest_result(computer_id, result):
    """Submit speed test result to server"""
    try:
        data = json.dumps(result).encode("utf-8")
        req = urllib.request.Request(
            f"{SERVER_URL}/api/speedtest/{computer_id}/result",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=10)
    except:
        pass

def handle_websocket_command(cmd_type, payload):
    """Handle a command received via WebSocket"""
    computer_id = get_computer_id()

    if cmd_type == "speedtest":
        print(f"[{time.strftime('%H:%M:%S')}] Running speed test...")
        result = run_speed_test()
        if result:
            result["type"] = "speedtest_result"
            return result
        return None

    elif cmd_type == "shell":
        print(f"[{time.strftime('%H:%M:%S')}] Executing: {payload}")
        result = execute_shell_command(payload)
        return {
            "type": "command_result",
            "command": payload,
            "output": result["output"],
            "exit_code": result["exit_code"]
        }

    elif cmd_type == "browse":
        print(f"[{time.strftime('%H:%M:%S')}] Browsing: {payload}")
        result = browse_directory(payload)
        return {
            "type": "command_result",
            "command": f"browse:{payload}",
            "output": result["output"],
            "exit_code": result["exit_code"]
        }

    elif cmd_type == "download":
        print(f"[{time.strftime('%H:%M:%S')}] Reading file: {payload}")
        result = read_file_for_transfer(payload)
        return {
            "type": "command_result",
            "command": f"download:{payload}",
            "output": result["output"],
            "exit_code": result["exit_code"]
        }

    elif cmd_type == "upload":
        print(f"[{time.strftime('%H:%M:%S')}] Receiving file upload...")
        result = write_file_from_transfer(payload)
        return {
            "type": "command_result",
            "command": "upload",
            "output": result["output"],
            "exit_code": result["exit_code"]
        }

    elif cmd_type == "update":
        print(f"[{time.strftime('%H:%M:%S')}] Update requested...")
        result = do_self_update()
        return {
            "type": "command_result",
            "command": "update",
            "output": result["output"],
            "exit_code": result["exit_code"]
        }

    elif cmd_type == "rustdesk_set_password":
        print(f"[{time.strftime('%H:%M:%S')}] Setting RustDesk password...")
        result = set_rustdesk_password(payload)
        return {
            "type": "command_result",
            "command": "rustdesk_set_password",
            "output": result["output"],
            "exit_code": result["exit_code"]
        }

    elif cmd_type == "kill_duplicates":
        print(f"[{time.strftime('%H:%M:%S')}] Killing duplicate agents...")
        result = kill_duplicate_agents()
        return {
            "type": "command_result",
            "command": "kill_duplicates",
            "output": result["output"],
            "exit_code": result["exit_code"]
        }

    elif cmd_type == "restart":
        print(f"[{time.strftime('%H:%M:%S')}] Restarting agent...")
        result = restart_agent()
        return {
            "type": "command_result",
            "command": "restart",
            "output": result["output"],
            "exit_code": result["exit_code"]
        }

    elif cmd_type == "reload_settings":
        print(f"[{time.strftime('%H:%M:%S')}] Reloading settings from server...")
        old_interval = HEARTBEAT_INTERVAL
        success = sync_settings_from_server()
        if success:
            new_interval = HEARTBEAT_INTERVAL
            if old_interval != new_interval:
                msg = f"Settings reloaded! Heartbeat changed: {old_interval}s -> {new_interval}s"
            else:
                msg = "Settings reloaded (no changes)"
            print(f"[{time.strftime('%H:%M:%S')}] {msg}")
            return {
                "type": "command_result",
                "command": "reload_settings",
                "output": msg,
                "exit_code": 0
            }
        else:
            return {
                "type": "command_result",
                "command": "reload_settings",
                "output": "Failed to reload settings",
                "exit_code": 1
            }

    return None


def do_self_update():
    """Download new version from server and restart"""
    try:
        # Get current script path
        script_path = os.path.abspath(__file__)

        # Download new version from server
        url = f"{SERVER_URL}/install/agent.py?key={API_KEY}"
        print(f"    Downloading from {url}...")

        req = urllib.request.Request(url, headers={'User-Agent': 'PC-Monitor-Agent'})
        response = urllib.request.urlopen(req, timeout=30)
        new_code = response.read().decode('utf-8')

        # Extract version from new code
        import re
        version_match = re.search(r'AGENT_VERSION\s*=\s*["\']([^"\']+)["\']', new_code)
        new_version = version_match.group(1) if version_match else "unknown"

        if new_version == AGENT_VERSION:
            return {"output": f"Already at latest version ({AGENT_VERSION})", "exit_code": 0}

        print(f"    Updating from {AGENT_VERSION} to {new_version}...")

        # Preserve current SERVER_URL and API_KEY
        new_code = re.sub(
            r'SERVER_URL\s*=\s*["\'][^"\']*["\']',
            f'SERVER_URL = "http://100.96.171.116:8000"',
            new_code
        )
        new_code = re.sub(
            r'API_KEY\s*=\s*["\'][^"\']*["\']',
            f'API_KEY = "5UmcdWxWlyER7snzbIbFlslNoapREZYh"',
            new_code
        )

        # Write new version
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(new_code)

        print(f"    Update complete! Restarting...")

        # Schedule restart
        threading.Thread(target=_restart_agent, daemon=True).start()

        return {"output": f"Updated from {AGENT_VERSION} to {new_version}. Restarting...", "exit_code": 0}

    except Exception as e:
        return {"output": f"Update failed: {str(e)}", "exit_code": 1}


def _restart_agent():
    """Restart the agent after a short delay"""
    time.sleep(2)  # Give time for response to be sent
    python = sys.executable
    script = os.path.abspath(__file__)
    print(f"\n{'='*50}")
    print("RESTARTING AGENT...")
    print(f"{'='*50}\n")
    os.execv(python, [python, script])

def websocket_listener():
    """Run WebSocket connection in a separate thread for instant commands"""
    global ws_connected, ws_connection

    try:
        import websockets.sync.client as ws_client
    except ImportError:
        print("[WebSocket] Installing websockets for instant commands...")
        subprocess.run(["pip", "install", "websockets", "--quiet"], capture_output=True, creationflags=SUBPROCESS_FLAGS)
        try:
            import websockets.sync.client as ws_client
            print("[WebSocket] Installed successfully!")
        except ImportError:
            print("[WebSocket] Could not install websockets, using HTTP polling (slower)")
            print("[WebSocket] Try manually: pip install websockets")
            return

    computer_id = get_computer_id()
    ws_url = SERVER_URL.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{ws_url}/ws/{computer_id}?key={API_KEY}"

    while True:
        try:
            print(f"[{time.strftime('%H:%M:%S')}] Connecting to WebSocket...")
            with ws_client.connect(ws_url, close_timeout=5) as websocket:
                ws_connected = True
                ws_connection = websocket
                print(f"[{time.strftime('%H:%M:%S')}] WebSocket connected! Commands are now INSTANT")

                while True:
                    try:
                        # Wait for commands from server (with timeout to detect disconnects)
                        websocket.socket.settimeout(30)
                        message = websocket.recv()
                        data = json.loads(message)

                        cmd_type = data.get("command")
                        payload = data.get("payload", "")

                        # Handle command and send result
                        result = handle_websocket_command(cmd_type, payload)
                        if result:
                            websocket.send(json.dumps(result))
                            print(f"[{time.strftime('%H:%M:%S')}] Command completed, result sent")

                    except TimeoutError:
                        # No message received, just continue (keeps connection alive)
                        continue
                    except Exception as e:
                        err_str = str(e).lower()
                        if "close" in err_str or "connection" in err_str or "eof" in err_str:
                            break
                        print(f"[{time.strftime('%H:%M:%S')}] WebSocket error: {e}")
                        break

        except Exception as e:
            pass  # Silent reconnect
        finally:
            ws_connected = False
            ws_connection = None

        time.sleep(3)  # Reconnect after 3 seconds

def sync_settings_from_server():
    """Fetch settings from server and apply them"""
    global HEARTBEAT_INTERVAL
    try:
        url = f"{SERVER_URL}/api/agent/settings?key={API_KEY}"
        req = urllib.request.Request(url, headers={'User-Agent': 'PC-Monitor-Agent'})
        response = urllib.request.urlopen(req, timeout=10)
        data = json.loads(response.read().decode('utf-8'))

        new_interval = data.get('heartbeat_interval', HEARTBEAT_INTERVAL)
        if new_interval != HEARTBEAT_INTERVAL:
            print(f"[{time.strftime('%H:%M:%S')}] Settings sync: heartbeat interval changed {HEARTBEAT_INTERVAL}s -> {new_interval}s")
            HEARTBEAT_INTERVAL = new_interval
        return True
    except Exception as e:
        # Silent fail - don't spam logs
        return False

def check_for_updates():
    """Check if a new version is available and auto-update if enabled"""
    if not AUTO_UPDATE:
        return False

    try:
        import re
        # Get server's agent version
        url = f"{SERVER_URL}/api/agent/version"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'PC-Monitor-Agent',
            'Authorization': f'Basic {API_KEY}'  # Won't work but that's ok, endpoint might not need auth
        })

        # Try to get version - this might fail if auth is required, that's ok
        try:
            response = urllib.request.urlopen(req, timeout=10)
            data = json.loads(response.read().decode('utf-8'))
            server_version = data.get('version', '')
        except:
            # Try getting version from the agent file directly
            url = f"{SERVER_URL}/install/agent.py?key={API_KEY}"
            req = urllib.request.Request(url, headers={'User-Agent': 'PC-Monitor-Agent'})
            response = urllib.request.urlopen(req, timeout=10)
            content = response.read().decode('utf-8')
            version_match = re.search(r'AGENT_VERSION\s*=\s*["\']([^"\']+)["\']', content)
            server_version = version_match.group(1) if version_match else None

            if not server_version:
                return False

        if server_version and server_version != AGENT_VERSION:
            print(f"[{time.strftime('%H:%M:%S')}] New version available: {server_version} (current: {AGENT_VERSION})")
            print(f"[{time.strftime('%H:%M:%S')}] Auto-updating...")
            result = do_self_update()
            if result['exit_code'] == 0:
                return True
            else:
                print(f"[{time.strftime('%H:%M:%S')}] Update failed: {result['output']}")

        return False
    except Exception as e:
        # Silent fail - don't spam logs if server is unreachable
        return False


def count_agent_instances():
    """Count how many agent instances are running (including this one)"""
    count = 0
    pids = []
    try:
        import psutil
        current_pid = os.getpid()

        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline') or []
                # Check if python process is running agent.py
                for arg in cmdline:
                    if arg and 'agent.py' in arg:
                        count += 1
                        if proc.info['pid'] != current_pid:
                            pids.append(proc.info['pid'])
                        break
            except:
                continue
    except:
        pass
    return count, pids

def check_already_running():
    """Check if another agent instance is already running"""
    count, _ = count_agent_instances()
    return count > 1

def kill_duplicate_agents():
    """Kill other agent instances (not this one)"""
    killed = []
    try:
        import psutil
        current_pid = os.getpid()

        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                if proc.info['pid'] == current_pid:
                    continue
                cmdline = proc.info.get('cmdline') or []
                for arg in cmdline:
                    if arg and 'agent.py' in arg:
                        proc.kill()
                        killed.append(proc.info['pid'])
                        break
            except:
                continue
    except Exception as e:
        return {"output": f"Error: {e}", "exit_code": -1}

    if killed:
        return {"output": f"Killed {len(killed)} duplicate agent(s): PIDs {killed}", "exit_code": 0}
    return {"output": "No duplicates found", "exit_code": 0}

def restart_agent():
    """Kill all agent instances and restart fresh with just one"""
    try:
        import psutil
        current_pid = os.getpid()
        script_path = os.path.abspath(__file__)

        # Kill ALL other agents first
        killed = []
        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                if proc.info['pid'] == current_pid:
                    continue
                cmdline = proc.info.get('cmdline') or []
                for arg in cmdline:
                    if arg and 'agent.py' in arg:
                        proc.kill()
                        killed.append(proc.info['pid'])
                        break
            except:
                continue

        # Schedule restart of this agent
        threading.Thread(target=_restart_agent, daemon=True).start()

        return {"output": f"Killed {len(killed)} duplicate(s). Restarting fresh...", "exit_code": 0}
    except Exception as e:
        return {"output": f"Error: {e}", "exit_code": -1}

def main():
    global ws_connected

    # Prevent multiple instances
    if check_already_running():
        print("ERROR: Another agent instance is already running!")
        print("Kill it first or check Task Manager for python processes.")
        sys.exit(1)

    rustdesk_id = get_rustdesk_id()
    rustdesk_status = rustdesk_id if rustdesk_id else "Not installed"
    mac = get_mac_address() or "Unknown"
    auto_update_status = f"Every {AUTO_UPDATE_INTERVAL}s" if AUTO_UPDATE else "Disabled"

    print(f"""
    ╔═════════════════════════════════════════════╗
    ║            PC Monitor Agent                 ║
    ╠═════════════════════════════════════════════╣
    ║  Computer:   {COMPUTER_NAME:<29}║
    ║  ID:         {get_computer_id():<29}║
    ║  Version:    {AGENT_VERSION:<29}║
    ║  Server:     {SERVER_URL:<29}║
    ║  Heartbeat:  {HEARTBEAT_INTERVAL}s (stats){' ' * 18}║
    ║  Commands:   INSTANT (WebSocket){' ' * 13}║
    ║  Auto-Update:{auto_update_status:<29}║
    ║  MAC:        {mac:<29}║
    ║  RustDesk:   {rustdesk_status:<29}║
    ╚═════════════════════════════════════════════╝
    """)

    if SERVER_URL == "CONFIGURE_ME" or API_KEY == "CONFIGURE_ME":
        print("ERROR: Agent not configured!")
        print()
        print("Download the agent from your server:")
        print("  curl -sL http://YOUR_SERVER:8000/i | bash")
        return

    print("Starting agent... (Ctrl+C to stop)")
    print(f"  - Heartbeats every {HEARTBEAT_INTERVAL}s (system stats)")
    print(f"  - Commands: INSTANT via WebSocket (fallback: {COMMAND_POLL_INTERVAL}s polling)\n")

    # Start WebSocket listener in background thread
    ws_thread = threading.Thread(target=websocket_listener, daemon=True)
    ws_thread.start()

    last_heartbeat = 0
    last_update_check = 0
    last_settings_sync = 0
    SETTINGS_SYNC_INTERVAL = 300  # Sync settings every 5 minutes

    # Sync settings and check for updates on startup
    print(f"[{time.strftime('%H:%M:%S')}] Syncing settings from server...")
    sync_settings_from_server()
    if AUTO_UPDATE:
        print(f"[{time.strftime('%H:%M:%S')}] Checking for updates...")
        check_for_updates()

    while True:
        current_time = time.time()

        # Send heartbeat at HEARTBEAT_INTERVAL
        if current_time - last_heartbeat >= HEARTBEAT_INTERVAL:
            success = send_heartbeat()
            status = "OK" if success else "FAILED"
            ws_status = "WebSocket" if ws_connected else "Polling"
            print(f"[{time.strftime('%H:%M:%S')}] Heartbeat: {status} | Mode: {ws_status} | Interval: {HEARTBEAT_INTERVAL}s")
            last_heartbeat = current_time

        # Sync settings periodically
        if current_time - last_settings_sync >= SETTINGS_SYNC_INTERVAL:
            sync_settings_from_server()
            last_settings_sync = current_time

        # Check for updates periodically
        if AUTO_UPDATE and current_time - last_update_check >= AUTO_UPDATE_INTERVAL:
            check_for_updates()
            last_update_check = current_time

        # Only poll for commands if WebSocket is NOT connected
        if not ws_connected:
            check_for_commands()

        time.sleep(COMMAND_POLL_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAgent stopped.")
