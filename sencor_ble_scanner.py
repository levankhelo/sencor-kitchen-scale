#!/usr/bin/env python3
"""
Sencor Kitchen Scale BLE Scanner

This script scans for BLE devices named "sencorfood", connects to them,
extracts data, displays it as a console output stream, and stores output
in output.txt file.
"""

import asyncio
import sys
from datetime import datetime

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

# Device name to search for
DEVICE_NAME = "sencorfood"

# Output file path
OUTPUT_FILE = "output.txt"


async def find_sencorfood_devices(timeout: float = 10.0) -> list[BLEDevice]:
    """
    Scan for BLE devices named 'sencorfood'.

    Args:
        timeout: Scan duration in seconds

    Returns:
        List of BLEDevice objects matching the device name
    """
    print(f"Scanning for BLE devices named '{DEVICE_NAME}'...")

    devices = []

    def detection_callback(device: BLEDevice, adv_data: AdvertisementData) -> None:
        if device.name and DEVICE_NAME.lower() in device.name.lower():
            if device not in devices:
                devices.append(device)
                print(f"  Found device: {device.name} ({device.address})")

    scanner = BleakScanner(detection_callback=detection_callback)
    await scanner.start()
    await asyncio.sleep(timeout)
    await scanner.stop()

    if not devices:
        print(f"No devices named '{DEVICE_NAME}' found.")
    else:
        print(f"Found {len(devices)} device(s) named '{DEVICE_NAME}'.")

    return devices


def format_data(data: bytes | bytearray) -> str:
    """
    Format received BLE data for display.

    Args:
        data: Raw bytes received from BLE device

    Returns:
        Formatted string representation of the data
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    hex_str = data.hex()

    # Try to decode as UTF-8 if possible
    try:
        text_str = data.decode("utf-8").strip()
        return f"[{timestamp}] HEX: {hex_str} | TEXT: {text_str}"
    except UnicodeDecodeError:
        return f"[{timestamp}] HEX: {hex_str} | RAW: {list(data)}"


async def connect_and_stream_data(
    device: BLEDevice, output_file: str = OUTPUT_FILE
) -> None:
    """
    Connect to a BLE device and stream data from it.

    Args:
        device: BLEDevice to connect to
        output_file: Path to file where output will be stored
    """
    print(f"\nConnecting to {device.name} ({device.address})...")

    try:
        async with BleakClient(device.address) as client:
            if not client.is_connected:
                print(f"Failed to connect to {device.name}")
                return

            print(f"Connected to {device.name}")
            print("Discovering services and characteristics...")

            # Open output file in append mode
            with open(output_file, "a", encoding="utf-8") as f:
                f.write(f"\n--- Session started: {datetime.now().isoformat()} ---\n")
                f.write(f"Device: {device.name} ({device.address})\n\n")

                # Discover all services and characteristics
                services = client.services
                notify_chars = []

                for service in services:
                    print(f"\nService: {service.uuid}")
                    for char in service.characteristics:
                        props = ", ".join(char.properties)
                        print(f"  Characteristic: {char.uuid} [{props}]")

                        # Subscribe to characteristics that support notify or indicate
                        if "notify" in char.properties or "indicate" in char.properties:
                            notify_chars.append(char)

                if not notify_chars:
                    print(
                        "\nNo notify/indicate characteristics found. "
                        "Attempting to read available characteristics..."
                    )

                    # Try to read characteristics that support read
                    for service in services:
                        for char in service.characteristics:
                            if "read" in char.properties:
                                try:
                                    data = await client.read_gatt_char(char.uuid)
                                    formatted = format_data(data)
                                    print(formatted)
                                    f.write(formatted + "\n")
                                    f.flush()
                                except Exception as e:
                                    print(f"  Error reading {char.uuid}: {e}")
                else:
                    # Create notification handler that uses the open file handle
                    def notification_handler(
                        sender: int, data: bytearray
                    ) -> None:
                        formatted = format_data(data)
                        print(formatted)
                        f.write(formatted + "\n")
                        f.flush()

                    # Subscribe to all notify characteristics
                    for char in notify_chars:
                        try:
                            await client.start_notify(char.uuid, notification_handler)
                            print(f"Subscribed to notifications from {char.uuid}")
                        except Exception as e:
                            print(f"Failed to subscribe to {char.uuid}: {e}")

                    print("\nStreaming data (press Ctrl+C to stop)...\n")

                    # Keep connection alive and receive notifications
                    try:
                        while client.is_connected:
                            await asyncio.sleep(1)
                    except KeyboardInterrupt:
                        print("\nStopping data stream...")

                    # Unsubscribe from notifications
                    for char in notify_chars:
                        try:
                            await client.stop_notify(char.uuid)
                        except Exception:
                            pass

                f.write(f"\n--- Session ended: {datetime.now().isoformat()} ---\n")

    except Exception as e:
        print(f"Error connecting to {device.name}: {e}")


async def main() -> None:
    """Main entry point for the BLE scanner."""
    print("=" * 60)
    print("Sencor Kitchen Scale BLE Scanner")
    print("=" * 60)

    # Scan for devices
    devices = await find_sencorfood_devices(timeout=10.0)

    if not devices:
        print("\nNo devices found. Make sure your Sencor scale is powered on.")
        sys.exit(1)

    # Connect to each found device
    for device in devices:
        await connect_and_stream_data(device)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nScanner stopped by user.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
