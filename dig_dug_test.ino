const int pinVerde = 7;
const int pinRojo  = 8;
const int pinCafe  = 9;

// NUEVO: pin de salida en el PLC Shield
const int pinSalida = 3;

// =====================================================================
// PARÁMETROS AJUSTABLES
// =====================================================================

// ---- Criterio de FAIL por flujo (fase de llenado = EN_PROCESO) ----
// La unidad pasa solo si durante el llenado el flujo se mantiene
// >= FLUJO_MINIMO de forma continua por al menos TIEMPO_FLUJO_MS.
// Si al terminar el llenado no se cumplió, se envía FAIL en lugar de PASS.
const float         FLUJO_MINIMO    = 1.4;     // flujo mínimo requerido
const unsigned long TIEMPO_FLUJO_MS = 10000;   // tiempo continuo requerido (10 s)

// ---- Conversión raw data (V) -> flujo ----
// Misma fórmula que logger.py (tipo 'flow_rate_new_sensor'):
//   frecuencia_Hz = (V - OFFSET_V) * ESCALA_HZ
//   flujo         = frecuencia_Hz * FACTOR_FLUJO
const float OFFSET_V     = 0.0057;
const float ESCALA_HZ    = 100.0;
const float FACTOR_FLUJO = 0.0058252314;  // estación SCP. BFT/IST: 0.005830904

// ---- Lectura del sensor (tarjeta F/V, salida V -> A0) ----
const int   PIN_V = A0;
// Mide con multímetro el pin 5V del Arduino y escribe aquí el valor real
// (ej. 4.96). De esto depende la exactitud de la lectura.
const float VREF  = 5.00;
const unsigned long INTERVALO_FLUJO_MS = 1000;  // una muestra por segundo
const int   LECTURAS_POR_CICLO = 4;             // lecturas de A0 en cada vuelta del loop

// =====================================================================

// Variables del sensor de flujo
unsigned long ultimoFlujo = 0;
long  sumaFlujo = 0;
int   muestrasFlujo = 0;
float flujoActual = 0.0;

// Variables del criterio de llenado
bool cicloActivo = false;          // true mientras dura la fase de llenado
bool flujoOK = false;              // true cuando ya se cumplió el criterio
bool flujoArriba = false;          // flujo actualmente >= FLUJO_MINIMO
unsigned long inicioFlujoArriba = 0;

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

float voltsAFlujo(float volts) {
  float frecuencia = (volts - OFFSET_V) * ESCALA_HZ;
  return frecuencia * FACTOR_FLUJO;
}

// Inicia la fase de llenado: reinicia el criterio de flujo
void iniciarCiclo(unsigned long ahora) {
  cicloActivo = true;
  flujoOK = false;
  flujoArriba = false;
  inicioFlujoArriba = ahora;
}

// Revisa con cada muestra si el flujo se ha sostenido el tiempo requerido
void evaluarFlujo(unsigned long ahora) {
  if (!cicloActivo || flujoOK) return;

  if (flujoActual >= FLUJO_MINIMO) {
    if (!flujoArriba) {
      flujoArriba = true;
      inicioFlujoArriba = ahora;
    }
    if (ahora - inicioFlujoArriba >= TIEMPO_FLUJO_MS) {
      flujoOK = true;
      Serial.println("FLUJO_OK");   // aviso a la app: criterio cumplido
    }
  } else {
    flujoArriba = false;  // se cayó el flujo: reinicia el conteo de 10 s
  }
}

// Acumula lecturas de A0 sin bloquear y cada INTERVALO_FLUJO_MS envía el promedio.
// Así la medición de flujo no retrasa la detección de parpadeo de los LEDs.
// Formato: DATA,<voltaje>,<flujo>   (logger.py sigue leyendo el voltaje igual)
void medirFlujo(unsigned long ahora) {
  for (int i = 0; i < LECTURAS_POR_CICLO; i++) {
    sumaFlujo += analogRead(PIN_V);
    muestrasFlujo++;
  }

  if (ahora - ultimoFlujo >= INTERVALO_FLUJO_MS && muestrasFlujo > 0) {
    ultimoFlujo = ahora;

    float volts = (sumaFlujo / (float)muestrasFlujo) * VREF / 1023.0;
    flujoActual = voltsAFlujo(volts);

    Serial.print("DATA,");
    Serial.print(volts, 4);
    Serial.print(",");
    Serial.println(flujoActual, 4);

    sumaFlujo = 0;
    muestrasFlujo = 0;

    evaluarFlujo(ahora);
  }
}

void enviar(String msg) {
  if (msg != "" && msg != lastMessage) {
    Serial.println(msg);
    lastMessage = msg;
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

  // ---- LÓGICA DE ESTADOS (según LEDs) ----
  String estadoLed = "";

  // PASS: Verde fijo sin cambios en 1 segundo
  if ((ahora - lastChangeVerde > 1000) && estadoVerde == HIGH && estadoRojo == LOW) {
    estadoLed = "PASS";
  }
  // EN PROCESO: Verde parpadeante
  else if ((ahora - lastChangeVerde <= 1000) && estadoRojo == LOW) {
    estadoLed = "EN_PROCESO";
  }
  // WARNING: Rojo parpadeante
  else if ((ahora - lastChangeRojo <= 1000) && estadoVerde == LOW) {
    estadoLed = "WARNING";
  }

  // ---- FASE DE LLENADO + CRITERIO DE FLUJO ----
  // Inicio del llenado (se ignora el primer segundo tras encender)
  if (estadoLed == "EN_PROCESO" && !cicloActivo && ahora > 1000) {
    iniciarCiclo(ahora);
  }

  if (estadoLed == "PASS" && cicloActivo) {
    // Termina el llenado: el resultado depende del flujo
    cicloActivo = false;
    if (!flujoOK) {
      // Alerta para la app antes del FAIL: revisar Supply tank
      Serial.println("ALERTA_SUPPLY_TANK");
    }
    enviar(flujoOK ? "PASS" : "FAIL");
  }
  else if (estadoLed == "PASS" && lastMessage == "FAIL") {
    // Ya se reportó FAIL en este ciclo: no enviar PASS hasta el siguiente llenado
  }
  else {
    enviar(estadoLed);
  }

  delay(50);
}
