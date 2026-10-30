/**
 * Smart Fish Feeder IoT Monitoring System - Frontend Application
 * Interacts with FastAPI backend over REST API endpoints:
 *   /api/stats, /api/readings, /api/commands
 */

// Configuration
const API_BASE = "";  // Empty string uses the same origin as the served page
const REFRESH_INTERVAL_MS = 3000;

// State
let chartInstance = null;
let isConnected = false;
let pollingTimer = null;
let lastAcknowledgedCommandId = null;

// DOM Elements
const elSystemStatusPill = document.getElementById("system-status-pill");
const elSystemStatusDot = document.getElementById("system-status-dot");
const elSystemStatusText = document.getElementById("system-status-text");
const elLastUpdated = document.getElementById("last-updated-time");
const elAlertBanner = document.getElementById("alert-banner");
const elAlertMessage = document.getElementById("alert-message");

const elMetricFoodStatus = document.getElementById("metric-food-status");
const elMetricFoodHint = document.getElementById("metric-food-hint");
const elMetricDistance = document.getElementById("metric-distance");
const elMetricTotalReadings = document.getElementById("metric-total-readings");
const elMetricActiveDevice = document.getElementById("metric-active-device");
const elMetricGateHint = document.getElementById("metric-gate-hint");

const elTankFillLevel = document.getElementById("tank-fill-level");
const elTankFillLabel = document.getElementById("tank-fill-label");
const elReadingsTableBody = document.getElementById("readings-table-body");

const elCmdBadge = document.getElementById("cmd-badge");
const elCmdMessage = document.getElementById("cmd-message");
const btnFeed = document.getElementById("btn-feed");
const btnOpen = document.getElementById("btn-open");
const btnClose = document.getElementById("btn-close");

// ============================================================================
// Chart Initialization (Chart.js)
// ============================================================================
function initChart() {
  const ctx = document.getElementById("readingsChart");
  if (!ctx) return;

  chartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Distance (cm)",
          data: [],
          borderColor: "#0284c7",
          backgroundColor: "rgba(2, 132, 199, 0.08)",
          fill: true,
          tension: 0.3,
          borderWidth: 2.5,
          pointRadius: 3,
          pointHoverRadius: 6,
          pointBackgroundColor: "#0284c7"
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: {
        duration: 300
      },
      scales: {
        x: {
          grid: {
            color: "#f1f5f9"
          },
          ticks: {
            maxTicksLimit: 8,
            font: { size: 11 }
          }
        },
        y: {
          title: {
            display: true,
            text: "Distance from Sensor (cm)",
            font: { size: 12, weight: "bold" }
          },
          suggestedMin: 0,
          suggestedMax: 10,
          grid: {
            color: "#f1f5f9"
          }
        }
      },
      plugins: {
        legend: {
          display: true,
          position: "top",
          labels: { boxWidth: 14, font: { size: 12 } }
        },
        tooltip: {
          callbacks: {
            label: function(context) {
              const dist = context.parsed.y;
              let status = "Unknown";
              if (dist < 0) status = "Sensor Error";
              else if (dist > 6.0) status = "Empty (>6cm)";
              else if (dist >= 5.0) status = "Fill (5-6cm)";
              else if (dist >= 4.0) status = "Half (4-5cm)";
              else if (dist >= 1.0) status = "Full (1-4cm)";
              return `Distance: ${dist} cm (${status})`;
            }
          }
        }
      }
    }
  });
}

// ============================================================================
// Data Fetching & UI Updates
// ============================================================================
async function fetchData() {
  try {
    const [statsRes, readingsRes, commandsRes] = await Promise.all([
      fetch(`${API_BASE}/api/stats`),
      fetch(`${API_BASE}/api/readings?limit=40`),
      fetch(`${API_BASE}/api/commands/latest?limit=1`)
    ]);

    if (!statsRes.ok || !readingsRes.ok) {
      throw new Error(`Server returned HTTP ${statsRes.status}`);
    }

    const stats = await statsRes.json();
    const readings = await readingsRes.json();
    const latestCommands = commandsRes.ok ? await commandsRes.json() : [];

    updateConnectionState(true);
    updateMetrics(stats);
    updateTankGraphic(stats.latest_reading);
    updateChart(readings);
    updateTable(readings);
    updateCommandStatus(latestCommands);

    elLastUpdated.textContent = new Date().toLocaleTimeString();
  } catch (err) {
    console.warn("Telemetry fetch error:", err);
    updateConnectionState(false, err.message);
  }
}

// Update Header connection status
function updateConnectionState(online, message = "") {
  isConnected = online;
  if (online) {
    elSystemStatusDot.className = "status-dot online";
    elSystemStatusText.textContent = "System Live";
    elSystemStatusPill.style.borderColor = "#a7f3d0";
    elAlertBanner.classList.add("hidden");
  } else {
    elSystemStatusDot.className = "status-dot offline";
    elSystemStatusText.textContent = "Backend Offline";
    elSystemStatusPill.style.borderColor = "#fecaca";
    elAlertBanner.classList.remove("hidden");
    elAlertMessage.textContent = `Backend connection unavailable (${message || "Retrying every 3s..."}). Ensure Docker or FastAPI is running.`;
  }
}

// Update top key metrics cards
function updateMetrics(stats) {
  elMetricTotalReadings.textContent = (stats.total_readings || 0).toLocaleString();

  if (stats.latest_reading) {
    const reading = stats.latest_reading;
    const status = reading.food_status || "Unknown";
    elMetricFoodStatus.textContent = status;
    elMetricFoodStatus.className = `status-badge-large status-${status.replace(/\s+/g, "")}`;

    if (reading.distance_cm < 0) {
      elMetricDistance.innerHTML = `<span style="color:#ef4444;">Error</span>`;
      elMetricFoodHint.textContent = "Sensor timeout or out of range";
    } else {
      elMetricDistance.innerHTML = `${reading.distance_cm.toFixed(1)} <span class="unit">cm</span>`;
      elMetricFoodHint.textContent = `Last reading: ${formatTimestamp(reading.received_at)}`;
    }

    elMetricActiveDevice.textContent = reading.device_id;
  } else {
    elMetricFoodStatus.textContent = "No Data";
    elMetricFoodStatus.className = "status-badge-large status-unknown";
    elMetricDistance.innerHTML = `-- <span class="unit">cm</span>`;
    elMetricFoodHint.textContent = "Waiting for initial ESP32 transmission...";
  }
}

// Update the visual container fluid height
function updateTankGraphic(latestReading) {
  if (!latestReading || latestReading.distance_cm < 0) {
    elTankFillLevel.style.height = "0%";
    elTankFillLabel.textContent = "--%";
    elTankFillLevel.className = "tank-fluid";
    return;
  }

  const dist = latestReading.distance_cm;
  const status = latestReading.food_status;

  // Approximate container visual height percentage based on distance thresholds
  let heightPct = 0;
  if (dist <= 1.0) heightPct = 95;
  else if (dist < 4.0) {
    // 1cm -> 95%, 4cm -> 70%
    heightPct = Math.round(95 - ((dist - 1.0) / 3.0) * 25);
  } else if (dist < 5.0) {
    // 4cm -> 70%, 5cm -> 45%
    heightPct = Math.round(70 - ((dist - 4.0) / 1.0) * 25);
  } else if (dist <= 6.0) {
    // 5cm -> 45%, 6cm -> 20%
    heightPct = Math.round(45 - ((dist - 5.0) / 1.0) * 25);
  } else {
    // > 6cm: Empty
    heightPct = Math.max(5, Math.round(20 - Math.min(dist - 6.0, 5) * 3));
  }

  elTankFillLevel.style.height = `${heightPct}%`;
  elTankFillLabel.textContent = `${heightPct}%`;
  elTankFillLevel.className = `tank-fluid fluid-${status.replace(/\s+/g, "")}`;
}

// Update Chart.js dataset with latest time-series readings
function updateChart(readings) {
  if (!chartInstance) return;

  // Clone and reverse so oldest reading is at the left, newest on right
  const chronological = [...readings].reverse();

  const labels = chronological.map(r => formatTimeOnly(r.recorded_at || r.received_at));
  const data = chronological.map(r => (r.distance_cm < 0 ? null : r.distance_cm));

  chartInstance.data.labels = labels;
  chartInstance.data.datasets[0].data = data;
  chartInstance.update();
}

// Update recent readings table
function updateTable(readings) {
  if (!readings || readings.length === 0) {
    elReadingsTableBody.innerHTML = `
      <tr>
        <td colspan="5" class="table-empty">No sensor readings stored in database yet.</td>
      </tr>
    `;
    return;
  }

  const top15 = readings.slice(0, 15);
  const rows = top15.map(r => {
    const timeFormatted = formatTimestamp(r.recorded_at || r.received_at);
    const distText = r.distance_cm < 0 ? '<span style="color:#ef4444;">Error</span>' : `${r.distance_cm.toFixed(1)} cm`;
    const statusClass = `status-${(r.food_status || "error").replace(/\s+/g, "")}`;

    return `
      <tr>
        <td>#${r.id}</td>
        <td>${timeFormatted}</td>
        <td><code>${r.device_id}</code></td>
        <td><strong>${distText}</strong></td>
        <td><span class="pill-sm ${statusClass}">${r.food_status}</span></td>
      </tr>
    `;
  });

  elReadingsTableBody.innerHTML = rows.join("");
}

// Update remote servo command status
function updateCommandStatus(latestCommands) {
  if (!latestCommands || latestCommands.length === 0) {
    elCmdBadge.className = "badge badge-idle";
    elCmdBadge.textContent = "Idle";
    elCmdMessage.textContent = "Ready to send servo gate command.";
    elMetricGateHint.textContent = "Gate: Closed (0°)";
    return;
  }

  const cmd = latestCommands[0];
  if (cmd.status === "PENDING") {
    elCmdBadge.className = "badge badge-pending";
    elCmdBadge.textContent = "Pending";
    elCmdMessage.textContent = `Command #${cmd.id} (${cmd.action}) enqueued. Awaiting ESP32 sync...`;
  } else if (cmd.status === "EXECUTED") {
    elCmdBadge.className = "badge badge-executed";
    elCmdBadge.textContent = "Executed";
    const execTime = cmd.executed_at ? formatTimeOnly(cmd.executed_at) : "recently";
    elCmdMessage.textContent = `Command #${cmd.id} (${cmd.action}) executed and confirmed by ESP32 at ${execTime}.`;
    
    if (cmd.action === "OPEN") {
      elMetricGateHint.textContent = "Gate: Open (90°)";
    } else {
      elMetricGateHint.textContent = "Gate: Closed (0°)";
    }
  } else {
    elCmdBadge.className = "badge badge-failed";
    elCmdBadge.textContent = cmd.status;
    elCmdMessage.textContent = `Command #${cmd.id} marked as ${cmd.status}.`;
  }
}

// Send servo command to FastAPI backend
async function sendCommand(action) {
  const buttons = [btnFeed, btnOpen, btnClose];
  buttons.forEach(b => b.disabled = true);

  elCmdBadge.className = "badge badge-pending";
  elCmdBadge.textContent = "Sending";
  elCmdMessage.textContent = `Sending ${action} command to backend...`;

  try {
    const res = await fetch(`${API_BASE}/api/commands`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        device_id: "esp32_feeder_01",
        action: action
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || `Server returned ${res.status}`);
    }

    const data = await res.json();
    elCmdBadge.className = "badge badge-pending";
    elCmdBadge.textContent = "Enqueued";
    elCmdMessage.textContent = `Command #${data.id} (${action}) saved in database. ESP32 will execute on next 3s reading cycle.`;

    // Immediately poll again to refresh UI
    setTimeout(fetchData, 800);
  } catch (err) {
    elCmdBadge.className = "badge badge-failed";
    elCmdBadge.textContent = "Error";
    elCmdMessage.textContent = `Failed to send command: ${err.message}`;
  } finally {
    setTimeout(() => {
      buttons.forEach(b => b.disabled = false);
    }, 1200);
  }
}

// ============================================================================
// Utilities
// ============================================================================
function formatTimestamp(isoStr) {
  if (!isoStr) return "--";
  const date = new Date(isoStr);
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
}

function formatTimeOnly(isoStr) {
  if (!isoStr) return "--";
  const date = new Date(isoStr);
  return date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
}

// ============================================================================
// Startup
// ============================================================================
document.addEventListener("DOMContentLoaded", () => {
  initChart();
  fetchData();
  // Poll every 3 seconds
  pollingTimer = setInterval(fetchData, REFRESH_INTERVAL_MS);
});

