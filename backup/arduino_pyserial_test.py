import serial
import time

# Configure the serial port.
# Replace 'COM4' with your Arduino's port (e.g., 'COM3' on Windows, '/dev/ttyUSB0' on Linux, '/dev/tty.usbmodem...' on macOS)
# Baud rate must match the Arduino sketch (9600)
try:
    arduino = serial.Serial('COM4', 9600, timeout=1)
    time.sleep(2) # Give the connection time to establish (Arduino resets when serial port opens)
    print("Connection established")
except serial.SerialException as e:
    print(f"Error opening serial port: {e}")
    exit()

while True:
    user_input = input("Enter 'H' to turn ON, 'L' to turn OFF, or 'q' to quit: ").strip().upper()

    if user_input == 'H':
        arduino.write(b'H') # Send byte string 'H'
        print("LED ON")
    elif user_input == 'L':
        arduino.write(b'L') # Send byte string 'L'
        print("LED OFF")
    elif user_input == 'Q':
        print("Exiting program.")
        arduino.close() # Close the serial port
        break
    else:
        print("Invalid input. Try again.")
