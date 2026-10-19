# worker_serial.py
import serial
import time
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, QTimer


class SerialReaderThread(QThread):
    data_received = pyqtSignal(str)
    serial_error = pyqtSignal(str)
    connected = pyqtSignal(str)
    disconnected = pyqtSignal()

    def __init__(self, port_name, baud_rate, parent=None):
        super().__init__(parent)
        self.port_name = port_name
        self.baud_rate = baud_rate
        self.running = True
        self.ser = None   # <-- clave

    def run(self):
        try:
            self.ser = serial.Serial(
                self.port_name,
                self.baud_rate,
                timeout=1
            )
            time.sleep(2)  # Arduino reset
            self.connected.emit(
                f"Conectado a {self.ser.port} @ {self.ser.baudrate}"
            )

            while self.running:
                if self.ser and self.ser.in_waiting:
                    line_bytes = self.ser.readline()
                    try:
                        line = line_bytes.decode("utf-8").strip()
                        if line:
                            self.data_received.emit(line)
                    except UnicodeDecodeError:
                        self.serial_error.emit("Error decodificando UTF-8")

        except serial.SerialException as e:
            self.serial_error.emit(str(e))

        finally:
            if self.ser and self.ser.is_open:
                self.ser.close()
            self.disconnected.emit()
    
    

    def simulate_cycle(self):
        """
        Simula el comportamiento REAL del Arduino Dig Dug:
        FAIL -> STANDBY -> EN_PROCESO -> PASS
        Emitiendo data_received como si viniera del puerto serial.
        """

        # FAIL forzado inicial
        self.data_received.emit("FAIL")

        # Verde fijo (STANDBY)
        QTimer.singleShot(
            500,
            lambda: self.data_received.emit("STANDBY")
        )

        # Verde parpadeante (EN_PROCESO)
        QTimer.singleShot(
            1500,
            lambda: self.data_received.emit("EN_PROCESO")
        )

        # Verde fijo final (PASS)
        QTimer.singleShot(
            4000,
            lambda: self.data_received.emit("PASS")
        )



    @pyqtSlot(str)
    def send_command(self, command):
        """
        Envía un comando a Arduino.
        Uso seguro desde el hilo principal.
        """
        if self.ser and self.ser.is_open:
            try:
                cmd = command.strip() + "\n"
                self.ser.write(cmd.encode("utf-8"))
            except serial.SerialException as e:
                self.serial_error.emit(str(e))

    def stop(self):
        self.running = False
        self.wait()