/*
 * Etapa 3 - Gateway IoT
 * Firmware Arduino - leitura de sensores ambientais
 *
 * Sensores ativos nesta versao:
 *   - DS18B20 (temperatura do solo) em D2, OneWire, pull-up 4,7kOhm
 *
 * Sensores previstos (descomente conforme forem chegando):
 *   - DHT22 (temperatura/umidade do ar)    -> D3
 *   - Capacitivo de umidade do solo         -> A0
 *   - BH1750 (luminosidade)                 -> I2C (A4=SDA, A5=SCL)
 */

#include <OneWire.h>
#include <DallasTemperature.h>

// ----- pinos -----
const int PIN_DS18B20 = 2;

// ----- DS18B20 -----
OneWire oneWire(PIN_DS18B20);
DallasTemperature ds18b20(&oneWire);

// ----- intervalo entre leituras -----
const unsigned long INTERVALO_MS = 2000;
unsigned long ultimaLeitura = 0;

void setup() {
  Serial.begin(9600);
  ds18b20.begin();
  // pequena pausa para deixar a serial estavel
  delay(500);
}

void loop() {
  unsigned long agora = millis();
  if (agora - ultimaLeitura < INTERVALO_MS) return;
  ultimaLeitura = agora;

  // ----- DS18B20: temperatura do solo -----
  ds18b20.requestTemperatures();
  float tSolo = ds18b20.getTempCByIndex(0);
  String tSoloStr;
  // -127 e o valor que a biblioteca retorna em caso de erro
  if (tSolo == DEVICE_DISCONNECTED_C || tSolo == -127.0) {
    tSoloStr = "err";
  } else {
    tSoloStr = String(tSolo, 1);  // 1 casa decimal
  }

  // ----- monta linha no formato definitivo da Etapa 3 -----
  // gw=gw01,type=sensors,t_soil=22.1
  Serial.print("gw=gw01,type=sensors,t_soil=");
  Serial.println(tSoloStr);
}
