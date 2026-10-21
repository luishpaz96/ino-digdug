const int pinVerde = 7;
const int pinRojo  = 8;
const int pinCafe  = 9;

// NUEVO: pin de salida en el PLC Shield
const int pinSalida = 3;

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

void loop() {
  int estadoVerde = digitalRead(pinVerde);
  int estadoRojo  = digitalRead(pinRojo);
  int estadoCafe  = digitalRead(pinCafe); // ✅ Leer pin café

  // ✅ Copiar estado del pin café a la salida
  digitalWrite(pinSalida, estadoCafe);

  unsigned long ahora = millis();

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
