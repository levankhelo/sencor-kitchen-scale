# sencor-kitchen-scale
Extract scale data from Sencor kitchen scales using BLE (Bluetooth Low Energy).

## Features

- Scans for BLE devices named "sencorfood"
- Connects to discovered devices and extracts data
- Displays data as console output stream (each data blob on a new line)
- Stores output in `output.txt` file

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
