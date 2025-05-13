from flask import Flask, render_template, request, jsonify
import socket

app = Flask(__name__)

# --- Configuration for Arduino ---
# !!! IMPORTANT: Set this to your Arduino's IP address on the laptop hotspot !!!
# You can get this from the Arduino's Serial Monitor output when it connects
ARDUINO_IP = "192.168.137.226" # <<< EXAMPLE IP - CHANGE THIS!!!
ARDUINO_PORT = 1000           # Must match the port in your Arduino sketch

# Create a UDP socket (used globally by the server)
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"UDP Socket created. Will send to {ARDUINO_IP}:{ARDUINO_PORT}")
except socket.error as e:
    print(f"Error creating socket: {e}")
    sock = None # Indicate that the socket is not available

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route('/send_command', methods=['POST'])
def send_command_route():
    """Receives a command from the web page and sends it as UDP to Arduino."""
    if not sock:
        return jsonify({'status': 'error', 'message': 'UDP Socket not available on server.'}), 500

    data = request.get_json()
    command = data.get('command')

    if command and command in ['F', 'L', 'R', 'S', 'B']:
        try:
            message = command.encode('utf-8')
            sock.sendto(message, (ARDUINO_IP, ARDUINO_PORT))
            print(f"Sent command '{command}' to Arduino.")
            return jsonify({'status': 'success', 'message': f"Command '{command}' sent."})
        except socket.gaierror:
            error_msg = f"Error: Hostname or IP '{ARDUINO_IP}' could not be resolved."
            print(error_msg)
            return jsonify({'status': 'error', 'message': error_msg}), 500
        except socket.error as e:
            error_msg = f"Socket Error sending data: {e}"
            print(error_msg)
            return jsonify({'status': 'error', 'message': error_msg}), 500
        except Exception as e:
            error_msg = f"An unexpected error occurred: {e}"
            print(error_msg)
            return jsonify({'status': 'error', 'message': error_msg}), 500
    else:
        return jsonify({'status': 'error', 'message': 'Invalid command.'}), 400

if __name__ == '__main__':
    if not ARDUINO_IP or ARDUINO_IP == "YOUR_ARDUINO_IP_HERE": # Basic check
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! ERROR: ARDUINO_IP is not set in app.py. Please edit   !!!")
        print("!!! the script and set it to your Arduino's IP address.   !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    else:
        print(f"Flask server starting. Open your browser to http://127.0.0.1:5000")
        app.run(debug=True, host='0.0.0.0') # host='0.0.0.0' makes it accessible on your network