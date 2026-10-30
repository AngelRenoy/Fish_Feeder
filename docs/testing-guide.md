# Testing and Verification Guide: IoT Automatic Fish Feeder

This document provides a step-by-step procedure for verifying every layer of the Smart Fish Feeder IoT system—from sensor reading and ESP32 telemetry to Docker Compose orchestration, PostgreSQL persistence, and dashboard visualization.

---

## Prerequisites & Test Environment

- **Host PC OS:** Windows 10/11 (or Linux / macOS)
- **Host LAN IP Address:** e.g., `192.168.39.243` (determine via `ipconfig` on Windows)
- **Local Port:** `8000` (FastAPI backend), `5432` (PostgreSQL)
- **Hardware:** ESP32 dev board, HC-SR04 ultrasonic sensor, SG90 servo motor, breadboard, 1kΩ and 2kΩ resistors (for Echo voltage divider), 5V external power supply.

---

## 12-Step Verification Checklist

### Step 1: Start Docker Compose and Confirm Container Health

Run the following command from the `fish-feeder-iot` directory:

```powershell
# Windows PowerShell
docker compose up -d --build
```

**Check Container Status:**
```powershell
docker compose ps
```

**Expected Output:**
```text
NAME                   IMAGE                 COMMAND                  SERVICE   STATUS                    PORTS
fishfeeder_postgres    postgres:16-alpine    "docker-entrypoint.s…"   db        Up (healthy)              0.0.0.0:5432->5432/tcp
fishfeeder_backend     fish-feeder-iot-backend "uvicorn main:app --…" backend   Up                        0.0.0.0:8000->8000/tcp
```
- Both containers must show `Up`. The `db` service must report `(healthy)`.

---

### Step 2: Open Backend Health Endpoint

Verify that FastAPI can communicate with PostgreSQL.

**Using PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get
```

**Using curl (Windows CMD or Linux/macOS):**
```bash
curl -X GET "http://localhost:8000/health"
```

**Expected Response (HTTP 200 OK):**
```json
{
  "status": "healthy",
  "database": "connected",
  "environment": "production",
  "timestamp": "2026-10-28T15:00:00.000000Z"
}
```

---

### Step 3: Access Web Dashboard and Swagger UI

Open your browser and navigate to:
1. **Real-Time Dashboard:** [http://localhost:8000](http://localhost:8000) or [http://192.168.39.243:8000](http://192.168.39.243:8000)
   - Status badge in top-right should show **"System Live"** with a pulsing green indicator.
2. **Interactive Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
   - Verify all endpoints (`/health`, `/api/readings`, `/api/stats`, `/api/commands`, etc.) are documented.

---

### Step 4: Send Test Sensor Reading via API

Simulate an ESP32 sensor transmission to verify validation, insertion, and response formatting.

**PowerShell Command:**
```powershell
$headers = @{ "Content-Type" = "application/json" }
$body = @{
    device_id = "esp32_feeder_01"
    distance_cm = 3.2
    food_status = "Full"
    uptime_seconds = 120
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/readings" -Method Post -Headers $headers -Body $body
```

**curl Command:**
```bash
curl -X POST "http://localhost:8000/api/readings" \
  -H "Content-Type: application/json" \
  -d '{"device_id":"esp32_feeder_01","distance_cm":3.2,"food_status":"Full","uptime_seconds":120}'
```

**Expected Response (HTTP 201 Created):**
```json
{
  "status": "success",
  "message": "Sensor reading successfully recorded",
  "reading": {
    "id": 1,
    "device_id": "esp32_feeder_01",
    "distance_cm": 3.2,
    "food_status": "Full",
    "uptime_seconds": 120,
    "recorded_at": "...",
    "received_at": "..."
  },
  "pending_command": null
}
```

---

### Step 5: Verify Reading in PostgreSQL Database

Execute a SQL query inside the running PostgreSQL container to confirm data persistence.

```powershell
# PowerShell
docker compose exec db psql -U postgres -d fishfeeder -c "SELECT id, device_id, distance_cm, food_status, received_at FROM sensor_readings ORDER BY id DESC LIMIT 5;"
```

**Expected Output:**
```text
 id |    device_id    | distance_cm | food_status |          received_at          
----+-----------------+-------------+-------------+-------------------------------
  1 | esp32_feeder_01 |         3.2 | Full        | 2026-10-28 15:02:10.123456+00
(1 row)
```

---

### Step 6: Verify ESP32 Hardware Wiring & Serial Monitor

1. Open `esp32/fish_feeder.ino` in Arduino IDE.
2. Confirm the settings at the top match your network:
   - `WIFI_SSID`: Your 2.4 GHz Wi-Fi SSID
   - `WIFI_PASSWORD`: Your Wi-Fi password
   - `BACKEND_HOST`: Your computer's LAN IP (e.g. `192.168.39.243`)
   - `BACKEND_PORT`: `8000`
3. Connect the ESP32 via USB and select the correct COM port.
4. Open **Serial Monitor** at **115200 baud**.
5. Press the **EN/RST** button on the ESP32.

**Expected Serial Output:**
```text
==================================================
   IoT Automatic Fish Feeder - ESP32 Firmware     
==================================================
[SERVO] Gate moved to: 0 degrees

[WIFI] Connecting to SSID: iQOO Neo9 Pro
......
[WIFI] Connected successfully!
[WIFI] ESP32 IP Address: 192.168.39.88
[WIFI] Signal Strength (RSSI): -52 dBm
[SETUP] Initialization completed. Starting telemetry loop...

[SENSOR] Distance: 3.42 cm | Food Level: Full

--------------------------------------------------
[HTTP] POST -> http://192.168.39.243:8000/api/readings
[HTTP] Payload: {"device_id":"esp32_feeder_01","distance_cm":3.42,"food_status":"Full","uptime_seconds":3}
[HTTP] Server Response Code: 201
[HTTP] Response Body: {"status":"success",...}
--------------------------------------------------
```

---

### Step 7: Confirm Dashboard Real-Time Updates

1. Keep the dashboard open at `http://localhost:8000`.
2. Notice that every 3 seconds:
   - The **Food Container Status** badge reflects the current reading.
   - The **Current Distance** updates with the exact centimeter value.
   - The **Live Distance Telemetry Chart** plots the new data point without page refresh.
   - The **Recent Sensor Readings Table** adds the new record at the top.
   - The **Food Level Visualization tank** adjusts its fluid height dynamically.

---

### Step 8: Test Each Food-Level Threshold

Place a flat card or object at varying distances in front of the HC-SR04 sensor and observe the classification:

| Test Case | Target Distance | Expected Status | Container Visual Fill |
| :--- | :--- | :--- | :--- |
| **Test 8A: Full** | 2.5 cm (between 1.0 and 4.0 cm) | `Full` | ~85% green fluid |
| **Test 8B: Half** | 4.4 cm (between 4.0 and 5.0 cm) | `Half` | ~55% cyan/teal fluid |
| **Test 8C: Fill** | 5.5 cm (between 5.0 and 6.0 cm) | `Fill` | ~25% amber fluid |
| **Test 8D: Empty** | 7.8 cm (> 6.0 cm) | `Empty` | ~5% red fluid |
| **Test 8E: Error** | Sensor blocked / obstructed (< 1.0 cm) | `Sensor Error` | 0% gray fluid |

Verify in the Serial Monitor and Dashboard that transitions occur reliably within 1-2 sampling cycles (3-6 seconds).

---

### Step 9: Test Remote Servo Control (Manual Feed)

1. On the dashboard, locate the **SG90 Servo Gate Control** panel.
2. Click **"Feed Now (1s Gate Cycle)"**.
3. **Dashboard feedback:**
   - Badge updates to **"Enqueued"** (`PENDING`).
4. **ESP32 Execution (on next 3-second cycle):**
   - In Serial Monitor:
     ```text
     [COMMAND] Received pending command #1 -> Action: FEED
     [FEED] Starting automatic feeding cycle...
     [SERVO] Gate moved to: 90 degrees
     [FEED] Feeding cycle complete. Gate secured closed.
     [SERVO] Gate moved to: 0 degrees
     [COMMAND] Successfully acknowledged command #1 as EXECUTED
     ```
   - Physical servo horn moves 90°, stays for 1.2 seconds, and returns to 0°.
5. **Dashboard confirmation:**
   - The command status box changes to green **"Executed"**: *"Command #1 (FEED) executed and confirmed by ESP32"*.

---

### Step 10: Test Wi-Fi Disconnection & Auto-Reconnection

1. Temporarily disable the Wi-Fi hotspot or router.
2. Observe ESP32 Serial Monitor:
   - `[HTTP] Wi-Fi not connected. Skipping upload.`
   - `[WIFI] Connection lost. Attempting reconnection...`
3. Observe Dashboard:
   - After a brief pause, the dashboard continues displaying the last known readings without crashing.
4. Re-enable the Wi-Fi hotspot.
5. Confirm that the ESP32 reconnects (`[WIFI] Connected successfully!`) and telemetry resumes seamlessly.

---

### Step 11: Verify Database Persistence Across Container Restarts

Verify that sensor readings survive container stops and restarts:

1. Record the current total reading count displayed on the dashboard (e.g., 42 readings).
2. Stop the containers:
   ```powershell
   docker compose down
   ```
3. Start the containers again:
   ```powershell
   docker compose up -d
   ```
4. Query PostgreSQL:
   ```powershell
   docker compose exec db psql -U postgres -d fishfeeder -c "SELECT COUNT(*) FROM sensor_readings;"
   ```
5. **Expected Result:** The count matches the prior count exactly. The Docker named volume `fishfeeder_postgres_data` guarantees persistent storage.

---

### Step 12: Test Invalid Payload Handling (API Robustness)

Send malformed requests to confirm robust validation:

**Invalid Food Status Test:**
```powershell
$badPayload = '{"device_id":"esp32_feeder_01","distance_cm":3.0,"food_status":"Overflowing"}'
try {
    Invoke-RestMethod -Uri "http://localhost:8000/api/readings" -Method Post -ContentType "application/json" -Body $badPayload
} catch {
    $_.Exception.Response.StatusCode.value__
}
```
**Expected Result:** HTTP `422 Unprocessable Entity` with error message explaining permitted food statuses (`Empty`, `Fill`, `Half`, `Full`, `Sensor Error`).

---

## Test Execution Summary Table

| Step # | Test Description | Expected Result | Pass/Fail |
| :---: | :--- | :--- | :---: |
| 1 | Docker Compose orchestration | `db` and `backend` containers healthy | [Pending Hardware Run] |
| 2 | Backend health check | HTTP 200 `status: healthy`, `database: connected` | [Verified in Local Test] |
| 3 | Static dashboard serving | Dashboard HTML/CSS/JS loads at port 8000 | [Verified in Local Test] |
| 4 | Manual sensor ingestion | HTTP 201 Created with JSON structure | [Verified in Local Test] |
| 5 | PostgreSQL table insertion | Row visible in `sensor_readings` | [Verified in Local Test] |
| 6 | ESP32 Wi-Fi connection | ESP32 obtains local IP from 2.4 GHz router | [Pending Hardware Run] |
| 7 | Live dashboard polling | Data updates every 3s without reload | [Verified in Local Test] |
| 8 | Food status classification | Correct state for Full, Half, Fill, Empty, Error | [Pending Hardware Run] |
| 9 | Remote servo gate control | Servo horn rotates to 90° and returns to 0° | [Pending Hardware Run] |
| 10 | Wi-Fi drop resilience | ESP32 reconnects automatically upon signal recovery | [Pending Hardware Run] |
| 11 | Docker volume persistence | Database records intact after `compose down/up` | [Pending Hardware Run] |
| 12 | Schema input validation | Invalid inputs rejected with HTTP 422 | [Verified in Local Test] |

