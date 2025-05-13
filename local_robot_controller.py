import socket
import time
import sys
from pynput import keyboard # Import the keyboard listener

ARDUINO_PORT = 1000

# Get IP from user
target_ip = input(f"Enter the Arduino's IP Address (e.g., 192.168.137.226): ")
if not target_ip:
    print("Error: IP address cannot be empty. Exiting.")
    sys.exit()

print(f"\nTargeting Arduino at {target_ip}:{ARDUINO_PORT}")
print("\nControl the robot using WASD or Arrow Keys:")
print("  W / Up Arrow    -> Forward (F)")
print("  A / Left Arrow  -> Left    (L)")
print("  D / Right Arrow -> Right   (R)")
print("  S / Down Arrow  -> Stop    (B)")
print("\nPress 'Q/esc' to Quit.")
print("-" * 30)

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print("UDP Socket Created.")
except socket.error as e:
    print(f"Error creating socket: {e}")
    sys.exit()

current_command = 'S' # Start in stopped state
last_sent_command = '' 
active_movement_key = None 

def send_command(command_to_send):
    global last_sent_command
    if command_to_send != last_sent_command:
        try:
            message = command_to_send.encode('utf-8')
            sock.sendto(message, (target_ip, ARDUINO_PORT))
            print(f"Sent: '{command_to_send}'")
            last_sent_command = command_to_send
        except socket.gaierror:
            print(f"Error: Hostname or IP '{target_ip}' could not be resolved.")
            return False 
        except socket.error as e:
            print(f"Socket Error sending data: {e}")
            return False # Indicate failure
        except Exception as e:
            print(f"An unexpected error occurred during sending: {e}")
            return False # Indicate failure
    return True # Indicate success or no change needed


def on_press(key):
    global current_command, active_movement_key
    new_command = None
    key_pressed = None

    try:
        key_pressed = key.char.upper()
        if key_pressed == 'W':
            new_command = 'F'
        elif key_pressed == 'A':
            new_command = 'L'
        elif key_pressed == 'D':
            new_command = 'R'
        elif key_pressed == 'S':
            new_command = 'B'
        elif key_pressed == 'Q':
            print("Quit key pressed...")
            return False 

    except AttributeError:
        if key == keyboard.Key.up:
            new_command = 'F'
            key_pressed = keyboard.Key.up
        elif key == keyboard.Key.left:
            new_command = 'L'
            key_pressed = keyboard.Key.left
        elif key == keyboard.Key.right:
            new_command = 'R'
            key_pressed = keyboard.Key.right
        elif key == keyboard.Key.down:
            new_command = 'B'
            key_pressed = keyboard.Key.down
        elif key == keyboard.Key.esc:
            print("Escape key pressed...")
            return False

    if new_command is not None:
        current_command = new_command
        active_movement_key = key_pressed 
        if not send_command(current_command): 
             return False 

    # Keep listener running unless 'Q' or error occurred
    return True


def on_release(key):
    global current_command, last_sent_command, active_movement_key
    key_released = None
    released_command_type = None # What type of command this key represents

    try:
        key_released = key.char.upper()
        if key_released == 'W': released_command_type = 'F'
        elif key_released == 'A': released_command_type = 'L'
        elif key_released == 'D': released_command_type = 'R'
        elif key_released == 'S': released_command_type = 'B'
        elif key_released == 'Q': return False # Already handled in on_press, but good practice
        elif key_released == 'ESC': return False # Also handled in on_press, but good practice

    except AttributeError:
        if key == keyboard.Key.up:
            released_command_type = 'F'
            key_released = keyboard.Key.up
        elif key == keyboard.Key.left:
            released_command_type = 'L'
            key_released = keyboard.Key.left
        elif key == keyboard.Key.right:
            released_command_type = 'R'
            key_released = keyboard.Key.right
        elif key == keyboard.Key.down:
            released_command_type = 'B'
            key_released = keyboard.Key.down

    # If the key that was just released is the one currently causing movement, send STOP
    if key_released == active_movement_key and released_command_type in ['F', 'L', 'R', 'B']:
        current_command = 'S'
        active_movement_key = None
        if not send_command(current_command): # Send Stop
             return False

    # Keep listener running unless 'Q' or error occurred
    return True

print("Starting keyboard listener... Press 'Q' to quit.")
listener = keyboard.Listener(on_press=on_press, on_release=on_release)
listener.start()
listener.join()

print("\nListener stopped. Closing socket.")
send_command('S')
time.sleep(0.05)
sock.close()
print("Exited.")