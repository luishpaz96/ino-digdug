import os
import sys
import time
import inspect
from configparser import ConfigParser
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
# Serial que inicia la prueba sin validar en Flex Flow (no distingue mayúsculas)
SERIAL_TEST = "test"

# ======================================================
# SENSOR DE FLUJO / REPORTE FINAL
# ======================================================
# El Arduino manda DATA,<voltaje>,<flujo> y es quien decide el criterio de flujo
# (FLUJO_MINIMO y TIEMPO_FLUJO_MS están en dig_dug_test.ino).
# Si llega solo DATA,<voltaje> (sketch viejo), la app convierte con el
# [ScaleFactor] flow_rate del .ini de la estación.
FLOW_RATE_DEFAULT = 0.0058252314   # flow_rate de la estación SCP
FLOW_OFFSET_V = 0.0057
FLOW_ESCALA_HZ = 100

FLUJO_RUIDO_LMIN = 0.05     # L/min. Flujos menores no se suman al volumen (ruido en drenado)
INTERVALO_MUESTRA_S = 1.0   # igual a INTERVALO_FLUJO_MS del Arduino
DT_MAX_MUESTRA_S = 5.0      # si entre dos muestras pasa más que esto, se cuenta INTERVALO_MUESTRA_S

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

    def __init__(self, parent=None):
        super().__init__(parent)
        try:
            self.setupUi(self)

            self.setFixedWidth(336)
            self.setFixedHeight(97)
            self.setWindowFlags(QtCore.Qt.WindowCloseButtonHint)

            if hasattr(self, 'buttonBox'):
                self.buttonBox.accepted.connect(self.emit_com)
            self.populate_ports()
            self.populate_station_name_comboBox()
        except Exception as e:
            print(f"[WARN] Error inicializando Settings: {e}\n")

    def populate_ports(self):
        try:
            if hasattr(self, 'comboBox'):
                self.comboBox.clear()
                ports = serial.tools.list_ports.comports()
                for p in ports:
                    self.comboBox.addItem(p.device)
        except Exception as e:
            print(f"[WARN] Error buscando puertos COM: {e}\n")

    def emit_com(self):
        try:
            if hasattr(self, 'comboBox'):
                self.com_selected.emit(self.comboBox.currentText())
            if hasattr(self, 'station_name_cb'):
                self.config_file_selected.emit(self.station_name_cb.currentText())
            self.close()
        except Exception as e:
            print(f"[WARN] Error al emitir configuracion: {e}\n")

    def populate_station_name_comboBox(self):
        try:
            if hasattr(self, 'station_name_cb'):
                self.station_name_cb.clear()
                folder_path = Path(FFETI_FOLDER)
                if folder_path.exists():
                    for file in folder_path.glob("*.ini"):
                        self.station_name_cb.addItem(file.name)
        except Exception as e:
            print(f"[WARN] Error cargando config files: {e}\n")


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

        # ---- SENSOR DE FLUJO ----
        self.flow_rate = FLOW_RATE_DEFAULT
        self.ultimo_flujo = 0.0
        self.t_ultima_muestra = None
        self.alerta_box = None
        self.reiniciar_flujo_ciclo()

        # ---- UI ----
        self.start_button.setEnabled(False)
        self.settings_button.clicked.connect(self.open_settings)
        self.start_button.clicked.connect(self.start_operation)

        # ---- Redirect stdout -> output_console ----
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
        try:
            self.settings = SettingsWindow(self)
            self.settings.com_selected.connect(self.open_serial)
            self.settings.config_file_selected.connect(self.get_config_file)
            self.settings.show()
        except Exception as e:
            print(f"[WARN] Error al abrir Settings: {e}\n")

    def closeEvent(self, event):
        print("\n[CLOSE] Cierre detectado -> FAIL seguro\n")

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
        if received:
            cfg_path = os.path.join(FFETI_FOLDER, received)
            if os.path.exists(cfg_path):
                try:
                    cfg = ConfigParser()
                    cfg.read(cfg_path)
                    if cfg.has_section("ScaleFactor") and cfg.has_option("ScaleFactor", "flow_rate"):
                        self.flow_rate = float(cfg.get("ScaleFactor", "flow_rate"))
                except Exception:
                    pass

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

    def enviar_a_flexflow(self, serial_no, action):
        # Limpiar el estado anterior: si la llamada falla no debe quedar un "OK" viejo
        self.ffeti.last_status = None
        try:
            sig = inspect.signature(self.ffeti.send_results_to_FF)
            if "ffeti_config_file" in sig.parameters:
                self.ffeti.send_results_to_FF(
                    serial_no=serial_no,
                    ffeti_config_file=self.ffeti_config_file,
                    action=action
                )
            else:
                self.ffeti.send_results_to_FF(
                    serial_no=serial_no,
                    action=action
                )
            if self.ffeti.last_raw_message:
                print(self.ffeti.last_raw_message)
        except Exception as e:
            print(f"[ERROR FF] {e}\n")

    # -------------------------------
    # FLUJO
    # -------------------------------
    def reiniciar_flujo_ciclo(self):
        self.lecturas_flujo = []
        self.volumen_ml = 0.0
        self.tiempo_con_flujo_s = 0.0
        self.criterio_flujo_ok = False

    def procesar_dato_flujo(self, msg):
        partes = msg.split(",")
        try:
            volts = float(partes[1])
            if len(partes) >= 3:
                flujo = float(partes[2])   # flujo calculado por el Arduino
            else:
                flujo = (volts - FLOW_OFFSET_V) * FLOW_ESCALA_HZ * self.flow_rate
        except (IndexError, ValueError):
            return   # línea incompleta o con ruido

        flujo = max(flujo, 0.0)

        # Tiempo real entre muestras, para calcular el volumen
        ahora = time.monotonic()
        dt = INTERVALO_MUESTRA_S
        if self.t_ultima_muestra is not None:
            dt = ahora - self.t_ultima_muestra
            if dt <= 0 or dt > DT_MAX_MUESTRA_S:
                dt = INTERVALO_MUESTRA_S
        self.t_ultima_muestra = ahora

        self.ultimo_flujo = round(flujo, 4)

        # Solo se registra durante drenado/llenado (EN_PROCESO)
        if self.last_state != "EN_PROCESO":
            return

        self.lecturas_flujo.append(self.ultimo_flujo)
        if flujo > FLUJO_RUIDO_LMIN:
            self.volumen_ml += flujo * dt * 1000.0 / 60.0   # L/min -> ml
            self.tiempo_con_flujo_s += dt

        print(f"[FLUJO] {self.ultimo_flujo:.3f} L/min | {self.volumen_ml:.0f} ml")

    def imprimir_reporte_flujo(self, resultado):
        if self.lecturas_flujo:
            promedio = sum(self.lecturas_flujo) / len(self.lecturas_flujo)
            min_f = min(self.lecturas_flujo)
            max_f = max(self.lecturas_flujo)
        else:
            promedio = min_f = max_f = self.ultimo_flujo
        criterio = "CUMPLE" if self.criterio_flujo_ok else "NO CUMPLE"

        print("========================================")
        print(f" REPORTE DE FLUJO ({resultado})")
        print(f"   Volumen llenado:  {self.volumen_ml:.0f} ml")
        print(f"   Tiempo con flujo: {self.tiempo_con_flujo_s:.0f} s")
        print(f"   Flujo Promedio:   {promedio:.3f} L/min (todo el proceso)")
        print(f"   Flujo Mínimo:     {min_f:.3f} L/min")
        print(f"   Flujo Máximo:     {max_f:.3f} L/min")
        print(f"   Total muestras:   {len(self.lecturas_flujo)}")
        print(f"   Criterio de flujo: {criterio}")
        print("========================================\n")

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
        try:
            msg = msg.strip()

            # ---- Sensor de flujo: DATA,<voltaje>,<flujo> ----
            if msg.startswith("DATA,"):
                self.procesar_dato_flujo(msg)
                return

            if msg == "FLUJO_OK":
                self.criterio_flujo_ok = True
                print("[OK] Criterio de flujo de llenado cumplido\n")
                return

            if msg == "ALERTA_SUPPLY_TANK":
                self.mostrar_alerta_supply_tank()
                return

            # FAIL inicial oculto
            if msg == "FAIL" and self.fail_inicial_oculto:
                self.fail_inicial_oculto = False
                self.last_state = "FAIL"
                return

            # FAIL después de PASS -> FIN DEL CICLO
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

            # FAIL real durante proceso (torreta roja o flujo insuficiente)
            if msg == "FAIL" and self.last_state == "EN_PROCESO":
                print(f"[FAIL] (Flujo al corte: {self.ultimo_flujo:.3f} L/min)\n")
                self.imprimir_reporte_flujo("FAIL")

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
                print(f"-> {msg}\n")
                self.set_status_label(msg)

                # Al iniciar EN_PROCESO, registrar muestras del ciclo
                if msg == "EN_PROCESO":
                    self.reiniciar_flujo_ciclo()

                # Al llegar a PASS, imprimir reporte completo
                if msg == "PASS":
                    self.imprimir_reporte_flujo("PASS")

                    # ---- Enviar PASS a Flex Flow ----
                    if self.serial_activo and self.es_serial_test(self.serial_activo):
                        print("[TEST] Serial de prueba: PASS no se reporta a Flex Flow\n")
                    elif self.serial_activo:
                        self.enviar_a_flexflow(self.serial_activo, action="-PASS")

                    # ---- Forzar FAIL para cerrar ciclo ----
                    QTimer.singleShot(
                        3000,
                        lambda: self.serial_thread.send_command("DISABLE")
                    )

                self.last_state = msg
        except Exception as e:
            print(f"[ERROR SERIAL EVENT] {e}\n")

    # -------------------------------
    # START
    # -------------------------------
    def start_operation(self):
        try:
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

            # ---- Modo prueba: serial "test" se salta la validación de Flex Flow ----
            if self.es_serial_test(serial_no):
                print("[TEST] Serial de prueba: se omite la validación de Flex Flow\n")
                self.habilitar_prueba(serial_no)
                return

            self.enviar_a_flexflow(serial_no, action="-INFO")

            if self.ffeti.last_status == "OK":
                self.habilitar_prueba(serial_no)
            else:
                print("[BLOCK] Unidad no validada por FF\n")
        except Exception as e:
            print(f"[ERROR START] {e}\n")

    def es_serial_test(self, serial_no):
        return serial_no.strip().lower() == SERIAL_TEST

    def habilitar_prueba(self, serial_no):
        self.unidad_confirmada = True
        self.serial_activo = serial_no

        self.serial_thread.send_command("ENABLE")
        self.start_button.setEnabled(False)
        self.lineEdit.setEnabled(False)

        print(f"Unidad escaneada: {serial_no}\n")
        print("Dig Dug habilitado, esperando Drain & Fill\n")


# ======================================================
# MAIN
# ======================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = DigDugTester()
    win.showFullScreen()
    sys.exit(app.exec())
