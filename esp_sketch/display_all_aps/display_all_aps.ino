#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ArduinoJson.h>
#include <FS.h>

// Configuration
const char* AP_SSID = "LocationTracker";
const char* AP_PASS = "locate1234";
const String IMAGE_PATH = "/floorplan.jpg";

// Access Point locations structure
struct AccessPoint {
  const char* mac;
  float x;
  float y;
};

// AP data (MACs in lowercase without colons)
const AccessPoint knownAPs[] = {
  {"cc88c7d3ffc0", 0.3896, 0.62},
  {"cc88c7d21920", 0.5176, 0.3044},
  {"cc88c7d3fc70", 0.5061, 0.7911},
  {"cc88c7d21930", 0.1434, 0.2756},
  {"cc88c7d38330", 0.786, 0.54},
  {"cc88c7d39ea0", 0.5951, 0.5467},
  {"cc88c7d21950", 0.2469, 0.0911},
  {"cc88c7d20700", 0.7515, 0.0778},
  {"cc88c7d39e70", 0.8612, 0.2711},
  {"cc88c7d3ffd0", 0.3903, 0.62},
  {"cc88c7d40020", 0.2385, 0.4289},
  {"cc88c7d3f740", 0.0475, 0.84}
};

ESP8266WebServer server(80);

void setup() {
  Serial.begin(115200);
  
  // Initialize filesystem
  if (!SPIFFS.begin()) {
    Serial.println("Failed to mount filesystem");
    return;
  }

  // Start Access Point
  WiFi.softAP(AP_SSID, AP_PASS);
  Serial.print("AP IP address: ");
  Serial.println(WiFi.softAPIP());

  // Configure server routes
  server.on("/", handleRoot);
  server.on("/accesspoints", handleAccessPoints);
  server.on("/floorplan.jpg", handleImage);

  server.begin();
  Serial.println("HTTP server started");
}

void loop() {
  server.handleClient();
}

void handleRoot() {
  String html = R"rawliteral(
  <!DOCTYPE html>
  <html>
  <head>
    <title>Detected AP Locations</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
      body { margin: 0; padding: 20px; background: #f0f0f0; }
      .container { position: relative; max-width: 800px; margin: 0 auto; }
      #map { width: 100%; height: auto; border: 2px solid #333; }
      .ap-marker { position: absolute; width: 12px; height: 12px; background: red; border-radius: 50%; }
      .ap-label { position: absolute; font-size: 12px; background: white; padding: 2px; }
    </style>
    <script>
      function updateAPs() {
        fetch('/accesspoints')
          .then(response => response.json())
          .then(aps => {
            document.querySelectorAll('.ap-marker, .ap-label').forEach(el => el.remove());
            aps.forEach(ap => {
              const marker = document.createElement('div');
              marker.className = 'ap-marker';
              marker.style.left = (ap.x * 100) + '%';
              marker.style.top = (ap.y * 100) + '%';
              document.querySelector('.container').appendChild(marker);
            });
          });
      }
      window.onload = updateAPs;
    </script>
  </head>
  <body>
    <div class="container">
      <img id="map" src="/floorplan.jpg" alt="Floor Plan">
    </div>
  </body>
  </html>
  )rawliteral";
  server.send(200, "text/html", html);
}

void handleAccessPoints() {
  WiFi.scanDelete();
  int numNetworks = WiFi.scanNetworks();
  DynamicJsonDocument doc(1024);
  JsonArray aps = doc.to<JsonArray>();

  for (int i = 0; i < numNetworks; i++) {
    String mac = WiFi.BSSIDstr(i);
    mac.replace(":", "");
    mac.toLowerCase();
    
    for (const auto& ap : knownAPs) {
      if (mac.equals(ap.mac)) {
        JsonObject apObj = aps.createNestedObject();
        apObj["mac"] = ap.mac;
        apObj["x"] = ap.x;
        apObj["y"] = ap.y;
      }
    }
  }
  String jsonResponse;
  serializeJson(doc, jsonResponse);
  server.send(200, "application/json", jsonResponse);
}

void handleImage() {
  File file = SPIFFS.open(IMAGE_PATH, "r");
  if (!file) {
    server.send(404, "text/plain", "Image not found");
    return;
  }
  server.streamFile(file, "image/jpeg");
  file.close();
}
