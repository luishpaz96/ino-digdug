// Lectura de la tarjeta F/V (salida V -> A0)
// Envía por serie solo el voltaje crudo, una línea por muestra:  DATA,<voltaje>
// La conversión a Hz y a flujo la hace logger.py, igual que data_logging.py
// del equipo de pruebas (tipo 'flow_rate_new_sensor').
//Subir sin cerrar sesion
//sudo chmod a+rw /dev/ttyACM0
const int   PIN_V        = A0;
// Mide con multímetro el pin 5V del Arduino y escribe aquí el valor real
// (ej. 4.96). De esto depende la exactitud de la lectura.
const float VREF         = 5.00;
const unsigned long INTERVALO_MS = 1000;  // una muestra por segundo
const int   PROMEDIOS    = 64;

unsigned long ultimo = 0;

void setup() {
  Serial.begin(9600);
}

void loop() {
  if (millis() - ultimo < INTERVALO_MS) return;
  ultimo = millis();

  long suma = 0;
  for (int i = 0; i < PROMEDIOS; i++) {
    suma += analogRead(PIN_V);
    delay(2);
  }
  float volts = (suma / (float)PROMEDIOS) * VREF / 1023.0;

  Serial.print("DATA,");
  Serial.println(volts, 4);
}
