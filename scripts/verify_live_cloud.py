"""Script to inspect live Streamlit Cloud deployment with proper CDP handling."""

import base64
import json
import subprocess
import time
import urllib.request
from pathlib import Path

import websocket

chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
port = 9225
url = "https://aegis-datanova-2026.streamlit.app"

print(f"Checking live deployment at {url}...")
proc = subprocess.Popen(
    [
        chrome_path,
        "--headless=new",
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        "--no-sandbox",
        "--disable-gpu",
        "--window-size=1440,1080",
        url,
    ]
)

time.sleep(3)
ws_url = None
for _ in range(10):
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/json/list") as resp:
            for p in json.loads(resp.read().decode()):
                if p.get("type") == "page":
                    ws_url = p.get("webSocketDebuggerUrl")
                    break
            if ws_url:
                break
    except Exception:
        time.sleep(1)

if not ws_url:
    proc.kill()
    print("Could not connect to Chrome CDP.")
    exit(1)


def send_cdp_cmd(ws, msg_id, method, params=None):
    payload = {"id": msg_id, "method": method, "params": params or {}}
    ws.send(json.dumps(payload))
    while True:
        resp = json.loads(ws.recv())
        if resp.get("id") == msg_id:
            return resp.get("result", {})


ws = websocket.create_connection(ws_url, timeout=20)
msg_id = 1

send_cdp_cmd(ws, msg_id, "Page.enable")
msg_id += 1
send_cdp_cmd(ws, msg_id, "Runtime.enable")
msg_id += 1

# Explicitly navigate to app URL
send_cdp_cmd(ws, msg_id, "Page.navigate", {"url": url})
msg_id += 1

print("Navigated. Waiting 15s for Cloud app to load and build...")
time.sleep(15)

eval_js = """
(() => {
    return {
        title: document.title,
        url: window.location.href,
        hasError: Array.from(document.querySelectorAll('.stException, [data-testid="stNotification"], div.stAlert')).length,
        bodyTextSnippet: document.body ? document.body.innerText.slice(0, 1500) : ''
    };
})()
"""

res = send_cdp_cmd(
    ws,
    msg_id,
    "Runtime.evaluate",
    {"expression": eval_js, "returnByValue": True},
)
msg_id += 1
val = res.get("result", {}).get("value", {})
print("Live App DOM Analysis:")
print(json.dumps(val, indent=2))

# Capture screenshot
sc_res = send_cdp_cmd(ws, msg_id, "Page.captureScreenshot", {"format": "png"})
msg_id += 1
if "data" in sc_res:
    data = base64.b64decode(sc_res["data"])
    out_file = Path("docs/screenshots/live_streamlit_cloud.png")
    out_file.write_bytes(data)
    print(f"Saved live cloud screenshot to {out_file} ({len(data)} bytes)")

proc.kill()
