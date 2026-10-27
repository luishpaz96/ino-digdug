#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hoja de prueba 1:1 para encontrar la distancia entre las dos filas de pines del módulo
sin vernier: se pone el módulo (con headers) sobre cada dibujo y se ve en cuál caen los 8 pines."""
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

DIST = [24.00, 24.25, 24.50, 24.75, 25.00, 25.20, 25.40, 25.60, 25.80, 26.00, 26.25, 26.50]
PASO = 2.54
SAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "salida", "Prueba_distancia_filas_1a1.pdf")

c = canvas.Canvas(SAL, pagesize=letter)
PW, PH = letter
c.setTitle("Prueba de distancia entre filas - modulo F/V")
c.setFont("Helvetica-Bold", 15)
c.drawString(15 * mm, PH - 18 * mm, "Prueba de distancia entre filas del módulo (escala 1:1)")
c.setFont("Helvetica", 9.5)
lineas = [
    "1. Imprime al 100 % (\"Tamaño real\", NO \"Ajustar a la página\") y revisa que la barra de abajo mida 50 mm.",
    "2. Toma un módulo que ya tenga los 2 headers macho y ponlo con los pines hacia la hoja (trimpots hacia ARRIBA).",
    "3. En cada dibujo, pon los 4 pines de arriba en los 4 círculos de arriba y presiona tantito para que piquen el papel.",
    "4. El dibujo bueno es en el que los 4 pines de ABAJO caen justo en el centro de los círculos de abajo.",
    "    Mándame el número de ese dibujo (si queda entre dos, dime los dos).",
]
for i, t in enumerate(lineas):
    c.drawString(15 * mm, PH - (27 + i * 5) * mm, t)

cols, ancho_celda, alto_celda = 4, 46 * mm, 44 * mm
x_ini, y_ini = 15 * mm + 23 * mm, PH - 62 * mm
for n, S in enumerate(DIST):
    fila, col = divmod(n, cols)
    cx = x_ini + col * ancho_celda                 # centro horizontal del dibujo
    y_top = y_ini - fila * alto_celda               # fila de pines de arriba
    y_bot = y_top - S * mm
    # contorno aproximado del módulo
    c.setDash(1.5, 1.5)
    c.setLineWidth(0.3)
    c.setStrokeColorRGB(0.6, 0.6, 0.6)
    c.rect(cx - 6.1 * mm, y_bot - 1.9 * mm, 12.2 * mm, (S + 3.8) * mm, stroke=1, fill=0)
    c.setDash()
    for yy in (y_top, y_bot):
        for i in range(4):
            x = cx + (i - 1.5) * PASO * mm
            c.setStrokeColorRGB(0.8, 0, 0)
            c.setLineWidth(0.35)
            c.circle(x, yy, 0.5 * mm, stroke=1, fill=0)          # círculo de 1.0 mm
            c.setStrokeColorRGB(0, 0, 0)
            c.setLineWidth(0.12)
            c.line(x - 1.1 * mm, yy, x + 1.1 * mm, yy)           # cruz al centro
            c.line(x, yy - 1.1 * mm, x, yy + 1.1 * mm)
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 6)
    c.drawCentredString(cx, y_top + 2.6 * mm, "ARRIBA")
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(cx, y_bot - 6.2 * mm, f"{n + 1}:  {S:.2f} mm")

BY = 18 * mm
c.setLineWidth(1)
c.line(15 * mm, BY, 65 * mm, BY)
for i in range(0, 51, 5):
    c.line(15 * mm + i * mm, BY, 15 * mm + i * mm, BY + (3 if i % 10 == 0 else 1.8) * mm)
c.setFont("Helvetica", 8)
c.drawString(15 * mm, BY - 4.5 * mm, "Esta barra debe medir 50 mm")
c.drawString(90 * mm, BY - 4.5 * mm, "Paso entre pines: 2.54 mm.  Círculos de 1.0 mm (el pin mide 0.64 mm).")
c.showPage()
c.save()
print(SAL)
