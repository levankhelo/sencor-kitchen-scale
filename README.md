# sencor-kitchen-scale
Extract scale data from Sencor kitchen scales using BLE (Bluetooth Low Energy).
Originally this was made to collect weight of my parrots, from their cage, during their treatment, so let me know if you have any suggestions!

## Features

- Scans for BLE devices named "sencorfood"
- Connects to discovered devices and extracts data
- Displays data as console output stream (each data blob on a new line)
- Stores output in `output.txt` file

## Home Assistant custom integration

A lightweight custom component lives in `custom_components/sencor_scale`:

- Automatically discovers nearby Sencor scales (`sencorfood`) and creates sensors per device (rename them in Home Assistant UI as needed).
- Configurable scan interval: set to `0` for continuous streaming, or any positive number of seconds to poll at that cadence (each poll opens a short BLE session and listens for weight notifications).

### Install

1) Copy the `custom_components/sencor_scale` folder into your Home Assistant `/config/custom_components/` directory.
2) Restart Home Assistant.
3) Add the integration via **Settings → Devices & Services → Add Integration → Sencor Kitchen Scale**.
4) Choose your scan interval (seconds). `0` = always connected streaming; otherwise a polling loop with a short listen window per cycle.

### HACS install (recommended)

1) In HACS, open **Integrations → ⋮ → Custom repositories**.
2) Add your repo URL, category **Integration**, and save.
3) Find **Sencor Kitchen Scale** in HACS, install, then restart Home Assistant.
4) Add the integration via **Settings → Devices & Services** and pick your scan interval (`0` for continuous, otherwise seconds between polls).
5) For updates, just pull the latest release in HACS; it handles copying to `/config/custom_components`.

### Notes/assumptions

- BLE connection/notification handling is performed with `bleak`; ensure your Home Assistant host has working Bluetooth.
- Weight parsing uses bytes 2–3 for the value (big endian) and byte 7 as a sign flag (1 = negative).

## Requirements

- Python 3.10+
- Bluetooth adapter with BLE support
- Linux: BlueZ 5.43+ (most modern distributions include this)
- macOS: Built-in Bluetooth support
- Windows: Windows 10+ with Bluetooth support

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/levankhelo/sencor-kitchen-scale.git
   cd sencor-kitchen-scale
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Power on your Sencor kitchen scale
2. Run the scanner:
   ```bash
   python sencor_ble_scanner.py
   ```

3. The script will:
   - Scan for BLE devices named "sencorfood" (10 second timeout)
   - Connect to any found devices
   - Display received data in the console
   - Save all data to `output.txt`

4. Press `Ctrl+C` to stop the data stream

## Output Format

Each data line includes:
- Timestamp
- Hexadecimal representation of the data
- Text representation (if decodable as UTF-8) or raw byte values

Example:
```
[2024-01-15 14:30:45.123] HEX: 0102030405 | RAW: [1, 2, 3, 4, 5]
```

## Troubleshooting

### No devices found
- Ensure your Sencor scale is powered on
- Make sure Bluetooth is enabled on your computer
- Try moving closer to the scale
- On Linux, ensure your user has permission to access Bluetooth (you may need to run with `sudo` or add your user to the `bluetooth` group)

### Permission issues on Linux
```bash
sudo usermod -a -G bluetooth $USER
# Log out and log back in for changes to take effect
```
