#!/usr/bin/env python3
"""
Conversión (read_type 'flow_rate_new_sensor'):
    frecuencia_Hz = (V - 0.0057) * 100
    flujo         = frecuencia_Hz * flow_rate      ([ScaleFactor] flow_rate del config.ini)

Funciona en Windows y en Ubuntu/Linux.

Instalación:
    Windows:  pip install pyserial
    Ubuntu:   sudo apt install python3-serial
              sudo usermod -aG dialout $USER     (una sola vez; luego cierra sesión)

Uso (sin --puerto busca el Arduino solo):
    python logger.py                                      # Windows
    python3 logger.py                                     # Ubuntu
    python logger.py --puerto COM3                        # puerto a mano en Windows
    python3 logger.py --puerto /dev/ttyACM0               # puerto a mano en Ubuntu
    python3 logger.py --config config.ini                 # toma flow_rate del config.ini
    python3 logger.py --factor 0.005830904                # factor a mano (BFT/IST)
    python3 logger.py --canal ch_101 --ruta logs/
    El factor por defecto es el de la estación SCP (0.0058252314).

Genera:
    sensor_flujo_log_<dd-mm-YYYY_HH-MM-SS>.csv   mismas columnas que el equipo de pruebas:
        timestamp, channel, type, raw data, converted data
    sensor_flujo_log_data_<dd-mm-YYYY_HH-MM-SS>.json  arreglo JSON (válido aunque cortes con Ctrl+C)
        con además fecha, hora y frecuencia_Hz.
    Al pasar de 10 MB empieza archivos nuevos, igual que el original.
"""
import argparse
import csv
import json
import os
import sys
import time
from configparser import ConfigParser
from datetime import datetime

import serial
import serial.tools.list_ports

# Constantes copiadas de data_logging.py
FLOW_RATE_NEW_SENSOR_OFFSET = 0.0057
FLOW_RATE_NEW_SENSOR_SCALE = 100
MAX_VALID_FREQ = 1000
MAX_CSV_SIZE = 10  # MB

# Factor Hz -> flujo del config.ini del equipo (estación SCP).
# Para BFT/IST el config usa 0.005830904 (pásalo con --factor).
FLOW_RATE_SCP = 0.0058252314

READ_TYPE = "flow_rate_new_sensor"
HEADER = ["timestamp", "channel", "type", "raw data", "converted data"]


def convertir(volts, flow_rate):
    """Igual que DataLoggingThread.read_data para 'flow_rate_new_sensor'."""
    frecuencia = (volts - FLOW_RATE_NEW_SENSOR_OFFSET) * FLOW_RATE_NEW_SENSOR_SCALE
    return frecuencia, frecuencia * flow_rate


def leer_factor(args):
    if args.factor is not None:
        return args.factor
    if args.config:
        cfg = ConfigParser()
        if not cfg.read(args.config):
            sys.exit(f"No se pudo leer {args.config}")
        return float(cfg.get("ScaleFactor", "flow_rate"))
    return FLOW_RATE_SCP   # [ScaleFactor] flow_rate del config.ini de la estación SCP


def _puntaje_arduino(p):
    """Mayor puntaje = más probable que sea el Arduino."""
    texto = f"{p.description} {p.manufacturer or ''} {p.product or ''}".lower()
    puntos = 0
    if p.vid is not None:                                   # es un dispositivo USB
        puntos += 2
    if any(k in texto for k in ("arduino", "ch340", "ch341", "cp210", "ftdi", "usb serial", "usb-serial")):
        puntos += 3
    if any(k in p.device for k in ("ttyACM", "ttyUSB", "usbmodem", "usbserial")):
        puntos += 2
    if "/dev/ttyS" in p.device or "bluetooth" in texto:    # puertos internos de Linux / BT
        puntos -= 5
    return puntos


def elegir_puerto(puerto):
    if puerto:
        return puerto
    puertos = sorted(serial.tools.list_ports.comports(), key=_puntaje_arduino, reverse=True)
    candidatos = [p for p in puertos if _puntaje_arduino(p) > 0]
    if not candidatos:
        sys.exit("No encontré el Arduino. Revisa el cable USB o indica el puerto con --puerto\n"
                 "(Windows: COM3, COM4...   Ubuntu: /dev/ttyACM0 o /dev/ttyUSB0).")
    print("Puertos USB encontrados:")
    for p in candidatos:
        print(f"  {p.device}  {p.description}")
    print(f"Usando {candidatos[0].device}\n")
    return candidatos[0].device


def abrir_serial(puerto, baudios):
    try:
        return serial.Serial(puerto, baudios, timeout=2)
    except serial.SerialException as exc:
        msg = str(exc)
        if sys.platform.startswith("linux") and ("Permission denied" in msg or "Errno 13" in msg):
            sys.exit(f"Sin permiso para abrir {puerto}. En Ubuntu ejecuta una vez:\n"
                     f"    sudo usermod -aG dialout $USER\n"
                     f"y cierra sesión (o reinicia) para que aplique.")
        if "busy" in msg.lower() or "Errno 16" in msg or "Access is denied" in msg:
            sys.exit(f"{puerto} está ocupado. Cierra el Monitor Serie del IDE de Arduino "
                     f"u otro programa que lo esté usando.")
        sys.exit(f"No se pudo abrir {puerto}: {msg}")


class Registro:
    """CSV con el formato del equipo + JSON paralelo, con rotación por tamaño."""

    def __init__(self, ruta):
        self.ruta = ruta
        os.makedirs(ruta or ".", exist_ok=True)
        self._nuevos_archivos()

    def _nuevos_archivos(self):
        base = os.path.join(self.ruta, f'sensor_flujo_log_{datetime.now().strftime("%d-%m-%Y_%H-%M-%S")}')
        self.csv_path, self.json_path = base + ".csv", base + ".json"
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(HEADER)
        with open(self.json_path, "wb") as f:
            f.write(b"[\n]")
        self.json_vacio = True
        print(f"Guardando en {self.csv_path} y {self.json_path}")

    def escribir(self, fila_csv, reg_json):
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(fila_csv)
        datos = json.dumps(reg_json, ensure_ascii=False).encode("utf-8")
        with open(self.json_path, "r+b") as f:
            f.seek(-2, os.SEEK_END)            # antes de "\n]"
            f.write((b"\n" if self.json_vacio else b",\n") + b"  " + datos + b"\n]")
            f.truncate()
        self.json_vacio = False
        if os.path.getsize(self.csv_path) > MAX_CSV_SIZE * 1024 * 1024:
            self._nuevos_archivos()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--puerto", help="COM3, /dev/ttyUSB0, /dev/ttyACM0...")
    ap.add_argument("--baudios", type=int, default=9600)
    ap.add_argument("--config", help="config.ini del equipo (usa [ScaleFactor] flow_rate)")
    ap.add_argument("--factor", type=float, help="flow_rate a mano (gana sobre --config)")
    ap.add_argument("--canal", default="arduino_A0", help="nombre del canal en la columna 'channel'")
    ap.add_argument("--ruta", default="", help="carpeta donde guardar los logs")
    args = ap.parse_args()

    flow_rate = leer_factor(args)
    print(f"flow_rate = {flow_rate}")

    ser = abrir_serial(elegir_puerto(args.puerto), args.baudios)
    time.sleep(2)                      # el Arduino se reinicia al abrir el puerto
    ser.reset_input_buffer()
    log = Registro(args.ruta)
    print("(Ctrl+C para salir)\n")

    try:
        while True:
            linea = ser.readline().decode("utf-8", errors="ignore").strip()
            if not linea.startswith("DATA,"):
                continue
            try:
                volts = float(linea.split(",")[1])
            except (IndexError, ValueError):
                continue               # línea incompleta o con ruido

            frecuencia, flujo = convertir(volts, flow_rate)
            flujo = round(flujo, 4)
            ahora = datetime.now()
            timestamp = ahora.strftime("%d/%m/%Y %H:%M:%S")   # mismo formato del equipo

            log.escribir(
                [timestamp, args.canal, READ_TYPE, volts, flujo],
                {
                    "timestamp": timestamp,
                    "fecha": ahora.strftime("%Y-%m-%d"),
                    "hora": ahora.strftime("%H:%M:%S"),
                    "channel": args.canal,
                    "type": READ_TYPE,
                    "raw_data_V": volts,
                    "frecuencia_Hz": round(frecuencia, 2),
                    "converted_data": flujo,
                },
            )
            aviso = "  <-- fuera de rango" if frecuencia > MAX_VALID_FREQ else ""
            print(f"{timestamp}  {volts:.4f} V  {frecuencia:7.2f} Hz  {flujo:.3f}{aviso}")
    except KeyboardInterrupt:
        print("\nDetenido.")
    except serial.SerialException as exc:
        print(f"\nSe perdió la conexión con el Arduino ({exc}). Los datos guardados están completos.")
    finally:
        ser.close()


if __name__ == "__main__":
    main()
