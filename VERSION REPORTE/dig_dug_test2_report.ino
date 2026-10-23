
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

const int   PIN_V              = A0;
const float VREF               = 5.00;
const unsigned long INTERVALO_FLUJO_MS = 1000;
const int   PROMEDIOS          = 64;
unsigned long ultimoFlujo      = 0;
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
      // Solo se puede salir si aparece verde fijo
      if (p == PATRON_STANDBY) {
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
          Serial.println("DEBUG -> PASS");
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