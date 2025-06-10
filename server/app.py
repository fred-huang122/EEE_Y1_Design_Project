from flask import Flask, render_template, request, jsonify, Response, url_for
import socket
import threading
import time
import json
import collections # For deque (efficient fixed-size list for log)

app = Flask(__name__)

# --- Configuration for Arduino ---
ARDUINO_IP = "192.168.137.226"  # MAKE SURE THIS IS YOUR ARDUINO'S CURRENT IP
PYTHON_LISTEN_FREQ_PORT = 1001   # Port THIS Flask app listens on for Arduino's frequency data

# --- Global State for Frequency Data (Thread-Safe) ---
latest_frequency_value = None
# frequency_log_server_side = collections.deque(maxlen=50) # Optional: if server needs to log too
frequency_data_lock = threading.Lock()

# --- Global State for UART Data (Thread-Safe) --- NEW
latest_uart_packet_type = None # To store 'PKT' or 'FAIL'
latest_uart_packet_value = None  # To store the 'xxxx' or 'xxx' data
uart_data_lock = threading.Lock() # New lock for UART data

running_udp_listener = True # Flag to control the listener thread

# --- UDP Listener Thread for UART and Frequency from Arduino ---
def udp_listener(): # Renamed for clarity, or keep as udp_frequency_listener
    global latest_frequency_value, running_udp_listener
    global latest_uart_packet_type, latest_uart_packet_value # Add new globals

    listener_sock = None
    try:
        listener_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        listener_sock.bind(('', PYTHON_LISTEN_FREQ_PORT)) # Bind to all available interfaces
        listener_sock.settimeout(1.0) # Timeout for recvfrom to allow checking running_udp_listener
        print(f"UDP listener started on port {PYTHON_LISTEN_FREQ_PORT} for Frequency and UART data.")
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
                    freq_str = message.split(":", 1)[1].strip()
                    current_freq = float(freq_str)
                    
                    with frequency_data_lock: # Use the specific lock
                        latest_frequency_value = current_freq
                    
                    # print(f"UDP Freq RX: {current_freq:.2f} Hz from {addr[0]}")
                except (IndexError, ValueError) as e:
                    print(f"UDP Freq: Error parsing message '{message}' from {addr[0]}: {e}")
            
            # --- Handle UART_PKT messages ---
            elif message.startswith("UART_PKT:"):
                try:
                    packet_data = message.split(":", 1)[1]
                    print(f"UDP UART Packet RX: '{packet_data}' from {addr[0]}")
                    with uart_data_lock: # Use the new UART lock
                        latest_uart_packet_type = "PKT"
                        latest_uart_packet_value = packet_data
                except IndexError as e:
                    print(f"UDP UART_PKT: Error parsing message '{message}' from {addr[0]}: {e}")

            # --- Handle UART_FAIL messages ---
            elif message.startswith("UART_FAIL:"):
                try:
                    fail_data = message.split(":", 1)[1]
                    print(f"UDP UART Fail RX: '{fail_data}' from {addr[0]}")
                    with uart_data_lock: # Use the new UART lock
                        latest_uart_packet_type = "FAIL"
                        latest_uart_packet_value = fail_data
                except IndexError as e:
                    print(f"UDP UART_FAIL: Error parsing message '{message}' from {addr[0]}: {e}")
            
        except socket.timeout:
            continue # This is normal, allows checking running_udp_listener
        except socket.error as e:
            if running_udp_listener:
                print(f"UDP listener socket error: {e}")
            break
        except Exception as e:
            if running_udp_listener:
                print(f"UDP listener unexpected error: {e}")
            break
            
    if listener_sock:
        listener_sock.close()
    print("UDP listener stopped.")
    
# --- Flask Routes ---
@app.route('/')
def dashboard():
    """Serves the new sensor dashboard HTML page."""
    return render_template('sensor_dashboard.html')

# --- Sensor Dashboard Route ---
@app.route('/stream_sensor_data')
def stream_sensor_data():
    """Streams sensor data (frequency and UART) using Server-Sent Events."""
    def event_stream():
        global latest_uart_packet_type, latest_uart_packet_value 

        last_sent_frequency = None
        last_sent_uart_type = None
        last_sent_uart_value = None

        while True:
            time.sleep(0.2) # Interval for sending updates
            
            # --- Frequency Data ---
            current_frequency_to_send = None
            with frequency_data_lock: # Ensure this lock is defined globally
                current_frequency_to_send = latest_frequency_value
            
            if current_frequency_to_send is not None:
                if current_frequency_to_send != last_sent_frequency:
                    payload = {'type': 'frequency', 'value': f"{current_frequency_to_send:.2f}"}
                    yield f"data: {json.dumps(payload)}\n\n"
                    last_sent_frequency = current_frequency_to_send
            elif last_sent_frequency is not None: # If it was sending and now it's None
                payload = {'type': 'frequency', 'value': None}
                yield f"data: {json.dumps(payload)}\n\n"
                last_sent_frequency = None

            # --- UART Data ---
            current_uart_type_from_global = None
            current_uart_value_from_global = None
            
            with uart_data_lock: # Read global state
                current_uart_type_from_global = latest_uart_packet_type
                current_uart_value_from_global = latest_uart_packet_value

            if current_uart_type_from_global is not None and \
               current_uart_value_from_global is not None and \
               (current_uart_type_from_global != last_sent_uart_type or \
                current_uart_value_from_global != last_sent_uart_value):
                
                # This is new data for this client stream. Apply filtering logic.
                data_to_stream_value = None # This will hold the value after processing '#'

                if '#' in current_uart_value_from_global:
                    # Condition met: '#' is in the packet value.
                    # Remove '#' from the value to be streamed.
                    data_to_stream_value = current_uart_value_from_global.replace('#', '')
                    
                    uart_payload = {'type': 'uart_data', 
                                    'packet_type': current_uart_type_from_global, 
                                    'value': data_to_stream_value}
                    yield f"data: {json.dumps(uart_payload)}\n\n"
                last_sent_uart_type = current_uart_type_from_global
                last_sent_uart_value = current_uart_value_from_global
            
            with uart_data_lock:
                latest_uart_packet_type = None
                latest_uart_packet_value = None
            
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
        udp_thread = threading.Thread(target=udp_listener, daemon=True)
        udp_thread.start()
        
        print(f"Flask server starting.")
        print(f"Sensor Dashboard: http://127.0.0.1:5000")
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
            print("Server exited.")