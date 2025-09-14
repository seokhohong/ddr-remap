#!/usr/bin/env python3
"""
DDR Dual Pad Input Logger for Mac
Detects two DDR pad devices and logs 8 inputs (4 directions per device).
Requires: pip install pygame
"""

import pygame
import threading
import time
import sys
import select
try:
    from Quartz import CGEventCreateKeyboardEvent, CGEventPost, kCGHIDEventTap
except Exception:
    CGEventCreateKeyboardEvent = None
    CGEventPost = None
    kCGHIDEventTap = None
try:
    from IOKit import hid as iokit_hid
    from CoreFoundation import kCFAllocatorDefault
    IOKIT_AVAILABLE = True
except Exception:
    iokit_hid = None
    kCFAllocatorDefault = None
    IOKIT_AVAILABLE = False
import hid  # Provided by the 'hidapi' or 'hid' Python packages

class DDRPadHandler:
    def __init__(self):
        # Initialize pygame (not used for input now, but harmless)
        pygame.init()
        
        # Device tracking
        self.detected_devices = []
        
        # Running state
        self.running = True
        self.command_thread = None
        
        # HID state
        self.use_hid = False
        self.hid_threads = []
        self.hid_devices = []  # list of {dev, label, prev_keys:set}
        # Virtual keyboards (IOHIDUserDevice) per pad index (1-based)
        self.virtual_keyboards = {}
        
        
    def scan_for_devices(self):
        """Scan for connected keyboard/joystick devices"""
        self.detected_devices = []
        
        # Joystick scanning removed; HID keyboard mode is used exclusively
        return 0
    
    def get_direction_from_input(self, event):
        """Convert pygame event to DDR direction"""
        if event.type == pygame.JOYBUTTONDOWN or event.type == pygame.JOYBUTTONUP:
            # Map joystick buttons to directions (common DDR pad mapping)
            button_map = {
                0: 'left',   # Usually left arrow
                1: 'down',   # Usually down arrow  
                2: 'up',     # Usually up arrow
                3: 'right'   # Usually right arrow
            }
            return button_map.get(event.button)
        
        elif event.type == pygame.JOYHATMOTION:
            # Handle D-pad input
            hat_x, hat_y = event.value
            if hat_x == -1:
                return 'left'
            elif hat_x == 1:
                return 'right'
            elif hat_y == 1:
                return 'up'
            elif hat_y == -1:
                return 'down'
        
        elif event.type == pygame.KEYDOWN or event.type == pygame.KEYUP:
            # Handle keyboard input for keyboard-based DDR pads
            key_map = {
                pygame.K_a: 'left',
                pygame.K_s: 'down',
                pygame.K_w: 'up', 
                pygame.K_d: 'right',
                pygame.K_x: 'down'  # Alternative down key
            }
            return key_map.get(event.key)
        
        return None
    
    def process_input(self, device_id, direction, is_pressed):
        """Process DDR input: log which device and which direction with state"""
        if not direction:
            return
        # Lookup device name by instance_id
        name = None
        for d in self.detected_devices:
            if d.get('instance_id') == device_id:
                name = d.get('name')
                break
        state = "DOWN" if is_pressed else "UP"
        if device_id is None:
            print(f"Keyboard: {direction} {state}")
        elif name is not None:
            print(f"Device {device_id} ({name}): {direction} {state}")
        else:
            print(f"Device {device_id}: {direction} {state}")
    
    # Removed keyboard output and hold logic
    
    # Calibration removed
    
    def input_loop(self):
        """Unused: pygame input loop removed in HID-only mode."""
        while self.running:
            time.sleep(0.1)

    # ===== HID (hidapi) support for per-device keyboard pads =====
    class VirtualHIDKeyboard:
        """Minimal virtual HID keyboard using IOHIDUserDevice."""
        def __init__(self, vendor_id=0x4D47, product_id=0x5762, product="DDR Virtual Keyboard", manufacturer="DDR Remap"):
            if not IOKIT_AVAILABLE:
                raise RuntimeError("IOKit not available")
            # Standard boot keyboard report descriptor
            desc_bytes = bytes([
                0x05, 0x01,        # Usage Page (Generic Desktop)
                0x09, 0x06,        # Usage (Keyboard)
                0xA1, 0x01,        # Collection (Application)
                0x05, 0x07,        #   Usage Page (Keyboard/Keypad)
                0x19, 0xE0,        #   Usage Minimum (224)
                0x29, 0xE7,        #   Usage Maximum (231)
                0x15, 0x00,        #   Logical Minimum (0)
                0x25, 0x01,        #   Logical Maximum (1)
                0x75, 0x01,        #   Report Size (1)
                0x95, 0x08,        #   Report Count (8)
                0x81, 0x02,        #   Input (Data,Var,Abs) ; Modifier byte
                0x95, 0x01,        #   Report Count (1)
                0x75, 0x08,        #   Report Size (8)
                0x81, 0x03,        #   Input (Cnst,Var,Abs) ; Reserved
                0x95, 0x06,        #   Report Count (6)
                0x75, 0x08,        #   Report Size (8)
                0x15, 0x00,        #   Logical Minimum (0)
                0x25, 0x65,        #   Logical Maximum (101)
                0x05, 0x07,        #   Usage Page (Keyboard/Keypad)
                0x19, 0x00,        #   Usage Minimum (0)
                0x29, 0x65,        #   Usage Maximum (101)
                0x81, 0x00,        #   Input (Data,Arr,Abs) ; Keys
                0xC0               # End Collection
            ])
            props = {
                iokit_hid.kIOHIDReportDescriptorKey: desc_bytes,
                iokit_hid.kIOHIDVendorIDKey: int(vendor_id),
                iokit_hid.kIOHIDProductIDKey: int(product_id),
                iokit_hid.kIOHIDProductKey: product,
                iokit_hid.kIOHIDManufacturerKey: manufacturer,
                iokit_hid.kIOHIDVersionNumberKey: 1,
                iokit_hid.kIOHIDCountryCodeKey: 0,
                iokit_hid.kIOHIDPrimaryUsagePageKey: 0x01,  # Generic Desktop
                iokit_hid.kIOHIDPrimaryUsageKey: 0x06,       # Keyboard
            }
            self._dev = iokit_hid.IOHIDUserDeviceCreate(kCFAllocatorDefault, props)
            if self._dev is None:
                raise RuntimeError("Failed to create IOHIDUserDevice")

        def send_usages(self, usages_set):
            """Send an 8-byte keyboard report with currently pressed usages (set of ints)."""
            # Build report: [mods, reserved, k1..k6]
            report = bytearray(8)
            # No modifiers for ESDF/IJKL
            keys = sorted([u for u in usages_set if u != 0])[:6]
            for i, u in enumerate(keys):
                report[2 + i] = u & 0xFF
            # report ID-less; send as is
            iokit_hid.IOHIDUserDeviceHandleReport(self._dev, report, len(report))
    def _hid_keycode_to_dir(self, code: int):
        """Map HID keyboard usage ID to DDR direction."""
        mapping = {
            0x04: 'left',   # 'a'
            0x16: 'down',   # 's'
            0x1A: 'up',     # 'w'
            0x07: 'right',  # 'd'
            0x1B: 'down',   # 'x' as alt down
        }
        return mapping.get(code)

    def _hid_device_loop(self, dev_info):
        """Read loop for a single HID keyboard interface. Also generates system key events."""
        dev = dev_info['dev']
        label = dev_info['label']
        pad_index = dev_info.get('pad_index', 1)
        prev_keys = set()
        debug_count = 0  # suppress raw spam
        # Direction to HID usage mapping per pad (Keyboard/Keypad page usages)
        pad_usages = {
            1: {  # ESDF
                'up': 0x08,   # E
                'down': 0x16, # S
                'left': 0x07, # D
                'right': 0x09 # F
            },
            2: {  # IJKL
                'up': 0x0C,   # I
                'down': 0x0E, # K
                'left': 0x0D, # J
                'right': 0x0F # L
            },
        }
        held_dirs = set()

        # Prepare virtual keyboard for this pad if available
        vk = None
        if IOKIT_AVAILABLE:
            vk = self.virtual_keyboards.get(pad_index)
            if vk is None:
                try:
                    vk = DDRPadHandler.VirtualHIDKeyboard(product=f"DDR Virtual Keyboard {pad_index}")
                    self.virtual_keyboards[pad_index] = vk
                except Exception as e:
                    print(f"Warning: Failed to create virtual keyboard for pad {pad_index}: {e}")
                    vk = None

        def emit(direction: str, is_down: bool):
            # Update held directions
            if is_down:
                held_dirs.add(direction)
            else:
                held_dirs.discard(direction)
            # Convert held directions to usages
            usages = set()
            for d in held_dirs:
                u = pad_usages.get(pad_index, {}).get(d)
                if u:
                    usages.add(u)
            if vk is not None:
                vk.send_usages(usages)
            elif CGEventCreateKeyboardEvent is not None and CGEventPost is not None and kCGHIDEventTap is not None:
                # Fallback to Quartz events if virtual device is unavailable
                u = pad_usages.get(pad_index, {}).get(direction)
                # Map HID usage letters to macOS keycodes (A=0,S=1,D=2,F=3,E=14,I=34,J=38,K=40,L=37)
                usage_to_keycode = {0x04:0,0x05:11,0x06:8,0x07:2,0x08:14,0x09:3,0x0C:34,0x0D:38,0x0E:40,0x0F:37,0x16:1}
                keycode = usage_to_keycode.get(u)
                if keycode is not None:
                    evt = CGEventCreateKeyboardEvent(None, keycode, True if is_down else False)
                    if evt is not None:
                        CGEventPost(kCGHIDEventTap, evt)
        try:
            while self.running:
                try:
                    # Prefer a short timeout read so we can exit promptly
                    try:
                        data = dev.read(64, 50)
                    except TypeError:
                        data = dev.read(64)
                except Exception:
                    data = []
                if data:
                    if debug_count > 0:
                        print(f"{label} raw: {data[:8]}")
                        debug_count -= 1
                    # Typical keyboard report: [mods, reserved, k1, k2, k3, k4, k5, k6]
                    keys = set()
                    if len(data) >= 8:
                        for kc in data[2:8]:
                            if kc != 0:
                                keys.add(kc)
                    # Determine downs and ups
                    downs = keys - prev_keys
                    ups = prev_keys - keys
                    for kc in downs:
                        direction = self._hid_keycode_to_dir(kc)
                        if direction:
                            print(f"{label}: {direction} DOWN")
                            emit(direction, True)
                    for kc in ups:
                        direction = self._hid_keycode_to_dir(kc)
                        if direction:
                            print(f"{label}: {direction} UP")
                            emit(direction, False)
                    prev_keys = keys
                else:
                    time.sleep(0.01)
        finally:
            try:
                dev.close()
            except Exception:
                pass

    def start_hid_logging(self, vendor_id=0x4D47, product_id=0x5761) -> bool:
        """Try to start per-device HID logging for the two DDR pads.
        Groups hid.enumerate() results by serial_number and interface, and
        opens exactly one path per pad (preferring Keyboard/Gamepad usages).
        Returns True if started successfully for 2 devices.
        """
        if hid is None:
            return False
        try:
            devices = hid.enumerate(vendor_id, product_id)
        except Exception:
            devices = []
        if not devices:
            return False
        # Group by serial_number (one group per physical pad)
        groups = {}
        for info in devices:
            sn = info.get('serial_number') or 'unknown'
            groups.setdefault(sn, []).append(info)
        # We only want to open keyboard interfaces (usage 6)
        # Sort serials for deterministic labeling
        serials = sorted(groups.keys())
        if len(serials) < 2:
            return False
        # Take the first two pads by serial
        serials = serials[:2]
        self.hid_devices = []
        for pad_index, sn in enumerate(serials, start=1):
            # Filter only keyboard interfaces
            keyboard_infos = [i for i in groups[sn] if (i.get('usage') or 0) == 6]
            if not keyboard_infos:
                print(f"No keyboard HID interface (usage=6) found for Pad {pad_index} (SN {sn}). Skipping this pad.")
                continue
            # Choose a deterministic keyboard interface (lowest interface_number)
            info = sorted(keyboard_infos, key=lambda x: (x.get('interface_number') or 0))[0]
            path = info.get('path')
            iface = info.get('interface_number')
            usage = info.get('usage')
            try:
                d = hid.device()
                d.open_path(path)
                d.set_nonblocking(True)
            except Exception as e:
                print(f"Failed to open HID keyboard interface for Pad {pad_index} (SN {sn}) iface={iface} usage={usage}: {e}")
                continue
            label = f"Pad {pad_index} (SN {sn}) iface={iface} usage={usage}"
            self.hid_devices.append({'dev': d, 'label': label, 'prev_keys': set(), 'pad_index': pad_index})
        # Start threads
        self.hid_threads = []
        for dev_info in self.hid_devices:
            t = threading.Thread(target=self._hid_device_loop, args=(dev_info,), daemon=True)
            t.start()
            self.hid_threads.append(t)
        self.use_hid = True
        print("Using HID keyboard mode (per-device)")
        for dev_info in self.hid_devices:
            print(f"  Opened {dev_info['label']}")
        return True

    def idle_loop(self):
        """Idle loop when HID threads are running; keep main thread alive."""
        while self.running:
            time.sleep(0.05)

    def command_loop(self):
        """Background thread to process terminal commands without blocking stdin at shutdown."""
        print("\nCommands: 'h' for help, 'q' to quit")
        try:
            buffer = ""
            while self.running:
                # Poll stdin for input without blocking
                try:
                    rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
                except Exception:
                    rlist = []
                if rlist:
                    line = sys.stdin.readline()
                    if line == '':
                        # EOF
                        break
                    command = line.strip().lower()
                    if not self.running:
                        break
                    if command == 'h':
                        self.show_help()
                    elif command == 'q':
                        print("Shutting down...")
                        self.running = False
                        break
                    elif command:
                        print("Commands: 'h' for help, 'q' to quit")
                else:
                    # Nothing to read; yield
                    time.sleep(0.05)
        finally:
            # Exiting command loop
            return
    
    def cleanup(self):
        """Clean up resources"""
        self.running = False
        
        # Quit pygame
        pygame.quit()
        # Wait briefly for command thread to exit to avoid stdin lock
        if self.command_thread and self.command_thread.is_alive():
            try:
                self.command_thread.join(timeout=1.0)
            except Exception:
                pass
    
    def show_help(self):
        """Display help information"""
        device_list = ""
        for i, device in enumerate(self.detected_devices):
            device_list += f"Device {i}: {device['name']} (Instance: {device['instance_id']})\n"
        
        help_text = f"""DDR Dual Pad Input Logger for Mac

DETECTED DEVICES:
{device_list}

CONTROLS:
- Press 'h' in terminal for this help
- Press 'q' in terminal to quit

HOLDS:
Not applicable – this tool only logs inputs (press/release) per device.

CLI FLAGS:
- --help, -h       Show this help and exit
"""
        print(help_text)
    
    def run(self, auto_calibrate: bool = False, show_help_flag: bool = False):
        """Main run method"""
        print("DDR Dual Pad Input Logger for Mac")
        print("========================================")
        
        # Scan for devices
        device_count = self.scan_for_devices()
        
        if show_help_flag:
            self.show_help()
        
        # HID keyboard mode only
        started_hid = self.start_hid_logging(0x4D47, 0x5761)
        if started_hid:
            print("Per-device logging active. Press on each pad.")
        else:
            print("Error: Could not open HID keyboard interfaces for pads.")
        print("Commands:")
        print("h = Show help")
        print("q = Quit")
        
        # Start command loop in background so pygame event loop can run on main thread
        # Non-daemon + non-blocking stdin so we can join at shutdown cleanly
        self.command_thread = threading.Thread(target=self.command_loop, daemon=False)
        self.command_thread.start()

        # Run the appropriate main loop on the MAIN thread (required on macOS)
        try:
            # HID-only
            self.idle_loop()
        finally:
            self.cleanup()

def main():
    """Main entry point"""
    try:
        # Check for required permissions on Mac
        print("Note: On Mac, you may need to grant accessibility permissions")
        print("Go to System Preferences > Security & Privacy > Accessibility")
        print("and add Terminal (or your Python executable) to the list.")
        print()
        
        # Simple CLI arg parsing
        args = sys.argv[1:]
        auto_calibrate = False
        show_help_flag = False
        if "--calibrate" in args or "-c" in args:
            auto_calibrate = True
        if "--help" in args or "-h" in args:
            show_help_flag = True
        
        handler = DDRPadHandler()
        handler.run(auto_calibrate=auto_calibrate, show_help_flag=show_help_flag)
        
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure pygame and pynput are installed: pip install pygame pynput")

if __name__ == "__main__":
    main()