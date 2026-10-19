const int pinVerde = 7;
const int pinRojo  = 8;
const int pinCafe  = 9;

// NUEVO: pin de salida en el PLC Shield
const int pinSalida = 3;

// ---- SENSOR DE FLUJO (tarjeta F/V, salida V -> A0) ----
// Envía por serie solo el voltaje crudo, una línea por muestra:  DATA,<voltaje>
// La conversión a Hz y a flujo la hace logger.py.
const int   PIN_V = A0;
// Mide con multímetro el pin 5V del Arduino y escribe aquí el valor real
// (ej. 4.96). De esto depende la exactitud de la lectura.
const float VREF  = 5.00;
const unsigned long INTERVALO_FLUJO_MS = 1000;  // una muestra por segundo
const int   LECTURAS_POR_CICLO = 4;             // lecturas de A0 en cada vuelta del loop

unsigned long ultimoFlujo = 0;
long sumaFlujo = 0;
int  muestrasFlujo = 0;

// Variables para detectar parpadeo
unsigned long lastChangeVerde = 0;
unsigned long lastChangeRojo = 0;

int lastStateVerde = LOW;
int lastStateRojo = LOW;

// Estado previo enviado
String lastMessage = "";

void setup() {
  Serial.begin(9600);

  pinMode(pinVerde, INPUT);
  pinMode(pinRojo, INPUT);
  pinMode(pinCafe, INPUT);    // ✅ Entrada café
  pinMode(pinSalida, OUTPUT); // ✅ Salida PLC
}

// Acumula lecturas de A0 sin bloquear y cada INTERVALO_FLUJO_MS envía el promedio.
// Así la medición de flujo no retrasa la detección de parpadeo de los LEDs.
void medirFlujo(unsigned long ahora) {
  for (int i = 0; i < LECTURAS_POR_CICLO; i++) {
    sumaFlujo += analogRead(PIN_V);
    muestrasFlujo++;
  }

  if (ahora - ultimoFlujo >= INTERVALO_FLUJO_MS && muestrasFlujo > 0) {
    ultimoFlujo = ahora;

    float volts = (sumaFlujo / (float)muestrasFlujo) * VREF / 1023.0;
    Serial.print("DATA,");
    Serial.println(volts, 4);

    sumaFlujo = 0;
    muestrasFlujo = 0;
  }
}

void loop() {
  int estadoVerde = digitalRead(pinVerde);
  int estadoRojo  = digitalRead(pinRojo);
  int estadoCafe  = digitalRead(pinCafe); // ✅ Leer pin café

  // ✅ Copiar estado del pin café a la salida
  digitalWrite(pinSalida, estadoCafe);

  unsigned long ahora = millis();

  // ✅ Medición del sensor de flujo en A0
  medirFlujo(ahora);

  // Detectar cambios (parpadeo)
  if (estadoVerde != lastStateVerde) {
    lastChangeVerde = ahora;
    lastStateVerde = estadoVerde;
  }

  if (estadoRojo != lastStateRojo) {
    lastChangeRojo = ahora;
    lastStateRojo = estadoRojo;
  }

  // ---- LÓGICA DE ESTADOS ----
  String currentMessage = "";

  // PASS: Verde fijo sin cambios en 1 segundo
  if ((ahora - lastChangeVerde > 1000) && estadoVerde == HIGH && estadoRojo == LOW) {
    currentMessage = "PASS";
  }
  // EN PROCESO: Verde parpadeante
  else if ((ahora - lastChangeVerde <= 1000) && estadoRojo == LOW) {
    currentMessage = "EN_PROCESO";
  }
  // WARNING: Rojo parpadeante
  else if ((ahora - lastChangeRojo <= 1000) && estadoVerde == LOW) {
    currentMessage = "WARNING";
  }
  else {
    currentMessage = "";
  }

  // --- Enviar solo cuando cambia el estado lógico ---
  if (currentMessage != "" && currentMessage != lastMessage) {
    Serial.println(currentMessage);
    lastMessage = currentMessage;
  }

  delay(50);
}
