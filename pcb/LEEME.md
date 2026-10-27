# PCB del convertidor F/V (Dig Dug)

Dos tarjetas para montar el módulo convertidor frecuencia/voltaje (LM331). Cada una se genera
con un script de Python, sin necesidad de KiCad.

## Shield formato Arduino Uno (`generar_shield.py`, rev 3)

Pila: Arduino Uno (abajo) → shield de relevadores 24V (en medio) → este shield (arriba).

- Headers apilables en las posiciones del Uno R3; la salida V del módulo va directo a A0.
- J1/J2: headers hembra 1x4 para el módulo (filas a 25.4 mm).
- J3: bornera del sensor (F, 24V, GND). J4: bornera de alimentación (24V, GND), encima de la
  bornera Vin del shield de relevadores.
- Protección de la entrada de 24V: F1 portafusible 5x20 **o** F2 PTC (se instala solo uno).
  D1 TVS opcional (P6KE33A).
- Cara de abajo: plano de tierra.

Archivos en `salida_shield/`:

| Archivo | Para qué |
|---|---|
| `DigDug_Shield_FV_gerbers.zip` | Subir tal cual a JLCPCB / PCBWay |
| `DigDug_Shield_FV.kicad_pcb` | Abrir y editar en KiCad 7 o más nuevo |
| `DigDug_Shield_FV_vista.png` | Vista previa de arriba y de abajo |
| `gerbers/` | Los mismos Gerbers y drill, sin comprimir |

## Base pequeña (`generar_pcb.py`, rev 6)

Tarjeta de 17 x 54 mm con J1/J2 para el módulo, bornera de 3 arriba (A0, GND, 24V) y bornera
de 3 abajo (F, 24V, GND). Archivos en `salida/`:

- Gerbers en `DigDug_Base_FV_gerbers.zip`
- Proyecto KiCad en `DigDug_Base_FV.kicad_pcb`
- Vista previa en `DigDug_Base_FV_vista.png`
- Plantilla 1:1 para imprimir, en `DigDug_Base_FV_plantilla_1a1.pdf` (la genera `plantilla_pdf.py`)
- Prueba de distancia entre filas, en `Prueba_distancia_filas_1a1.pdf` (la genera `prueba_distancia.py`)

## Regenerar

```
pip install reportlab          # solo para los PDF
python3 generar_shield.py      # -> salida_shield/
python3 generar_pcb.py         # -> salida/
python3 plantilla_pdf.py       # -> salida/DigDug_Base_FV_plantilla_1a1.pdf
```

Las medidas y posiciones se cambian en la sección `PARÁMETROS` al inicio de cada script.
