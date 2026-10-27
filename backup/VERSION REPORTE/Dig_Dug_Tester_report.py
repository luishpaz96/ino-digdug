import os
import sys
import serial.tools.list_ports
from PyQt5 import QtCore
from PyQt5.QtCore import pyqtSignal, QTimer, Qt
from PyQt5.QtWidgets import QApplication, QDialog
from pathlib import Path

from worker_serial import SerialReaderThread
from dig_dug_ui import Ui_Form as digdug_ui
from settings_window import Ui_Form as settings_ui
from ffeticlient import FFEtiClient

SERIAL_DUMMY = "FLG2545-00408"
FFETI_FOLDER = r"C:\ffeti"

# ======================================================
# UMBRALES DE DOBLE VALIDACIÓN DE FLUJO
# ======================================================
FLUJO_PICO_MINIMO_DRAIN = 2.00     # L/min (Regla 1: No tapamiento / libre desahogo)
SEGUNDOS_PICO_MINIMO    = 4        # Muestras mínimas en pico de purga
VOLUMEN_MINIMO_FILL_ML  = 350.0    # mL (Regla 2: Llenado real de la unidad >= 350 mL)
VOLUMEN_MINIMO_TOTAL_ML = 800.0    # mL (Volumen total mínimo del ciclo)
FLUJO_MAXIMO_SELLADO    = 0.20     # L/min (Regla 3: Corte y sellado sin fuga al final)

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
        self.flow_rate = 0.0058252314
        self.lecturas_flujo = []
        self.ultimo_flujo = 0.0

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
                    from configparser import ConfigParser
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
        try:
            import inspect
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

    def validar_perfil_flujo(self):
        """
        Evalúa las 3 reglas de doble validación:
        1. Draining (No tapón): Pico >= 2.0 L/min al menos 4s
        2. Filling (Llenado completo): Volumen inyectado >= 350 mL (o ciclo total >= 800 mL)
        3. Sellado: Flujo al final del ciclo <= 0.20 L/min
        """
        if not self.lecturas_flujo:
            return False, "Sin lecturas de flujo registradas en el ciclo"

        muestras = [max(0.0, f) for f in self.lecturas_flujo]
        total_muestras = len(muestras)

        # Regla 1: Draining / No obstrucción
        pico_max = max(muestras)
        muestras_pico = sum(1 for f in muestras if f >= FLUJO_PICO_MINIMO_DRAIN)
        draining_ok = (pico_max >= FLUJO_PICO_MINIMO_DRAIN and muestras_pico >= SEGUNDOS_PICO_MINIMO)

        # Regla 2: Llenado Real (Post-Draining)
        # Encontrar el último índice de la fase inicial de draining (flujo >= 2.0 L/min)
        idx_picos = [idx for idx, f in enumerate(muestras) if f >= FLUJO_PICO_MINIMO_DRAIN]
        last_drain_idx = max(idx_picos) if idx_picos else 0

        # Muestras de la fase de llenado (posteriores al draining, flujo activo >= 0.15 L/min)
        post_drain = muestras[last_drain_idx + 1:]
        muestras_fill = [f for f in post_drain if f >= 0.15]

        volumen_fill_ml = sum(muestras_fill) * (1000.0 / 60.0)
        flujo_prom_fill = sum(muestras_fill) / len(muestras_fill) if muestras_fill else 0.0

        # Llenado ESTRICTO: la cold plate debe recibir >= 350 mL reales
        llenado_ok = (volumen_fill_ml >= VOLUMEN_MINIMO_FILL_ML)

        # Diagnóstico de tanque sin líquido o nivel bajo
        tanque_sin_liquido = (not llenado_ok) or (flujo_prom_fill < 0.90 and len(muestras_fill) > 3)

        # Regla 3: Sellado final (promedio de las últimas 5 muestras)
        ultimas = muestras[-5:] if total_muestras >= 5 else muestras
        flujo_final = sum(ultimas) / len(ultimas)
        sellado_ok = (flujo_final <= FLUJO_MAXIMO_SELLADO)

        pasa_todo = draining_ok and llenado_ok and sellado_ok

        color_borde = "#008800" if pasa_todo else "#cc0000"
        color_titulo = "#008800" if pasa_todo else "#cc0000"
        estado_hdr = "PASS" if pasa_todo else "FAIL"

        draining_tag = '<b style="color: #008800;">[OK]</b>' if draining_ok else '<b style="color: #cc0000;">[FALLO - OBSTRUCCIÓN]</b>'

        if llenado_ok:
            filling_tag = f'<b style="color: #008800;">[OK] ({volumen_fill_ml:.0f} mL)</b>'
            diagnostico_tanque = '<b style="color: #008800;">[OK - Flujo Normal]</b>'
        else:
            filling_tag = f'<b style="color: #cc0000;">[FALLO - INCOMPLETO: {volumen_fill_ml:.0f} mL]</b>'
            diagnostico_tanque = '<b style="color: #cc0000;">[ALERTA: TANQUE SIN LÍQUIDO O NIVEL BAJO]</b>'

        sellado_tag = '<b style="color: #008800;">[OK]</b>' if sellado_ok else '<b style="color: #cc0000;">[FALLO - FUGA]</b>'

        if pasa_todo:
            res_line = '<b style="font-size: 14pt; color: #008800;">RESULTADO: ✅ PASS - LLENADO COMPLETO Y LIBRE DE OBSTRUCCIÓN</b>'
        else:
            fallas = []
            if not draining_ok:
                fallas.append("Pico insuficiente / Obstrucción")
            if not llenado_ok:
                if tanque_sin_liquido:
                    fallas.append(f"Tanque sin líquido o nivel bajo ({volumen_fill_ml:.0f} mL inyectados de {VOLUMEN_MINIMO_FILL_ML:.0f} mL requeridos)")
                else:
                    fallas.append(f"Llenado incompleto ({volumen_fill_ml:.0f} mL < {VOLUMEN_MINIMO_FILL_ML:.0f} mL)")
            if not sellado_ok:
                fallas.append("Fuga o válvula abierta al final")
            fallas_str = "<br>&nbsp;&nbsp;&nbsp;&nbsp;• " + "<br>&nbsp;&nbsp;&nbsp;&nbsp;• ".join(fallas)
            res_line = f'<b style="font-size: 14pt; color: #cc0000;">RESULTADO: ❌ FAIL - UNIDAD RECHAZADA POR FLUJO:{fallas_str}</b>'

        reporte = (
            f'<div style="font-family: Consolas, \'Courier New\', monospace; font-size: 13pt; color: #111111; '
            f'background-color: #ffffff; border: 3px solid {color_borde}; padding: 12px; margin: 8px 0;">\n'
            f'<b style="color: {color_titulo}; font-size: 15pt;">==================================================<br>\n'
            f'&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;VALIDACIÓN DE FLUJO ({estado_hdr})<br>\n'
            f'==================================================</b><br>\n'
            f'&nbsp;&nbsp;1. Draining (Pico):&nbsp;&nbsp;&nbsp;&nbsp;<b>{pico_max:.3f} L/min</b> ({muestras_pico}s) {draining_tag} &gt;= {FLUJO_PICO_MINIMO_DRAIN:.2f}<br>\n'
            f'&nbsp;&nbsp;2. Llenado (Filling):&nbsp;&nbsp;<b>{volumen_fill_ml:.0f} mL</b> {filling_tag} &gt;= {VOLUMEN_MINIMO_FILL_ML:.0f} mL<br>\n'
            f'&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Flujo Prom. Llenado:<b>{flujo_prom_fill:.3f} L/min</b> {diagnostico_tanque}<br>\n'
            f'&nbsp;&nbsp;3. Sellado Final:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<b>{flujo_final:.3f} L/min</b> {sellado_tag} &lt;= {FLUJO_MAXIMO_SELLADO:.2f}<br>\n'
            f'&nbsp;&nbsp;Total Duración:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<b>{total_muestras} seg</b><br>\n'
            f'--------------------------------------------------<br>\n'
            f'{res_line}<br>\n'
            f'==================================================\n'
            f'</div>\n'
        )

        return pasa_todo, reporte

    def on_serial_event(self, msg):
        try:
            msg = msg.strip()

            # Lectura de sensor de flujo
            if msg.startswith("DATA,"):
                try:
                    volts = float(msg.split(",")[1])
                    frecuencia = (volts - 0.0057) * 100
                    flujo = frecuencia * self.flow_rate
                    self.ultimo_flujo = round(flujo, 4)
                    if self.last_state == "EN_PROCESO":
                        self.lecturas_flujo.append(self.ultimo_flujo)
                        print(f"[FLUJO] {self.ultimo_flujo:.3f} L/min\n")
                except Exception:
                    pass
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

            # FAIL real durante proceso
            if msg == "FAIL" and self.last_state == "EN_PROCESO":
                print(
                    f'<div style="font-family: Consolas, monospace; font-size: 13pt; color: #cc0000; font-weight: bold; '
                    f'background-color: #ffffff; border: 2px solid #cc0000; padding: 8px; margin: 6px 0;">'
                    f'[FAIL] CORTE EN PROCESO (Flujo al momento del corte: {self.ultimo_flujo:.3f} L/min)</div>\n'
                )

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
                    self.lecturas_flujo = []

                # Al llegar a PASS, evaluar doble validación de flujo
                if msg == "PASS":
                    flujo_valido, reporte = self.validar_perfil_flujo()
                    print(reporte)

                    if flujo_valido:
                        # ---- Enviar PASS a Flex Flow ----
                        if self.serial_activo:
                            self.enviar_a_flexflow(self.serial_activo, action="-PASS")
                    else:
                        print("[RECHAZO] Torreta en PASS pero flujo NO cumplió reglas de llenado.\n")
                        self.set_status_label("FAIL")
                        if self.serial_activo:
                            self.enviar_a_flexflow(self.serial_activo, action="-FAIL")

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

            self.enviar_a_flexflow(serial_no, action="-INFO")

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
        except Exception as e:
            print(f"[ERROR START] {e}\n")


# ======================================================
# MAIN
# ======================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = DigDugTester()
    win.showFullScreen()
    sys.exit(app.exec())