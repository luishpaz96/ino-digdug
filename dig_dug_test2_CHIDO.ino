bool failForzadoEmitido = false;

unsigned long tiempoInicioProceso = 0;
unsigned long tiempoStandbyFinal = 0;

bool huboProceso = false;
bool esperandoPassFinal = false;

const unsigned long TIEMPO_MIN_PROCESO = 5000;   // ms
const unsigned long TIEMPO_ESTABLE_PASS = 3000;  // ms


// ======================================================
// CONFIGURACIÓN DE PINES
// ======================================================
const int pinVerde  = 7;   // Torreta verde
const int pinRojo   = 8;   // Torreta roja
const int pinEnable = 3;   // SALIDA: simula sensor / interlock Dig Dug

// ======================================================
// SENSOR DE FLUJO (F/V A0)
// ======================================================
const int   PIN_V              = A0;
const float VREF               = 5.00;
const unsigned long INTERVALO_FLUJO_MS = 1000;
const int   PROMEDIOS          = 64;
unsigned long ultimoFlujo      = 0;

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
    }
    else if (cmd == "DISABLE") {
      digitalWrite(pinEnable, LOW);    // ✅ forzar FAIL
    }
  }

  // --------------------------------------------------
  // SENSOR DE FLUJO (cada 1s envía DATA,<volts>)
  // --------------------------------------------------
  if (millis() - ultimoFlujo >= INTERVALO_FLUJO_MS) {
    ultimoFlujo = millis();

    long suma = 0;
    for (int i = 0; i < PROMEDIOS; i++) {
      suma += analogRead(PIN_V);
      delay(2);
    }
    float volts = (suma / (float)PROMEDIOS) * VREF / 1023.0;

    Serial.print("DATA,");
    Serial.println(volts, 4);
  }

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
  // FAIL REAL → rojo parpadeante
  if (rojo == HIGH && verde == LOW && dtRojo <= BLINK_THRESHOLD) {
    return PATRON_FAIL;
  }

  // EN PROCESO → verde parpadeante
  if (verde == HIGH && rojo == LOW && dtVerde <= BLINK_THRESHOLD) {
    return PATRON_EN_PROCESO;
  }

  // STANDBY o PASS → verde fijo
  if (verde == HIGH && rojo == LOW && dtVerde > BLINK_THRESHOLD) {
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
      // Solo se puede salir si aparece verde fijo
      if (p == PATRON_STANDBY) {
        estadoActual = EST_STANDBY;
      }
      break;



    case EST_STANDBY:
      if (p == PATRON_EN_PROCESO) {
        estadoActual = EST_EN_PROCESO;
        tiempoInicioProceso = millis();
        huboProceso = true;
        esperandoPassFinal = false;

        failForzadoEmitido = false;  // ✅ CLAVE
      }
      break;

    case EST_EN_PROCESO:

      // FAIL real inmediato
      if (p == PATRON_FAIL) {
        estadoActual = EST_FAIL;
        huboProceso = false;
        esperandoPassFinal = false;
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
          estadoActual = EST_PASS;   // ✅ PASS REAL
          esperandoPassFinal = false;
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