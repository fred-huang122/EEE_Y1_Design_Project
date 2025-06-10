import socket
import time
import sys
from pynput import keyboard
import threading

ARDUINO_COMMAND_PORT = 1000
PYTHON_LISTEN_FREQ_PORT = 1002

# Get IP from user
target_ip = "192.168.137.226"
if not target_ip:
    print("Error: IP address cannot be empty. Exiting.")
    sys.exit()

print(f"\nTargeting Arduino at {target_ip}:{ARDUINO_COMMAND_PORT} for commands.")
print(f"Listening for frequency data on all interfaces, port {PYTHON_LISTEN_FREQ_PORT}.") # Clarified binding
print("\nControl the robot using WASD or Arrow Keys:")
print("  W / Up Arrow    -> Forward (F)")
print("  A / Left Arrow  -> Left    (L)")
print("  D / Right Arrow -> Right   (R)")
print("  S / Down Arrow  -> Backward/Stop (B)")
print("\nPress 'Q' or 'ESC' to Quit.")
print("-" * 30)

pressed_keys = set()
speed_keys = set()
last_sent_command = ''
running = True
status_line_lock = threading.Lock() # To manage printing to the status line

try:
    send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print("UDP Command Sending Socket Created.")
except socket.error as e:
    print(f"Error creating command sending socket: {e}")
    sys.exit()

try:
    listen_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Try binding to the specific IP of the hotspot interface if '' causes issues,
    # but '' should be more general. For now, keep as is.
    listen_sock.bind(('', PYTHON_LISTEN_FREQ_PORT))
    listen_sock.settimeout(0.5) # Shorter timeout for more responsive shutdown check
    print(f"UDP Frequency Listening Socket Bound to port {PYTHON_LISTEN_FREQ_PORT}.")
except socket.error as e:
    print(f"Error creating or binding frequency listening socket: {e}")
    if 'send_sock' in locals(): send_sock.close()
    sys.exit()

def get_key_representation(key_event):
    if hasattr(key_event, 'char') and key_event.char: return key_event.char.upper()
    if key_event == keyboard.Key.up: return 'UP'
    if key_event == keyboard.Key.down: return 'DOWN'
    if key_event == keyboard.Key.left: return 'LEFT'
    if key_event == keyboard.Key.right: return 'RIGHT'
    if key_event == keyboard.Key.shift: return 'FASTER'
    if key_event == keyboard.Key.ctrl_l: return 'SLOWER'
    if key_event == keyboard.Key.esc: return 'ESC'
    return None

def evaluate_current_command():
    if last_sent_command == '': return 'S'
    
    if len(pressed_keys) == 1 and ('S' in pressed_keys or 'DOWN' in pressed_keys or '\x13' in pressed_keys): return 'B'
    if last_sent_command[0] == 'B' and ('D' in pressed_keys or 'RIGHT' in pressed_keys or '\x04' in pressed_keys): return 'R'
    if last_sent_command[0] == 'B' and ('A' in pressed_keys or 'LEFT' in pressed_keys or '\x01' in pressed_keys): return 'L'

    if len(pressed_keys) == 1 and ('D' in pressed_keys or 'RIGHT' in pressed_keys or '\x04' in pressed_keys): return 'R'
    if last_sent_command[0] == 'R' and ('W' in pressed_keys or 'UP' in pressed_keys or '\x17' in pressed_keys): return 'F'
    if last_sent_command[0] == 'R' and ('S' in pressed_keys or 'DOWN' in pressed_keys or '\x13' in pressed_keys): return 'B'

    if len(pressed_keys) == 1 and ('A' in pressed_keys or 'LEFT' in pressed_keys or '\x01' in pressed_keys): return 'L'
    if last_sent_command[0] == 'L' and ('W' in pressed_keys or 'UP' in pressed_keys or '\x17' in pressed_keys): return 'F'
    if last_sent_command[0] == 'L' and ('S' in pressed_keys or 'DOWN' in pressed_keys or '\x13' in pressed_keys): return 'B'

    if len(pressed_keys) == 1 and ('W' in pressed_keys or 'UP' in pressed_keys or '\x17' in pressed_keys): return 'F'
    if last_sent_command[0] == 'F' and ('D' in pressed_keys or 'RIGHT' in pressed_keys or '\x04' in pressed_keys): return 'R'
    if last_sent_command[0] == 'F' and ('A' in pressed_keys or 'LEFT' in pressed_keys or '\x01' in pressed_keys): return 'L'


    return 'S'

def evaluate_speed_command(current_command: str):
    if current_command == 'S':
        return 'S'
    if 'FASTER' in speed_keys:
        return current_command + 'F'
    elif 'SLOWER' in speed_keys:
        return current_command + 'S'
    return current_command

def print_status(message):
    """Helper to print status messages on one line, managing clearing."""
    with status_line_lock:
        sys.stdout.write("\r" + " " * 80 + "\r") # Clear previous line
        sys.stdout.write(message)
        sys.stdout.flush()

def send_robot_command(command_to_send):
    global last_sent_command
    if command_to_send != last_sent_command or command_to_send == 'S': # Always send S if it's the command
        try:
            message = command_to_send.encode('utf-8')
            send_sock.sendto(message, (target_ip, ARDUINO_COMMAND_PORT))
            print_status(f"Sent Command: '{command_to_send}")
            last_sent_command = command_to_send
        except socket.gaierror:
            print_status(f"Error: Hostname or IP '{target_ip}' could not be resolved.")
            return False
        except socket.error as e:
            print_status(f"Socket Error sending command: {e}")
            return False
        except Exception as e:
            print_status(f"Unexpected error sending command: {e}")
            return False
    return True

def on_press(key_event):
    global running
    if not running: return False
    key_rep = get_key_representation(key_event)
    if key_rep == 'Q' or key_rep == 'ESC':
        print_status("\nQuit key pressed. Stopping...") # Print on new line before status clear
        sys.stdout.flush() # Make sure it's seen
        running = False
        return False
    if key_rep == 'FASTER' or key_rep == 'SLOWER' and key_rep not in speed_keys:
        speed_keys.add(key_rep)
        current_robot_command = evaluate_current_command()
        current_robot_command = evaluate_speed_command(current_robot_command)
        # print(f" Speed Keys: {speed_keys} | Pressed: {pressed_keys} | Current Command: {current_robot_command}")
        return send_robot_command(current_robot_command)

    if key_rep not in pressed_keys and key_rep not in ['FASTER', 'SLOWER']:
        pressed_keys.add(key_rep)
        current_robot_command = evaluate_current_command()
        current_robot_command = evaluate_speed_command(current_robot_command)
        # print(f" Speed Keys: {speed_keys} | Pressed: {pressed_keys} | Current Command: {current_robot_command}")
        send_robot_command(current_robot_command)
    return True

def on_release(key_event):
    if not running: return False
    key_rep = get_key_representation(key_event)
    if key_rep == 'FASTER' or key_rep == 'SLOWER' and key_rep in speed_keys:
        speed_keys.remove(key_rep)
        current_robot_command = evaluate_current_command()
        current_robot_command = evaluate_speed_command(current_robot_command)
        send_robot_command(current_robot_command)

    if key_rep in pressed_keys and key_rep != 'FASTER' and key_rep != 'SLOWER':
        pressed_keys.remove(key_rep)
        current_robot_command = evaluate_current_command()
        current_robot_command = evaluate_speed_command(current_robot_command)
        send_robot_command(current_robot_command)
    return True

def frequency_listener_thread():
    return
    global running
    print("\nFrequency listener thread started. Waiting for data...") # New line for clarity
    last_freq_display = ""

    while running:  
        try:
            data, _ = listen_sock.recvfrom(1024)
            message = data.decode('utf-8', errors='ignore')
            
            # Always print that something was received for debugging
            # print_status(f"RX UDP from {addr[0]}:{addr[1]}: {message[:30]}...") # DEBUG Line

            if message.startswith("FREQ:"):
                try:
                    freq_value_str = message.split(":")[1].strip()
                    freq_value = float(freq_value_str)
                    new_freq_display = f"Frequency: {freq_value:.2f} Hz"
                    if new_freq_display != last_freq_display:
                        print_status(f"Sent Command: '{last_sent_command}' | {new_freq_display}")
                        last_freq_display = new_freq_display
                except (IndexError, ValueError) as e:
                    print_status(f"Sent Command: '{last_sent_command}' | Error parsing freq: {message[:20]}... ({e})")
                    last_freq_display = "" # Reset to force update next time
            # else: # Optional: log non-frequency packets
            #     print_status(f"Sent Command: '{last_sent_command}' | RX Other: {message[:20]}...")


        except socket.timeout:
            # This is expected, just continue the loop to check 'running'
            continue
        except socket.error as e:
            if running:
                print(f"\nSocket error in frequency listener: {e}") # Print on new line
            break
        except Exception as e:
            if running:
                print(f"\nUnexpected error in frequency listener: {e}") # Print on new line
            break
    print("\nFrequency listener thread stopped.")


if __name__ == "__main__":
    # for debugging
    # freq_thread = threading.Thread(target=frequency_listener_thread, daemon=True)
    # freq_thread.start()

    print("Starting keyboard listener...")
    kb_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    kb_listener.start()

    try:
        while running and kb_listener.is_alive():
            time.sleep(0.1)
    except KeyboardInterrupt:
        print_status("\nCtrl+C detected. Shutting down...")
        sys.stdout.flush()
        running = False
    finally:
        if kb_listener.is_alive():
            kb_listener.stop()

        print_status("\nMain loop ended. Cleaning up...")
        sys.stdout.flush()
        running = False

        # if freq_thread.is_alive():
        #     print("Waiting for frequency listener to exit...")
        #     freq_thread.join(timeout=1.0) # Shorter join timeout

        print("Sending final STOP command.")
        send_robot_command('S') # This will use print_status
        time.sleep(0.1)

        print("\nClosing sockets.") # New line
        if 'send_sock' in locals(): send_sock.close()
        # if 'listen_sock' in locals(): listen_sock.close()

        print_status("Exited." + " "*70) # Clear line and print Exited
        print() # New line at the very end