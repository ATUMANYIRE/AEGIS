"""Automated browser verification using native Chrome DevTools Protocol over WebSocket."""

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


def send_cdp_cmd(ws, msg_id, method, params=None):
    payload = {"id": msg_id, "method": method, "params": params or {}}
    ws.send(json.dumps(payload))
    while True:
        resp = json.loads(ws.recv())
        if resp.get("id") == msg_id:
            return resp.get("result", {})


def eval_js(ws, msg_id, expr):
    res = send_cdp_cmd(ws, msg_id, "Runtime.evaluate", {"expression": expr, "returnByValue": True})
    return res.get("result", {}).get("value")


def click_element_by_text(ws, msg_id, text_snippet):
    js = f"""
    (() => {{
        const all = Array.from(document.querySelectorAll('button, div[data-baseweb="tab"], p'));
        const el = all.find(e => e.innerText && e.innerText.includes('{text_snippet}'));
        if (el) {{
            el.scrollIntoView();
            el.click();
            el.dispatchEvent(new MouseEvent('click', {{bubbles: true, cancelable: true, view: window}}));
            return el.innerText;
        }}
        return null;
    }})()
    """
    return eval_js(ws, msg_id, js)


def capture_screenshot(ws, msg_id, out_path: Path):
    res = send_cdp_cmd(ws, msg_id, "Page.captureScreenshot", {"format": "png"})
    data = base64.b64decode(res["data"])
    out_path.write_bytes(data)
    print(f"Captured: {out_path} ({len(data)} bytes)")


def main():
    screenshots_dir = Path("docs/screenshots")
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    port = 9222
    app_url = "http://localhost:8501"

    print("Spawning Chrome process with CDP...")
    chrome_proc = subprocess.Popen(
        [
            chrome_path,
            "--headless=new",
            f"--remote-debugging-port={port}",
            "--remote-allow-origins=*",
            "--no-sandbox",
            "--disable-gpu",
            "--window-size=1440,1080",
            app_url,
        ]
    )

    try:
        # Wait for CDP endpoint to become ready
        time.sleep(3)
        ws_url = None
        for _ in range(10):
            try:
                with urllib.request.urlopen(
                    f"http://localhost:{port}/json/list", timeout=3
                ) as resp:
                    pages = json.loads(resp.read().decode("utf-8"))
                    for p in pages:
                        if p.get("type") == "page":
                            ws_url = p.get("webSocketDebuggerUrl")
                            break
                    if ws_url:
                        break
            except Exception:
                time.sleep(1)

        if not ws_url:
            raise RuntimeError("Failed to obtain Chrome WebSocket debugger URL")

        print("Connected to Chrome CDP.")
        ws = websocket.create_connection(ws_url, timeout=15)
        msg_id = 1

        # Enable Page and Runtime domains
        send_cdp_cmd(ws, msg_id, "Page.enable")
        msg_id += 1
        send_cdp_cmd(ws, msg_id, "Runtime.enable")
        msg_id += 1

        # Set desktop viewport (1440x1080)
        send_cdp_cmd(
            ws,
            msg_id,
            "Emulation.setDeviceMetricsOverride",
            {
                "width": 1440,
                "height": 1080,
                "deviceScaleFactor": 1,
                "mobile": False,
            },
        )
        msg_id += 1

        print("Waiting 6s for Streamlit app and Plotly graphs to render...")
        time.sleep(6)

        # 1. Overview Tab
        print("Capturing 01_overview_desktop.png...")
        capture_screenshot(ws, msg_id, screenshots_dir / "01_overview_desktop.png")
        msg_id += 1

        # 2. Click Tab 2: Scenario Lab
        print("Navigating to Tab 2 (Scenario Lab)...")
        tab_name = click_element_by_text(ws, msg_id, "Scenario Lab")
        msg_id += 1
        print(f"Clicked tab: {tab_name}")
        time.sleep(4)

        # Click 'Run Multi-Echelon Optimization'
        print("Triggering solver optimization run...")
        btn_name = click_element_by_text(ws, msg_id, "Run Multi-Echelon Optimization")
        msg_id += 1
        print(f"Clicked button: {btn_name}")
        time.sleep(6)

        print("Capturing 02_scenario_lab_desktop.png...")
        capture_screenshot(ws, msg_id, screenshots_dir / "02_scenario_lab_desktop.png")
        msg_id += 1

        # 3. Click Tab 3: Explainability & GenAI
        print("Navigating to Tab 3 (Explainability)...")
        tab_name = click_element_by_text(ws, msg_id, "Explainability")
        msg_id += 1
        print(f"Clicked tab: {tab_name}")
        time.sleep(4)

        # Click GenAI subtab
        print("Activating GenAI subtab...")
        subtab_name = click_element_by_text(ws, msg_id, "Grounded GenAI")
        msg_id += 1
        print(f"Clicked subtab: {subtab_name}")
        time.sleep(4)

        print("Capturing 03_explainability_genai_desktop.png...")
        capture_screenshot(ws, msg_id, screenshots_dir / "03_explainability_genai_desktop.png")
        msg_id += 1

        # 4. Click Tab 4: Stress Testing
        print("Navigating to Tab 4 (Stress Testing)...")
        tab_name = click_element_by_text(ws, msg_id, "Stress Testing")
        msg_id += 1
        print(f"Clicked tab: {tab_name}")
        time.sleep(4)
        print("Capturing 04_stress_testing_desktop.png...")
        capture_screenshot(ws, msg_id, screenshots_dir / "04_stress_testing_desktop.png")
        msg_id += 1

        # 5. Click Tab 5: Responsible AI & Governance
        print("Navigating to Tab 5 (Responsible AI)...")
        tab_name = click_element_by_text(ws, msg_id, "Responsible AI")
        msg_id += 1
        print(f"Clicked tab: {tab_name}")
        time.sleep(4)
        print("Capturing 05_governance_desktop.png...")
        capture_screenshot(ws, msg_id, screenshots_dir / "05_governance_desktop.png")
        msg_id += 1

        # 6. Mobile Viewport (375x812 iPhone X)
        print("Switching to Mobile Viewport (375x812)...")
        send_cdp_cmd(
            ws,
            msg_id,
            "Emulation.setDeviceMetricsOverride",
            {
                "width": 375,
                "height": 812,
                "deviceScaleFactor": 2,
                "mobile": True,
            },
        )
        msg_id += 1
        time.sleep(2)
        click_element_by_text(ws, msg_id, "Executive Overview")
        msg_id += 1
        time.sleep(3)
        print("Capturing 06_mobile_responsive.png...")
        capture_screenshot(ws, msg_id, screenshots_dir / "06_mobile_responsive.png")
        msg_id += 1

        ws.close()
        print("ALL REAL SCREENSHOTS CAPTURED SUCCESSFULLY VIA CDP.")

    finally:
        chrome_proc.terminate()
        chrome_proc.wait(timeout=5)


if __name__ == "__main__":
    main()
