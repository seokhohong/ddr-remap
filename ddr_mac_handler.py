#!/usr/bin/env python3
"""
DDR Dual Pad Handler for Mac
Hardware-level device distinction for identical DDR pads
Requires: pip install pygame pynput
"""

import pygame
import threading
import time
from pynput.keyboard import Key, Controller
from collections import defaultdict
import tkinter as tk
from tkinter import messagebox, simpledialog
import sys

class DDRPadHandler:
    def __init__(self):
        # Initialize pygame for input handling
        pygame.init()
        pygame.joystick.init()
        
        # Initialize pynput for output
        self.keyboard = Controller()
        
        # Configuration - Player key mappings
        self.p1_keys = {
            'left': Key.left,
            'down': Key.down, 
            'up': Key.up,
            'right': Key.right
        }
        
        self.p2_keys = {
            'left': Key.f1,  # Using F-keys as default for P2
            'down': Key.f2,
            'up': Key.f3, 
            'right': Key.f4
        }
        
        # Device tracking
        self.device_assignments = {}  # device_instance_id -> player_number
        self.detected_devices = []
        self.calibration_mode = False
        self.calibration_step = 0
        self.calibrated_devices = []
        
        # Hold tracking for DDR holds/freezes
        self.held_keys = {}  # (device_id, direction) -> threading.Timer
        self.hold_interval = 0.03  # 30ms for smooth holds
        
        # Running state
        self.running = True
        self.input_thread = None
        
        # Initialize GUI for messages
        self.root = tk.Tk()
        self.root.withdraw()  # Hide main window
        
    def scan_for_devices(self):
        """Scan for connected keyboard/joystick devices"""
        self.detected_devices = []
        
        # Scan for joysticks/gamepads (most DDR pads appear as these)
        joystick_count = pygame.joystick.get_count()
        print(f"Found {joystick_count} joystick devices")
        
        for i in range(joystick_count):
            joy = pygame.joystick.Joystick(i)
            joy.init()
            device_info = {
                'id': i,
                'name': joy.get_name(),
                'instance_id': joy.get_instance_id(),
                'type': 'joystick',
                'device': joy
            }
            self.detected_devices.append(device_info)
            print(f"Device {i}: {joy.get_name()} (Instance: {joy.get_instance_id()})")
        
        # Also check for keyboard devices if needed
        # Note: pygame doesn't distinguish between multiple keyboards well
        # For keyboard-based DDR pads, you might need additional libraries
        
        return len(self.detected_devices)
    
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
        """Process DDR input from a specific device"""
        if not direction:
            return
            
        if self.calibration_mode:
            if is_pressed:  # Only respond to key down during calibration
                self.handle_calibration_input(device_id, direction)
            return
        
        # Check if device is assigned
        if device_id not in self.device_assignments:
            print(f"Unknown device {device_id} - need calibration")
            return
        
        player = self.device_assignments[device_id]
        
        if is_pressed:
            self.start_hold_input(device_id, player, direction)
        else:
            self.stop_hold_input(device_id, direction)
    
    def send_player_input(self, player, direction):
        """Send keyboard input for the specified player and direction"""
        try:
            if player == 1:
                key = self.p1_keys.get(direction)
            elif player == 2:
                key = self.p2_keys.get(direction)
            else:
                return
            
            if key:
                self.keyboard.press(key)
                self.keyboard.release(key)
                print(f"P{player}: {direction}")
        except Exception as e:
            print(f"Error sending input: {e}")
    
    def start_hold_input(self, device_id, player, direction):
        """Start holding input for DDR holds/freezes"""
        key_id = (device_id, direction)
        
        # If already holding, ignore
        if key_id in self.held_keys:
            return
        
        # Send initial press
        self.send_player_input(player, direction)
        
        # Start repeating timer
        def repeat_input():
            if key_id in self.held_keys and self.running:
                self.send_player_input(player, direction)
                # Schedule next repeat
                timer = threading.Timer(self.hold_interval, repeat_input)
                self.held_keys[key_id] = timer
                timer.start()
        
        # Start the repeat cycle
        timer = threading.Timer(self.hold_interval, repeat_input)
        self.held_keys[key_id] = timer
        timer.start()
    
    def stop_hold_input(self, device_id, direction):
        """Stop holding input"""
        key_id = (device_id, direction)
        
        if key_id in self.held_keys:
            self.held_keys[key_id].cancel()
            del self.held_keys[key_id]
    
    def start_calibration(self):
        """Start the calibration process"""
        self.calibration_mode = True
        self.calibration_step = 1
        self.calibrated_devices = []
        self.device_assignments = {}
        
        messagebox.showinfo("Calibration Started", 
                          "CALIBRATION MODE ACTIVE\n\n"
                          "Step 1: Press ANY arrow on the LEFT/FIRST pad\n"
                          "(The pad you want to be Player 1)\n\n"
                          "Close this dialog and press an arrow on your first pad.")
        print("Calibration: Waiting for Player 1 pad input...")
    
    def handle_calibration_input(self, device_id, direction):
        """Handle input during calibration"""
        if self.calibration_step == 1:
            # First device = Player 1
            self.device_assignments[device_id] = 1
            self.calibrated_devices.append(device_id)
            self.calibration_step = 2
            
            print(f"Player 1 pad registered (Device {device_id})")
            messagebox.showinfo("Step 1 Complete", 
                              "Player 1 pad registered!\n\n"
                              "Step 2: Press ANY arrow on the RIGHT/SECOND pad\n"
                              "(The pad you want to be Player 2)")
            print("Calibration: Waiting for Player 2 pad input...")
            
        elif self.calibration_step == 2:
            # Check if this is a different device
            if device_id != self.calibrated_devices[0]:
                # Second device = Player 2
                self.device_assignments[device_id] = 2
                self.calibrated_devices.append(device_id)
                
                print(f"Player 2 pad registered (Device {device_id})")
                messagebox.showinfo("Calibration Complete!", 
                                  "Both pads calibrated successfully!\n\n"
                                  "Player 1 -> Arrow Keys\n"
                                  "Player 2 -> F1-F4 Keys\n\n"
                                  "You can now use your DDR pads!")
                
                self.end_calibration()
            else:
                print("Same pad detected - press arrow on the OTHER pad")
                messagebox.showwarning("Same Device", 
                                     "Same pad detected!\n"
                                     "Please press an arrow on the OTHER pad.")
    
    def end_calibration(self):
        """End calibration mode"""
        self.calibration_mode = False
        print("Calibration complete! Both pads ready.")
    
    def input_loop(self):
        """Main input processing loop"""
        clock = pygame.time.Clock()
        
        while self.running:
            try:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                        break
                    
                    # Get device information
                    device_id = None
                    if hasattr(event, 'instance_id'):
                        device_id = event.instance_id
                    elif hasattr(event, 'joy'):
                        # For older pygame versions
                        device_id = event.joy
                    
                    # Get direction from input
                    direction = self.get_direction_from_input(event)
                    
                    if direction and device_id is not None:
                        # Determine if this is press or release
                        is_pressed = (event.type in [pygame.JOYBUTTONDOWN, pygame.KEYDOWN] or 
                                    (event.type == pygame.JOYHATMOTION and event.value != (0, 0)))
                        
                        self.process_input(device_id, direction, is_pressed)
                
                clock.tick(60)  # 60 FPS
                
            except Exception as e:
                print(f"Error in input loop: {e}")
                time.sleep(0.01)  # Brief pause to prevent tight error loop
    
    def cleanup(self):
        """Clean up resources"""
        self.running = False
        
        # Cancel all hold timers
        for timer in self.held_keys.values():
            timer.cancel()
        self.held_keys.clear()
        
        # Quit pygame
        pygame.quit()
        
        # Destroy GUI
        if self.root:
            self.root.destroy()
    
    def show_help(self):
        """Display help information"""
        device_list = ""
        for i, device in enumerate(self.detected_devices):
            player = self.device_assignments.get(device['instance_id'], "Unassigned")
            device_list += f"Device {i}: {device['name']} -> Player {player}\n"
        
        help_text = f"""DDR Hardware-Level Input Handler for Mac

DETECTED DEVICES:
{device_list}

CONTROLS:
- Press 'c' in terminal to start calibration
- Press 'h' in terminal for this help
- Press 'q' in terminal to quit

CALIBRATION:
Use calibration to assign which physical pad controls which player.
This creates a hardware-level mapping.

OUTPUT MAPPINGS:
Player 1: Arrow Keys (←↓↑→)
Player 2: F1-F4 Keys (F1=Left, F2=Down, F3=Up, F4=Right)

HOLDS:
The script supports DDR holds/freezes - just hold down the arrow!
"""
        print(help_text)
        messagebox.showinfo("DDR Handler Help", help_text)
    
    def run(self):
        """Main run method"""
        print("DDR Hardware-Level Input Handler for Mac")
        print("========================================")
        
        # Scan for devices
        device_count = self.scan_for_devices()
        
        if device_count < 2:
            response = messagebox.askyesno("Limited Devices", 
                                         f"Only {device_count} device(s) detected.\n\n"
                                         "Note: Some DDR pads only appear when actively used.\n"
                                         "Make sure both DDR pads are connected.\n\n"
                                         "Start calibration now?")
            if response:
                self.start_calibration()
        else:
            messagebox.showinfo("DDR Handler Active", 
                              f"DDR Hardware-Level Input Handler is running!\n\n"
                              f"Detected {device_count} devices.\n\n"
                              "CALIBRATION NEEDED:\n"
                              "Press 'c' in the terminal to start calibration.\n\n"
                              "Commands:\n"
                              "c = Start calibration\n"
                              "h = Show help\n"
                              "q = Quit")
        
        # Start input processing thread
        self.input_thread = threading.Thread(target=self.input_loop, daemon=True)
        self.input_thread.start()
        
        # Main command loop
        print("\nCommands: 'c' for calibration, 'h' for help, 'q' to quit")
        try:
            while self.running:
                try:
                    command = input().strip().lower()
                    
                    if command == 'c':
                        self.start_calibration()
                    elif command == 'h':
                        self.show_help()
                    elif command == 'q':
                        print("Shutting down...")
                        break
                    else:
                        print("Commands: 'c' for calibration, 'h' for help, 'q' to quit")
                        
                except EOFError:
                    break
                except KeyboardInterrupt:
                    print("\nShutting down...")
                    break
                    
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
        
        handler = DDRPadHandler()
        handler.run()
        
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure pygame and pynput are installed: pip install pygame pynput")

if __name__ == "__main__":
    main()