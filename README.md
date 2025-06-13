# EEE Y1 Design Project: Robot Control & Sensor Dashboard

This project provides a comprehensive system for controlling a robot and monitoring its sensors in real-time. It consists of two main components:
1.  A **Web-Based Sensor Dashboard** that displays live data from the robot's sensors on any device on the local network.
2.  A **Local Robot Controller** that allows for direct, keyboard-based control of the robot's movements.

---

## Features

* **Real-time Sensor Monitoring**: A web dashboard visualizes data from multiple sensors simultaneously, including:
    * AM Frequency
    * Ultrasound UART packets (including Duck Name)
    * IR Pulse frequency
    * Magnetometer direction (North/South)
* **Intelligent Species Identification**: The dashboard automatically deduces the "species" of the detected object based on a combination of IR, AM, and magnetic field sensor readings.
* **Live Data Logs**: Each sensor on the dashboard has a running log that shows the most recent timestamped values.
* **Direct Keyboard Control**: A command-line interface provides precise, low-latency control over the robot's movement using WASD or arrow keys.
* **Network-Based Architecture**: The robot, server, and client devices communicate over the local network using UDP and Server-Sent Events (SSE), allowing for flexible and decoupled operation.

---

## Project Structure

EEE_Y1_Design_Project/
├── server/
│   ├── app.py                      # The Flask web server backend for the dashboard.
│   ├── local_robot_controller.py   # The command-line script for direct robot control.
│   ├── static/
│   │   └── sensor_dashboard.css    # CSS styling for the web dashboard.
│   └── templates/
│       └── sensor_dashboard.html   # HTML structure for the web dashboard.
└── README.md                       # This file.


---

## System Components

### 1. Web-Based Sensor Dashboard

The dashboard is a Flask web application that provides a rich, graphical interface for monitoring the robot's sensors.

**How it Works:**
* The Flask server (`app.py`) starts a background thread that continuously listens for UDP packets sent from the Arduino on port `1001`.
* It parses incoming packets, which are formatted as simple key-value strings (e.g., `FREQ:100.5`, `MAG:North`, `IR:457.2`).
* The main Flask application serves the `sensor_dashboard.html` page.
* Once the page is loaded, it establishes a connection to the server's `/stream_sensor_data` endpoint. The server uses Server-Sent Events (SSE) to push live sensor data to the webpage as it arrives from the robot.

### 2. Local Robot Controller

The `local_robot_controller.py` script allows you to directly drive the robot from the computer connected to the same network.

**How it Works:**
* The script listens for keyboard presses (WASD, Arrow Keys, Shift, Ctrl).
* Based on the keys being pressed, it determines the appropriate command (e.g., `F` for Forward, `L` for Left, `B` for Backward).
* These commands are sent as UDP packets to the Arduino's IP address on command port `1000`.

---

## Prerequisites

* Python 3
* An Arduino correctly flashed with the project's `.ino` code and a configured WiFi shield.
* The following Python libraries:
    * `Flask`
    * `pynput`

## Setup & Usage

**This is the most important step.** The IP address of the Arduino is hardcoded in the Python scripts. You must update it to match your Arduino's IP address on the network.

1.  Open `server/app.py` and change the `ARDUINO_IP` variable to your Arduino's IP address.
2.  Open `server/local_robot_controller.py` and change the `target_ip` variable to the same IP address.
