#!/usr/bin/env python3
"""
DDR Gamepad Interface Reader
Read input from DDR pads using gamepad interfaces and remap them
"""

import hid
import time
import threading
from pynput.keyboard import Key, Controller
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class PadMapping:
    """Mapping configuration for a DDR pad"""
    serial: str
    up_key: str = 'w'
    left_key: str = 'a' 
    down_key: str = 's'
    right_key: str = 'd'

class DDRPadReader:
    def __init__(self, mapping: PadMapping):
        self.mapping = mapping
        self.device = None
        self.keyboard = Controller()
        self.running = False
        self.thread = None
        
        # State tracking to avoid key repeat
        self.button_states = {}
        
    def connect(self) -> bool:
        """Connect to the DDR pad gamepad interface"""
        devices = hid.enumerate()
        
        for dev in devices:
            if (dev['manufacturer_string'] == 'MusicGame' and 
                dev['serial_number'] == self.mapping.serial and
                dev['usage'] == 5):  # Gamepad interface
                
                try:
                    self.device = hid.device()
                    self.device.open_path(dev['path'])
                    self.device.set_nonblocking(True)
                    print(f"✓ Connected to pad {self.mapping.serial}")
                    return True
                except Exception as e:
                    print(f"✗ Failed to connect to {self.mapping.serial}: {e}")
                    return False
        
        print(f"✗ Pad {self.mapping.serial} not found")
        return False
    
    def disconnect(self):
        """Disconnect from the pad"""
        if self.device:
            self.device.close()
            self.device = None
    
    def start_reading(self):
        """Start reading input in a separate thread"""
        if not self.device:
            print(f"Device {self.mapping.serial} not connected")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()
    
    def stop_reading(self):
        """Stop reading input"""
        self.running = False
        if self.thread:
            self.thread.join()
    
    def _read_loop(self):
        """Main reading loop"""
        print(f"Reading from pad {self.mapping.serial}...")
        
        while self.running:
            try:
                data = self.device.read(64)
                if data:
                    self._process_input(data)
                time.sleep(0.01)  # 100Hz polling
                
            except Exception as e:
                print(f"Read error for {self.mapping.serial}: {e}")
                break
    
    def _process_input(self, data):
        """Process HID input data and send keyboard events"""
        # This is pad-specific - you'll need to analyze the data format
        # Common format is first few bytes contain button states
        
        if len(data) < 4:
            return
            
        # Example format - adjust based on your pad's actual data format
        # Usually buttons are in a bitmask format
        buttons = data[0] if len(data) > 0 else 0
        
        # Map button bits to directions (you'll need to determine these)
        button_map = {
            0x01: 'up_key',    # Bit 0 = Up
            0x02: 'down_key',  # Bit 1 = Down  
            0x04: 'left_key',  # Bit 2 = Left
            0x08: 'right_key', # Bit 3 = Right
        }
        
        for bit_mask, key_attr in button_map.items():
            key_name = getattr(self.mapping, key_attr)
            is_pressed = bool(buttons & bit_mask)
            
            # Only send key events on state changes
            if self.button_states.get(key_attr) != is_pressed:
                self.button_states[key_attr] = is_pressed
                
                if is_pressed:
                    self.keyboard.press(key_name)
                    print(f"Pad {self.mapping.serial}: {key_attr} pressed -> {key_name}")
                else:
                    self.keyboard.release(key_name)
                    print(f"Pad {self.mapping.serial}: {key_attr} released -> {key_name}")


def analyze_pad_data(serial_number: str):
    """Analyze raw data from a specific pad to understand its format"""
    devices = hid.enumerate()
    device = None
    
    for dev in devices:
        if (dev['manufacturer_string'] == 'MusicGame' and 
            dev['serial_number'] == serial_number and
            dev['usage'] == 5):
            
            try:
                device = hid.device()
                device.open_path(dev['path'])
                device.set_nonblocking(True)
                break
            except:
                continue
    
    if not device:
        print(f"Could not open pad {serial_number}")
        return
    
    print(f"Analyzing data from pad {serial_number}")
    print("Press buttons on the pad to see the data format...")
    print("Press Ctrl+C to stop\n")
    
    try:
        while True:
            data = device.read(64)
            if data:
                # Display data in multiple formats
                hex_data = [f"{b:02x}" for b in data[:8]]  # First 8 bytes
                bin_data = [f"{b:08b}" for b in data[:4]]  # First 4 bytes in binary
                int_data = list(data[:8])  # First 8 bytes as integers
                
                print(f"Hex: {' '.join(hex_data)}")
                print(f"Bin: {' '.join(bin_data)}")
                print(f"Int: {int_data}")
                print("---")
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nAnalysis stopped")
    finally:
        device.close()


def main():
    """Main function to set up dual DDR pads"""
    
    # Define mappings for your two pads
    pad1_mapping = PadMapping(
        serial="081E472A7027",
        up_key='w', left_key='a', down_key='s', right_key='d'
    )
    
    pad2_mapping = PadMapping(
        serial="0835C7297027", 
        up_key='i', left_key='j', down_key='k', right_key='l'  # Different keys
    )
    
    # Create readers
    pad1 = DDRPadReader(pad1_mapping)
    pad2 = DDRPadReader(pad2_mapping)
    
    # Connect to pads
    if not pad1.connect():
        print("Failed to connect to pad 1")
        return
        
    if not pad2.connect():
        print("Failed to connect to pad 2")
        pad1.disconnect()
        return
    
    try:
        # Start reading from both pads
        pad1.start_reading()
        pad2.start_reading()
        
        print("DDR pads active! Press Ctrl+C to stop...")
        print(f"Pad 1 ({pad1_mapping.serial}): WASD keys")
        print(f"Pad 2 ({pad2_mapping.serial}): IJKL keys")
        
        # Keep running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        pad1.stop_reading()
        pad2.stop_reading()
        pad1.disconnect()
        pad2.disconnect()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "analyze":
        # Analysis mode
        if len(sys.argv) >= 3:
            analyze_pad_data(sys.argv[2])
        else:
            print("Usage: python script.py analyze SERIAL_NUMBER")
            print("Example: python script.py analyze 081E472A7027")
    else:
        main()
