import os
import sys
import time
import inspect
import traceback
from datetime import datetime
from configparser import ConfigParser
import serial.tools.list_ports
from PyQt5 import QtCore
from PyQt5.QtCore import pyqtSignal, QTimer, Qt
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox
from PyQt5.QtGui import QTextCursor, QTextCharFormat, QTextBlockFormat, QColor, QFont
from pathlib import Path

from worker_serial import SerialReaderThread
from dig_dug_ui import Ui_Form as digdug_ui
from settings_window import Ui_Form as settings_ui
from ffeticlient import FFEtiClient

SERIAL_DUMMY = "FLG2545-00408"
FFETI_FOLDER = r"C:\ffeti"
# Serial que inicia la prueba sin validar en Flex Flow y sin condición de volumen
# (no distingue mayúsculas). El botón CICLO MANUAL hace lo mismo.
SERIAL_TEST = "test"
SERIAL_MANUAL = "CICLO MANUAL"   # lo que se muestra en el SN durante un ciclo manual

# ======================================================
# SENSOR DE FLUJO / REPORTE FINAL
# ======================================================
# El Arduino (dig_dug_test2.ino) manda DATA,<voltaje>,<flujo>,<volumen_ml> y es
# quien decide el PASS por volumen (VOLUMEN_MINIMO_ML). Solo cuenta el volumen
# del llenado: después de TIEMPO_DRENADO_MS avisa INICIO_LLENADO. El reporte
# muestra ese mismo volumen.
# Con un sketch que solo manda el voltaje, la app convierte con el
# [ScaleFactor] flow_rate del .ini de la estación y calcula el volumen.
FLOW_RATE_DEFAULT = 0.0058252314   # flow_rate de la estación SCP
FLOW_OFFSET_V = 0.0057
FLOW_ESCALA_HZ = 100

FLUJO_RUIDO_LMIN = 0.35     # L/min. Solo si la app calcula el volumen: lecturas menores son ruido y no suman
INTERVALO_MUESTRA_S = 1.0   # igual a INTERVALO_FLUJO_MS del Arduino
DT_MAX_MUESTRA_S = 5.0      # si entre dos muestras pasa más que esto, se cuenta INTERVALO_MUESTRA_S

# ======================================================
# COLORES DEL OUTPUT MONITOR
# ======================================================
COLOR_NORMAL = "#000000"   # negro: mensajes normales
COLOR_PASS   = "#1E8E3E"   # verde: PASS y resultados buenos
COLOR_FAIL   = "#D93025"   # rojo: FAIL, alertas y errores
COLOR_TEST   = "#E37400"   # naranja: serial de prueba (no se registra en Flex Flow)
COLOR_INFO   = "#1A73E8"   # azul: avisos del proceso

# ======================================================
# Redirect stdout to QTextEdit with auto-scroll (y colores)
# ======================================================
class QTextEditStream:
    def __init__(self, text_edit):
        self.text_edit = text_edit

    def write(self, message):
        self.escribir(message, COLOR_NORMAL)

    def escribir(self, message, color, negrita=False):
        # Cada mensaje lleva su propio formato: el color no se pasa a la línea siguiente
        if message.strip():
            doc = self.text_edit.document()
            cursor = QTextCursor(doc)
            cursor.movePosition(QTextCursor.End)
            formato = QTextCharFormat()
            formato.setForeground(QColor(color))
            formato.setFontWeight(QFont.Bold if negrita else QFont.Normal)
            if not doc.isEmpty():
                cursor.insertBlock(QTextBlockFormat(), formato)
            cursor.insertText(message, formato)
            self.text_edit.verticalScrollBar().setValue(
                self.text_edit.verticalScrollBar().maximum()
            )

    def flush(self):
        pass


# ======================================================
# ERRORES: se muestran en rojo y se guardan; la app no se cierra
# ======================================================
LOG_ERRORES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "errores_dig_dug.log")

def log_error(texto):
    escribir = getattr(sys.stdout, "escribir", None)
    if escribir:
        escribir(texto, COLOR_FAIL, True)
    else:
        print(texto)

def registrar_excepcion(tipo, valor, tb):
    # Sin esto, PyQt5 cierra toda la app ante cualquier error no atrapado
    detalle = "".join(traceback.format_exception(tipo, valor, tb))
    try:
        with open(LOG_ERRORES, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}]\n{detalle}")
    except Exception:
        pass
    try:
        log_error(f"[ERROR] {tipo.__name__}: {valor} (detalle en errores_dig_dug.log)\n")
    except Exception:
        sys.__stderr__.write(detalle)


# ======================================================
# SETTINGS WINDOW (solo selecciona COM)
# ======================================================
class SettingsWindow(QDialog, settings_ui):

    com_selected = pyqtSignal(str)
    config_file_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        # Protegido como en CHIDO: si settings_window.py no trae algún control
        # (por ejemplo el selector de config), la ventana abre igual y la app no se cierra
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
            log_error(f"[WARN] Error inicializando Settings: {e}\n")

    def populate_ports(self):
        try:
            if hasattr(self, 'comboBox'):
                self.comboBox.clear()
                ports = serial.tools.list_ports.comports()
                for p in ports:
                    self.comboBox.addItem(p.device)
        except Exception as e:
            log_error(f"[WARN] Error buscando puertos COM: {e}\n")

    def emit_com(self):
        try:
            if hasattr(self, 'comboBox'):
                self.com_selected.emit(self.comboBox.currentText())
            if hasattr(self, 'station_name_cb'):
                self.config_file_selected.emit(self.station_name_cb.currentText())
            else:
                log_error("[WARN] Settings sin selector de config file: Flex Flow puede fallar\n")
            self.close()
        except Exception as e:
            log_error(f"[WARN] Error al emitir configuracion: {e}\n")

    def populate_station_name_comboBox(self):
        try:
            if hasattr(self, 'station_name_cb'):
                self.station_name_cb.clear()
                folder_path = Path(FFETI_FOLDER)
                if folder_path.exists():
                    for file in folder_path.glob("*.ini"):
                        self.station_name_cb.addItem(file.name)
        except Exception as e:
            log_error(f"[WARN] Error cargando config files: {e}\n")


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
        self.manual_button.setEnabled(False)
        self.settings_button.clicked.connect(self.open_settings)
        self.start_button.clicked.connect(self.start_operation)
        self.manual_button.clicked.connect(self.start_manual)

        # ---- Redirect stdout ? output_console ----
        self.consola = QTextEditStream(self.output_console)
        sys.stdout = self.consola

        # ---- Estado de proceso ----
        self.last_state = None
        self.fail_inicial_oculto = True

        # ---- Estado de unidad (TRAZABILIDAD) ----
        self.unidad_confirmada = False
        self.serial_activo = None
        self.modo_test = False      # ciclo manual o serial "test": sin Flex Flow ni condición de volumen
        self.etiqueta_test = ""
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
            self.settings = SettingsWindow()
            self.settings.com_selected.connect(self.open_serial)
            self.settings.config_file_selected.connect(self.get_config_file)
            self.settings.show()
        except Exception as e:
            self.log(f"[ERROR SETTINGS] {e}\n", COLOR_FAIL, True)

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
        self.manual_button.setEnabled(True)

        # Estado listo para operar
        self.set_status_label("STANDBY")

        # Reset de estados por seguridad
        self.last_state = None
        self.fail_inicial_oculto = True

        # ? HABILITAR TORRETA AUTOMÁTICAMENTE
        if self.serial_thread:
            print("[AUTO] Enviando ENABLE al conectar\n")
            self.serial_thread.send_command("ENABLE")

        # Cursor listo en el SN para escanear
        self.enfocar_sn()


    def on_error(self, err):
        self.log(f"[ERROR] {err}\n", COLOR_FAIL, True)
        self.set_status_label("NOT_CONNECTED")
        self.start_button.setEnabled(False)
        self.manual_button.setEnabled(False)


    def reset_ciclo_unidad(self):
        self.unidad_confirmada = False
        self.serial_activo = None
        self.modo_test = False
        self.etiqueta_test = ""
        self.lineEdit.clear()
        self.lineEdit.setEnabled(True)
        self.start_button.setEnabled(True)
        self.manual_button.setEnabled(True)
        # Cursor de regreso en el SN: la siguiente unidad se escanea sin dar clic
        self.enfocar_sn()

    def enfocar_sn(self):
        self.activateWindow()       # por si la alerta de Supply tank tenía el foco
        self.lineEdit.setFocus()
        self.lineEdit.selectAll()   # un serial rechazado se reemplaza con el siguiente escaneo

    def log(self, texto, color=COLOR_NORMAL, negrita=False):
        """Escribe en el Output Monitor con color."""
        self.consola.escribir(texto, color, negrita)

    def color_pass(self):
        # PASS de un ciclo manual o serial "test" en naranja: no es una unidad real
        if self.modo_test:
            return COLOR_TEST
        return COLOR_PASS

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
                if self.ffeti.last_status in ("OK", "PASS"):
                    color = COLOR_PASS
                elif self.ffeti.last_status in ("ERROR", "FAIL"):
                    color = COLOR_FAIL
                else:
                    color = COLOR_NORMAL
                self.log(self.ffeti.last_raw_message, color)
        except Exception as e:
            self.log(f"[ERROR FF] {e}\n", COLOR_FAIL, True)

    # -------------------------------
    # FLUJO
    # -------------------------------
    def reiniciar_flujo_ciclo(self):
        self.lecturas_flujo = []
        self.volumen_ml = 0.0
        self.tiempo_con_flujo_s = 0.0
        self.volumen_ok = False

    def procesar_dato_flujo(self, msg):
        partes = msg.split(",")
        try:
            volts = float(partes[1])
            if len(partes) >= 3:
                flujo = float(partes[2])   # flujo calculado por el Arduino
            else:
                flujo = (volts - FLOW_OFFSET_V) * FLOW_ESCALA_HZ * self.flow_rate
            volumen_arduino = float(partes[3]) if len(partes) >= 4 else None
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
        if volumen_arduino is not None:
            # El Arduino decide el PASS con este volumen: se muestra el mismo
            if volumen_arduino > self.volumen_ml:
                self.tiempo_con_flujo_s += dt
            self.volumen_ml = volumen_arduino
        elif flujo >= FLUJO_RUIDO_LMIN:
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

        if self.volumen_ok:
            criterio = "CUMPLE"
        elif self.modo_test:
            criterio = f"NO CUMPLE (omitido: {self.etiqueta_test.lower()})"
        else:
            criterio = "NO CUMPLE"

        color = self.color_pass() if resultado == "PASS" else COLOR_FAIL
        self.log("========================================", color)
        self.log(f" REPORTE DE FLUJO ({resultado})", color, True)
        self.log(f"   Volumen llenado:  {self.volumen_ml:.0f} ml", color, True)
        self.log(f"   Tiempo de llenado: {self.tiempo_con_flujo_s:.0f} s", color)
        self.log(f"   Flujo Promedio:   {promedio:.3f} L/min (todo el proceso)", color)
        self.log(f"   Flujo Mínimo:     {min_f:.3f} L/min", color)
        self.log(f"   Flujo Máximo:     {max_f:.3f} L/min", color)
        self.log(f"   Total muestras:   {len(self.lecturas_flujo)}", color)
        self.log(f"   Volumen mínimo:   {criterio}", color, True)
        self.log("========================================\n", color)

    def mostrar_alerta_supply_tank(self):
        self.log(f"[ALERTA] Volumen insuficiente ({self.volumen_ml:.0f} ml): REVISAR SUPPLY TANK\n",
                 COLOR_FAIL, True)

        # Ventana no bloqueante: la app sigue leyendo el serial mientras está abierta
        self.cerrar_alerta()
        self.alerta_box = QMessageBox(self)
        self.alerta_box.setIcon(QMessageBox.Warning)
        self.alerta_box.setWindowTitle("Alerta de llenado")
        self.alerta_box.setText("REVISAR SUPPLY TANK")
        self.alerta_box.setInformativeText(
            f"La unidad no alcanzó el volumen mínimo de llenado "
            f"(se llenaron {self.volumen_ml:.0f} ml)."
        )
        self.alerta_box.setWindowFlags(self.alerta_box.windowFlags() | Qt.WindowStaysOnTopHint)
        self.alerta_box.setModal(False)
        self.alerta_box.show()

    def cerrar_alerta(self):
        # Se cierra sola al iniciar la siguiente prueba, si nadie la cerró
        if self.alerta_box is not None:
            self.alerta_box.close()
            self.alerta_box = None

    # -------------------------------
    # EVENTOS DEL ARDUINO
    # -------------------------------
    def on_serial_event(self, msg):
        # Un error aquí no debe cerrar la app
        try:
            self.procesar_evento_serial(msg)
        except Exception as e:
            self.log(f"[ERROR SERIAL EVENT] {e}\n", COLOR_FAIL, True)

    def procesar_evento_serial(self, msg):
        msg = msg.strip()

        # ---- Sensor de flujo: DATA,<voltaje>,<flujo>,<volumen_ml> ----
        if msg.startswith("DATA,"):
            self.procesar_dato_flujo(msg)
            return

        if msg == "INICIO_LLENADO":
            self.log("[LLENADO] Terminó el drenado: inicia el conteo de volumen\n", COLOR_INFO, True)
            return

        if msg == "VOLUMEN_OK":
            self.volumen_ok = True
            self.log(f"[OK] Volumen mínimo alcanzado ({self.volumen_ml:.0f} ml)\n", COLOR_PASS, True)
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
            self.log(f"[FAIL] (Flujo al corte: {self.ultimo_flujo:.3f} L/min)\n", COLOR_FAIL, True)
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
            if msg == "PASS":
                self.log(f"-> {msg}\n", self.color_pass(), True)
            else:
                print(f"-> {msg}\n")
            self.set_status_label(msg)

            # Al iniciar EN_PROCESO, registrar muestras del ciclo
            if msg == "EN_PROCESO":
                self.reiniciar_flujo_ciclo()

            if msg == "PASS":
                # ---- Reporte de flujo y volumen ----
                self.imprimir_reporte_flujo("PASS")

                # ---- Enviar PASS a Flex Flow ----
                if self.serial_activo and self.modo_test:
                    self.log(f"[TEST] {self.etiqueta_test}: PASS no se reporta a Flex Flow\n", COLOR_TEST, True)
                elif self.serial_activo:
                    self.enviar_a_flexflow(self.serial_activo, action="-PASS")

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
        # Un error aquí no debe cerrar la app
        try:
            self.iniciar_unidad()
        except Exception as e:
            self.log(f"[ERROR START] {e}\n", COLOR_FAIL, True)

    def start_manual(self):
        # Botón CICLO MANUAL: lo mismo que escanear el serial "test"
        try:
            self.iniciar_unidad(manual=True)
        except Exception as e:
            self.log(f"[ERROR CICLO MANUAL] {e}\n", COLOR_FAIL, True)

    def iniciar_unidad(self, manual=False):
        if not self.serial_thread or not self.serial_thread.isRunning():
            print("[MSG] Seleccione puerto primero\n")
            return

        if self.unidad_confirmada:
            print("[BLOCK] Unidad ya validada, espere fin de ciclo\n")
            return

        # ---- Ciclo manual: sin validación de Flex Flow ni condición de volumen ----
        if manual:
            print("CICLO MANUAL presionado\n")
            self.lineEdit.setText(SERIAL_MANUAL)
            self.log("[TEST] Ciclo manual: se omite la validación de Flex Flow\n", COLOR_TEST, True)
            self.habilitar_prueba(SERIAL_MANUAL, "Ciclo manual")
            return

        serial_no = self.lineEdit.text().strip()
        if not serial_no:
            print("[BLOCK] Escanee una unidad válida\n")
            self.enfocar_sn()
            return

        print("START presionado\n")

        # ---- Serial de prueba: sin validación de Flex Flow ----
        if self.es_serial_test(serial_no):
            self.log("[TEST] Serial de prueba: se omite la validación de Flex Flow\n", COLOR_TEST, True)
            self.habilitar_prueba(serial_no, "Serial de prueba")
            return

        self.enviar_a_flexflow(serial_no, action="-INFO")

        if self.ffeti.last_status == "OK":
            self.habilitar_prueba(serial_no)
        else:
            self.log("[BLOCK] Unidad no validada por FF\n", COLOR_FAIL, True)
            self.enfocar_sn()

    def es_serial_test(self, serial_no):
        return serial_no.strip().lower() == SERIAL_TEST

    def habilitar_prueba(self, serial_no, etiqueta_test=None):
        # Con etiqueta_test ("Ciclo manual" o "Serial de prueba"): sin Flex Flow ni condición de volumen
        self.unidad_confirmada = True
        self.serial_activo = serial_no
        self.modo_test = etiqueta_test is not None
        self.etiqueta_test = etiqueta_test or ""
        self.cerrar_alerta()   # si quedó abierta la alerta de la unidad anterior

        self.serial_thread.send_command("ENABLE")
        if self.modo_test:
            # El Arduino omite la condición de volumen: se puede probar sin flujo
            self.serial_thread.send_command("MODO_TEST")
            self.log(f"[TEST] {self.etiqueta_test}: sin condición de volumen, la prueba puede correr sin flujo\n",
                     COLOR_TEST, True)
        self.start_button.setEnabled(False)
        self.manual_button.setEnabled(False)
        self.lineEdit.setEnabled(False)

        if serial_no != SERIAL_MANUAL:
            print(f"Unidad escaneada: {serial_no}\n")
        print("Dig Dug habilitado, esperando Drain & Fill\n")


# ======================================================
# MAIN
# ======================================================
if __name__ == "__main__":
    sys.excepthook = registrar_excepcion
    app = QApplication(sys.argv)
    win = DigDugTester()
    win.showFullScreen()
    sys.exit(app.exec())