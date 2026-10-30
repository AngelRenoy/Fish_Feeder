# 🐟 IoT-Based Automatic Fish Feeder with Real-Time Monitoring Dashboard

A complete, beginner-friendly Internet of Things (IoT) project for MCA college assignment submissions.

This project monitors fish food container capacity using an **ESP32 microcontroller** and an **HC-SR04 ultrasonic distance sensor**, classifies the food level into four distinct states (**Empty**, **Fill**, **Half**, **Full**), transmits telemetry to a **containerized FastAPI backend**, persists data in **PostgreSQL**, and presents live metrics and remote servo gate actuation controls on a **modern web dashboard**.

---

## 📁 Project Directory Structure

```text
fish-feeder-iot/
├── esp32/
│   └── fish_feeder.ino       # ESP32 Arduino C++ firmware
├── backend/
│   ├── main.py               # FastAPI endpoints & static dashboard serving
│   ├── database.py           # SQLAlchemy database engine & session manager
│   ├── models.py             # PostgreSQL ORM models (readings & commands)
│   ├── schemas.py            # Pydantic v2 validation models
│   ├── requirements.txt      # Pinned Python package dependencies
│   └── Dockerfile            # Container build recipe for backend
├── dashboard/
│   ├── index.html            # Real-time web monitoring interface
│   ├── style.css             # Modern Blue/Teal responsive styling
│   └── app.js                # Live Chart.js telemetry & servo control
├── docs/
│   ├── project-report.md     # 21-section MCA college assignment project report
│   └── testing-guide.md      # 12-step verification & testing procedures
├── docker-compose.yml        # Orchestration for FastAPI + PostgreSQL
├── .env.example              # Template configuration file
├── .gitignore                # Git ignore configuration
└── README.md                 # Complete beginner guide (this file)
```

---

## 🛠️ Required Software & Installations

Before starting, ensure you have the following installed on your Windows computer:

1. **Docker Desktop for Windows:**
   - Download & install from [Docker Desktop Official Site](https://www.docker.com/products/docker-desktop/).
   - Ensure WSL 2 backend is selected during installation.
   - Start Docker Desktop from the Start menu and wait until the whale icon in the taskbar stays solid.

2. **Arduino IDE (v2.x or v1.8.x):**
   - Download & install from [Arduino Software](https://www.arduino.cc/en/software).
   - In Arduino IDE, open **File > Preferences** and add this URL to **Additional Board Manager URLs**:
     ```text
     https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
     ```
   - Go to **Tools > Board > Boards Manager**, search for `esp32` by Espressif Systems, and click **Install**.
   - Go to **Sketch > Include Library > Manage Libraries**, search for `ESP32Servo` (by Kevin Harrington), and click **Install**.

3. **CP210x or CH340 USB Driver (if ESP32 is not recognized):**
   - Most ESP32 boards use CP2102 or CH340 chips. If your COM port does not appear in Arduino IDE, install the driver corresponding to your board's USB chip.

---

## 🔌 Hardware Circuit & Pinout

| Component | Component Pin | ESP32 Pin | Connection Note |
| :--- | :--- | :--- | :--- |
| **HC-SR04** | VCC | 5V / VIN | ESP32 board 5V / VIN pin |
| **HC-SR04** | GND | GND | Common ground |
| **HC-SR04** | TRIG | **GPIO 23** | Direct connection |
| **HC-SR04** | ECHO | **GPIO 22** | **Via Voltage Divider (1kΩ and 2kΩ)** |
| **SG90 Servo** | Signal (Orange) | **GPIO 18** | Direct PWM connection |
| **SG90 Servo** | Power (Red) | Ext +5V | **External 5V regulated supply** |
| **SG90 Servo** | Ground (Brown) | Ext GND & ESP32 GND | **Common ground must be tied to ESP32 GND** |

> [!CAUTION]
> **Important Hardware Protection:**  
> The HC-SR04 Echo pin outputs 5V signals, but the ESP32 GPIO pins only tolerate 3.3V. Connect a 1.0 kΩ resistor from the HC-SR04 Echo pin to ESP32 GPIO 22, and connect a 2.0 kΩ resistor from GPIO 22 to GND. This steps the voltage safely down to ~3.33V.

---

## 📏 Food-Level Classification Logic

The ultrasonic sensor measures the distance from the top sensor mounting point down to the surface of the food pellets inside the container:

| Distance Range | Classified Status | Meaning | Container Indicator |
| :--- | :--- | :--- | :--- |
| **Distance > 6.0 cm** | `Empty` | Food level critically low | Red (~5% fill) |
| **5.0 cm &le; Distance &le; 6.0 cm** | `Fill` | Container needs refilling soon | Amber (~25% fill) |
| **4.0 cm &le; Distance < 5.0 cm** | `Half` | Food hopper is roughly half full | Cyan/Teal (~55% fill) |
| **1.0 cm &le; Distance < 4.0 cm** | `Full` | Food container is full | Green (~85% fill) |
| **Distance < 1.0 cm or Timeout** | `Sensor Error` | Sensor blocked or echo missed | Gray (0% fill) |

*Note: These are distance-based capacity estimates, not precise volumetric measurements.*

---

## 🚀 Step-by-Step Setup Guide

### Step 1: Find Your Computer's LAN IP Address
On your Windows host computer, open PowerShell or Command Prompt and run:
```powershell
ipconfig
```
Look for your active Wi-Fi adapter's **IPv4 Address** (e.g. `192.168.39.243`).
Write this address down—you will enter it into the ESP32 firmware.

---

### Step 2: Configure Environment Variables
Inside the `fish-feeder-iot` directory, verify or create the `.env` configuration file from `.env.example`:
```powershell
# In PowerShell:
Copy-Item .env.example .env
```
The pre-configured defaults are:
```ini
POSTGRES_USER=postgres
POSTGRES_PASSWORD=fishfeeder_secret_pw
POSTGRES_DB=fishfeeder
POSTGRES_PORT=5432
BACKEND_PORT=8000
ENVIRONMENT=production
```

---

### Step 3: Launch Docker Compose Stack
Ensure Docker Desktop is running, then execute:
```powershell
docker compose up -d --build
```
This automatically:
1. Downloads and starts the official PostgreSQL 16 Alpine container with a persistent volume.
2. Builds the Python 3.11 FastAPI backend container.
3. Automatically waits for PostgreSQL to become healthy before starting FastAPI.
4. Mounts the live dashboard and exposes ports `8000` (FastAPI + Dashboard) and `5432` (PostgreSQL).

**Verify both containers are running:**
```powershell
docker compose ps
```

**Check backend logs:**
```powershell
docker compose logs -f backend
```

---

### Step 4: Open Web Dashboard & Swagger UI
Open your web browser and navigate to:
- **Web Dashboard:** [http://localhost:8000](http://localhost:8000) or `http://<YOUR_LAN_IP>:8000`
- **FastAPI Interactive API Docs (Swagger UI):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Backend Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

---

### Step 5: Configure and Flash ESP32 Firmware
1. Open the Arduino IDE.
2. Open `fish-feeder-iot/esp32/fish_feeder.ino`.
3. Locate lines 40-52 at the top of the sketch:
   ```cpp
   // --- Wi-Fi Credentials (2.4 GHz only) ---
   const char* WIFI_SSID     = "YOUR_WIFI_SSID";
   const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

   // --- Backend Host IP (Use your PC's LAN IP, NOT localhost) ---
   const char* BACKEND_HOST = "192.168.39.243"; // Replace with your computer's IP
   const int   BACKEND_PORT = 8000;
   ```
4. Connect the ESP32 to your computer with a micro-USB cable.
5. In Arduino IDE:
   - Go to **Tools > Board > ESP32 Arduino > ESP32 Dev Module** (or your exact 38-pin ESP32 board).
   - Go to **Tools > Port** and select your ESP32 COM port (e.g., `COM3`, `COM4`).
   - Click the **Upload** button (arrow icon).
6. Once uploaded, open **Tools > Serial Monitor** and set baud rate to **115200**.
7. Press the **EN/RST** button on the ESP32. You will see Wi-Fi connection logs, ultrasonic distance measurements, and HTTP POST responses every 3 seconds!

---

## 🧪 Testing Telemetry & Remote Servo Control

### 1. Ingesting a Test Reading via PowerShell
You can test the backend even before connecting the ESP32:
```powershell
$body = '{"device_id":"esp32_feeder_01","distance_cm":3.5,"food_status":"Full","uptime_seconds":60}'
Invoke-RestMethod -Uri "http://localhost:8000/api/readings" -Method Post -ContentType "application/json" -Body $body
```
The reading will immediately appear on the web dashboard and live chart!

### 2. Remote Feeding from Dashboard
1. Open the dashboard at `http://localhost:8000`.
2. Click **"Feed Now (1s Gate Cycle)"**.
3. The command is queued in PostgreSQL with status `PENDING`.
4. On the next 3-second cycle, the ESP32 picks up the command, rotates the SG90 servo to 90°, delays 1.2 seconds to drop pellets, rotates back to 0°, and sends an acknowledgment back to the backend.
5. The dashboard updates the status to **"Executed"** with a confirmation timestamp.

---

## 🔍 Database Inspection (PostgreSQL)

To view records directly inside the running PostgreSQL container:

```powershell
docker compose exec db psql -U postgres -d fishfeeder -c "SELECT id, device_id, distance_cm, food_status, received_at FROM sensor_readings ORDER BY id DESC LIMIT 10;"
```

To view command execution history:
```powershell
docker compose exec db psql -U postgres -d fishfeeder -c "SELECT id, device_id, action, status, created_at, executed_at FROM feeder_commands ORDER BY id DESC LIMIT 5;"
```

---

## 🛑 How to Shut Down Without Losing Data

To stop the containers while **preserving** all database records:
```powershell
docker compose down
```
When you run `docker compose up -d` next time, all past readings and statistics remain intact because they are stored in the persistent volume `fishfeeder_postgres_data`.

> [!WARNING]
> Only run `docker compose down -v` if you explicitly wish to delete the persistent volume and erase all database history.

---

## 🔧 Troubleshooting Guide

| Issue | Likely Cause | Solution |
| :--- | :--- | :--- |
| **ESP32 prints `POST failed: -1`** | Wrong IP address or firewall block | Verify that `BACKEND_HOST` in `fish_feeder.ino` uses your computer's LAN IP (`192.168.x.x`), not `localhost`. Allow port 8000 through Windows Defender Firewall. |
| **ESP32 prints `Sensor Error`** | Echo pin wiring or lack of common GND | Verify HC-SR04 connections (TRIG=23, ECHO=22 with voltage divider). Ensure sensor VCC connects to 5V and GND connects to ESP32 GND. |
| **Servo twitches or resets ESP32** | Brownout due to high servo current draw | Do NOT power the SG90 servo directly from the ESP32 3.3V or VIN pin. Power the servo from an external regulated 5V power source and tie its GND to ESP32 GND. |
| **Docker: `open //./pipe/dockerDesktopLinuxEngine`** | Docker Desktop engine is not running | Launch Docker Desktop from the Windows Start menu and wait 1 minute until it finishes starting. |
| **Dashboard shows "Backend Offline"** | FastAPI container not running | Run `docker compose ps` to check container status. Check logs via `docker compose logs backend`. |
| **Arduino IDE: `ESP32Servo.h: No such file`** | Missing library | In Arduino IDE, open **Sketch > Include Library > Manage Libraries**, search for `ESP32Servo`, and install it. |

---

## 📜 Academic Attribution
- **Student Assignment:** MCA IoT Laboratory Project
- **Architecture:** Microcontroller Telemetry &bull; REST API &bull; Relational Persistence &bull; Responsive Dashboard
- **Documentation:** Full 21-section technical report available at [`docs/project-report.md`](file:///c:/Users/user/Documents/IOT-Angel/fish-feeder-iot/docs/project-report.md).
- **Verification Procedures:** Comprehensive testing guide available at [`docs/testing-guide.md`](file:///c:/Users/user/Documents/IOT-Angel/fish-feeder-iot/docs/testing-guide.md).

