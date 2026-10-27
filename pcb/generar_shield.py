#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shield Dig Dug F/V con las medidas del Arduino Uno R3.

Pila de tarjetas:  Arduino Uno (abajo)  ->  shield de relevadores 24V (en medio)  ->  este shield (arriba).

- Headers apilables (stacking) en las posiciones del Uno R3: hembra arriba (para otro shield o
  jumpers) y pines largos abajo que entran en los headers de la tarjeta de abajo.
- El módulo convertidor F/V (LM331) entra en dos headers hembra 1x4 a 25.4 mm (10 x 2.54).
- La salida V del módulo va directo al pin A0. La GND del módulo es la GND del Arduino.
- Bornera de 3 polos para el sensor (F, 24V, GND).
- Bornera de 2 polos de alimentación (24V, GND), encima de la bornera Vin del shield de
  relevadores para puentearlas. Protección de la entrada de 24V con DOS opciones en paralelo
  (se instala solo una): portafusible 5x20 mm (F1) o fusible reseteable PTC radial (F2).
  Lugar opcional para un TVS (D1, P6KE33A) de 24V a GND después de la protección.
- Los 24V NO tocan ningún pin del Arduino: solo van al módulo y al sensor. GND es común.
- Cara de abajo: plano de tierra.

Coordenadas en mm, vista desde arriba con el USB a la izquierda: x hacia la derecha, y hacia
abajo, origen en la esquina superior izquierda. Header digital arriba (y = 2.54) y power/analog
abajo (y = 50.8). La geometría del Uno sale de la huella de KiCad
Module:Arduino_UNO_R3_WithMountingHoles (que viene vista por debajo; aquí está volteada).

Salida (carpeta salida_shield/):
    DigDug_Shield_FV.kicad_pcb          proyecto KiCad 7 o más nuevo (editable)
    gerbers/                            Gerbers RS-274X + drill Excellon
    DigDug_Shield_FV_gerbers.zip        zip para JLCPCB / PCBWay

Para regenerar:   python3 generar_shield.py
"""
import math
import os
import uuid
import zipfile
import datetime

NOMBRE = "DigDug_Shield_FV"
REV = "3"
SALIDA = "salida_shield"

# ======================= PARÁMETROS (mm) =======================
PASO = 2.54
S_FILAS = 25.4          # filas del módulo F/V (10 x 2.54, igual que en el header del Arduino de 5V a A5)
MOD_ANCHO, MOD_LARGO = 12.4, 28.0
MOD_CX, MOD_CY = 35.0, 22.5    # centro del módulo (acostado: fila V a la derecha, fila F a la izquierda)
SILK_W = 0.15
TXT_H = 1.0
TXT_PIN = 0.9           # etiquetas de los pines del Arduino
MASK_EXP = 0.05
PISTA_SENAL = 0.5
PISTA_POT = 0.8
PLANO_GND = True        # cara de abajo = plano de tierra
PLANO_CLR = 0.4
PLANO_BORDE = 0.5
TERM_GAP = 0.4
TERM_W = 0.5
KEEP_M3 = 3.5           # radio sin cobre (abajo) alrededor de los barrenos M3
BORNERA_P = 5.08        # paso de las borneras (entran las de 5.0 y 5.08 mm)
BORNERA_BROCA = 1.3
BORNERA_PAD = 3.0
BORNERA_FRENTE = 5.0    # del centro de los pines a la cara por donde entra el cable
BORNERA_ATRAS = 5.0
X_BORNERAS = 5.5        # línea de pines de las borneras (la cara de entrada queda a 0.5 mm de la orilla)
Y_FUENTE = 41.91        # pin 1 de la bornera de alimentación J4 (encima de la bornera Vin del shield de relevadores)
X_FUSIBLE, Y_FUSIBLE = 19.5, 37.75  # pin 1 del portafusible 5x20 (entrada); el pin 2 queda a 22.5 mm
X_TVS, Y_TVS = 49.5, 11.0           # cátodo del TVS opcional D1 (esquina libre de arriba a la derecha); ánodo 12.7 mm a la derecha
X_PTC, Y_PTC = 48.5, 37.75          # PTC opcional F2 (en línea con F1, a su derecha); pad 1 = 24V, pad 2 = 24V_IN
X_RUTA_A0, Y_DIAG_A0 = 59.0, 39.0   # la pista V -> A0 rodea por la derecha a F2
X_TITULO, Y_TITULO = 29.0, 10.0

# ======================= ARDUINO UNO R3 =======================
UNO_CONTORNO = [(0, 0), (64.52, 0), (66.04, 1.52), (66.04, 12.95), (68.58, 15.49),
                (68.58, 48.26), (66.04, 50.8), (66.04, 53.34), (0, 53.34)]
Y_DIG, Y_PWR = 2.54, 50.8
HEADERS = {   # ref: (y, [(pin, x), ...])  -- headers apilables
    "J5": (Y_DIG, [("SCL", 18.8), ("SDA", 21.34), ("AREF", 23.88), ("GND", 26.42), ("D13", 28.96),
                   ("D12", 31.5), ("D11", 34.04), ("D10", 36.58), ("D9", 39.12), ("D8", 41.66)]),
    "J6": (Y_DIG, [("D7", 45.72), ("D6", 48.26), ("D5", 50.8), ("D4", 53.34), ("D3", 55.88),
                   ("D2", 58.42), ("D1", 60.96), ("D0", 63.5)]),
    "J7": (Y_PWR, [("NC", 27.94), ("IOREF", 30.48), ("RESET", 33.02), ("3V3", 35.56), ("5V", 38.1),
                   ("GND", 40.64), ("GND", 43.18), ("VIN", 45.72)]),
    "J8": (Y_PWR, [("A0", 50.8), ("A1", 53.34), ("A2", 55.88), ("A3", 58.42), ("A4", 60.96),
                   ("A5", 63.5)]),
}
ETIQUETA_PIN = {"D13": "13", "D12": "12", "D11": "11", "D10": "10", "D9": "9", "D8": "8", "D7": "7",
                "D6": "6", "D5": "5", "D4": "4", "D3": "3", "D2": "2", "D1": "TX1", "D0": "RX0",
                "3V3": "3.3V", "NC": ""}
UNO_BARRENOS = [(13.97, 50.8), (15.24, 2.54), (66.04, 17.78), (66.04, 45.72)]

# Pines del módulo F/V, vistos desde arriba con los trimpots (fila V) hacia la derecha, de arriba a abajo
J1_NETS = ["GND", None, "A0", "GND"]          # fila V
J1_ETIQ = ["GND", "NC", "V", "GND"]
J2_NETS = [None, "F_SENSOR", "+24V", "GND"]   # fila F
J2_ETIQ = ["NC", "F", "24V", "GND"]


def _nets():
    n = {"GND": 1, "A0": 2, "F_SENSOR": 3, "+24V": 4, "+24V_IN": 5}
    for _, (_, pines) in HEADERS.items():
        for p, _x in pines:
            if p not in n and p != "NC":
                n[p] = len(n) + 1
    return n


NETS = _nets()
OX, OY = 100.0, 100.0
FECHA = datetime.date.today().isoformat()
_uid_n = [0]


def uid():
    _uid_n[0] += 1
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{NOMBRE}-{REV}-{_uid_n[0]}"))


def fmt(v):
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "", "-") else s


# ======================= FUENTE DE TRAZOS =======================
G = {
    "A": [[(0, 0), (2, 6), (4, 0)], [(0.67, 2), (3.33, 2)]],
    "B": [[(0, 0), (0, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)], [(3, 3), (4, 2), (4, 1), (3, 0), (0, 0)]],
    "C": [[(4, 1), (3, 0), (1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5)]],
    "D": [[(0, 0), (0, 6), (2.5, 6), (4, 4.5), (4, 1.5), (2.5, 0), (0, 0)]],
    "E": [[(4, 0), (0, 0), (0, 6), (4, 6)], [(0, 3), (3, 3)]],
    "F": [[(0, 0), (0, 6), (4, 6)], [(0, 3), (3, 3)]],
    "G": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0), (3, 0), (4, 1), (4, 3), (2.5, 3)]],
    "H": [[(0, 0), (0, 6)], [(4, 0), (4, 6)], [(0, 3), (4, 3)]],
    "I": [[(2, 0), (2, 6)], [(1, 0), (3, 0)], [(1, 6), (3, 6)]],
    "J": [[(4, 6), (4, 1), (3, 0), (1, 0), (0, 1)]],
    "K": [[(0, 0), (0, 6)], [(4, 6), (0, 2)], [(1.4, 3.4), (4, 0)]],
    "L": [[(0, 6), (0, 0), (4, 0)]],
    "M": [[(0, 0), (0, 6), (2, 3), (4, 6), (4, 0)]],
    "N": [[(0, 0), (0, 6), (4, 0), (4, 6)]],
    "O": [[(1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5), (4, 1), (3, 0), (1, 0)]],
    "P": [[(0, 0), (0, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)]],
    "R": [[(0, 0), (0, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)], [(2, 3), (4, 0)]],
    "S": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 4), (1, 3), (3, 3), (4, 2), (4, 1), (3, 0), (1, 0), (0, 1)]],
    "T": [[(0, 6), (4, 6)], [(2, 6), (2, 0)]],
    "U": [[(0, 6), (0, 1), (1, 0), (3, 0), (4, 1), (4, 6)]],
    "V": [[(0, 6), (2, 0), (4, 6)]],
    "X": [[(0, 0), (4, 6)], [(0, 6), (4, 0)]],
    "Y": [[(0, 6), (2, 3), (4, 6)], [(2, 3), (2, 0)]],
    "0": [[(1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5), (4, 1), (3, 0), (1, 0)], [(3.4, 5), (0.6, 1)]],
    "1": [[(1, 5), (2, 6), (2, 0)], [(1, 0), (3, 0)]],
    "2": [[(0, 5), (1, 6), (3, 6), (4, 5), (4, 4), (0, 0), (4, 0)]],
    "3": [[(0, 5), (1, 6), (3, 6), (4, 5), (4, 4), (3, 3), (1.5, 3)], [(3, 3), (4, 2), (4, 1), (3, 0), (1, 0), (0, 1)]],
    "4": [[(3, 0), (3, 6), (0, 2), (4, 2)]],
    "5": [[(4, 6), (0, 6), (0, 3.5), (3, 3.5), (4, 2.5), (4, 1), (3, 0), (1, 0), (0, 1)]],
    "6": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0), (3, 0), (4, 1), (4, 2.5), (3, 3.5), (0, 3.5)]],
    "7": [[(0, 6), (4, 6), (1.5, 0)]],
    "8": [[(1, 3), (0, 4), (0, 5), (1, 6), (3, 6), (4, 5), (4, 4), (3, 3), (1, 3), (0, 2), (0, 1), (1, 0), (3, 0),
           (4, 1), (4, 2), (3, 3)]],
    "9": [[(0, 1), (1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (1, 6), (0, 5), (0, 3.5), (1, 2.5), (4, 2.5)]],
    "/": [[(0, 0), (4, 6)]],
    "-": [[(1, 3), (3, 3)]],
    ".": [[(2, 0), (2, 0.25)]],
    "+": [[(2, 1), (2, 5)], [(0, 3), (4, 3)]],
    " ": [],
}
AVANCE = 5.5


def ancho_texto(texto, h):
    return ((len(texto) - 1) * AVANCE + 4) * h / 6.0


def xf(x, y, ang, lx, ly):
    a = math.radians(ang)
    return (x + lx * math.cos(a) + ly * math.sin(a),
            y - lx * math.sin(a) + ly * math.cos(a))


def trazos_texto(texto, x, y, h, ang=0, espejo=False):
    u = h / 6.0
    ancho = ancho_texto(texto, h)
    polis = []
    for i, ch in enumerate(texto):
        for poli in G[ch.upper()]:
            pts = []
            for gx, gy in poli:
                lx = i * AVANCE * u + gx * u - ancho / 2
                ly = -(gy - 3) * u
                if espejo:
                    lx = -lx
                pts.append(xf(x, y, ang, lx, ly))
            polis.append(pts)
    return polis


# ======================= MODELO =======================
class Pad:
    def __init__(self, num, forma, lx, ly, tx, ty, bx, net=None, tipo="thru_hole", keep=None):
        self.num, self.forma, self.lx, self.ly = num, forma, lx, ly
        self.tx, self.ty, self.bx = tx, ty, bx
        self.net, self.tipo = net, tipo
        self.keep = keep        # NPTH: radio sin cobre (plano) alrededor del agujero


class Fp:
    def __init__(self, lib, ref, valor, x, y, descr="", attr="through_hole", banda=False):
        self.lib, self.ref, self.valor = lib, ref, valor
        self.x, self.y = x, y
        self.descr, self.attr = descr, attr
        self.banda = banda          # fila de pines a 2.54: el plano se despeja con una franja continua
        self.pads, self.lineas, self.circulos = [], [], []
        self.ref_pos, self.val_pos = (0, -2.5), (0, 2.5)

    def xy(self, lx, ly):
        return self.x + lx, self.y + ly

    def linea(self, capa, pts, w):
        for a, b in zip(pts, pts[1:]):
            self.lineas.append((capa, a, b, w))

    def rect(self, capa, x0, y0, x1, y1, w):
        self.linea(capa, [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], w)


def fp_header_apilable(ref, y, pines):
    """Header apilable 1xN (stacking) de Arduino, pines a lo largo de x."""
    n = len(pines)
    x0 = pines[0][1]
    f = Fp(f"DigDug:Arduino_Stacking_1x{n:02d}_P2.54mm", ref, f"Header apilable 1x{n:02d}", x0, y,
           f"Header apilable (stacking) 1x{n:02d} 2.54 mm, posiciones del Arduino Uno R3", banda=True)
    for i, (p, x) in enumerate(pines):
        net = None if p == "NC" else p
        f.pads.append(Pad(str(i + 1), "circle", x - x0, 0, 1.7, 1.7, 1.0, net))
    xl = pines[-1][1] - x0
    f.rect("F.SilkS", -1.33, -1.33, xl + 1.33, 1.33, SILK_W)
    f.rect("F.Fab", -1.27, -1.27, xl + 1.27, 1.27, 0.1)
    f.rect("F.CrtYd", -1.8, -1.8, xl + 1.8, 1.8, 0.05)
    f.ref_pos, f.val_pos = (xl / 2, -2.6), (xl / 2, 2.6)
    return f


def fp_socket_1x04_v(ref, x, y, nets):
    """Header hembra 1x04 2.54 mm para el módulo, pines hacia abajo (+y), pin 1 arriba (cuadrado)."""
    f = Fp("DigDug:PinSocket_1x04_P2.54mm_Vertical", ref, "Header hembra 1x04 2.54mm", x, y,
           "Header hembra 1x04 2.54mm para el modulo F/V", banda=True)
    for i in range(4):
        f.pads.append(Pad(str(i + 1), "rect" if i == 0 else "circle", 0, i * PASO, 1.7, 1.7, 1.0, nets[i]))
    s = SILK_W
    yl = 3 * PASO + 1.33
    f.rect("F.SilkS", -1.33, 1.27, 1.33, yl, s)                 # cuerpo (pines 2 a 4)
    f.linea("F.SilkS", [(-1.33, 0), (-1.33, -1.33), (1.33, -1.33), (1.33, 0)], s)   # marca del pin 1
    f.rect("F.Fab", -1.27, -1.27, 1.27, 3 * PASO + 1.27, 0.1)
    f.rect("F.CrtYd", -1.8, -1.8, 1.8, 3 * PASO + 1.8, 0.05)
    f.ref_pos, f.val_pos = (0, -2.6), (0, yl + 1.2)
    return f


def fp_bornera_v(ref, x, y, nets):
    """Bornera de tornillo paso 5.08 mm, polos hacia abajo (+y), entrada del cable hacia la izquierda (-x)."""
    n = len(nets)
    P_ = BORNERA_P
    f = Fp(f"DigDug:Bornera_1x{n:02d}_P5.08mm_EntradaIzq", ref, f"Bornera {n} polos 5.08mm", x, y,
           f"Bornera de tornillo {n} polos, paso 5.0/5.08 mm (KF301, DG301, KF128, MKDS), broca {BORNERA_BROCA} mm")
    for i in range(n):
        f.pads.append(Pad(str(i + 1), "circle", 0, i * P_, BORNERA_PAD, BORNERA_PAD, BORNERA_BROCA, nets[i]))
    y0, y1 = -P_ / 2, (n - 1) * P_ + P_ / 2
    xa, xb = -BORNERA_FRENTE, BORNERA_ATRAS
    s = SILK_W
    f.rect("F.SilkS", xa, y0, xb, y1, s)
    xl = xa + 1.2
    f.linea("F.SilkS", [(xl, y0), (xl, y1)], s)
    for i in range(n):
        f.rect("F.SilkS", xa + 0.35, i * P_ - 1.4, xl - 0.35, i * P_ + 1.4, s)
    f.rect("F.Fab", xa, y0, xb, y1, 0.1)
    f.rect("F.CrtYd", xa - 0.5, y0 - 0.5, xb + 0.5, y1 + 0.5, 0.05)
    f.ref_pos, f.val_pos = (xb + 1.5, (n - 1) * P_ / 2), (0, (n - 1) * P_ / 2)
    return f


def fp_barreno_m3(ref, x, y):
    f = Fp("MountingHole:MountingHole_3.2mm_M3", ref, "Barreno M3", x, y,
           "Mounting Hole 3.2mm, no annular, M3", attr="exclude_from_pos_files exclude_from_bom")
    f.pads.append(Pad("", "circle", 0, 0, 3.2, 3.2, 3.2, None, "np_thru_hole", keep=KEEP_M3))
    f.circulos.append(("Cmts.User", 0, 0, 3.2, 0.15))
    f.circulos.append(("F.CrtYd", 0, 0, 3.45, 0.05))
    f.ref_pos, f.val_pos = (0, -4.2), (0, 4.2)
    return f


def fp_tvs_axial(ref, x, y, nets, anodo_derecha=False):
    """Diodo TVS axial acostado, paso 12.7 mm (DO-15: P6KE33A; también entra un 1.5KE33A doblando las patas).
    Origen en el cátodo (pad 1, cuadrado); el ánodo (pad 2) queda 12.7 mm a la izquierda
    (o a la derecha con anodo_derecha=True)."""
    k = -1 if anodo_derecha else 1           # sentido en x
    f = Fp("DigDug:D_DO-15_P12.70mm_Horizontal", ref, "TVS P6KE33A (opcional)", x, y,
           "TVS unidireccional axial DO-15, paso 12.7 mm, P6KE33A o equivalente (opcional)")
    f.pads.append(Pad("1", "rect", 0, 0, 2.6, 2.6, 1.3, nets[0]))
    f.pads.append(Pad("2", "circle", -12.7 * k, 0, 2.6, 2.6, 1.3, nets[1]))
    s = SILK_W
    xa, xc = k * (-6.35 - 3.8), k * (-6.35 + 3.8)   # cuerpo DO-15 (7.6 mm): lado ánodo y lado cátodo
    f.rect("F.SilkS", min(xa, xc), -2.0, max(xa, xc), 2.0, s)
    f.linea("F.SilkS", [(xc - 0.9 * k, -2.0), (xc - 0.9 * k, 2.0)], 0.6)    # franja del cátodo
    f.linea("F.SilkS", [(k * (-12.7 + 1.75), 0), (xa, 0)], s)
    f.linea("F.SilkS", [(xc, 0), (k * -1.75, 0)], s)
    f.rect("F.Fab", min(xa, xc), -1.8, max(xa, xc), 1.8, 0.1)
    f.rect("F.CrtYd", min(-14.3 * k, 1.6 * k), -2.3, max(-14.3 * k, 1.6 * k), 2.3, 0.05)
    f.ref_pos, f.val_pos = (-6.35 * k, -3.2), (-6.35 * k, 3.2)
    return f


def fp_ptc_radial(ref, x, y, nets):
    """Fusible reseteable PTC radial, patas a 5.08 mm (Bourns MF-R025, Littelfuse RXEF025 y similares)."""
    f = Fp("DigDug:PTC_Radial_P5.08mm", ref, "PTC 0.25A 60V (opcional)", x, y,
           "Fusible reseteable PTC radial, paso 5.08 mm (MF-R025 / RXEF025)")
    f.pads.append(Pad("1", "circle", 0, 0, 2.0, 2.0, 1.0, nets[0]))
    f.pads.append(Pad("2", "circle", 5.08, 0, 2.0, 2.0, 1.0, nets[1]))
    f.rect("F.SilkS", -1.3, -1.5, 5.08 + 1.3, 1.5, SILK_W)
    f.rect("F.Fab", 2.54 - 3.7, -1.6, 2.54 + 3.7, 1.6, 0.1)
    f.rect("F.CrtYd", -1.3, -1.9, 6.4, 1.9, 0.05)
    f.ref_pos, f.val_pos = (2.54, -2.6), (2.54, 2.6)
    return f


def fp_portafusible(ref, x, y, nets):
    """Portafusible 5x20 mm horizontal, 2 pines a 22.5 mm (Schurter OGN 0031.8201, Stelvio PTF78,
    BLX-A y compatibles). Agujero central de 2.7 mm para el poste de centrado (si lo trae)."""
    f = Fp("DigDug:Portafusible_5x20mm_P22.5mm", ref, "Portafusible 5x20mm", x, y,
           "Portafusible 5x20 mm horizontal, pines a 22.5 mm (Schurter OGN 0031.8201 / PTF78 / BLX-A)")
    f.pads.append(Pad("1", "circle", 0, 0, 3.0, 3.0, 1.3, nets[0]))
    f.pads.append(Pad("2", "circle", 22.5, 0, 3.0, 3.0, 1.3, nets[1]))
    f.pads.append(Pad("", "circle", 11.25, 0, 2.7, 2.7, 2.7, None, "np_thru_hole", keep=2.7 / 2 + 0.5))
    s = SILK_W
    f.rect("F.SilkS", -2.1, -4.9, 24.6, 4.9, s)
    f.rect("F.Fab", -1.5, -4.8, 24.0, 4.8, 0.1)
    f.rect("F.CrtYd", -2.0, -5.1, 24.5, 5.1, 0.05)
    f.ref_pos, f.val_pos = (11.25, -6.0), (11.25, 6.0)
    return f


# ======================= GEOMETRÍA =======================
def offset_poligono(pts, d):
    """Polígono simple desplazado hacia adentro una distancia d (esquinas en inglete)."""
    n = len(pts)
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n)) / 2
    sg = 1 if area > 0 else -1
    lineas = []
    for i in range(n):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        nx, ny = -dy / L * sg, dx / L * sg
        lineas.append(((x0 + nx * d, y0 + ny * d), (dx, dy)))
    out = []
    for i in range(n):
        (p1, d1), (p2, d2) = lineas[i - 1], lineas[i]
        den = d1[0] * d2[1] - d1[1] * d2[0]
        t = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / den
        out.append((p1[0] + t * d1[0], p1[1] + t * d1[1]))
    return out


def dentro_poligono(pts, x, y):
    c = False
    n = len(pts)
    for i in range(n):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            c = not c
    return c


def contorno(d):
    pts = list(UNO_CONTORNO) + [UNO_CONTORNO[0]]
    prim = [("line", a, b) for a, b in zip(pts, pts[1:])]
    return prim, pts


def contorno_plano(d):
    pts = offset_poligono(UNO_CONTORNO, PLANO_BORDE)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return pts + [pts[0]], (min(xs), min(ys), max(xs), max(ys))


def pads_abs(d):
    out = []
    for f in d["fps"]:
        for p in f.pads:
            cx, cy = f.xy(p.lx, p.ly)
            out.append(dict(ref=f"{f.ref}.{p.num}", forma=p.forma, cx=cx, cy=cy, tx=p.tx, ty=p.ty,
                            net=p.net, tipo=p.tipo, bx=p.bx, fp=f, keep=p.keep))
    return out


def dist_pad(q, x, y):
    dx, dy = abs(x - q["cx"]), abs(y - q["cy"])
    hx, hy = q["tx"] / 2, q["ty"] / 2
    if q["forma"] == "rect":
        return math.hypot(max(dx - hx, 0), max(dy - hy, 0))
    r = min(hx, hy)
    return max(math.hypot(max(dx - (hx - r), 0), max(dy - (hy - r), 0)) - r, 0)


def rayos_termicos(d):
    """Rayos de los pads de GND al plano (cara de abajo); se omiten los que pasarían cerca de otra net."""
    pads = pads_abs(d)
    interior = offset_poligono(UNO_CONTORNO, PLANO_BORDE + TERM_W / 2)
    m3 = [q for q in pads if q["tipo"] == "np_thru_hole"]
    otros = [q for q in pads if q["tipo"] != "np_thru_hole" and q["net"] != "GND"]
    rayos = []
    for q in pads:
        if q["net"] != "GND" or q["tipo"] == "np_thru_hole":
            continue
        n = 0
        for ux, uy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            L = (q["tx"] / 2 if ux else q["ty"] / 2) + TERM_GAP + 0.35
            ex, ey = q["cx"] + ux * L, q["cy"] + uy * L
            ok = dentro_poligono(interior, ex, ey)
            ok = ok and all(math.hypot(ex - h["cx"], ey - h["cy"]) > h["keep"] + TERM_W / 2 for h in m3)
            if ok:
                for k in range(41):
                    t = k / 40
                    x, y = q["cx"] + ux * L * t, q["cy"] + uy * L * t
                    if any(dist_pad(o, x, y) < PLANO_CLR + TERM_W / 2 for o in otros):
                        ok = False
                        break
            if ok:
                rayos.append(((q["cx"], q["cy"]), (ex, ey)))
                n += 1
        assert n >= 2, f"{q['ref']}: solo {n} rayos térmicos"
    return rayos


# ======================= DISEÑO =======================
def construir():
    d = {"fps": [], "pistas": [], "silk": [], "textos": [], "borde": (0, 0, 68.58, 53.34)}
    cx, cy = MOD_CX, MOD_CY
    xJ1, xJ2 = cx + S_FILAS / 2, cx - S_FILAS / 2      # fila V (derecha) y fila F (izquierda)
    y_p1 = cy - 1.5 * PASO                               # y del pin 1 de J1/J2
    yF = y_p1 + 2 * PASO - BORNERA_P                     # polos de la bornera del sensor: F, 24V, GND (24V alineado con J2.3)
    y24 = yF + BORNERA_P
    yA = Y_FUENTE                                        # bornera de alimentación: 24V, GND
    d.update(xJ1=xJ1, xJ2=xJ2, yF=yF, yA=yA)

    # ---------- componentes ----------
    d["fps"].append(fp_socket_1x04_v("J1", xJ1, y_p1, J1_NETS))
    d["fps"].append(fp_socket_1x04_v("J2", xJ2, y_p1, J2_NETS))
    d["fps"].append(fp_bornera_v("J3", X_BORNERAS, yF, ["F_SENSOR", "+24V", "GND"]))
    d["fps"].append(fp_bornera_v("J4", X_BORNERAS, yA, ["+24V_IN", "GND"]))
    xF1, yF1 = X_FUSIBLE, Y_FUSIBLE
    d["fps"].append(fp_portafusible("F1", xF1, yF1, ["+24V_IN", "+24V"]))
    xP1, xP2, yP = X_PTC, X_PTC + 5.08, Y_PTC     # PTC a la derecha de F1 (se usa F1 o F2, no los dos)
    d["fps"].append(fp_ptc_radial("F2", xP1, yP, ["+24V", "+24V_IN"]))
    d["fps"].append(fp_tvs_axial("D1", X_TVS, Y_TVS, ["+24V", "GND"], anodo_derecha=True))
    for ref, (y, pines) in HEADERS.items():
        d["fps"].append(fp_header_apilable(ref, y, pines))
    for i, (hx, hy) in enumerate(UNO_BARRENOS, 1):
        d["fps"].append(fp_barreno_m3(f"H{i}", hx, hy))

    # ---------- pistas (capa, puntos, ancho, net) ----------
    P = d["pistas"]
    yJF, yJ24, yJV = y_p1 + PASO, y_p1 + 2 * PASO, y_p1 + 2 * PASO     # J2.2 (F), J2.3 (24V), J1.3 (V)
    # F: bornera del sensor -> J2.2 (entra por la izquierda, lejos del pad cuadrado de J2.1)
    xq = xJ2 - 1.76
    P.append(("F.Cu", [(X_BORNERAS, yF), (xq - (yJF - yF), yF), (xq, yJF), (xJ2, yJF)], PISTA_SENAL, "F_SENSOR"))
    # 24V de entrada: bornera de alimentación (J4.1) -> portafusible (F1.1)
    P.append(("F.Cu", [(X_BORNERAS, yA), (xF1 - (yA - yF1), yA), (xF1, yF1)], PISTA_POT, "+24V_IN"))
    # 24V con fusible: F1.2 sube a la unión (xF2, yJ24); de ahí a J2.3 y, más arriba, al cátodo del TVS D1.
    # La bornera del sensor llega a J2.3 por la izquierda.
    xF2 = xF1 + 22.5
    P.append(("F.Cu", [(xF2, yF1), (xF2, yJ24)], PISTA_POT, "+24V"))
    P.append(("F.Cu", [(xF2, yJ24), (xJ2, yJ24)], PISTA_POT, "+24V"))
    # PTC F2 en paralelo con F1: la entrada pasa por debajo del portafusible hasta F2.2 ; F2.1 -> F1.2
    yI = yF1 + 3.7
    P.append(("F.Cu", [(xF1, yF1), (xF1 + (yI - yF1), yI), (xP2, yI), (xP2, yP)], PISTA_POT, "+24V_IN"))
    tramo = [(xP1, yP)] + ([(xP1 - abs(yF1 - yP), yF1)] if abs(yF1 - yP) > 1e-6 else []) + [(xF2, yF1)]
    P.append(("F.Cu", tramo, PISTA_POT, "+24V"))
    # cátodo del TVS D1 (esquina de arriba a la derecha) <- unión de 24V, subiendo entre las filas del módulo
    P.append(("F.Cu", [(xF2, yJ24), (xF2, Y_TVS + 2.0), (xF2 + 2.0, Y_TVS), (X_TVS, Y_TVS)], PISTA_POT, "+24V"))
    P.append(("F.Cu", [(X_BORNERAS, y24), (xJ2, yJ24)], PISTA_POT, "+24V"))
    # V del módulo (J1.3) -> A0 del Arduino, rodeando a F2 por la derecha
    xA0 = HEADERS["J8"][1][0][1]
    xa = xJ1 + 2.0
    P.append(("F.Cu", [(xJ1, yJV), (xa, yJV), (X_RUTA_A0, yJV + (X_RUTA_A0 - xa)), (X_RUTA_A0, Y_DIAG_A0),
                       (xA0, Y_DIAG_A0 + (X_RUTA_A0 - xA0)), (xA0, Y_PWR)], PISTA_SENAL, "A0"))

    # ---------- serigrafía ----------
    S, T = d["silk"], d["textos"]
    h2 = TXT_H / 2 + SILK_W / 2
    # módulo F/V
    mx0, mx1 = xJ2 - 1.33 - 0.6, xJ1 + 1.33 + 0.6
    my0, my1 = cy - MOD_ANCHO / 2 - 0.15, cy + MOD_ANCHO / 2 + 0.15
    S.append(("F.SilkS", [(mx0, my0), (mx1, my0), (mx1, my1), (mx0, my1), (mx0, my0)], SILK_W))
    T.append(dict(t="D1 TVS", x=X_TVS + 6.35, y=Y_TVS + 2.0 + SILK_W / 2 + 0.5 + h2, h=TXT_H, capa="F.SilkS"))
    T.append(dict(t="MODULO F/V", x=cx - 2.0, y=cy - 2.0, h=TXT_H, capa="F.SilkS"))
    for i in range(4):
        y = y_p1 + i * PASO
        w2 = ancho_texto(J2_ETIQ[i], TXT_H)
        w1 = ancho_texto(J1_ETIQ[i], TXT_H)
        T.append(dict(t=J2_ETIQ[i], x=xJ2 + 1.33 + 0.075 + 0.45 + w2 / 2, y=y, h=TXT_H, capa="F.SilkS"))
        T.append(dict(t=J1_ETIQ[i], x=xJ1 - 1.33 - 0.075 - 0.45 - w1 / 2, y=y, h=TXT_H, capa="F.SilkS"))
    T.append(dict(t="J2", x=xJ2, y=my0 - 0.4 - h2, h=TXT_H, capa="F.SilkS"))
    T.append(dict(t="J1", x=xJ1, y=my0 - 0.4 - h2, h=TXT_H, capa="F.SilkS"))
    # borneras
    xt = X_BORNERAS + BORNERA_ATRAS + 0.075 + 0.45
    for t, y in (("F", yF), ("24V", y24), ("GND", yF + 2 * BORNERA_P), ("24V", yA), ("GND", yA + BORNERA_P)):
        T.append(dict(t=t, x=xt + ancho_texto(t, TXT_H) / 2, y=y, h=TXT_H, capa="F.SilkS"))
    T.append(dict(t="F2 PTC", x=xP1 + 2.54, y=yP - 1.5 - 0.075 - 0.45 - h2, h=TXT_H, capa="F.SilkS"))
    T.append(dict(t="F1 5X20", x=(xF1 + 11.25 + 1.35 + xF2 - 1.5) / 2, y=yF1, h=TXT_H, capa="F.SilkS"))
    T.append(dict(t="USAR SOLO F1 O F2", x=xF1 + 11.25, y=yF1 - 2.8, h=TXT_H, capa="F.SilkS"))
    T.append(dict(t="SENSOR", x=X_BORNERAS, y=yF - BORNERA_P / 2 - 0.4 - h2, h=TXT_H, capa="F.SilkS"))
    T.append(dict(t="FUENTE 24V", x=X_BORNERAS, y=yA - BORNERA_P / 2 - 0.4 - h2, h=TXT_H, capa="F.SilkS"))
    # pines del Arduino
    for ref, (y, pines) in HEADERS.items():
        for p, x in pines:
            t = ETIQUETA_PIN.get(p, p)
            if not t:
                continue
            w = ancho_texto(t, TXT_PIN)
            off = 1.33 + 0.075 + 0.35 + w / 2
            T.append(dict(t=t, x=x, y=y + off if y < 26 else y - off, h=TXT_PIN, capa="F.SilkS", ang=90))
    T.append(dict(t=f"DIG DUG F/V SHIELD V{REV}", x=X_TITULO, y=Y_TITULO, h=1.2, capa="F.SilkS"))
    # lado de abajo (espejo): textos en el hueco libre entre el módulo y el portafusible
    yb = (cy + MOD_ANCHO / 2 + yF1 - 4.9) / 2
    for t, x, y in ((f"DIG DUG F/V SHIELD V{REV}", cx, yb - 1.25), ("ARRIBA DEL SHIELD DE RELEVADORES", cx, yb + 1.25),
                    ("SENSOR", X_BORNERAS + 1.5, yF - BORNERA_P / 2 - 0.4 - h2),
                    ("FUENTE 24V", X_BORNERAS + 1.5, yA - BORNERA_P / 2 - 0.4 - h2)):
        T.append(dict(t=t, x=x, y=y, h=TXT_H, capa="B.SilkS", espejo=True))
    return d


# ======================= KiCad =======================
def escribir_kicad(d, ruta):
    L = []
    a = L.append
    a('(kicad_pcb (version 20221018) (generator pcbnew)')
    a('')
    a('  (general')
    a('    (thickness 1.6)')
    a('  )')
    a('')
    a('  (paper "A4")')
    a('  (title_block')
    a('    (title "Dig Dug - Shield F/V (formato Arduino Uno R3)")')
    a(f'    (date "{FECHA}")')
    a(f'    (rev "{REV}")')
    a(f'    (comment 1 "Pila: Arduino Uno / shield de relevadores 24V / este shield. Modulo F/V a {fmt(S_FILAS)} mm.")')
    a('    (comment 2 "24V solo al modulo y al sensor; NO va a ningun pin del Arduino. V del modulo -> A0.")')
    a('  )')
    a('')
    a('  (layers')
    for ln in ['(0 "F.Cu" signal)', '(31 "B.Cu" signal)', '(32 "B.Adhes" user "B.Adhesive")',
               '(33 "F.Adhes" user "F.Adhesive")', '(34 "B.Paste" user)', '(35 "F.Paste" user)',
               '(36 "B.SilkS" user "B.Silkscreen")', '(37 "F.SilkS" user "F.Silkscreen")',
               '(38 "B.Mask" user)', '(39 "F.Mask" user)', '(40 "Dwgs.User" user "User.Drawings")',
               '(41 "Cmts.User" user "User.Comments")', '(42 "Eco1.User" user "User.Eco1")',
               '(43 "Eco2.User" user "User.Eco2")', '(44 "Edge.Cuts" user)', '(45 "Margin" user)',
               '(46 "B.CrtYd" user "B.Courtyard")', '(47 "F.CrtYd" user "F.Courtyard")',
               '(48 "B.Fab" user)', '(49 "F.Fab" user)']:
        a('    ' + ln)
    a('  )')
    a('')
    a('  (setup')
    a('    (pad_to_mask_clearance 0)')
    a('  )')
    a('')
    a('  (net 0 "")')
    for n, i in NETS.items():
        a(f'  (net {i} "{n}")')
    a('')

    def K(x, y):
        return f"{fmt(x + OX)} {fmt(y + OY)}"

    for f in d["fps"]:
        a(f'  (footprint "{f.lib}" (layer "F.Cu")')
        a(f'    (tstamp {uid()})')
        a(f'    (at {K(f.x, f.y)})')
        a(f'    (descr "{f.descr}")')
        a(f'    (attr {f.attr})')
        for tipo, txt, pos in (("reference", f.ref, f.ref_pos), ("value", f.valor, f.val_pos)):
            a(f'    (fp_text {tipo} "{txt}" (at {fmt(pos[0])} {fmt(pos[1])}) (layer "F.Fab")')
            a('        (effects (font (size 1 1) (thickness 0.15)))')
            a(f'      (tstamp {uid()})')
            a('    )')
        for capa, p, q, w in f.lineas:
            a(f'    (fp_line (start {fmt(p[0])} {fmt(p[1])}) (end {fmt(q[0])} {fmt(q[1])})')
            a(f'      (stroke (width {fmt(w)}) (type solid)) (layer "{capa}") (tstamp {uid()}))')
        for capa, ccx, ccy, r, w in f.circulos:
            a(f'    (fp_circle (center {fmt(ccx)} {fmt(ccy)}) (end {fmt(ccx + r)} {fmt(ccy)})')
            a(f'      (stroke (width {fmt(w)}) (type solid)) (fill none) (layer "{capa}") (tstamp {uid()}))')
        for p in f.pads:
            pos = f"(at {fmt(p.lx)} {fmt(p.ly)})"
            tam = f"(size {fmt(p.tx)} {fmt(p.ty)})"
            broca = f"(drill {fmt(p.bx)})"
            if p.tipo == "np_thru_hole":
                a(f'    (pad "" np_thru_hole circle {pos} {tam} {broca} (layers "*.Cu" "*.Mask")')
                a(f'      (tstamp {uid()}))')
            else:
                net = f' (net {NETS[p.net]} "{p.net}")' if p.net else ""
                a(f'    (pad "{p.num}" thru_hole {p.forma} {pos} {tam} {broca} (layers "*.Cu" "*.Mask"){net}')
                a(f'      (pintype "passive") (tstamp {uid()}))')
        a('  )')
        a('')

    prim, _ = contorno(d)
    for pr in prim:
        a(f'  (gr_line (start {K(*pr[1])}) (end {K(*pr[2])})')
        a(f'    (stroke (width 0.1) (type default)) (layer "Edge.Cuts") (tstamp {uid()}))')
    for capa, pts, w in d["silk"]:
        for p, q in zip(pts, pts[1:]):
            a(f'  (gr_line (start {K(*p)}) (end {K(*q)})')
            a(f'    (stroke (width {fmt(w)}) (type solid)) (layer "{capa}") (tstamp {uid()}))')
    for t in d["textos"]:
        ang = f" {fmt(t['ang'])}" if t.get("ang") else ""
        a(f'  (gr_text "{t["t"]}" (at {K(t["x"], t["y"])}{ang}) (layer "{t["capa"]}") (tstamp {uid()})')
        just = " (justify mirror)" if t.get("espejo") else ""
        h = fmt(t["h"])
        a(f'    (effects (font (size {h} {h}) (thickness {fmt(SILK_W)})){just})')
        a('  )')
    a('')
    if PLANO_GND:
        pts, _ = contorno_plano(d)
        xy = " ".join(f"(xy {K(*p)})" for p in pts[:-1])
        a(f'  (zone (net {NETS["GND"]}) (net_name "GND") (layer "B.Cu") (tstamp {uid()}) (hatch edge 0.5)')
        a(f'    (connect_pads (clearance {fmt(PLANO_CLR)}))')
        a('    (min_thickness 0.25) (filled_areas_thickness no)')
        a(f'    (fill (thermal_gap {fmt(TERM_GAP)}) (thermal_bridge_width {fmt(TERM_W)}))')
        a(f'    (polygon (pts {xy}))')
        a('  )')
        for q in pads_abs(d):
            if q["tipo"] != "np_thru_hole":
                continue
            kr = q["keep"]
            circ = " ".join(f"(xy {K(q['cx'] + kr * math.cos(2 * math.pi * i / 24), q['cy'] + kr * math.sin(2 * math.pi * i / 24))})"
                            for i in range(24))
            a(f'  (zone (net 0) (net_name "") (layer "B.Cu") (tstamp {uid()}) (hatch edge 0.5)')
            a('    (connect_pads (clearance 0))')
            a('    (min_thickness 0.25) (filled_areas_thickness no)')
            a('    (keepout (tracks allowed) (vias allowed) (pads allowed) (copperpour not_allowed) (footprints allowed))')
            a('    (fill (thermal_gap 0.5) (thermal_bridge_width 0.5))')
            a(f'    (polygon (pts {circ}))')
            a('  )')
        a('')
    for capa, pts, w, net in d["pistas"]:
        for p, q in zip(pts, pts[1:]):
            a(f'  (segment (start {K(*p)}) (end {K(*q)}) (width {fmt(w)}) (layer "{capa}") (net {NETS[net]}) (tstamp {uid()}))')
    a('')
    a(')')
    with open(ruta, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")


# ======================= GERBER / DRILL =======================
class Gerber:
    def __init__(self, funcion, polaridad="Positive"):
        self.funcion, self.polaridad = funcion, polaridad
        self.aps = {}
        self.cuerpo = []
        self.ap_actual = None

    def _ap(self, clave):
        if clave not in self.aps:
            self.aps[clave] = 10 + len(self.aps)
        code = self.aps[clave]
        if code != self.ap_actual:
            self.cuerpo.append(f"D{code}*")
            self.ap_actual = code

    @staticmethod
    def c(v):
        return str(int(round(v * 1e6)))

    def flash(self, forma, tx, ty, x, y):
        clave = {"rect": "R", "circle": "C", "oval": "O"}[forma]
        self._ap((clave, round(tx, 4), round(ty, 4)))
        self.cuerpo.append(f"X{self.c(x)}Y{self.c(y)}D03*")

    def polilinea(self, pts, w):
        self._ap(("C", round(w, 4), round(w, 4)))
        (x, y) = pts[0]
        self.cuerpo.append(f"X{self.c(x)}Y{self.c(y)}D02*")
        for (x, y) in pts[1:]:
            self.cuerpo.append(f"X{self.c(x)}Y{self.c(y)}D01*")

    def lp(self, oscura):
        self.cuerpo.append("%LPD*%" if oscura else "%LPC*%")

    def region(self, pts):
        self.cuerpo.append("G36*")
        (x, y) = pts[0]
        self.cuerpo.append(f"X{self.c(x)}Y{self.c(y)}D02*")
        for (x, y) in pts[1:]:
            self.cuerpo.append(f"X{self.c(x)}Y{self.c(y)}D01*")
        self.cuerpo.append("G37*")

    def texto(self):
        h = [f"%TF.GenerationSoftware,Claude,generar_shield.py,{REV}*%",
             f"%TF.CreationDate,{FECHA}T00:00:00-06:00*%",
             f"%TF.ProjectId,{NOMBRE},{uuid.uuid5(uuid.NAMESPACE_URL, NOMBRE).hex},rev{REV}*%",
             "%TF.SameCoordinates,Original*%",
             f"%TF.FileFunction,{self.funcion}*%",
             f"%TF.FilePolarity,{self.polaridad}*%",
             "%FSLAX46Y46*%",
             "G04 Dig Dug - shield F/V formato Arduino Uno*",
             "%MOMM*%",
             "%LPD*%",
             "G01*"]
        for (forma, tx, ty), code in sorted(self.aps.items(), key=lambda kv: kv[1]):
            if forma == "C":
                h.append(f"%ADD{code}C,{tx:.6f}*%")
            else:
                h.append(f"%ADD{code}{forma},{tx:.6f}X{ty:.6f}*%")
        return "\n".join(h + self.cuerpo + ["M02*"]) + "\n"


def escribir_gerbers(d, carpeta):
    os.makedirs(carpeta, exist_ok=True)
    x0, y0, x1, y1 = d["borde"]

    def G_(x, y):              # tarjeta (y abajo) -> Gerber (y arriba, origen esquina inferior izquierda)
        return (x - x0, y1 - y)

    capas = {
        "F_Cu": Gerber("Copper,L1,Top"), "B_Cu": Gerber("Copper,L2,Bot"),
        "F_Mask": Gerber("Soldermask,Top", "Negative"), "B_Mask": Gerber("Soldermask,Bot", "Negative"),
        "F_Silkscreen": Gerber("Legend,Top"), "B_Silkscreen": Gerber("Legend,Bot"),
        "Edge_Cuts": Gerber("Profile,NP"),
    }
    pth, npth = {}, {}
    bcu = capas["B_Cu"]
    if PLANO_GND:
        # 1) plano completo  2) se despeja alrededor de pads ajenos, filas de pines y barrenos  3) cobre encima
        pts, _ = contorno_plano(d)
        bcu.region([G_(*p) for p in pts])
        bcu.lp(False)
        for f in d["fps"]:
            if f.banda:     # franja continua a lo largo de la fila (evita astillas de plano entre pines)
                r = max(p.tx for p in f.pads) / 2 + PLANO_CLR
                pa = [f.xy(p.lx, p.ly) for p in f.pads]
                bcu.polilinea([G_(*pa[0]), G_(*pa[-1])], 2 * r)
        for q in pads_abs(d):
            gx, gy = G_(q["cx"], q["cy"])
            if q["tipo"] == "np_thru_hole":
                bcu.flash("circle", 2 * q["keep"], 2 * q["keep"], gx, gy)
            else:
                e = 2 * (TERM_GAP if q["net"] == "GND" else PLANO_CLR)
                bcu.flash(q["forma"], q["tx"] + e, q["ty"] + e, gx, gy)
        bcu.lp(True)
    for f in d["fps"]:
        for p in f.pads:
            x, y = f.xy(p.lx, p.ly)
            gx, gy = G_(x, y)
            m = 2 * MASK_EXP
            if p.tipo == "np_thru_hole":
                npth.setdefault(p.bx, []).append((gx, gy))
                for k in ("F_Mask", "B_Mask"):
                    capas[k].flash("circle", p.tx + m, p.ty + m, gx, gy)
                continue
            pth.setdefault(p.bx, []).append((gx, gy))
            for k in ("F_Cu", "B_Cu"):
                capas[k].flash(p.forma, p.tx, p.ty, gx, gy)
            for k in ("F_Mask", "B_Mask"):
                capas[k].flash(p.forma, p.tx + m, p.ty + m, gx, gy)
        for capa, p, q, w in f.lineas:
            if capa == "F.SilkS":
                capas["F_Silkscreen"].polilinea([G_(*f.xy(*p)), G_(*f.xy(*q))], w)
    for capa, pts_, w, net in d["pistas"]:
        capas[capa.replace(".", "_")].polilinea([G_(*p) for p in pts_], w)
    if PLANO_GND:
        for a_, b_ in rayos_termicos(d):
            bcu.polilinea([G_(*a_), G_(*b_)], TERM_W)
    for capa, pts_, w in d["silk"]:
        capas["F_Silkscreen" if capa == "F.SilkS" else "B_Silkscreen"].polilinea([G_(*p) for p in pts_], w)
    for t in d["textos"]:
        dest = capas["F_Silkscreen" if t["capa"] == "F.SilkS" else "B_Silkscreen"]
        for poli in trazos_texto(t["t"], t["x"], t["y"], t["h"], t.get("ang", 0), t.get("espejo", False)):
            dest.polilinea([G_(*p) for p in poli], SILK_W)
    _, pts_b = contorno(d)
    capas["Edge_Cuts"].polilinea([G_(*p) for p in pts_b], 0.1)

    ext = {"F_Cu": "gtl", "B_Cu": "gbl", "F_Mask": "gts", "B_Mask": "gbs",
           "F_Silkscreen": "gto", "B_Silkscreen": "gbo", "Edge_Cuts": "gm1"}
    archivos = []
    for k, g in capas.items():
        ruta = os.path.join(carpeta, f"{NOMBRE}-{k}.{ext[k]}")
        with open(ruta, "w", newline="\n") as fh:
            fh.write(g.texto())
        archivos.append(ruta)

    def drill(nombre, herramientas, plated):
        tipo = "Plated,1,2,PTH" if plated else "NonPlated,1,2,NPTH"
        lineas = ["M48", f"; DRILL file {{generar_shield.py rev{REV}}} date {FECHA}",
                  "; FORMAT={-:-/ absolute / metric / decimal}",
                  f"; #@! TF.FileFunction,{tipo}", "FMAT,2", "METRIC"]
        orden = sorted(herramientas)
        for i, dia in enumerate(orden, 1):
            lineas.append(f"T{i}C{dia:.3f}")
        lineas += ["%", "G90", "G05"]
        for i, dia in enumerate(orden, 1):
            lineas.append(f"T{i}")
            for gx, gy in herramientas[dia]:
                lineas.append(f"X{gx:.4f}Y{gy:.4f}")
        lineas += ["T0", "M30"]
        ruta = os.path.join(carpeta, nombre)
        with open(ruta, "w", newline="\n") as fh:
            fh.write("\n".join(lineas) + "\n")
        archivos.append(ruta)

    drill(f"{NOMBRE}-PTH.drl", pth, True)
    if npth:
        drill(f"{NOMBRE}-NPTH.drl", npth, False)
    return archivos


def main():
    aqui = os.path.dirname(os.path.abspath(__file__))
    salida = os.path.join(aqui, SALIDA)
    gdir = os.path.join(salida, "gerbers")
    os.makedirs(gdir, exist_ok=True)
    for n in os.listdir(gdir):
        os.remove(os.path.join(gdir, n))
    d = construir()
    escribir_kicad(d, os.path.join(salida, f"{NOMBRE}.kicad_pcb"))
    archivos = escribir_gerbers(d, gdir)
    zip_ruta = os.path.join(salida, f"{NOMBRE}_gerbers.zip")
    with zipfile.ZipFile(zip_ruta, "w", zipfile.ZIP_DEFLATED) as z:
        for r in archivos:
            z.write(r, os.path.basename(r))
    print(f"Shield {NOMBRE} rev {REV}: 68.58 x 53.34 mm (Arduino Uno R3)")
    print(f"KiCad:   {os.path.join(salida, NOMBRE + '.kicad_pcb')}")
    print(f"Gerbers: {zip_ruta}")


if __name__ == "__main__":
    main()
