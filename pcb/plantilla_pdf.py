#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Plantilla 1:1 para comprobar que el módulo cuadra con la base antes de mandarla a fabricar."""
import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generar_pcb as gp  # noqa: E402

d = gp.construir()
x0, y0, x1, y1 = d["borde"]
SAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "salida", f"{gp.NOMBRE}_plantilla_1a1.pdf")
c = canvas.Canvas(SAL, pagesize=letter)
PW, PH = letter
c.setTitle("Plantilla 1:1 - Base convertidor F/V")

# ---------- textos ----------
c.setFont("Helvetica-Bold", 15)
c.drawString(18 * mm, PH - 20 * mm, "Plantilla 1:1  -  Base para convertidor F/V (Dig Dug)")
c.setFont("Helvetica", 9.5)
rango = gp.RANURA_L - 0.9 if gp.RANURADOS else 0.0
if gp.RANURADOS:
    lineas = [
        f"Tarjeta: {x1 - x0:.1f} x {y1 - y0:.1f} mm.  J1 y J2 ranurados: sirve con filas de {gp.S_FILAS - rango:.1f} a {gp.S_FILAS + rango:.1f} mm.",
        "1. Imprime al 100 % (\"Tamaño real\"). NO uses \"Ajustar a la página\".",
        "2. Con una regla, revisa que la barra de 50 mm mida 50 mm.",
        "3. Pon el módulo encima (componentes hacia arriba, trimpots hacia ARDUINO): los 8 pines",
        "    deben caer dentro de las ranuras rojas de J1 (arriba) y J2 (abajo).",
        "4. Opcional: alinea la fila de arriba con el 0 de la regla y lee dónde cae la de abajo.",
    ]
else:
    lineas = [
        f"Tarjeta: {x1 - x0:.1f} x {y1 - y0:.1f} mm.  Distancia entre filas: {gp.S_FILAS} mm (centro a centro, 10 x 2.54 mm).",
        "1. Imprime al 100 % (\"Tamaño real\"). NO uses \"Ajustar a la página\".",
        "2. Con una regla, revisa que la barra de 50 mm mida 50 mm.",
        "3. Pon el módulo encima (componentes hacia arriba, trimpots hacia ARDUINO), o pícale el papel",
        "    con los pines de un módulo que ya tenga headers: los 8 pines deben caer en los círculos rojos.",
        "4. Si la fila de abajo no cae: alinea la de arriba con el 0 de la regla y lee dónde cae la de abajo.",
        "    Ese número es la distancia real entre filas; con él se ajusta la tarjeta antes de mandarla a hacer.",
    ]
for i, t in enumerate(lineas):
    c.drawString(18 * mm, PH - (29 + i * 5.2) * mm, t)

# ---------- tarjeta 1:1 ----------
k = mm
OXp, OYp = 50 * mm, PH - 100 * mm      # punto (0,0) de la tarjeta (centro del módulo)


def P(x, y):
    return OXp + x * k, OYp - y * k


c.setLineWidth(0.6)
c.setStrokeColorRGB(0, 0, 0)
_, pts = gp.contorno(d)
path = c.beginPath()
path.moveTo(*P(*pts[0]))
for p in pts[1:]:
    path.lineTo(*P(*p))
c.drawPath(path, stroke=1, fill=0)
# contorno aproximado del módulo
c.setDash(2, 2)
c.setLineWidth(0.4)
c.setStrokeColorRGB(0.35, 0.35, 0.35)
for capa, sp, w in d["silk"]:
    path = c.beginPath()
    path.moveTo(*P(*sp[0]))
    for p in sp[1:]:
        path.lineTo(*P(*p))
    c.drawPath(path, stroke=1, fill=0)
c.setDash()
# serigrafía de los footprints (cuerpo de borneras y conectores)
c.setStrokeColorRGB(0.45, 0.45, 0.45)
c.setLineWidth(0.3)
for f in d["fps"]:
    for capa, p, q, w in f.lineas:
        if capa == "F.SilkS":
            c.line(*P(*f.xy(*p)), *P(*f.xy(*q)))
# pistas (gris claro, solo referencia)
c.setStrokeColorRGB(0.75, 0.75, 0.75)
for capa, tp, w, net in d["pistas"]:
    c.setLineWidth(w * k)
    path = c.beginPath()
    path.moveTo(*P(*tp[0]))
    for p in tp[1:]:
        path.lineTo(*P(*p))
    c.drawPath(path, stroke=1, fill=0)
# pads y agujeros
c.setLineWidth(0.5)
for f in d["fps"]:
    for p in f.pads:
        x, y = f.xy(p.lx, p.ly)
        X, Y = P(x, y)
        es_modulo = f.ref in ("J1", "J2")
        if p.tipo == "np_thru_hole":
            c.setStrokeColorRGB(0, 0, 0)
            c.circle(X, Y, p.bx / 2 * k, stroke=1, fill=0)
            continue
        c.setStrokeColorRGB(0.8, 0, 0) if es_modulo else c.setStrokeColorRGB(0, 0, 0)
        if p.ranura:
            c.roundRect(X - p.bx / 2 * k, Y - p.by / 2 * k, p.bx * k, p.by * k, p.bx / 2 * k, stroke=1, fill=0)
        if p.forma == "rect":
            c.rect(X - p.tx / 2 * k, Y - p.ty / 2 * k, p.tx * k, p.ty * k, stroke=1, fill=0)
        elif p.forma == "oval":
            c.roundRect(X - p.tx / 2 * k, Y - p.ty / 2 * k, p.tx * k, p.ty * k, p.tx / 2 * k, stroke=1, fill=0)
        else:
            c.circle(X, Y, p.tx / 2 * k, stroke=1, fill=0)
        c.setFillColorRGB(0.8, 0, 0) if es_modulo else c.setFillColorRGB(0, 0, 0)
        if not p.ranura:
            c.circle(X, Y, 0.3 * k, stroke=0, fill=1)     # centro marcado
c.setFillColorRGB(0, 0, 0)
# etiquetas pequeñas
c.setFont("Helvetica", 5)
for t in d["textos"]:
    if t["capa"] != "F.SilkS":
        continue
    X, Y = P(t["x"], t["y"])
    if t.get("ang") == 90:
        c.saveState()
        c.translate(X, Y)
        c.rotate(90)
        c.drawCentredString(0, -1.8, t["t"])
        c.restoreState()
    else:
        c.drawCentredString(X, Y - 1.8, t["t"])
c.setFont("Helvetica-Bold", 7)
c.setFillColorRGB(0.8, 0, 0)
c.drawRightString(P(x0, d["y1"])[0] - 2 * mm, P(0, d["y1"])[1] - 2.5, "J1")
c.drawRightString(P(x0, d["y2"])[0] - 2 * mm, P(0, d["y2"])[1] - 2.5, "J2")
c.setFillColorRGB(0, 0, 0)

# ---------- regla de filas (0 en la fila de arriba) ----------
RX = P(x1, 0)[0] + 8 * mm
y_cero = P(0, d["y1"])[1]
c.setStrokeColorRGB(0, 0, 0)
c.setLineWidth(0.4)
c.line(RX, y_cero, RX, y_cero - 31 * mm)
c.setFont("Helvetica", 5.5)
for i in range(0, 62):
    v = i * 0.5
    Y = y_cero - v * mm
    if v < 20 and i % 2:
        continue                       # antes de 20 mm, solo cada 1 mm
    largo = 3.5 if i % 4 == 0 else (2.5 if i % 2 == 0 else 1.5)
    c.line(RX, Y, RX + largo * mm, Y)
    if v == 0 or (v >= 20 and i % 4 == 0):
        c.drawString(RX + 4.2 * mm, Y - 1.8, f"{v:.0f}")
# franja que cubren las ranuras de J2 y marca del valor nominal
if rango:
    c.setFillColorRGB(0.85, 0.85, 0.85)
    c.rect(RX - 1.5 * mm, y_cero - (gp.S_FILAS + rango) * mm, 1.5 * mm, 2 * rango * mm, stroke=0, fill=1)
    c.setFillColorRGB(0, 0, 0)
Yd = y_cero - gp.S_FILAS * mm
c.setStrokeColorRGB(0.8, 0, 0)
c.setLineWidth(0.5)
c.line(RX - 1.5 * mm, Yd, RX + 3.5 * mm, Yd)
c.setFillColorRGB(0.8, 0, 0)
c.setFont("Helvetica-Bold", 5.5)
c.drawString(RX + 9 * mm, Yd - 1.8, f"nominal: {gp.S_FILAS}")
c.setFillColorRGB(0, 0, 0)
c.setStrokeColorRGB(0, 0, 0)
c.setLineWidth(0.4)
c.setLineWidth(0.3)
c.setDash(1, 1.5)
c.line(P(x0, 0)[0], y_cero, RX, y_cero)
c.setDash()
c.setFont("Helvetica-Bold", 6.5)
c.drawString(RX + 1 * mm, y_cero + 2.5 * mm, "mm (fila de arriba = 0)")

# ---------- barras de escala ----------
BY = 42 * mm
c.setLineWidth(1)
c.line(18 * mm, BY, 68 * mm, BY)
for i in range(0, 51, 5):
    h = 3 if i % 10 == 0 else 1.8
    c.line(18 * mm + i * mm, BY, 18 * mm + i * mm, BY + h * mm)
c.setFont("Helvetica", 8)
c.drawString(18 * mm, BY - 4.5 * mm, "Esta barra debe medir 50 mm")
c.line(90 * mm, BY, 90 * mm + 25.4 * mm, BY)
c.line(90 * mm, BY, 90 * mm, BY + 3 * mm)
c.line(115.4 * mm, BY, 115.4 * mm, BY + 3 * mm)
c.drawString(90 * mm, BY - 4.5 * mm, "1 pulgada (25.4 mm)")

# ---------- referencia ampliada ----------
img = os.path.join(os.path.dirname(os.path.abspath(__file__)), "salida", "vista_top.png")
if os.path.exists(img):
    from reportlab.lib.utils import ImageReader
    ir = ImageReader(img)
    iw, ih = ir.getSize()
    h = 140 * mm
    w = h * iw / ih
    c.drawImage(ir, PW - 18 * mm - w, PH - 68 * mm - h, w, h)
    c.setFont("Helvetica", 8)
    c.drawCentredString(PW - 18 * mm - w / 2, PH - 72 * mm - h, "Referencia ampliada (no a escala)")

c.setFont("Helvetica", 7)
c.setFillColorRGB(0.4, 0.4, 0.4)
c.drawString(18 * mm, 14 * mm, f"{gp.NOMBRE} rev {gp.REV}  -  {gp.FECHA}  -  rojo: pines del módulo (J1/J2)")
c.showPage()
c.save()
print(SAL)
