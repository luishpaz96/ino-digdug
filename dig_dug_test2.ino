
// ======================================================
// DIG DUG TESTER - ARDUINO (sketch de prueba)
// + sensor de flujo en A0 y condición de PASS por volumen llenado
//
// Envía por serial:
//   FAIL / STANDBY / EN_PROCESO / PASS   estado del proceso (solo cuando cambia)
//   DATA,<voltaje>,<flujo>,<volumen_ml>  una muestra por segundo (volumen acumulado del ciclo)
//   VOLUMEN_OK                           se alcanzó VOLUMEN_MINIMO_ML
//   ALERTA_SUPPLY_TANK                   NO se alcanzó (se envía justo antes del FAIL)
//   DEBUG ...                            mensajes de depuración (la app los ignora)
// Recibe:
//   ENABLE / DISABLE
//   MODO_TEST   (después de ENABLE, serial "test"): se omite la condición de volumen
// ======================================================

// ======================================================
// PARÁMETROS DE FLUJO Y VOLUMEN (AJUSTABLES)
// ======================================================

// ---- Condición de PASS por volumen (drenado/llenado = EN_PROCESO) ----
// La unidad pasa solo si durante el proceso se llenan al menos VOLUMEN_MINIMO_ML.
// Si al terminar no se alcanzó, se envía ALERTA_SUPPLY_TANK y FAIL en lugar de PASS.
const float VOLUMEN_MINIMO_ML = 355.0;   // ml
const float FLUJO_RUIDO_LMIN  = 0.05;    // L/min. Flujos menores no se suman (ruido en el drenado)

// ---- Conversión raw data (V) -> flujo (misma fórmula que logger.py) ----
//   frecuencia_Hz = (V - OFFSET_V) * ESCALA_HZ
//   flujo         = frecuencia_Hz * FACTOR_FLUJO      (L/min)
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

// ---- Variables del sensor de flujo y volumen ----
unsigned long ultimoFlujo = 0;
long  sumaFlujo = 0;
int   muestrasFlujo = 0;
float flujoActual = 0.0;

bool  criterioActivo = false;       // true durante EN_PROCESO (se acumula volumen)
float volumenMl = 0.0;              // ml llenados en el ciclo
bool  volumenOK = false;            // true cuando volumenMl >= VOLUMEN_MINIMO_ML
bool  modoTest = false;             // serial "test": se omite la condición de volumen
bool  bloqueoFallaVolumen = false;  // tras FAIL por volumen, no salir de FAIL hasta el siguiente ENABLE

// ======================================================

bool failForzadoEmitido = false;

unsigned long tiempoInicioProceso = 0;
unsigned long tiempoStandbyFinal = 0;

bool huboProceso = false;
bool esperandoPassFinal = false;

const unsigned long TIEMPO_MIN_PROCESO = 5000;   // ms
const unsigned long TIEMPO_ESTABLE_PASS = 3000;  // ms

// ======================================================
// DETECCIÓN DE PARPADEO REAL
// ======================================================
int cambiosVerde = 0;
unsigned long ultimoCambioVerde = 0;

const int CAMBIOS_MIN_PROCESO = 3;
const unsigned long VENTANA_PARPADEO = 4000;


// ======================================================
// CONFIGURACIÓN DE PINES
// ======================================================
const int pinVerde  = 7;   // Torreta verde
const int pinRojo   = 8;   // Torreta roja
const int pinEnable = 2;   // SALIDA: simula sensor / interlock Dig Dug

// ======================================================
// CONSTANTES DE TIEMPO
// ======================================================
const unsigned long BLINK_THRESHOLD = 1000; // ms para detectar parpadeo
const unsigned long LOOP_DELAY = 50;         // ms

// ======================================================
// VARIABLES PARA DETECTAR PARPADEO
// ======================================================
unsigned long lastChangeVerde = 0;
unsigned long lastChangeRojo  = 0;

int lastStateVerde = LOW;
int lastStateRojo  = LOW;

// ======================================================
// ESTADOS DEL PROCESO (MÁQUINA DE ESTADOS)
// ======================================================
enum ProcesoEstado {
  EST_FAIL,        // Rojo parpadeante o FAIL forzado
  EST_STANDBY,     // Verde fijo (antes de proceso)
  EST_EN_PROCESO,  // Verde parpadeante
  EST_PASS         // Verde fijo (después de proceso)
};

ProcesoEstado estadoActual = EST_FAIL;
ProcesoEstado ultimoEstadoEnviado = EST_FAIL;

// ======================================================
// PATRONES DE TORRETA
// ======================================================
enum PatronFoco {
  PATRON_NONE,
  PATRON_FAIL,
  PATRON_STANDBY,
  PATRON_EN_PROCESO
};

// ======================================================
// SENSOR DE FLUJO Y VOLUMEN
// ======================================================
float voltsAFlujo(float volts) {
  float frecuencia = (volts - OFFSET_V) * ESCALA_HZ;
  float flujo = frecuencia * FACTOR_FLUJO;
  return (flujo < 0) ? 0.0 : flujo;   // sin flujo negativo por el offset del sensor
}

// Inicio del drenado/llenado: volumen del ciclo en cero
void iniciarCriterioVolumen() {
  criterioActivo = true;
  volumenOK = false;
  volumenMl = 0.0;
}

// Suma el volumen de la última muestra (flujo promedio x duración de la ventana).
// Regresa true justo cuando se alcanza VOLUMEN_MINIMO_ML.
bool acumularVolumen(unsigned long ventanaMs) {
  if (!criterioActivo) return false;

  if (flujoActual > FLUJO_RUIDO_LMIN) {
    volumenMl += flujoActual * ventanaMs / 60.0;   // L/min x ms -> ml
  }

  if (!volumenOK && volumenMl >= VOLUMEN_MINIMO_ML) {
    volumenOK = true;
    return true;
  }
  return false;
}

// Acumula lecturas de A0 sin bloquear y cada INTERVALO_FLUJO_MS envía el promedio.
// Así la medición no retrasa la lectura de la torreta ni de los comandos.
void medirFlujo(unsigned long ahora) {
  for (int i = 0; i < LECTURAS_POR_CICLO; i++) {
    sumaFlujo += analogRead(PIN_V);
    muestrasFlujo++;
  }

  unsigned long ventana = ahora - ultimoFlujo;
  if (ventana < INTERVALO_FLUJO_MS) return;
  ultimoFlujo = ahora;

  float volts = (sumaFlujo / (float)muestrasFlujo) * VREF / 1023.0;
  flujoActual = voltsAFlujo(volts);
  sumaFlujo = 0;
  muestrasFlujo = 0;

  bool alcanzado = acumularVolumen(ventana);

  Serial.print("DATA,");
  Serial.print(volts, 4);
  Serial.print(",");
  Serial.print(flujoActual, 4);
  Serial.print(",");
  Serial.println(volumenMl, 1);

  if (alcanzado) {
    Serial.println("VOLUMEN_OK");   // aviso a la app: ya se llenó el mínimo
  }
}

// ======================================================
// SETUP
// ======================================================
void setup() {
  Serial.begin(9600);

  pinMode(pinVerde, INPUT);
  pinMode(pinRojo, INPUT);

  pinMode(pinEnable, OUTPUT);

  // 🔒 FAIL FORZADO AL ARRANCAR
  digitalWrite(pinEnable, LOW);
  estadoActual = EST_FAIL;
  enviarEstadoSerial();
}

// ======================================================
// LOOP PRINCIPAL
// ======================================================
void loop() {

  // --------------------------------------------------
  // 0. COMANDOS SERIAL (HABILITAR / BLOQUEAR)
  // --------------------------------------------------
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "ENABLE") {
      digitalWrite(pinEnable, HIGH);
      //Serial.println("ENABLED_OK");
      failForzadoEmitido = false;  // ✅ preparar siguiente ciclo
      bloqueoFallaVolumen = false; // ✅ nueva unidad: ya puede volver a STANDBY
      modoTest = false;            // ✅ cada unidad empieza en modo normal
    }
    else if (cmd == "MODO_TEST") {
      modoTest = true;             // ✅ serial "test": PASS sin condición de volumen
    }
    else if (cmd == "DISABLE") {
      digitalWrite(pinEnable, LOW);    // ✅ forzar FAIL
    }
  }

  // --------------------------------------------------
  // SENSOR DE FLUJO (cada 1 s envía DATA,<volts>,<flujo>,<volumen>)
  // --------------------------------------------------
  medirFlujo(millis());

  // --------------------------------------------------
  // 1. LEER TORRETAS
  // --------------------------------------------------
  int estadoVerde = digitalRead(pinVerde);
  int estadoRojo  = digitalRead(pinRojo);

  unsigned long ahora = millis();

  // --------------------------------------------------
  // 2. DETECTAR CAMBIOS (PARPADEO)
  // --------------------------------------------------
  if (estadoVerde != lastStateVerde) {

    unsigned long ahora = millis();

    if ((ahora - ultimoCambioVerde) <= VENTANA_PARPADEO) {
      cambiosVerde++;
    }
    else {
      cambiosVerde = 1;
    }

    ultimoCambioVerde = ahora;

    lastChangeVerde = ahora;
    lastStateVerde = estadoVerde;
  }

  if (estadoRojo != lastStateRojo) {
    lastChangeRojo = ahora;
    lastStateRojo = estadoRojo;
  }

  unsigned long dtVerde = ahora - lastChangeVerde;
  unsigned long dtRojo  = ahora - lastChangeRojo;

  // --------------------------------------------------
  // 3. INTERLOCK: ¿PIN ENABLE ACTIVO?
  // --------------------------------------------------

  if (digitalRead(pinEnable) == LOW) {
    estadoActual = EST_FAIL;
    criterioActivo = false;

    if (!failForzadoEmitido) {
      ultimoEstadoEnviado = (ProcesoEstado)-1; // fuerza emisión
      enviarEstadoSerial();                    // 🔔 FAIL UNA SOLA VEZ
      failForzadoEmitido = true;
    }

    delay(LOOP_DELAY);
    return;
  }


  // --------------------------------------------------
  // 4. DETECTAR PATRÓN DE TORRETA
  // --------------------------------------------------
  PatronFoco patron = detectarPatron(
    estadoVerde,
    estadoRojo,
    dtVerde,
    dtRojo
  );

  // --------------------------------------------------
  // 5. MÁQUINA DE ESTADOS
  // --------------------------------------------------
  if (patron != PATRON_NONE) {
    procesarPatron(patron);
  }

  // --------------------------------------------------
  // 6. ENVIAR ESTADO POR SERIAL
  // --------------------------------------------------
  enviarEstadoSerial();

  delay(LOOP_DELAY);
}

// ======================================================
// DETECCIÓN DE PATRÓN DE TORRETA
// ======================================================
PatronFoco detectarPatron(
  int verde,
  int rojo,
  unsigned long dtVerde,
  unsigned long dtRojo
) {

  // FAIL REAL
  if (rojo == HIGH && verde == LOW) {

    cambiosVerde = 0;

    return PATRON_FAIL;
  }

  // EN PROCESO:
  // requiere múltiples cambios reales del foco verde
  if (verde == HIGH &&
      rojo == LOW &&
      cambiosVerde >= CAMBIOS_MIN_PROCESO &&
      (millis() - ultimoCambioVerde) < 2500)
  {
      return PATRON_EN_PROCESO;
  }

  // STANDBY / PASS:
  // verde encendido sin suficientes cambios
  if (verde == HIGH && rojo == LOW) {

    return PATRON_STANDBY;
  }

  return PATRON_NONE;
}

// ======================================================
// LÓGICA DE SECUENCIA DEL DIG DUG
// ======================================================
void procesarPatron(PatronFoco p) {

  switch (estadoActual) {

    case EST_FAIL:
      // Solo se puede salir si aparece verde fijo.
      // Tras un FAIL por volumen la torreta sigue en verde fijo: esperar al siguiente ENABLE.
      if (p == PATRON_STANDBY && !bloqueoFallaVolumen) {
        estadoActual = EST_STANDBY;
      }
      break;



    case EST_STANDBY:

      if (p == PATRON_EN_PROCESO) {

        Serial.print("DEBUG EN_PROCESO dtVerde=");
        Serial.println(millis() - lastChangeVerde);

        estadoActual = EST_EN_PROCESO;

        tiempoInicioProceso = millis();

        huboProceso = true;

        esperandoPassFinal = false;

        failForzadoEmitido = false;

        iniciarCriterioVolumen();   // ✅ empieza a contar el volumen
      }

      break;

    case EST_EN_PROCESO:

      // FAIL real inmediato
      if (p == PATRON_FAIL) {
        estadoActual = EST_FAIL;
        huboProceso = false;
        esperandoPassFinal = false;
        criterioActivo = false;
        break;
      }

      // Verde fijo posible final
      if (p == PATRON_STANDBY) {

        // 1️⃣ ¿Duró suficiente el proceso?
        if (millis() - tiempoInicioProceso < TIEMPO_MIN_PROCESO) {
          break;  // ignorar verde fijo prematuro
        }

        // 2️⃣ Primera detección de posible PASS
        if (!esperandoPassFinal) {
          tiempoStandbyFinal = millis();
          esperandoPassFinal = true;
          break;
        }

        // 3️⃣ ¿Fue estable?
        if (millis() - tiempoStandbyFinal >= TIEMPO_ESTABLE_PASS) {
          esperandoPassFinal = false;
          criterioActivo = false;

          // 4️⃣ ¿Se llenó el volumen mínimo? (en modo test no se revisa)
          if (volumenOK || modoTest) {
            Serial.println("DEBUG -> PASS");
            estadoActual = EST_PASS;   // ✅ PASS REAL
          } else {
            Serial.println("ALERTA_SUPPLY_TANK");
            estadoActual = EST_FAIL;   // ❌ FAIL POR VOLUMEN
            bloqueoFallaVolumen = true;
          }
        }
      }
      else {
        // Si vuelve a parpadear, cancelar intento de PASS
        esperandoPassFinal = false;
      }

      break;

    case EST_PASS:
      // Se queda en PASS hasta nuevo FAIL
      if (p == PATRON_FAIL) {
        estadoActual = EST_FAIL;
      }
      break;
  }
}

// ======================================================
// ENVÍO DE ESTADO POR SERIAL (SOLO SI CAMBIA)
// ======================================================
void enviarEstadoSerial() {
  if (estadoActual != ultimoEstadoEnviado) {

    switch (estadoActual) {
      case EST_FAIL:
        Serial.println("FAIL");
        break;

      case EST_STANDBY:
        Serial.println("STANDBY");
        break;

      case EST_EN_PROCESO:
        Serial.println("EN_PROCESO");
        break;

      case EST_PASS:
        Serial.println("PASS");
        break;
    }

    ultimoEstadoEnviado = estadoActual;
  }
}