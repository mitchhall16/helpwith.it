PC Monitor - Install Scripts
============================

Server URL: http://192.168.12.125:8000
API Key: 5UmcdWxWlyER7snzbIbFlslNoapREZYh

Dashboard Login:
  Username: admin
  Password: _c1RA9jDPv0ElAws

WINDOWS:
  Run install-windows.bat on the target computer

MAC/LINUX:
  Copy install-mac-linux.sh to the target computer and run:
    chmod +x install-mac-linux.sh
    ./install-mac-linux.sh

Or manually:
  1. Copy the agent folder to the target computer
  2. Edit agent.py and set:
     SERVER_URL = "http://192.168.12.125:8000"
     API_KEY = "5UmcdWxWlyER7snzbIbFlslNoapREZYh"
  3. Run: pip install psutil websockets
  4. Run: python agent.py
