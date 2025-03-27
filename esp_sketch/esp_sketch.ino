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

//  AP data (MACs in lowercase without colons)
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

// Parameters for RSSI to distance calculation
const int RSSI_REFERENCE = -45;  // RSSI at reference distance (1 meter)
const float PATH_LOSS_EXPONENT = 2.0;  // Path loss exponent (typically between 2 and 4)

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
  server.on("/location", handleLocation);
  server.on("/floorplan.jpg", handleImage);
  server.on("/upload", HTTP_POST, handleUploadSuccess, handleUpload);

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
    <title>WiFi Localization</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
      body { margin: 0; padding: 20px; background: #f0f0f0; }
      .container { 
        position: relative; 
        max-width: 800px; 
        margin: 0 auto;
        box-shadow: 0 0 15px rgba(0,0,0,0.2);
      }
      #map { 
        width: 100%; 
        height: auto;
        border: 2px solid #333;
      }
      #marker {
        position: absolute;
        width: 15px;
        height: 15px;
        background: #FF0000;
        border-radius: 50%;
        transform: translate(-50%, -50%);
        border: 2px solid white;
        box-shadow: 0 0 10px rgba(0,0,0,0.5);
        display: none;
      }
      #coords {
        position: absolute;
        top: 15px;
        left: 15px;
        background: rgba(255,255,255,0.9);
        padding: 10px;
        border-radius: 5px;
        font-family: monospace;
      }
      .upload-form {
        margin-top: 20px;
      }
    </style>
    <script>
      function updateLocation() {
        fetch('/location')
          .then(response => response.json())
          .then(data => {
            if(data.x && data.y) {
              const img = document.getElementById('map');
              const marker = document.getElementById('marker');
              const coords = document.getElementById('coords');
              
              // Convert normalized coordinates to pixels
              const x = data.x * img.clientWidth;
              const y = data.y * img.clientHeight;
              
              marker.style.display = 'block';
              marker.style.left = x + 'px';
              marker.style.top = y + 'px';
              coords.innerHTML = `X: ${data.x.toFixed(3)}<br>Y: ${data.y.toFixed(3)}`;
            }
            setTimeout(updateLocation, 2000);
          })
          .catch(error => {
            console.error('Error:', error);
            setTimeout(updateLocation, 5000);
          });
      }
      window.onload = updateLocation;
    </script>
  </head>
  <body>
    <div class="container">
      <img id="map" src="/floorplan.jpg" alt="Floor Plan">
      <div id="marker"></div>
      <div id="coords">Initializing...</div>

      <div class="upload-form">
        <h3>Upload a new Floorplan Image</h3>
        <form action="/upload" method="POST" enctype="multipart/form-data">
          <input type="file" name="fileUpload" accept="image/jpeg">
          <input type="submit" value="Upload Image">
        </form>
      </div>
    </div>
  </body>
  </html>
  )rawliteral";

  server.send(200, "text/html", html);
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

void handleLocation() {
  DynamicJsonDocument doc(512);
  JsonObject response = doc.to<JsonObject>();
  
  // Perform WiFi scan
  int numNetworks = WiFi.scanNetworks(false, false);
  float totalWeight = 0;
  float weightedX = 0;
  float weightedY = 0;

  for (int i = 0; i < numNetworks; i++) {
    String mac = WiFi.BSSIDstr(i);
    mac.toLowerCase();
    mac.replace(":", "");
    int rssi = WiFi.RSSI(i);

    // Find matching AP in knownAPs
    for (const auto& ap : knownAPs) {
      if (mac == ap.mac) {
        // Calculate distance based on RSSI
        float distance = calculateDistance(rssi);
        
        if (distance > 0) {
          // Use inverse of distance as weight
          float weight = 1 / distance;  // Inverse of distance as weight
          weightedX += ap.x * weight;
          weightedY += ap.y * weight;
          totalWeight += weight;
        }
        break;
      }
    }
  }

  if (totalWeight > 0) {
    response["x"] = weightedX / totalWeight;
    response["y"] = weightedY / totalWeight;
  } else {
    response["error"] = "No matching APs found";
  }

  String jsonResponse;
  serializeJson(response, jsonResponse);
  server.send(200, "application/json", jsonResponse);
  
  WiFi.scanDelete();
}

float calculateDistance(int rssi) {
  // Use log-distance path loss model to calculate distance
  return pow(10, (RSSI_REFERENCE - rssi) / (10 * PATH_LOSS_EXPONENT));
}

void handleUpload() {
  HTTPUpload& upload = server.upload();
  if (upload.status == UPLOAD_FILE_START) {
    String filename = "/floorplan.jpg";  // Save the image as floorplan.jpg
    File file = SPIFFS.open(filename, "w");
    if (!file) {
      server.send(500, "text/plain", "Failed to open file for writing");
      return;
    }
    file.close();
  } else if (upload.status == UPLOAD_FILE_WRITE) {
    File file = SPIFFS.open("/floorplan.jpg", "a");
    if (file) {
      file.write(upload.buf, upload.currentSize);
      file.close();
    }
  } else if (upload.status == UPLOAD_FILE_END) {
    // File upload is done
    server.send(200, "text/html", "<html><body><h1>Upload complete!</h1><a href='/'>Go to Home</a></body></html>");
  }
}

void handleUploadSuccess() {
  // Handle successful upload
  String html = "<html><body><h1>File uploaded successfully!</h1><a href='/'>Go to Home</a></body></html>";
  server.send(200, "text/html", html);
}
