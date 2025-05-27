from flask import Flask, render_template, request, jsonify, Response
import socket
import threading
import time
import json
import collections # For deque (efficient fixed-size list for log)

app = Flask(__name__)

# --- Configuration for Arduino ---
ARDUINO_IP = "192.168.137.226"  # MAKE SURE THIS IS YOUR ARDUINO'S CURRENT IP
ARDUINO_COMMAND_PORT = 1000      # Port to send commands TO Arduino (from index.html)
PYTHON_LISTEN_FREQ_PORT = 1001   # Port THIS Flask app listens on for Arduino's frequency data

# --- Socket for SENDING commands (from index.html) ---
# This socket is used by the original robot controller page
try:
    command_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"UDP Command Socket created. Will send to {ARDUINO_IP}:{ARDUINO_COMMAND_PORT}")
except socket.error as e:
    print(f"Error creating command socket: {e}")
    command_sock = None

# --- Global State for Frequency Data (Thread-Safe) ---
latest_frequency_value = None
# frequency_log_server_side = collections.deque(maxlen=50) # Optional: if server needs to log too
frequency_data_lock = threading.Lock()
running_udp_listener = True # Flag to control the listener thread

# --- UDP Listener Thread for Frequency from Arduino ---
def udp_frequency_listener():
    global latest_frequency_value, running_udp_listener
    
    listener_sock = None
    try:
        listener_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        listener_sock.bind(('', PYTHON_LISTEN_FREQ_PORT)) # Bind to all available interfaces
        listener_sock.settimeout(1.0) # Timeout for recvfrom to allow checking running_udp_listener
        print(f"UDP Frequency listener started on port {PYTHON_LISTEN_FREQ_PORT}")
    except socket.error as e:
        print(f"!!! ERROR: Could not bind UDP listener socket on port {PYTHON_LISTEN_FREQ_PORT}: {e}")
        running_udp_listener = False 
        return

    while running_udp_listener:
        try:
            data, addr = listener_sock.recvfrom(1024) # Buffer size
            message = data.decode('utf-8', errors='ignore')

            if message.startswith("FREQ:"):
                try:
                    freq_str = message.split(":")[1].strip()
                    current_freq = float(freq_str)
                    
                    with frequency_data_lock:
                        latest_frequency_value = current_freq
                    
                    # For server-side debugging, can be removed later
                    # print(f"UDP Freq RX: {current_freq:.2f} Hz from {addr[0]}") 
                except (IndexError, ValueError):
                    print(f"UDP Freq: Error parsing message '{message}' from {addr[0]}")
        except socket.timeout:
            continue # This is normal, allows checking running_udp_listener
        except socket.error as e:
            if running_udp_listener: # Avoid error message during planned shutdown
                print(f"UDP Frequency listener socket error: {e}")
            break 
        except Exception as e:
            if running_udp_listener:
                print(f"UDP Frequency listener unexpected error: {e}")
            break
            
    if listener_sock:
        listener_sock.close()
    print("UDP Frequency listener stopped.")

# --- Flask Routes ---
@app.route('/')
def index():
    """Serves the main robot control HTML page."""
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    """Serves the new sensor dashboard HTML page."""
    return render_template('sensor_dashboard.html')

@app.route('/send_command', methods=['POST'])
def send_command_route():
    """Receives a command from the robot control page and sends it via UDP to Arduino."""
    if not command_sock: # Use the dedicated command socket
        return jsonify({'status': 'error', 'message': 'UDP Command Socket not available on server.'}), 500

    data = request.get_json()
    command = data.get('command')

    if command and command in ['F', 'L', 'R', 'S', 'B']:
        try:
            message = command.encode('utf-8')
            command_sock.sendto(message, (ARDUINO_IP, ARDUINO_COMMAND_PORT))
            print(f"Sent command '{command}' to Arduino ({ARDUINO_IP}:{ARDUINO_COMMAND_PORT}).")
            return jsonify({'status': 'success', 'message': f"Command '{command}' sent."})
        except socket.gaierror: # ... (error handling as before) ...
            error_msg = f"Error: Hostname or IP '{ARDUINO_IP}' could not be resolved."
            print(error_msg)
            return jsonify({'status': 'error', 'message': error_msg}), 500
        except socket.error as e: # ... (error handling as before) ...
            error_msg = f"Socket Error sending data: {e}"
            print(error_msg)
            return jsonify({'status': 'error', 'message': error_msg}), 500
        except Exception as e: # ... (error handling as before) ...
            error_msg = f"An unexpected error occurred: {e}"
            print(error_msg)
            return jsonify({'status': 'error', 'message': error_msg}), 500
    else:
        return jsonify({'status': 'error', 'message': 'Invalid command.'}), 400

@app.route('/stream_sensor_data')
def stream_sensor_data():
    """Streams sensor data (currently just frequency) using Server-Sent Events."""
    def event_stream():
        last_sent_frequency = None
        while True:
            # Send data roughly every 200ms, or when it changes
            # The client-side log updates every 1s based on the latest value it has
            time.sleep(0.2) 
            current_frequency_to_send = None
            with frequency_data_lock:
                current_frequency_to_send = latest_frequency_value
            
            if current_frequency_to_send is not None:
                if current_frequency_to_send != last_sent_frequency:
                    payload = {'type': 'frequency', 'value': f"{current_frequency_to_send:.2f}"}
                    yield f"data: {json.dumps(payload)}\n\n"
                    last_sent_frequency = current_frequency_to_send
            elif last_sent_frequency is not None : # If it was sending and now it's None
                payload = {'type': 'frequency', 'value': None} # Send None to indicate data loss/stop
                yield f"data: {json.dumps(payload)}\n\n"
                last_sent_frequency = None


    return Response(event_stream(), mimetype='text/event-stream')

# --- Main Execution ---
if __name__ == '__main__':
    if not ARDUINO_IP or ARDUINO_IP == "YOUR_ARDUINO_IP_HERE": # Basic check
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!!  ERROR: ARDUINO_IP is not set in app.py. Please edit    !!!")
        print("!!!  the script and set it to your Arduino's IP address.    !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    else:
        # Start the UDP frequency listener thread
        udp_thread = threading.Thread(target=udp_frequency_listener, daemon=True)
        udp_thread.start()
        
        print(f"Flask server starting.")
        print(f"Robot Controller: http://127.0.0.1:5000")
        print(f"Sensor Dashboard: http://127.0.0.1:5000/dashboard")
        try:
            # use_reloader=False is important for threads when not in production with a proper WSGI server
            app.run(debug=False, host='0.0.0.0', use_reloader=False) 
        except KeyboardInterrupt:
            print("Flask server shutting down...")
        finally:
            print("Stopping UDP listener...")
            running_udp_listener = False # Signal thread to stop
            if udp_thread.is_alive():
                udp_thread.join(timeout=2.0) # Wait for thread to finish
            if command_sock: # From original robot controller part
                print("Closing main command socket.")
                command_sock.close()
            print("Server exited.")