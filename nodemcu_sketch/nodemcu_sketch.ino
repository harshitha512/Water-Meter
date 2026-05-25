// ─────────────────────────────────────────────────────────────
//  Smart Water Meter — NodeMCU ESP8266
//  Sends data via HTTP POST to local Flask server (no cloud)
// ─────────────────────────────────────────────────────────────
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ── Wi-Fi credentials ──────────────────────────────────────
#define SSID        "YOUR_WIFI_NAME"
#define PASS        "YOUR_WIFI_PASSWORD"

// ── Your PC/server IP (run ipconfig or ifconfig to find it) ──
#define SERVER_IP   "192.168.1.100"
#define SERVER_PORT 5000
#define SERVER_URL  "http://" SERVER_IP ":" + String(SERVER_PORT) + "/api/data"

// ── Sensor & display setup ─────────────────────────────────
#define SENSOR_PIN    2    // D4 on NodeMCU
#define SCREEN_W    128
#define SCREEN_H     64
#define OLED_RESET   -1

Adafruit_SSD1306 display(SCREEN_W, SCREEN_H, &Wire, OLED_RESET);

// ── Flow variables ─────────────────────────────────────────
volatile byte pulseCount = 0;
float calibrationFactor  = 4.5;
float flowRate           = 0.0;
float flowLitres         = 0.0;
float totalLitres        = 0.0;
float unitPrice          = 0.025;
float totalBill          = 0.0;
unsigned long lastMillis = 0;
unsigned long lastPost   = 0;
const int POST_INTERVAL  = 2000;   // send data every 2 seconds

// ── Interrupt: counts pulses from sensor ──────────────────
IRAM_ATTR void pulseCounter() {
  pulseCount++;
}

// ── Indian Water Tariff (INR per liter) ───────────────────
float getUnitPrice(float litres) {
  if (litres <= 10000) return 0.005;   // Rs. 5 per 1000 L
  if (litres <= 30000) return 0.012;   // Rs. 12 per 1000 L
  return 0.025;                         // Rs. 25 per 1000 L
}

void setup() {
  Serial.begin(115200);

  // OLED init
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OLED not found");
    while (true);
  }
  display.clearDisplay();
  display.setTextColor(WHITE);
  display.setTextSize(1);
  display.setCursor(10, 25);
  display.print("Connecting WiFi...");
  display.display();

  // Wi-Fi connect
  WiFi.begin(SSID, PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected: " + WiFi.localIP().toString());

  display.clearDisplay();
  display.setCursor(0, 0);
  display.print("IP: " + WiFi.localIP().toString());
  display.display();
  delay(2000);

  // Sensor interrupt
  pinMode(SENSOR_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(SENSOR_PIN), pulseCounter, FALLING);

  pulseCount  = 0;
  lastMillis  = millis();
  lastPost    = millis();
}

void loop() {
  unsigned long now = millis();

  // ── Calculate flow every 1 second ───────────────────────
  if (now - lastMillis >= 1000) {
    detachInterrupt(digitalPinToInterrupt(SENSOR_PIN));

    float elapsed = (now - lastMillis);
    flowRate      = ((1000.0 / elapsed) * pulseCount) / calibrationFactor;
    flowLitres    = flowRate / 60.0;
    totalLitres  += flowLitres;
    unitPrice     = getUnitPrice(totalLitres);
    totalBill     = totalLitres * unitPrice;

    pulseCount    = 0;
    lastMillis    = now;

    attachInterrupt(digitalPinToInterrupt(SENSOR_PIN), pulseCounter, FALLING);

    // ── Update OLED ─────────────────────────────────────
    display.clearDisplay();
    display.setTextSize(1);
    display.setCursor(0, 0);
    display.print("Water Flow Meter");
    display.drawLine(0, 10, 128, 10, WHITE);

    display.setTextSize(2);
    display.setCursor(0, 16);
    display.print(flowRate, 2);
    display.setTextSize(1);
    display.print(" L/m");

    display.setTextSize(1);
    display.setCursor(0, 40);
    display.print("Total: ");
    display.print(totalLitres, 2);
    display.print(" L");

    display.setCursor(0, 52);
    display.print("Bill: Rs.");
    display.print(totalBill, 2);

    display.display();

    // ── Serial monitor ───────────────────────────────────
    Serial.print("Flow: "); Serial.print(flowRate);
    Serial.print(" L/min | Total: "); Serial.print(totalLitres);
    Serial.print(" L | Bill: "); Serial.println(totalBill);
  }

  // ── Send data to Flask server every 2 seconds ───────────
  if (now - lastPost >= POST_INTERVAL && WiFi.status() == WL_CONNECTED) {
    lastPost = now;

    WiFiClient client;
    HTTPClient http;

    String url = "http://" + String(SERVER_IP) + ":" + String(SERVER_PORT) + "/api/data";
    http.begin(client, url);
    http.addHeader("Content-Type", "application/json");

    String body = "{";
    body += "\"flow_rate\":"    + String(flowRate, 4) + ",";
    body += "\"total_liters\":" + String(totalLitres, 4) + ",";
    body += "\"total_bill\":"   + String(totalBill, 4) + ",";
    body += "\"unit_price\":"   + String(unitPrice, 3);
    body += "}";

    int code = http.POST(body);
    if (code == 200) {
      Serial.println("Data sent OK");
    } else {
      Serial.println("POST failed: " + String(code));
    }
    http.end();
  }
}
