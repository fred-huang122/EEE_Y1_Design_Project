# EEE_Y1_Design_Project

You will need python install and open the .ino file in the Arduino IDE if you want to install the code onto the Arduino

Note: if the packets aren't wroking you will need to update the wifi shield firmware using an old verion of the Arduino IDE and the WIfi101 library.

The local_robot_controller.py file allows you to control the robot directly on the machine/laptop which is hosting the hotspot by connecting to the IP of the arduino (after the arduino is connected to wifi) and the UDP port which is deafaulted to 1000.

The Server Controller is a way to host the controller on the web so that devices connected to the loacl network is able to access the website through <HostID>:5000

The Ltspice folder contains the latest version of the circuits made.