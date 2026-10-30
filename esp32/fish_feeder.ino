#include <WiFi.h>
#include <WebServer.h>
#include <ESP32Servo.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>   // Install: Arduino IDE > Library Manager > "ArduinoJson" by Benoit Blanchon

// ===== YOUR PHONE HOTSPOT =====
const char* ssid     = "iQOO Neo9 Pro";
const char* password = "12345678";

// ===== CLOUD BACKEND (Render) =====
// After deploying to Render, paste your real URL here
const char* SERVER_URL   = "https://fish-feeder-backend.onrender.com";
const char* DEVICE_ID    = "esp32_feeder_01";

// ===== API KEY =====
// After Render deploys, go to:
//   Dashboard -> fish-feeder-backend -> Environment -> ESP32_API_KEY
// Copy the value and paste it below (between the quotes)
const char* ESP32_API_KEY = "PASTE_YOUR_KEY_HERE";

// How often to send data to the cloud (milliseconds)
const unsigned long REPORT_INTERVAL = 10000; // 10 seconds

// ===== HARDWARE PINS =====
const int SERVO_PIN = 18;
const int TRIG_PIN  = 23;
const int ECHO_PIN  = 22;

// ===== SERVO SETTINGS =====
const int CLOSED_ANGLE = 0;
const int OPEN_ANGLE   = 90;
const unsigned long FEED_DURATION = 1000;

// ===== FOOD LEVEL THRESHOLDS =====
const float MIN_DISTANCE   = 1.0;
const float EMPTY_DISTANCE = 6.0;
const float FILL_DISTANCE  = 5.0;
const float HALF_DISTANCE  = 4.0;

// ===== GLOBALS =====
Servo feeder;
WebServer server(80);

int  servoAngle       = CLOSED_ANGLE;
bool feeding          = false;
unsigned long feedStartTime   = 0;
unsigned long lastSensorRead  = 0;
unsigned long lastServerReport = 0;

float  distanceCM = -1;
String foodLevel  = "Reading...";

// =============================================================================
//  CLOUD REPORTING — sends reading to Render & executes any pending command
// =============================================================================
void reportToCloud() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[Cloud] WiFi not connected, skipping report.");
    return;
  }

  // ---- Build JSON payload ----
  StaticJsonDocument<200> payload;
  payload["device_id"]      = DEVICE_ID;
  payload["distance_cm"]    = distanceCM;
  payload["food_status"]    = foodLevel;
  payload["uptime_seconds"] = (int)(millis() / 1000);

  String body;
  serializeJson(payload, body);

  // ---- POST /api/readings ----
  HTTPClient http;
  String url = String(SERVER_URL) + "/api/readings";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", ESP32_API_KEY);   // <-- API key sent here
  http.setTimeout(8000); // 8 second timeout (free Render can be slow)

  int code = http.POST(body);
  Serial.print("[Cloud] POST /api/readings -> HTTP ");
  Serial.println(code);

  if (code == 201) {
    String resp = http.getString();

    // ---- Parse response for pending command ----
    StaticJsonDocument<512> doc;
    DeserializationError err = deserializeJson(doc, resp);

    if (!err && !doc["pending_command"].isNull()) {
      int    cmdId  = doc["pending_command"]["id"].as<int>();
      String action = doc["pending_command"]["action"].as<String>();

      Serial.print("[Cloud] Pending command #");
      Serial.print(cmdId);
      Serial.print(" -> ");
      Serial.println(action);

      // ---- Execute command ----
      if (action == "FEED") {
        if (!feeding) {
          feeding       = true;
          feedStartTime = millis();
          servoAngle    = OPEN_ANGLE;
          feeder.write(servoAngle);
          Serial.println("[Command] FEED executed.");
        }
      } else if (action == "OPEN") {
        feeding    = false;
        servoAngle = OPEN_ANGLE;
        feeder.write(servoAngle);
        Serial.println("[Command] OPEN executed.");
      } else if (action == "CLOSE") {
        feeding    = false;
        servoAngle = CLOSED_ANGLE;
        feeder.write(servoAngle);
        Serial.println("[Command] CLOSE executed.");
      }

      // ---- Acknowledge command ----
      HTTPClient ack;
      String ackUrl = String(SERVER_URL) + "/api/commands/" + String(cmdId) + "/ack?status_code=EXECUTED";
      ack.begin(ackUrl);
      ack.addHeader("X-API-Key", ESP32_API_KEY);   // <-- API key sent here
      ack.setTimeout(5000);
      ack.POST("");
      ack.end();
      Serial.println("[Cloud] Command acknowledged.");
    }
  } else {
    Serial.print("[Cloud] Error body: ");
    Serial.println(http.getString());
  }

  http.end();
}

// =============================================================================
//  BASE CODE — untouched original functions below
// =============================================================================

// ===== READ ULTRASONIC SENSOR =====
float readDistanceCM() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  unsigned long duration = pulseIn(ECHO_PIN, HIGH, 30000);

  if (duration == 0) return -1;

  return duration * 0.0343f / 2.0f;
}

// ===== FOOD LEVEL =====
String getFoodLevel(float d) {
  if (d < MIN_DISTANCE)    return "Sensor Error";
  if (d > EMPTY_DISTANCE)  return "Empty";
  if (d >= FILL_DISTANCE)  return "Fill";
  if (d >= HALF_DISTANCE)  return "Half";
  return "Full";
}

// ===== WEBSITE =====
void handleRoot() {
  String html = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smart Fish Feeder</title>
<style>
body{font-family:Arial;text-align:center;background:#eaf6ff;color:#17324d;padding:18px 10px}
.card{max-width:430px;margin:auto;background:white;padding:22px;border-radius:18px;box-shadow:0 4px 15px #0002}
h1{color:#087fbb}
button{padding:14px;margin:6px 3px;border:0;border-radius:9px;color:white;background:#087fbb;font-size:16px}
.close{background:#526777}.feed{background:#159447}
input{width:90%;margin:18px 0}
.status{font-size:26px;font-weight:bold;background:#e5f5ff;padding:14px;border-radius:12px}
.small{font-size:13px;color:#64748b}
</style>
</head>
<body>
<div class="card">
<h1>🐟 Smart Fish Feeder</h1>
<p>ESP32 Phone Hotspot Control</p>
<hr>
<h2>Food Quantity</h2>
<div class="status" id="quantity">Reading...</div>
<p id="distance">Distance: --</p>
<hr>
<h2>Motor Control</h2>
<p>Servo angle: <b><span id="angle">0</span>&deg;</b></p>
<button onclick="moveServo(90)">Open Gate</button>
<button class="close" onclick="moveServo(0)">Close Gate</button><br>
<button class="feed" onclick="feedFish()">Feed Now 🐟</button>
<h3>Adjust Gate Angle</h3>
<input type="range" id="slider" min="0" max="180" value="0"
oninput="document.getElementById('angle').textContent=this.value"
onchange="moveServo(this.value)">
<p id="message">Ready</p>
<p class="small">Food status refreshes automatically.</p>
</div>
<script>
async function moveServo(a){
  a=Math.max(0,Math.min(180,Number(a)));
  document.getElementById('slider').value=a;
  document.getElementById('angle').textContent=a;
  document.getElementById('message').textContent='Sending command...';
  try{
    let r=await fetch('/servo?angle='+a);
    let d=await r.json();
    document.getElementById('angle').textContent=d.angle;
    document.getElementById('message').textContent=d.message;
  }catch(e){
    document.getElementById('message').textContent='Connection failed';
  }
}
async function feedFish(){
  document.getElementById('message').textContent='Feeding...';
  try{
    let r=await fetch('/feed');
    let d=await r.json();
    document.getElementById('angle').textContent=d.angle;
    document.getElementById('slider').value=d.angle;
    document.getElementById('message').textContent=d.message;
  }catch(e){
    document.getElementById('message').textContent='Connection failed';
  }
}
async function updateQuantity(){
  try{
    let r=await fetch('/quantity');
    let d=await r.json();
    document.getElementById('quantity').textContent=d.level;
    document.getElementById('distance').textContent =
      d.distance<0?'Distance: unavailable':'Distance: '+d.distance.toFixed(1)+' cm';
  }catch(e){
    document.getElementById('quantity').textContent='Sensor unavailable';
  }
}
updateQuantity();
setInterval(updateQuantity,1000);
</script>
</body>
</html>
)rawliteral";

  server.send(200, "text/html", html);
}

// ===== SERVO API =====
void handleServo() {
  if (!server.hasArg("angle")) {
    server.send(400, "application/json",
                "{\"message\":\"Missing angle\"}");
    return;
  }

  int angle = constrain(server.arg("angle").toInt(), 0, 180);
  feeding    = false;
  servoAngle = angle;
  feeder.write(servoAngle);

  String response = "{\"angle\":" + String(servoAngle) +
    ",\"message\":\"Gate moved to " + String(servoAngle) + " degrees\"}";
  server.send(200, "application/json", response);
}

// ===== FEED NOW API =====
void handleFeed() {
  if (feeding) {
    server.send(409, "application/json",
                "{\"angle\":90,\"message\":\"Feeding already in progress\"}");
    return;
  }

  feeding       = true;
  feedStartTime = millis();
  servoAngle    = OPEN_ANGLE;
  feeder.write(servoAngle);

  server.send(200, "application/json",
              "{\"angle\":90,\"message\":\"Feeding started\"}");
}

// ===== QUANTITY API =====
void handleQuantity() {
  String response = "{\"level\":\"" + foodLevel +
                    "\",\"distance\":" + String(distanceCM, 1) + "}";
  server.send(200, "application/json", response);
}

// ===== SETUP =====
void setup() {
  Serial.begin(115200);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);

  feeder.setPeriodHertz(50);
  feeder.attach(SERVO_PIN, 500, 2400);
  feeder.write(CLOSED_ANGLE);

  // Connect to your phone's hotspot
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  Serial.print("Connecting to phone hotspot");
  unsigned long start = millis();

  while (WiFi.status() != WL_CONNECTED &&
         millis() - start < 30000) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("Connected to phone hotspot!");
    Serial.print("ESP32 local website: http://");
    Serial.println(WiFi.localIP());
    Serial.print("Cloud dashboard: ");
    Serial.println(SERVER_URL);
  } else {
    Serial.println("Wi-Fi connection failed!");
    Serial.println("Check hotspot name, password, and 2.4GHz setting.");
  }

  server.on("/",        HTTP_GET, handleRoot);
  server.on("/servo",   HTTP_GET, handleServo);
  server.on("/feed",    HTTP_GET, handleFeed);
  server.on("/quantity",HTTP_GET, handleQuantity);
  server.begin();

  Serial.println("Local web server started.");
}

// ===== MAIN LOOP =====
void loop() {
  server.handleClient();   // keep local web server alive

  // Read sensor every 1 second
  if (millis() - lastSensorRead >= 1000) {
    lastSensorRead = millis();
    distanceCM     = readDistanceCM();
    foodLevel      = getFoodLevel(distanceCM);

    Serial.print("Distance: ");
    if (distanceCM < 0) Serial.print("Unavailable");
    else {
      Serial.print(distanceCM, 1);
      Serial.print(" cm");
    }
    Serial.print(" | Food: ");
    Serial.println(foodLevel);
  }

  // Report to cloud every REPORT_INTERVAL
  if (millis() - lastServerReport >= REPORT_INTERVAL) {
    lastServerReport = millis();
    reportToCloud();
  }

  // Auto-close gate after feeding duration
  if (feeding && millis() - feedStartTime >= FEED_DURATION) {
    feeding    = false;
    servoAngle = CLOSED_ANGLE;
    feeder.write(servoAngle);
    Serial.println("Feeding complete; gate closed.");
  }
}