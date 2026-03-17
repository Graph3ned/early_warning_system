"""
BLE connection to YK-100 to prevent auto power-off.

Uses direct connection by address (no scanning). If the device is already connected at the
OS level (e.g. via bluetoothctl), treats it as connected and does not open a second connection.
"""

import asyncio
import threading
from bleak import BleakClient

from ocr_config import BLE_ADDRESS

_ble_client = None
ble_connected = False


def _is_ble_connected_via_system() -> bool:
    """Return True if BLE_ADDRESS is already connected at OS level (e.g. bluetoothctl)."""
    try:
        import subprocess
        r = subprocess.run(
            ["bluetoothctl", "info", BLE_ADDRESS],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return r.returncode == 0 and "Connected: yes" in (r.stdout or "")
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return False


async def maintain_ble_connection():
    global _ble_client, ble_connected
    while True:
        client = None
        try:
            # If already connected (our Bleak client), just monitor until disconnect
            if _ble_client is not None and _ble_client.is_connected:
                ble_connected = True
                while _ble_client.is_connected:
                    await asyncio.sleep(1)
                ble_connected = False
                print("[WARN] BLE Disconnected, reconnecting...")
                _ble_client = None
                await asyncio.sleep(2)
                continue

            # If device is already connected at system level (e.g. bluetoothctl), don't open a second connection
            if _is_ble_connected_via_system():
                ble_connected = True
                while _is_ble_connected_via_system():
                    await asyncio.sleep(2)
                ble_connected = False
                print("[WARN] BLE no longer connected (system), reconnecting...")
                await asyncio.sleep(2)
                continue

            # Direct connection by address (no scan) - same as explore_ble.py
            client = BleakClient(BLE_ADDRESS)
            print("Connecting to YK-100...")
            await asyncio.wait_for(client.connect(), timeout=10.0)
            _ble_client = client
            ble_connected = True
            print("BLE Connected to YK-100")
            while ble_connected and client.is_connected:
                await asyncio.sleep(1)
            if not client.is_connected:
                ble_connected = False
                print("[WARN] BLE Disconnected, reconnecting...")
            if client and client.is_connected:
                await client.disconnect()
            _ble_client = None
        except asyncio.TimeoutError:
            print("[WARN] BLE Connection timeout, retrying...")
            ble_connected = False
            _ble_client = None
            if client and client.is_connected:
                try:
                    await client.disconnect()
                except Exception:
                    pass
            await asyncio.sleep(3)
        except Exception as e:
            print(f"[WARN] BLE Connection error: {e}")
            ble_connected = False
            _ble_client = None
            if client and client.is_connected:
                try:
                    await client.disconnect()
                except Exception:
                    pass
            await asyncio.sleep(3)


def start_ble_connection():
    def run():
        asyncio.run(maintain_ble_connection())
    threading.Thread(target=run, daemon=True).start()
