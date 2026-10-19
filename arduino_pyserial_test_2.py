import serial
import time

def read_serial_data(port_name, baud_rate):
    # Configure and open the serial port
    # It's recommended to set a timeout to prevent the script from blocking forever
    try:
        ser = serial.Serial(port_name, baud_rate, timeout=1)
        time.sleep(2) # Give some time for the connection to establish
        print(f"Connected to {ser.port} at {ser.baudrate} baud")

        while True:
            # Read a line from the serial port (up to the newline character '\n')
            # The result is in bytes, so decode it to a string and strip whitespace
            # 'utf-8' is a common encoding
            line_bytes = ser.readline()
            if line_bytes:
                try:
                    line = line_bytes.decode('utf-8').strip()
                    if line:
                        print(f"Received: {line}")
                except UnicodeDecodeError:
                    print("Could not decode bytes to utf-8")

    except serial.SerialException as e:
        print(f"Error opening serial port: {e}")
    except KeyboardInterrupt:
        print("Serial reading stopped by user.")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("Serial port closed.")

if __name__ == '__main__':
    # !!! IMPORTANT: Replace 'COM4' or '/dev/ttyUSB0' with your actual port name
    # On Windows, it's typically 'COMx' (e.g., 'COM4')
    # On Linux, it's typically '/dev/ttyUSBx' or '/dev/ttyACMx'
    # On macOS, it might be '/dev/tty.usbmodem...'

    # Check your device manager (Windows) or 'ls /dev/tty*' (Linux/macOS) for the correct name
    
    serial_port_name = 'COM7' 
    serial_baud_rate = 9600 # Set to match the device you are communicating with

    read_serial_data(serial_port_name, serial_baud_rate)