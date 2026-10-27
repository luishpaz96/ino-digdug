#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base (carrier) para el convertidor F/V (LM331) del Dig Dug.

El módulo se conecta en dos headers hembra 1x4 de 2.54 mm (se cambia sin desoldar).
Arriba: bornera de 3 polos A0 / GND / 24V: A0 y GND van al Arduino, GND y 24V a la fuente
(la GND del centro es común). Abajo: bornera de 3 polos para el sensor (F, 24V, GND).
Los 24V de las dos borneras van unidos al pin 24V del módulo. Borneras de paso 5.08 mm (entran las comunes de
5.0 y 5.08 mm: KF301, DG301, KF128, Phoenix MKDS...), con la entrada del cable hacia la orilla.
Sin componentes: la salida V va directo al A0.

J1 y J2 usan la huella estándar del header hembra (agujero de 1.0 mm). La distancia entre las
dos filas del módulo (S_FILAS) es 25.4 mm (10 x 2.54: entra en el header del Arduino de 5V a A5); si se mide
otra, cambia S_FILAS y vuelve a correr. Con RANURADOS = True los agujeros son ranurados y los
conectores se acomodan solos al soldarlos con el módulo puesto.

Todo sale de la misma geometría:
    salida/DigDug_Base_FV.kicad_pcb       proyecto KiCad 7 o más nuevo (editable)
    salida/gerbers/                        Gerbers RS-274X + drill Excellon
    salida/DigDug_Base_FV_gerbers.zip      zip para subir a JLCPCB / PCBWay

Si cambias un parámetro, vuelve a correr:   python3 generar_pcb.py
"""
import math
import os
import uuid
import zipfile
import datetime

# ======================= PARÁMETROS (mm) =======================
PASO       = 2.54   # paso entre pines del módulo
S_FILAS    = 25.4   # centro a centro = 10 x 2.54: el módulo entra en el header del Arduino de 5V a A5 (vernier en las puntas: 25.1)
RANURADOS  = False  # True: J1 y J2 con agujeros ranurados (autoalineables)
RANURA_L   = 3.2    # largo de la ranura (broca 1.0 mm) -> juego de +/- (3.2-0.9)/2 = 1.15 mm por conector
MOD_ANCHO  = 12.4   # ancho del módulo medido con vernier: 12.36 mm (solo para el contorno de serigrafía)
ANCHO_PCB  = 17.0
BORNERA_P      = 5.08   # paso de las borneras (sirven las de 5.0 y 5.08 mm)
BORNERA_BROCA  = 1.3
BORNERA_PAD    = 3.0
BORNERA_FRENTE = 5.0    # del centro de los pines a la cara de entrada del cable (espacio reservado)
BORNERA_ATRAS  = 5.0    # del centro de los pines a la cara de atrás (espacio reservado)
R_ESQUINA  = 1.0
PISTA_SENAL = 0.5
PISTA_POT   = 0.6
SILK_W     = 0.15
TXT_H      = 1.0
MASK_EXP   = 0.05   # crecimiento de la máscara por lado
PLANO_GND  = True   # cara de abajo = un solo plano de tierra
PLANO_CLR  = 0.4    # separación del plano a cobre de otra net
PLANO_BORDE = 0.5   # separación del plano al borde de la tarjeta
TERM_GAP   = 0.4    # hueco térmico alrededor de los pads de GND (facilita soldar)
TERM_W     = 0.5    # ancho de los rayos térmicos
KEEP_M3    = 3.5    # radio sin cobre alrededor de los barrenos M3 (para separadores metálicos)
NOMBRE     = "DigDug_Base_FV"
REV        = "6"

# Pines del módulo, vista desde arriba (lado de componentes, trimpots arriba), de izquierda a derecha
J1_NETS = ["GND", None, "V_A0", "GND"]         # fila de arriba (salida)
J1_ETIQ = ["GND", "NC", "V", "GND"]
J2_NETS = [None, "F_SENSOR", "+24V", "GND"]    # fila de abajo (sensor)
J2_ETIQ = ["NC", "F", "24V", "GND"]

NETS = {"GND": 1, "V_A0": 2, "F_SENSOR": 3, "+24V": 4}

OX, OY = 100.0, 100.0   # posición en la hoja de KiCad
FECHA = datetime.date.today().isoformat()

_uid_n = [0]


def uid():
    _uid_n[0] += 1
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{NOMBRE}-{REV}-{_uid_n[0]}"))


def fmt(v):
    s = f"{v:.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "", "-") else s


# ======================= FUENTE DE TRAZOS =======================
# Rejilla de 4 x 6 (x a la derecha, y hacia arriba). Cada glifo: lista de polilíneas.
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
    ":": [[(2, 1), (2, 1.25)], [(2, 4), (2, 4.25)]],
    "+": [[(2, 1), (2, 5)], [(0, 3), (4, 3)]],
    " ": [],
}
AVANCE = 5.5   # unidades de rejilla por carácter


def xf(x, y, ang, lx, ly):
    """Convención de KiCad: y hacia abajo, ángulo positivo = antihorario en pantalla."""
    a = math.radians(ang)
    return (x + lx * math.cos(a) + ly * math.sin(a),
            y - lx * math.sin(a) + ly * math.cos(a))


def trazos_texto(texto, x, y, h, ang=0, espejo=False):
    """Polilíneas (coordenadas de tarjeta) del texto centrado en (x, y)."""
    u = h / 6.0
    n = len(texto)
    ancho = ((n - 1) * AVANCE + 4) * u
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
    """forma: rect | circle | oval.  Tamaños y broca en x/y locales (los footprints van a 0°)."""

    def __init__(self, num, forma, lx, ly, tx, ty, bx, by=None, net=None, tipo="thru_hole"):
        self.num, self.forma, self.lx, self.ly = num, forma, lx, ly
        self.tx, self.ty = tx, ty
        self.bx, self.by = bx, (by if by is not None else bx)
        self.net, self.tipo = net, tipo

    @property
    def ranura(self):
        return abs(self.bx - self.by) > 1e-9


class Fp:
    def __init__(self, lib, ref, valor, x, y, descr="", attr="through_hole"):
        self.lib, self.ref, self.valor = lib, ref, valor
        self.x, self.y, self.ang = x, y, 0
        self.descr, self.attr = descr, attr
        self.pads, self.lineas, self.circulos = [], [], []
        self.ref_pos = (0, -2.5)
        self.val_pos = (0, 2.5)

    def xy(self, lx, ly):
        return xf(self.x, self.y, self.ang, lx, ly)

    def linea(self, capa, pts, w):
        for a, b in zip(pts, pts[1:]):
            self.lineas.append((capa, a, b, w))

    def rect(self, capa, x0, y0, x1, y1, w):
        self.linea(capa, [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], w)


def fp_socket_1x04(ref, x, y, nets, ranurado=False):
    """Header hembra 1x04 de 2.54 mm, pines de izquierda a derecha (pin 1 en el origen)."""
    if ranurado:
        lib = "DigDug:PinSocket_1x04_P2.54mm_Ranurado"
        descr = f"Header hembra 1x04 2.54mm, agujeros ranurados {RANURA_L}x1.0mm para autoalinear con el modulo"
    else:
        lib = "DigDug:PinSocket_1x04_P2.54mm_Horizontal"
        descr = "Header hembra 1x04 2.54mm, fila horizontal"
    f = Fp(lib, ref, "Header hembra 1x04 2.54mm", x, y, descr)
    for i in range(4):
        if ranurado:
            f.pads.append(Pad(str(i + 1), "rect" if i == 0 else "oval", i * PASO, 0, 1.8, RANURA_L + 0.8,
                              1.0, RANURA_L, nets[i]))
        else:
            f.pads.append(Pad(str(i + 1), "rect" if i == 0 else "circle", i * PASO, 0, 1.7, 1.7, 1.0, None, nets[i]))
    s = SILK_W
    hy = (RANURA_L + 0.8) / 2 + MASK_EXP + 0.25 if ranurado else 1.33
    x_fin = 3 * PASO + 1.33
    f.rect("F.SilkS", 1.27, -hy, x_fin, hy, s)                    # cuerpo (pines 2-4)
    f.linea("F.SilkS", [(-1.33, -hy), (-1.33, hy)], s)            # marca del pin 1
    f.linea("F.SilkS", [(-1.33, -hy), (0, -hy)], s)
    f.linea("F.SilkS", [(-1.33, hy), (0, hy)], s)
    f.rect("F.Fab", -1.27, -1.27, 3 * PASO + 1.27, 1.27, 0.1)
    f.rect("F.CrtYd", -1.8, -hy - 0.3, 3 * PASO + 1.8, hy + 0.3, 0.05)
    f.ref_pos, f.val_pos = (3.81, -hy - 1.2), (3.81, hy + 1.2)
    return f


def fp_bornera(ref, x, y, nets, frente):
    """Bornera de tornillo, paso 5.08 mm. frente = -1: cable entra por arriba (-y); +1: por abajo (+y)."""
    n = len(nets)
    P_ = BORNERA_P
    f = Fp(f"DigDug:Bornera_1x{n:02d}_P5.08mm", ref, f"Bornera {n} polos 5.08mm", x, y,
           f"Bornera de tornillo {n} polos, paso 5.0/5.08 mm (KF301, DG301, KF128, MKDS), broca {BORNERA_BROCA} mm")
    for i in range(n):
        f.pads.append(Pad(str(i + 1), "circle", i * P_, 0, BORNERA_PAD, BORNERA_PAD, BORNERA_BROCA, None, nets[i]))
    x0, x1 = -P_ / 2, (n - 1) * P_ + P_ / 2
    yf, yb = frente * BORNERA_FRENTE, -frente * BORNERA_ATRAS
    s = SILK_W
    f.rect("F.SilkS", x0, min(yf, yb), x1, max(yf, yb), s)          # cuerpo
    yl = yf - frente * 1.2                                           # labio de la entrada del cable
    f.linea("F.SilkS", [(x0, yl), (x1, yl)], s)
    for i in range(n):                                               # una boca por polo
        f.rect("F.SilkS", i * P_ - 1.4, min(yf, yl) + 0.35, i * P_ + 1.4, max(yf, yl) - 0.35, s)
    f.rect("F.Fab", x0, min(yf, yb), x1, max(yf, yb), 0.1)
    f.rect("F.CrtYd", x0 - 0.5, min(yf, yb) - 0.5, x1 + 0.5, max(yf, yb) + 0.5, 0.05)
    f.ref_pos, f.val_pos = ((n - 1) * P_ / 2, yb - frente * 1.2), ((n - 1) * P_ / 2, 0)
    return f


def fp_barreno_m3(ref, x, y):
    f = Fp("MountingHole:MountingHole_3.2mm_M3", ref, "Barreno M3", x, y,
           "Mounting Hole 3.2mm, no annular, M3", attr="exclude_from_pos_files exclude_from_bom")
    f.pads.append(Pad("", "circle", 0, 0, 3.2, 3.2, 3.2, None, None, "np_thru_hole"))
    f.circulos.append(("Cmts.User", 0, 0, 3.2, 0.15))
    f.circulos.append(("F.CrtYd", 0, 0, 3.45, 0.05))
    f.ref_pos, f.val_pos = (0, -4.2), (0, 4.2)
    return f


def construir():
    d = {"fps": [], "pistas": [], "silk": [], "textos": []}
    cols = [(i - 1.5) * PASO for i in range(4)]           # -3.81 -1.27 1.27 3.81
    y1, y2 = -S_FILAS / 2, S_FILAS / 2
    j_hy = (RANURA_L + 0.8) / 2 if RANURADOS else 0.85    # medio alto de los pads de J1/J2
    silk_hy = j_hy + MASK_EXP + 0.25 if RANURADOS else 1.33   # contorno de serigrafía de J1/J2
    y_mod0, y_mod1 = y1 - (silk_hy + 0.5), y2 + silk_hy + 0.5  # contorno del módulo
    h2 = TXT_H / 2 + SILK_W / 2
    y_etqT, y_etqB = y_mod0 - 0.4 - h2, y_mod1 + 0.4 + h2     # franja de etiquetas entre módulo y bornera
    yT = y_etqT - h2 - 0.4 - BORNERA_ATRAS                # pines de la bornera de arriba (Arduino y fuente)
    yB = y_etqB + h2 + 0.4 + BORNERA_ATRAS                # pines de la bornera de abajo (sensor)
    y_sup, y_inf = yT - BORNERA_FRENTE - 0.5, yB + BORNERA_FRENTE + 0.5   # bordes de la tarjeta
    x_izq, x_der = -ANCHO_PCB / 2, ANCHO_PCB / 2
    d.update(cols=cols, y1=y1, y2=y2, yT=yT, yB=yB, borde=(x_izq, y_sup, x_der, y_inf))

    # ---------- componentes ----------
    d["fps"].append(fp_socket_1x04("J1", cols[0], y1, J1_NETS, ranurado=RANURADOS))
    d["fps"].append(fp_socket_1x04("J2", cols[0], y2, J2_NETS, ranurado=RANURADOS))
    d["fps"].append(fp_bornera("J3", -BORNERA_P, yT, ["V_A0", "GND", "+24V"], -1))
    d["fps"].append(fp_bornera("J4", -BORNERA_P, yB, ["F_SENSOR", "+24V", "GND"], +1))
    h_off = 7.6
    if S_FILAS - 2 * h_off > 2 * 0.9:   # que quepan sin encimarse
        d["fps"].append(fp_barreno_m3("H1", 0, y1 + h_off))
        d["fps"].append(fp_barreno_m3("H2", 0, y2 - h_off))

    # ---------- pistas (capa, puntos, ancho, net) ----------
    P = d["pistas"]
    c = cols
    # V (J1.3) -> A0 de la bornera de arriba (J3.1)
    ya = y1 - 1.5
    P.append(("F.Cu", [(c[2], y1), (c[2], ya), (-BORNERA_P, ya - (c[2] + BORNERA_P)), (-BORNERA_P, yT)],
              PISTA_SENAL, "V_A0"))
    # GND de arriba (J3.2) -> J1.4 (además llega al plano de tierra de abajo)
    P.append(("F.Cu", [(0, yT), (0, ya - c[3]), (c[3], ya), (c[3], y1)], PISTA_POT, "GND"))
    # 24V de la fuente (J3.3) -> pin 24V del módulo (J2.3), por la orilla derecha
    xs, yh24 = 6.9, y2 - 1.5
    P.append(("F.Cu", [(BORNERA_P, yT), (xs, yT + (xs - BORNERA_P)), (xs, yh24 - (xs - c[2])), (c[2], yh24),
                       (c[2], y2)], PISTA_POT, "+24V"))
    # tierras del módulo unidas por abajo (J1.1, J1.4, J2.4)
    xg = 5.6
    yh = y1 + j_hy + 1.2                                  # unión de tierras, abajo de los pads de J1
    P.append(("B.Cu", [(c[3], y1), (xg, y1 + (xg - c[3])), (xg, yh)], PISTA_POT, "GND"))
    P.append(("B.Cu", [(xg, yh), (xg, y2 - (xg - c[3])), (c[3], y2)], PISTA_POT, "GND"))
    P.append(("B.Cu", [(c[0], y1), (c[0], yh), (xg, yh)], PISTA_POT, "GND"))
    # fila del sensor -> huecos de abajo
    yd = y2 + j_hy + 0.3                                  # las diagonales empiezan abajo de los pads
    P.append(("F.Cu", [(c[3], y2), (c[3], yd), (5.08, yd + (5.08 - c[3])), (5.08, yB)], PISTA_POT, "GND"))
    P.append(("F.Cu", [(c[2], y2), (c[2], yd), (0, yd + c[2]), (0, yB)], PISTA_POT, "+24V"))
    P.append(("F.Cu", [(c[1], y2), (c[1], yd), (-5.08, yd + (5.08 + c[1])), (-5.08, yB)], PISTA_SENAL, "F_SENSOR"))

    # ---------- serigrafía ----------
    S, T = d["silk"], d["textos"]
    mx = MOD_ANCHO / 2
    S.append(("F.SilkS", [(-mx, y_mod0), (mx, y_mod0), (mx, y_mod1), (-mx, y_mod1), (-mx, y_mod0)], SILK_W))
    for t, x in (("A0", -BORNERA_P), ("GND", 0), ("24V", BORNERA_P)):
        T.append(dict(t=t, x=x, y=y_etqT, h=TXT_H, capa="F.SilkS"))
    d_etq = silk_hy + 0.075 + 0.45 + 1.325                 # del centro de la fila al centro de la etiqueta
    for i in range(4):
        T.append(dict(t=J1_ETIQ[i], x=c[i], y=y1 + d_etq, h=TXT_H, capa="F.SilkS", ang=90))
        T.append(dict(t=J2_ETIQ[i], x=c[i], y=y2 - d_etq, h=TXT_H, capa="F.SilkS", ang=90))
    if RANURADOS:
        T.append(dict(t="SOLDAR J1-J2", x=0, y=-0.8, h=TXT_H, capa="F.SilkS"))
        T.append(dict(t="CON MODULO", x=0, y=0.8, h=TXT_H, capa="F.SilkS"))
    else:
        T.append(dict(t="MODULO F/V", x=0, y=0, h=TXT_H, capa="F.SilkS"))
    xj = -(mx + 0.075 + 0.4 + h2)                          # "J1"/"J2" junto al contorno del módulo
    T.append(dict(t="J1", x=xj, y=y1, h=TXT_H, capa="F.SilkS", ang=90))
    T.append(dict(t="J2", x=xj, y=y2, h=TXT_H, capa="F.SilkS", ang=90))
    for t, x in (("F", -BORNERA_P), ("24V", 0), ("GND", BORNERA_P)):
        T.append(dict(t=t, x=x, y=y_etqB, h=TXT_H, capa="F.SilkS"))
    # lado de abajo (texto en espejo, se lee bien viendo la tarjeta por debajo)
    y_bT, y_bB = yT - BORNERA_PAD / 2 - 1.0 - h2, yB + BORNERA_PAD / 2 + 1.0 + h2
    for t, x, y in (("ARDUINO/FUENTE", 0, y_bT), ("A0", -BORNERA_P, y_etqT), ("GND", 0, y_etqT), ("24V", BORNERA_P, y_etqT),
                    ("SENSOR", 0, y_bB), ("F", -BORNERA_P, y_etqB), ("24V", 0, y_etqB), ("GND", BORNERA_P, y_etqB),
                    ("DIG DUG", 0, -0.9), (f"BASE F/V V{REV}", 0, 0.9)):
        T.append(dict(t=t, x=x, y=y, h=TXT_H, capa="B.SilkS", espejo=True))
    return d


def contorno(d, seg_arco=12):
    """Polilínea cerrada del borde (esquinas redondeadas) y lista de primitivas para KiCad."""
    x0, y0, x1, y1 = d["borde"]
    r = R_ESQUINA
    k = r * math.sqrt(0.5)
    prim = [("line", (x0 + r, y0), (x1 - r, y0)),
            ("arc", (x1 - r, y0), (x1 - r + k, y0 + r - k), (x1, y0 + r)),
            ("line", (x1, y0 + r), (x1, y1 - r)),
            ("arc", (x1, y1 - r), (x1 - r + k, y1 - r + k), (x1 - r, y1)),
            ("line", (x1 - r, y1), (x0 + r, y1)),
            ("arc", (x0 + r, y1), (x0 + r - k, y1 - r + k), (x0, y1 - r)),
            ("line", (x0, y1 - r), (x0, y0 + r)),
            ("arc", (x0, y0 + r), (x0 + r - k, y0 + r - k), (x0 + r, y0))]
    pts = []
    for cx, cy, a0 in [(x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)]:
        for i in range(seg_arco + 1):
            a = math.radians(a0 + 90 * i / seg_arco)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    pts.append(pts[0])
    return prim, pts


# ======================= PLANO DE TIERRA (cara de abajo) =======================
def pads_abs(d):
    """Pads con posición absoluta (coordenadas de tarjeta)."""
    out = []
    for f in d["fps"]:
        for p in f.pads:
            cx, cy = f.xy(p.lx, p.ly)
            out.append(dict(ref=f"{f.ref}.{p.num}", forma=p.forma, cx=cx, cy=cy, tx=p.tx, ty=p.ty,
                            net=p.net, tipo=p.tipo, bx=p.bx))
    return out


def dist_pad(q, x, y):
    """Distancia de un punto al cobre del pad q (0 si cae adentro)."""
    dx, dy = abs(x - q["cx"]), abs(y - q["cy"])
    hx, hy = q["tx"] / 2, q["ty"] / 2
    if q["forma"] == "rect":
        return math.hypot(max(dx - hx, 0), max(dy - hy, 0))
    r = min(hx, hy)
    return max(math.hypot(max(dx - (hx - r), 0), max(dy - (hy - r), 0)) - r, 0)


def contorno_plano(d, seg_arco=8):
    x0, y0, x1, y1 = d["borde"]
    m = PLANO_BORDE
    x0, y0, x1, y1 = x0 + m, y0 + m, x1 - m, y1 - m
    r = max(R_ESQUINA - m, 0.2)
    pts = []
    for cx, cy, a0 in [(x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)]:
        for i in range(seg_arco + 1):
            a = math.radians(a0 + 90 * i / seg_arco)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    pts.append(pts[0])
    return pts, (x0, y0, x1, y1)


def rayos_termicos(d):
    """Rayos de los pads de GND al plano; se quitan los que pasarían cerca de cobre de otra net."""
    pads = pads_abs(d)
    _, (bx0, by0, bx1, by1) = contorno_plano(d)
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
            ok = bx0 + TERM_W / 2 <= ex <= bx1 - TERM_W / 2 and by0 + TERM_W / 2 <= ey <= by1 - TERM_W / 2
            ok = ok and all(math.hypot(ex - h["cx"], ey - h["cy"]) > KEEP_M3 + TERM_W / 2 for h in m3)
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
    a('    (title "Dig Dug - Base para convertidor F/V")')
    a(f'    (date "{FECHA}")')
    a(f'    (rev "{REV}")')
    nota = " J1/J2 ranurados: soldarlos con el modulo puesto." if RANURADOS else " (10 x 2.54 mm)"
    a(f'    (comment 1 "Filas del modulo a {fmt(S_FILAS)} mm.{nota}")')
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
        for capa, cx, cy, r, w in f.circulos:
            a(f'    (fp_circle (center {fmt(cx)} {fmt(cy)}) (end {fmt(cx + r)} {fmt(cy)})')
            a(f'      (stroke (width {fmt(w)}) (type solid)) (fill none) (layer "{capa}") (tstamp {uid()}))')
        for p in f.pads:
            pos = f"(at {fmt(p.lx)} {fmt(p.ly)})"
            tam = f"(size {fmt(p.tx)} {fmt(p.ty)})"
            broca = f"(drill oval {fmt(p.bx)} {fmt(p.by)})" if p.ranura else f"(drill {fmt(p.bx)})"
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
        if pr[0] == "line":
            a(f'  (gr_line (start {K(*pr[1])}) (end {K(*pr[2])})')
        else:
            a(f'  (gr_arc (start {K(*pr[1])}) (mid {K(*pr[2])}) (end {K(*pr[3])})')
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
            circ = " ".join(f"(xy {K(q['cx'] + KEEP_M3 * math.cos(2 * math.pi * i / 24), q['cy'] + KEEP_M3 * math.sin(2 * math.pi * i / 24))})"
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
        h = [f"%TF.GenerationSoftware,Claude,generar_pcb.py,{REV}*%",
             f"%TF.CreationDate,{FECHA}T00:00:00-06:00*%",
             f"%TF.ProjectId,{NOMBRE},{uuid.uuid5(uuid.NAMESPACE_URL, NOMBRE).hex},rev{REV}*%",
             "%TF.SameCoordinates,Original*%",
             f"%TF.FileFunction,{self.funcion}*%",
             f"%TF.FilePolarity,{self.polaridad}*%",
             "%FSLAX46Y46*%",
             "G04 Dig Dug - base para convertidor F/V*",
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

    def G_(x, y):              # coordenadas de tarjeta (y abajo) -> Gerber (y arriba, origen esquina inf. izq.)
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
        # 1) plano completo  2) se recorta alrededor de cobre ajeno, anillos térmicos y barrenos  3) cobre encima
        pts, _ = contorno_plano(d)
        bcu.region([G_(*p) for p in pts])
        bcu.lp(False)
        for q in pads_abs(d):
            gx, gy = G_(q["cx"], q["cy"])
            if q["tipo"] == "np_thru_hole":
                bcu.flash("circle", 2 * KEEP_M3, 2 * KEEP_M3, gx, gy)
            else:
                e = 2 * (TERM_GAP if q["net"] == "GND" else PLANO_CLR)
                bcu.flash(q["forma"], q["tx"] + e, q["ty"] + e, gx, gy)
        for capa, pts_, w, net in d["pistas"]:
            if capa == "B.Cu" and net != "GND":
                bcu.polilinea([G_(*p) for p in pts_], w + 2 * PLANO_CLR)
        bcu.lp(True)
    for f in d["fps"]:
        for p in f.pads:
            x, y = f.xy(p.lx, p.ly)
            gx, gy = G_(x, y)
            m = 2 * MASK_EXP
            if p.tipo == "np_thru_hole":
                npth.setdefault(p.bx, []).append((gx, gy, 0.0))
                for k in ("F_Mask", "B_Mask"):
                    capas[k].flash("circle", p.tx + m, p.ty + m, gx, gy)
                continue
            # ranura vertical: medio largo del recorrido de la broca (sin contar el radio)
            pth.setdefault(p.bx, []).append((gx, gy, (p.by - p.bx) / 2 if p.ranura else 0.0))
            for k in ("F_Cu", "B_Cu"):
                capas[k].flash(p.forma, p.tx, p.ty, gx, gy)
            for k in ("F_Mask", "B_Mask"):
                capas[k].flash(p.forma, p.tx + m, p.ty + m, gx, gy)
        for capa, p, q, w in f.lineas:
            if capa == "F.SilkS":
                capas["F_Silkscreen"].polilinea([G_(*f.xy(*p)), G_(*f.xy(*q))], w)
    for capa, pts, w, net in d["pistas"]:
        capas[capa.replace(".", "_")].polilinea([G_(*p) for p in pts], w)
    if PLANO_GND:
        for a_, b_ in rayos_termicos(d):
            bcu.polilinea([G_(*a_), G_(*b_)], TERM_W)
    for capa, pts, w in d["silk"]:
        capas["F_Silkscreen" if capa == "F.SilkS" else "B_Silkscreen"].polilinea([G_(*p) for p in pts], w)
    for t in d["textos"]:
        dest = capas["F_Silkscreen" if t["capa"] == "F.SilkS" else "B_Silkscreen"]
        for poli in trazos_texto(t["t"], t["x"], t["y"], t["h"], t.get("ang", 0), t.get("espejo", False)):
            dest.polilinea([G_(*p) for p in poli], SILK_W)
    _, pts = contorno(d)
    capas["Edge_Cuts"].polilinea([G_(*p) for p in pts], 0.1)

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
        lineas = ["M48", f"; DRILL file {{generar_pcb.py rev{REV}}} date {FECHA}",
                  "; FORMAT={-:-/ absolute / metric / decimal}",
                  f"; #@! TF.FileFunction,{tipo}", "FMAT,2", "METRIC"]
        orden = sorted(herramientas)
        for i, dia in enumerate(orden, 1):
            lineas.append(f"T{i}C{dia:.3f}")
        lineas += ["%", "G90", "G05"]
        for i, dia in enumerate(orden, 1):
            lineas.append(f"T{i}")
            for gx, gy, med in herramientas[dia]:
                if med > 0:     # ranura con comando de ruteo (como KiCad "use route command")
                    lineas += [f"G00X{gx:.4f}Y{gy + med:.4f}", "M15", f"G01X{gx:.4f}Y{gy - med:.4f}", "M16", "G05"]
                else:
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
    salida = os.path.join(aqui, "salida")
    os.makedirs(salida, exist_ok=True)
    gdir = os.path.join(salida, "gerbers")
    if os.path.isdir(gdir):
        for n in os.listdir(gdir):
            os.remove(os.path.join(gdir, n))
    d = construir()
    escribir_kicad(d, os.path.join(salida, f"{NOMBRE}.kicad_pcb"))
    archivos = escribir_gerbers(d, gdir)
    zip_ruta = os.path.join(salida, f"{NOMBRE}_gerbers.zip")
    with zipfile.ZipFile(zip_ruta, "w", zipfile.ZIP_DEFLATED) as z:
        for r in archivos:
            z.write(r, os.path.basename(r))
    x0, y0, x1, y1 = d["borde"]
    rango = f"  (J1/J2 ranurados: {S_FILAS - (RANURA_L - 0.9):.2f} a {S_FILAS + (RANURA_L - 0.9):.2f} mm)" if RANURADOS else ""
    print(f"Tarjeta: {x1 - x0:.1f} x {y1 - y0:.1f} mm   filas a {S_FILAS} mm{rango}")
    print(f"KiCad:   {os.path.join(salida, NOMBRE + '.kicad_pcb')}")
    print(f"Gerbers: {zip_ruta}")


if __name__ == "__main__":
    main()
