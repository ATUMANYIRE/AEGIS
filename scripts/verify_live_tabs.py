"""Comprehensive verification of live Streamlit Cloud app across all 5 tabs and multiple viewports."""

import base64
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import websocket

# Ensure UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8")

LIVE_URL = "https://aegis-datanova-2026.streamlit.app/~/+/"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9226
SCREENSHOTS_DIR = Path("docs/screenshots")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def send_cdp_cmd(ws, msg_id, method, params=None):
    payload = {"id": msg_id, "method": method, "params": params or {}}
    ws.send(json.dumps(payload))
    while True:
        resp = json.loads(ws.recv())
        if resp.get("id") == msg_id:
            return resp.get("result", {})


def eval_js(ws, msg_id, expr):
    res = send_cdp_cmd(
        ws, msg_id, "Runtime.evaluate", {"expression": expr, "returnByValue": True}
    )
    return res.get("result", {}).get("value")


def capture_screenshot(ws, msg_id, path: Path):
    res = send_cdp_cmd(ws, msg_id, "Page.captureScreenshot", {"format": "png"})
    if "data" in res:
        data = base64.b64decode(res["data"])
        path.write_bytes(data)
        print(f"Captured screenshot: {path} ({len(data):,} bytes)")


def main():
    print(f"Launching Chrome to inspect live deployment at {LIVE_URL}...")
    chrome_proc = subprocess.Popen(
        [
            CHROME_PATH,
            "--headless=new",
            f"--remote-debugging-port={PORT}",
            "--remote-allow-origins=*",
            "--no-sandbox",
            "--disable-gpu",
            "--window-size=1440,900",
            LIVE_URL,
        ]
    )

    try:
        time.sleep(3)
        ws_url = None
        for attempt in range(12):
            try:
                with urllib.request.urlopen(f"http://localhost:{PORT}/json/list") as resp:
                    pages = json.loads(resp.read().decode())
                    for p in pages:
                        if p.get("type") == "page":
                            ws_url = p.get("webSocketDebuggerUrl")
                            break
                    if ws_url:
                        break
            except Exception:
                time.sleep(1)

        if not ws_url:
            raise RuntimeError("Could not connect to Chrome DevTools Protocol.")

        ws = websocket.create_connection(ws_url, timeout=30)
        msg_id = 1

        send_cdp_cmd(ws, msg_id, "Page.enable")
        msg_id += 1
        send_cdp_cmd(ws, msg_id, "Runtime.enable")
        msg_id += 1

        print("Navigating to live app and waiting for Streamlit Cloud to render...")
        send_cdp_cmd(ws, msg_id, "Page.navigate", {"url": LIVE_URL})
        msg_id += 1

        # Wait for Streamlit Cloud app to load
        for wait_sec in range(1, 7):
            time.sleep(5)
            status_check = eval_js(
                ws,
                msg_id,
                """
                (() => {
                    const tabs = Array.from(document.querySelectorAll('[data-baseweb="tab"]')).map(t => t.innerText.trim());
                    const exceptions = Array.from(document.querySelectorAll('.stException, [data-testid="stNotification"]')).map(e => e.innerText.trim());
                    const title = document.title;
                    const isRunning = document.querySelector('[data-testid="stStatusWidget"]') !== null;
                    return { tabs, exceptions, title, isRunning, bodyLength: document.body ? document.body.innerText.length : 0 };
                })()
                """,
            )
            msg_id += 1
            print(f"[{wait_sec * 5}s] Title: {status_check.get('title')}, Tabs found: {status_check.get('tabs')}, Exceptions: {status_check.get('exceptions')}")
            if status_check.get("tabs") and len(status_check.get("tabs")) >= 3:
                break

        time.sleep(3)

        # 1. Desktop 1440x900 Verification
        print("\n--- 1. Desktop 1440x900 Verification ---")
        send_cdp_cmd(
            ws,
            msg_id,
            "Emulation.setDeviceMetricsOverride",
            {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False},
        )
        msg_id += 1

        tab_names = [
            "Network Overview",
            "Scenario Lab",
            "Explainability & AI",
            "Stress Testing",
            "Responsible AI & Governance",
        ]

        for tab_name in tab_names:
            print(f"\nClicking Tab: '{tab_name}'...")
            click_js = f"""
            (() => {{
                const tabs = Array.from(document.querySelectorAll('button[role="tab"], div[role="tab"], [data-baseweb="tab"], button[data-testid="stTab"]'));
                const foundNames = tabs.map(t => (t.textContent || t.innerText || "").trim());
                const target = tabs.find(t => (t.textContent || t.innerText || "").toLowerCase().includes('{tab_name.lower()}'));
                if (target) {{
                    target.scrollIntoView();
                    target.click();
                    target.dispatchEvent(new MouseEvent('click', {{bubbles: true, cancelable: true, view: window}}));
                    return 'Clicked: ' + (target.textContent || target.innerText) + ' (Found: ' + foundNames.join(', ') + ')';
                }}
                return 'Tab not found: {tab_name} (Available: ' + foundNames.join(', ') + ')';
            }})()
            """
            click_res = eval_js(ws, msg_id, click_js)
            msg_id += 1
            print(f"Click result: {click_res}")
            time.sleep(4)

            # Check DOM state
            audit_js = """
            (() => {
                const exceptions = Array.from(document.querySelectorAll('.stException')).map(e => e.innerText.trim());
                const alerts = Array.from(document.querySelectorAll('[data-testid="stAlert"]')).map(e => e.innerText.trim().slice(0, 100));
                const metrics = Array.from(document.querySelectorAll('[data-testid="stMetric"]')).map(m => m.innerText.replace(/\\n/g, ' '));
                const tables = document.querySelectorAll('[data-testid="stDataFrame"], table').length;
                const charts = document.querySelectorAll('[data-testid="stPlotlyChart"]').length;
                return { exceptions, alerts, metricCount: metrics.length, sampleMetrics: metrics.slice(0, 4), tables, charts };
            })()
            """
            tab_audit = eval_js(ws, msg_id, audit_js)
            msg_id += 1
            print(f"Tab Audit for '{tab_name}':")
            print(json.dumps(tab_audit, indent=2))

            safe_slug = tab_name.lower().replace(" ", "_").replace("&", "and")
            capture_screenshot(ws, msg_id, SCREENSHOTS_DIR / f"desktop_live_{safe_slug}.png")
            msg_id += 1

        # 2. Laptop 1366x768 Verification
        print("\n--- 2. Laptop 1366x768 Responsive Check ---")
        send_cdp_cmd(
            ws,
            msg_id,
            "Emulation.setDeviceMetricsOverride",
            {"width": 1366, "height": 768, "deviceScaleFactor": 1, "mobile": False},
        )
        msg_id += 1
        time.sleep(2)
        capture_screenshot(ws, msg_id, SCREENSHOTS_DIR / "laptop_1366x768_live.png")
        msg_id += 1

        # 3. Mobile 390x844 Verification
        print("\n--- 3. Mobile 390x844 Responsive Check ---")
        send_cdp_cmd(
            ws,
            msg_id,
            "Emulation.setDeviceMetricsOverride",
            {"width": 390, "height": 844, "deviceScaleFactor": 3, "mobile": True},
        )
        msg_id += 1
        time.sleep(2)
        capture_screenshot(ws, msg_id, SCREENSHOTS_DIR / "mobile_390x844_live.png")
        msg_id += 1

        print("\nAll live verification steps completed successfully!")

    finally:
        chrome_proc.kill()


if __name__ == "__main__":
    main()
