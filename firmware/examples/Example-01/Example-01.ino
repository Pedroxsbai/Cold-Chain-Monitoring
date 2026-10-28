//* Program that read the temperature and humidity from the DHT11 sensor and display it in the serial console every 2 seconds

#include <DHT.h>

#define DHTPIN D1
#define DHTTYPE DHT11

DHT dht(DHTPIN, DHTTYPE);

void setup() {
  
  Serial.begin(9600);

  dht.begin();
}

void loop() {

  float temperature = dht.readTemperature();
  float humidite = dht.readHumidity();
  
  Serial.print("Temperature : ");
  Serial.print(temperature);
  Serial.println(" C");
  
  Serial.print("Humidite : ");
  Serial.print(humidite);
  Serial.println(" %");
  
  delay(2000);
}
