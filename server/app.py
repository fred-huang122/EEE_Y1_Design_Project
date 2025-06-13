from flask import Flask, render_template, request, jsonify, Response, url_for
import socket
import threading
import time
import json
import collections # For deque (efficient fixed-size list for log)

app = Flask(__name__)

# --- Configuration for Arduino ---
ARDUINO_IP = "192.168.137.226"  # MAKE SURE THIS IS YOUR ARDUINO'S CURRENT IP
PYTHON_LISTEN_FREQ_PORT = 1001   # Port THIS Flask app listens on for Arduino's data

# --- Global State for Sensor Data (Thread-Safe) ---
latest_frequency_value = None
latest_uart_packet_type = None
latest_uart_packet_value = None
latest_ir_pulse_value = None
latest_magnet_direction_value = None

frequency_data_lock = threading.Lock()
uart_data_lock = threading.Lock()
ir_pulse_data_lock = threading.Lock()
magnet_direction_data_lock = threading.Lock()

running_udp_listener = True # Flag to control the listener thread

# --- UDP Listener Thread for all sensor data from Arduino ---
def udp_listener():
    global latest_frequency_value, running_udp_listener
    global latest_uart_packet_type, latest_uart_packet_value
    global latest_ir_pulse_value, latest_magnet_direction_value

    listener_sock = None
    try:
        listener_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        listener_sock.bind(('', PYTHON_LISTEN_FREQ_PORT)) # Bind to all available interfaces
        listener_sock.settimeout(1.0) # Timeout to allow checking the running flag
        print(f"UDP listener started on port {PYTHON_LISTEN_FREQ_PORT} for all sensor data.")
    except socket.error as e:
        print(f"!!! ERROR: Could not bind UDP listener socket on port {PYTHON_LISTEN_FREQ_PORT}: {e}")
        running_udp_listener = False
        return

    while running_udp_listener:
        try:
            data, addr = listener_sock.recvfrom(1024) # Buffer size
            message = data.decode('utf-8', errors='ignore')

            # --- Handle FREQ messages ---
            if message.startswith("FREQ:"):
                try:
                    freq_str = message.split(":", 1)[1].strip()
                    with frequency_data_lock:
                        latest_frequency_value = float(freq_str)
                except (IndexError, ValueError) as e:
                    print(f"UDP Freq: Error parsing message '{message}' from {addr[0]}: {e}")

            # --- Handle UART_PKT messages ---
            elif message.startswith("UART_PKT:"):
                try:
                    packet_data = message.split(":", 1)[1]
                    with uart_data_lock:
                        latest_uart_packet_type = "PKT"
                        latest_uart_packet_value = packet_data
                except IndexError as e:
                    print(f"UDP UART_PKT: Error parsing message '{message}' from {addr[0]}: {e}")

            # --- Handle UART_FAIL messages ---
            elif message.startswith("UART_FAIL:"):
                try:
                    fail_data = message.split(":", 1)[1]
                    with uart_data_lock:
                        latest_uart_packet_type = "FAIL"
                        latest_uart_packet_value = fail_data
                except IndexError as e:
                    print(f"UDP UART_FAIL: Error parsing message '{message}' from {addr[0]}: {e}")

            # --- Handle IR messages ---
            elif message.startswith("IR:"):
                try:
                    ir_str = message.split(":", 1)[1].strip()
                    with ir_pulse_data_lock:
                        latest_ir_pulse_value = float(ir_str)
                except (IndexError, ValueError) as e:
                    print(f"UDP IR: Error parsing message '{message}' from {addr[0]}: {e}")

            # --- Handle MAG messages ---
            elif message.startswith("MAG:"):
                try:
                    magnet_data = message.split(":", 1)[1].strip()
                    with magnet_direction_data_lock:
                        latest_magnet_direction_value = magnet_data
                except IndexError as e:
                    print(f"UDP MAG: Error parsing message '{message}' from {addr[0]}: {e}")

        except socket.timeout:
            continue # Normal, allows checking running_udp_listener
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

@app.route('/stream_sensor_data')
def stream_sensor_data():
    """Streams all sensor data using Server-Sent Events."""
    def event_stream():
        # Per-client state to avoid sending duplicate data
        last_sent_frequency = None
        last_sent_uart_type = None
        last_sent_uart_value = None
        last_sent_ir_pulse = None
        last_sent_magnet_direction = None

        while True:
            time.sleep(0.2) # Send updates every 200ms

            # --- Frequency Data ---
            with frequency_data_lock:
                current_frequency = latest_frequency_value
            if current_frequency != last_sent_frequency:
                payload = {'type': 'frequency', 'value': f"{current_frequency:.2f}" if current_frequency is not None else None}
                yield f"data: {json.dumps(payload)}\n\n"
                last_sent_frequency = current_frequency

            # --- UART Data ---
            with uart_data_lock:
                current_uart_type = latest_uart_packet_type
                current_uart_value = latest_uart_packet_value
            if current_uart_type != last_sent_uart_type or current_uart_value != last_sent_uart_value:
                payload = {'type': 'uart_data', 'packet_type': current_uart_type, 'value': current_uart_value}
                yield f"data: {json.dumps(payload)}\n\n"
                last_sent_uart_type = current_uart_type
                last_sent_uart_value = current_uart_value

            # --- IR Pulse Data ---
            with ir_pulse_data_lock:
                current_ir_pulse = latest_ir_pulse_value
            if current_ir_pulse != last_sent_ir_pulse:
                payload = {'type': 'ir_pulse', 'value': f"{current_ir_pulse:.2f}" if current_ir_pulse is not None else None}
                yield f"data: {json.dumps(payload)}\n\n"
                last_sent_ir_pulse = current_ir_pulse

            # --- Magnet Direction Data ---
            with magnet_direction_data_lock:
                current_magnet_direction = latest_magnet_direction_value
            if current_magnet_direction != last_sent_magnet_direction:
                payload = {'type': 'magnet_direction', 'value': current_magnet_direction}
                yield f"data: {json.dumps(payload)}\n\n"
                last_sent_magnet_direction = current_magnet_direction

    return Response(event_stream(), mimetype='text/event-stream')

# --- Main Execution ---
if __name__ == '__main__':
    if not ARDUINO_IP or ARDUINO_IP == "YOUR_ARDUINO_IP_HERE":
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!!  ERROR: ARDUINO_IP is not set in app.py. Please edit    !!!")
        print("!!!  the script and set it to your Arduino's IP address.    !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    else:
        udp_thread = threading.Thread(target=udp_listener, daemon=True)
        udp_thread.start()

        print(f"Flask server starting.")
        print(f"Sensor Dashboard: http://127.0.0.1:5000")
        try:
            app.run(debug=False, host='0.0.0.0', use_reloader=False)
        except KeyboardInterrupt:
            print("Flask server shutting down...")
        finally:
            print("Stopping UDP listener...")
            running_udp_listener = False
            if udp_thread.is_alive():
                udp_thread.join(timeout=2.0)
            print("Server exited.")