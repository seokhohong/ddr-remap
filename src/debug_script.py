#!/usr/bin/env python3
"""
DDR HID Debug Tool
Diagnose why HID devices can't be opened
"""

import hid
import os
import subprocess
import sys


def debug_hid_access():
    """Comprehensive HID access debugging"""
    print("=== DDR HID Debug Tool ===\n")

    # 1. Check if running with appropriate permissions
    print(f"1. USER INFO:")
    print(f"   User ID: {os.getuid()}")
    print(f"   Effective User ID: {os.geteuid()}")
    print(f"   Running as root: {os.geteuid() == 0}")
    print()

    # 2. List all DDR-related devices
    print("2. DETECTED DDR DEVICES:")
    devices = hid.enumerate()
    ddr_devices = []

    for i, dev in enumerate(devices):
        if dev['manufacturer_string'] == 'MusicGame':
            ddr_devices.append(dev)
            print(f"   Device {i}:")
            print(f"     Serial: {dev['serial_number']}")
            print(f"     Path: {dev['path']}")
            print(f"     Usage: {dev['usage']} (Page: {dev['usage_page']})")
            print(f"     Interface: {dev['interface_number']}")
            print(f"     Product ID: {dev['product_id']}")
            print(f"     Vendor ID: {dev['vendor_id']}")
            print()

    if not ddr_devices:
        print("   No DDR devices found!")
        return

    # 3. Test opening each device
    print("3. DEVICE ACCESS TEST:")
    for i, dev in enumerate(ddr_devices):
        print(f"   Testing device {dev['serial_number']} (Usage: {dev['usage']})...")

        try:
            device = hid.device()
            device.open_path(dev['path'])
            print(f"   ✓ SUCCESS: Opened device")

            # Try to read device info
            try:
                manufacturer = device.get_manufacturer_string()
                product = device.get_product_string()
                serial = device.get_serial_number_string()
                print(f"   ✓ Device info: {manufacturer} - {product} ({serial})")
            except Exception as e:
                print(f"   ⚠ Could not read device info: {e}")

            device.close()

        except OSError as e:
            print(f"   ✗ FAILED: {e}")

            # More detailed error analysis
            if hasattr(e, 'errno'):
                errno = e.errno
                if errno == 1:  # EPERM
                    print(f"     → Permission denied (try with sudo)")
                elif errno == 16:  # EBUSY
                    print(f"     → Device is busy (close other applications using it)")
                elif errno == 2:  # ENOENT
                    print(f"     → Device not found")
                else:
                    print(f"     → Error code: {errno}")

        except Exception as e:
            print(f"   ✗ UNEXPECTED ERROR: {e}")

        print()

    # 4. Check what processes might be using the devices
    print("4. PROCESSES THAT MIGHT BE USING DDR PADS:")
    try:
        # Look for processes that might interfere
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        lines = result.stdout.split('\n')

        keywords = ['stepmania', 'ddr', 'dance', 'music', 'game', 'hid']
        found_processes = []

        for line in lines:
            for keyword in keywords:
                if keyword.lower() in line.lower() and 'python' not in line.lower():
                    found_processes.append(line.strip())
                    break

        if found_processes:
            for proc in found_processes:
                print(f"   {proc}")
        else:
            print("   No obvious interfering processes found")

    except Exception as e:
        print(f"   Could not check processes: {e}")

    print()

    # 5. Recommendations
    print("5. TROUBLESHOOTING RECOMMENDATIONS:")
    print()

    # Check which interfaces are keyboard-like
    keyboard_devices = [dev for dev in ddr_devices if dev['usage'] == 6]
    gamepad_devices = [dev for dev in ddr_devices if dev['usage'] == 5]

    if keyboard_devices:
        print("   KEYBOARD INTERFACES (Usage 6) - These send arrow keys:")
        for dev in keyboard_devices:
            print(f"     Serial: {dev['serial_number']}")
        print("   → These are what you want for DDR input")
        print()

    if gamepad_devices:
        print("   GAMEPAD INTERFACES (Usage 5) - These act like joysticks:")
        for dev in gamepad_devices:
            print(f"     Serial: {dev['serial_number']}")
        print("   → These might be easier to access")
        print()

    print("   SOLUTIONS TO TRY:")
    print("   1. Run with sudo: sudo python your_script.py")
    print("   2. Close StepMania or other DDR software")
    print("   3. Try using gamepad interfaces (Usage 5) instead of keyboard (Usage 6)")
    print("   4. Use pygame approach instead of direct HID")
    print("   5. Switch to pyhidapi: pip uninstall hid && pip install pyhidapi")
    print()


def test_specific_interface(serial_number, usage):
    """Test opening a specific device interface"""
    print(f"Testing specific device: {serial_number}, Usage: {usage}")

    devices = hid.enumerate()
    target_device = None

    for dev in devices:
        if (dev['serial_number'] == serial_number and
                dev['usage'] == usage and
                dev['manufacturer_string'] == 'MusicGame'):
            target_device = dev
            break

    if not target_device:
        print("Device not found!")
        return False

    try:
        device = hid.device()
        device.open_path(target_device['path'])
        print("✓ Successfully opened device!")

        # Set non-blocking mode
        device.set_nonblocking(True)

        # Try to read some data
        print("Listening for input (press arrows on this pad, Ctrl+C to stop)...")
        try:
            while True:
                data = device.read(64)
                if data:
                    print(f"Received: {[hex(x) for x in data]}")
                time.sleep(0.01)

        except KeyboardInterrupt:
            print("\nStopped listening")

        device.close()
        return True

    except Exception as e:
        print(f"✗ Failed: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Test mode - try to open a specific device
        if len(sys.argv) >= 4:
            serial = sys.argv[2]
            usage = int(sys.argv[3])
            test_specific_interface(serial, usage)
        else:
            print("Usage: python debug.py test SERIAL_NUMBER USAGE")
            print("Example: python debug.py test 0835C7297027 6")
    else:
        debug_hid_access()