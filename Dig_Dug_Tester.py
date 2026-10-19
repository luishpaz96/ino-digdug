import os
import sys
import serial.tools.list_ports
from PyQt5 import QtCore
from PyQt5.QtCore import pyqtSignal, QTimer, Qt
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox
from pathlib import Path

from worker_serial import SerialReaderThread
from dig_dug_ui import Ui_Form as digdug_ui
from settings_window import Ui_Form as settings_ui
from ffeticlient import FFEtiClient

SERIAL_DUMMY = "FLG2545-00408"
FFETI_FOLDER = r"C:\ffeti"

# ======================================================
# Redirect stdout to QTextEdit with auto-scroll
# ======================================================
class QTextEditStream:
    def __init__(self, text_edit):
        self.text_edit = text_edit

    def write(self, message):
        if message.strip():
            self.text_edit.append(message)
            self.text_edit.verticalScrollBar().setValue(
                self.text_edit.verticalScrollBar().maximum()
            )

    def flush(self):
        pass


# ======================================================
# SETTINGS WINDOW (solo selecciona COM)
# ======================================================
class SettingsWindow(QDialog, settings_ui):

    com_selected = pyqtSignal(str)
    config_file_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.setFixedWidth(336)
        self.setFixedHeight(97)
        self.setWindowFlags(QtCore.Qt.WindowCloseButtonHint)

        self.buttonBox.accepted.connect(self.emit_com)
        self.populate_ports()
        self.populate_station_name_comboBox()

    def populate_ports(self):
        self.comboBox.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.comboBox.addItem(p.device)

    def emit_com(self):
        self.com_selected.emit(self.comboBox.currentText())
        self.config_file_selected.emit(self.station_name_cb.currentText())
        self.close()

    def populate_station_name_comboBox(self):
        folder_path = Path(FFETI_FOLDER)
        for file in folder_path.glob("*.ini"):
            file = str(file)
            item = file.split('\\')[-1]
            self.station_name_cb.addItem(item)


# ======================================================
# MAIN WINDOW
# ======================================================
class DigDugTester(QDialog, digdug_ui):

    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowSystemMenuHint | Qt.WindowTitleHint | Qt.FramelessWindowHint)

        #self.setWindowFlags(Qt.WindowType_Mask) 
        

        # ---- SERIAL ----
        self.serial_thread = None

        # ---- UI ----
        self.start_button.setEnabled(False)
        self.settings_button.clicked.connect(self.open_settings)
        self.start_button.clicked.connect(self.start_operation)

        # ---- Redirect stdout ? output_console ----
        sys.stdout = QTextEditStream(self.output_console)

        # ---- Estado de proceso ----
        self.last_state = None
        self.fail_inicial_oculto = True

        # ---- Estado de unidad (TRAZABILIDAD) ----
        self.unidad_confirmada = False
        self.serial_activo = None
        self.set_status_label("NOT_CONNECTED")

        # ---- Flags ----
        self.debug_pass_fail = False
        self.ff_enabled = True

        # ---- ETI CLIENT ----
        self.ffeti = FFEtiClient()
        self.ffeti_config_file = None

        print("Sistema iniciado\n")

    # -------------------------------
    # SETTINGS
    # -------------------------------
    def open_settings(self):
        self.settings = SettingsWindow()
        self.settings.com_selected.connect(self.open_serial)
        self.settings.config_file_selected.connect(self.get_config_file)
        self.settings.show()

    def closeEvent(self, event):
        print("\n[CLOSE] Cierre detectado ? FAIL seguro\n")

        try:
            if self.serial_thread and self.serial_thread.isRunning():
                self.last_state = "FAIL"
                try:
                    self.serial_thread.send_command("FAIL")
                except Exception:
                    pass

                self.serial_thread.send_command("DISABLE")
                self.serial_thread.stop()
                self.serial_thread.wait(300)

        except Exception as e:
            print(f"[WARN] Error en cierre seguro: {e}\n")

        event.accept()

    def open_serial(self, port):
        self.com_port_label.setText(port)
        self.com_port_label.setStyleSheet("font-weight: bold")

        if self.serial_thread and self.serial_thread.isRunning():
            self.serial_thread.stop()

        self.serial_thread = SerialReaderThread(port, 9600)

        self.serial_thread.data_received.connect(self.on_serial_event)
        self.serial_thread.connected.connect(self.on_connected)
        self.serial_thread.serial_error.connect(self.on_error)
        
        self.serial_thread.start()

    def get_config_file(self, received):
        self.ffeti_config_file = received

    def set_status_label(self, estado):
        """
        Actualiza texto y color de label_status según estado del proceso
        """

        styles = {
            "NOT_CONNECTED": {
                "text": "NOT CONNECTED",
                "bg": "#A9A9A9",  # gris
            },
            "STANDBY": {
                "text": "STAND BY",
                "bg": "#FFD700",
            },
            "EN_PROCESO": {
                "text": "EN PROCESO",
                "bg": "#87CEEB",
            },
            "FAIL": {
                "text": "FAIL",
                "bg": "#FF4C4C",
            },
            "PASS": {
                "text": "PASS",
                "bg": "#32CD32",
            },
            "FINALIZADO": {
                "text": "FINALIZADO",
                "bg": "#D3D3D3",
            },
        }

        if estado not in styles:
            return

        self.label_status.setText(styles[estado]["text"])
        self.label_status.setAlignment(QtCore.Qt.AlignCenter)

        self.label_status.setStyleSheet(f"""
            QLabel {{
                background-color: {styles[estado]["bg"]};
                color: black;
                font-weight: bold;
                font-size: 38px;
                border-radius: 10px;
                padding: 8px;
            }}
        """)

    # -------------------------------
    # SERIAL EVENTS
    # -------------------------------
    def on_connected(self, msg):
        print(f"[OK] {msg}\n")
        self.start_button.setEnabled(True)

        # Estado listo para operar
        self.set_status_label("STANDBY")

        # Reset de estados por seguridad
        self.last_state = None
        self.fail_inicial_oculto = True

        # ? HABILITAR TORRETA AUTOMÁTICAMENTE
        if self.serial_thread:
            print("[AUTO] Enviando ENABLE al conectar\n")
            self.serial_thread.send_command("ENABLE")


    def on_error(self, err):
        print(f"[ERROR] {err}\n")
        self.set_status_label("NOT_CONNECTED")
        self.start_button.setEnabled(False)


    def reset_ciclo_unidad(self):
        self.unidad_confirmada = False
        self.serial_activo = None
        self.lineEdit.clear()
        self.lineEdit.setEnabled(True)
        self.start_button.setEnabled(True)

    def mostrar_alerta_supply_tank(self):
        print("[ALERTA] Flujo insuficiente en llenado: REVISAR SUPPLY TANK\n")

        # Ventana no bloqueante: la app sigue leyendo el serial mientras está abierta
        self.alerta_box = QMessageBox(self)
        self.alerta_box.setIcon(QMessageBox.Warning)
        self.alerta_box.setWindowTitle("Alerta de flujo")
        self.alerta_box.setText("REVISAR SUPPLY TANK")
        self.alerta_box.setInformativeText(
            "El flujo no se mantuvo en el mínimo requerido durante el llenado."
        )
        self.alerta_box.setWindowFlags(self.alerta_box.windowFlags() | Qt.WindowStaysOnTopHint)
        self.alerta_box.setModal(False)
        self.alerta_box.show()

    def on_serial_event(self, msg):
        msg = msg.strip()

        # ---- Datos del sensor de flujo: DATA,<voltaje>,<flujo> ----
        # Se imprimen solo durante drenado/llenado (EN_PROCESO)
        if msg.startswith("DATA,"):
            if self.last_state == "EN_PROCESO":
                partes = msg.split(",")
                try:
                    flujo = float(partes[2])
                    print(f"Flujo: {flujo:.3f}")
                except (IndexError, ValueError):
                    pass
            return

        if msg == "FLUJO_OK":
            print("[OK] Flujo de llenado dentro de especificación\n")
            return

        if msg == "ALERTA_SUPPLY_TANK":
            self.mostrar_alerta_supply_tank()
            return

        # FAIL inicial oculto
        if msg == "FAIL" and self.fail_inicial_oculto:
            self.fail_inicial_oculto = False
            self.last_state = "FAIL"
            return

        # FAIL después de PASS ? FIN DEL CICLO

        if msg == "FAIL" and self.last_state == "PASS":
            print("Proceso finalizado\n")

            self.set_status_label("FINALIZADO")

            QTimer.singleShot(
                150,
                lambda: self.serial_thread.send_command("DISABLE")
            )

            self.reset_ciclo_unidad()
            self.last_state = "FINALIZADO"
            return

        # FAIL real durante proceso
        if msg == "FAIL" and self.last_state == "EN_PROCESO":
            print("? FAIL\n")

            QTimer.singleShot(
                150,
                lambda: self.serial_thread.send_command("DISABLE")
            )

            self.reset_ciclo_unidad()
            self.last_state = "FAIL"
            self.set_status_label("FAIL")
            return

        # Estados normales
        if msg in ["STANDBY", "EN_PROCESO", "PASS"]:
            print(f"? {msg}\n")
            self.set_status_label(msg)

            if msg == "PASS":
                # ---- Enviar PASS a Flex Flow ----
                if self.serial_activo:
                    self.ffeti.send_results_to_FF(
                        serial_no=self.serial_activo,
                        ffeti_config_file= self.ffeti_config_file,
                        action="-PASS"
                    )
                    print(self.ffeti.last_raw_message)

                # ---- Forzar FAIL para cerrar ciclo ----
                QTimer.singleShot(
                    3000,
                    lambda: self.serial_thread.send_command("DISABLE")
                )

            self.last_state = msg
        
        # if msg == "ENABLED_OK":
        #     print("Dig Dug habilitado correctamente")

    # -------------------------------
    # START
    # -------------------------------
    def start_operation(self):
        if not self.serial_thread or not self.serial_thread.isRunning():
            print("[MSG] Seleccione puerto primero\n")
            return

        if self.unidad_confirmada:
            print("[BLOCK] Unidad ya validada, espere fin de ciclo\n")
            return

        serial_no = self.lineEdit.text().strip()
        if not serial_no:
            print("[BLOCK] Escanee una unidad válida\n")
            return

        print("START presionado\n")


        self.ffeti.send_results_to_FF(
            serial_no=serial_no,
            ffeti_config_file=self.ffeti_config_file,
            action="-INFO"
        )

        print(self.ffeti.last_raw_message)

        if self.ffeti.last_status == "OK":
            self.unidad_confirmada = True
            self.serial_activo = serial_no

            self.serial_thread.send_command("ENABLE")
            self.start_button.setEnabled(False)
            self.lineEdit.setEnabled(False)

            print(f"Unidad escaneada: {serial_no}\n")
            print("Dig Dug habilitado, esperando Drain & Fill\n")
        else:
            print("[BLOCK] Unidad no validada por FF\n")


# ======================================================
# MAIN
# ======================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = DigDugTester()
    win.showFullScreen()
    sys.exit(app.exec())