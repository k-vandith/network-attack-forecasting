const rowsInput = document.getElementById("rows");
const rowsValue = document.getElementById("rowsValue");
const horizonInput = document.getElementById("horizon");
const refreshButton = document.getElementById("refresh");
const toast = document.getElementById("toast");
let currentPayload = null;
let toastTimer = null;

const formatNumber = (value, digits = 0) => Number(value || 0).toLocaleString(undefined, {
  minimumFractionDigits: digits,
  maximumFractionDigits: digits
});

function announce(message, isError = false) {
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.add("show");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toast.classList.remove("show"), 2800);
}

function escapeText(value) {
  return String(value).replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
}

function updateOutlook(data) {
  const outlook = document.getElementById("outlookWord");
  outlook.textContent = data.outlook;
  outlook.className = "";
  const descriptions = {
    Stable: "Predicted volume is tracking close to the recent observed baseline.",
    Watch: "The projection is trending above the recent average. Review the upcoming windows.",
    Elevated: "Projected attack volume is materially above the recent baseline. Validate with trusted telemetry."
  };
  document.getElementById("outlookText").textContent = descriptions[data.outlook] || "Relative to the recent observed baseline.";
  document.getElementById("forecastTotal").textContent = formatNumber(data.forecast_total);
  document.getElementById("forecastHours").textContent = String(data.forecast.length);
}

function updateMetrics(data) {
  document.getElementById("attackEvents").textContent = formatNumber(data.attack_events);
  document.getElementById("attackShare").textContent = formatNumber(data.attack_share, 1) + "%";
  document.getElementById("avgAttacks").textContent = formatNumber(data.average_attacks, 1);
  document.getElementById("backend").textContent = data.backend_label;
  document.getElementById("modelStatus").textContent = data.backend === "moving_average" ? "Fallback engine" : "Local calculation";
  document.getElementById("alertCount").textContent = formatNumber(data.alerts.length);
  document.getElementById("sourceRows").textContent = formatNumber(data.rows) + " rows";
  document.getElementById("signalBadge").textContent = data.alerts.length ? data.alerts.length + " FLAGGED" : "CLEAR";
  document.getElementById("chartWindow").textContent = "Window: " + data.history.length + " observed intervals";
  updateOutlook(data);
}

function drawTrend(data) {
  const target = document.getElementById("trendChart");
  const history = data.history || [];
  const forecast = data.forecast || [];
  if (!history.length) {
    target.innerHTML = '<div class="chart-loading">Not enough observations to draw the chart.</div>';
    return;
  }
  const width = 920;
  const height = 280;
  const left = 43;
  const right = 14;
  const top = 16;
  const bottom = 34;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const values = history.map(item => Number(item.attacks)).concat(forecast.map(item => Number(item.attacks)));
  const maxValue = Math.max(4, Math.ceil(Math.max(...values, 1) * 1.18));
  const x = index => left + index * plotWidth / Math.max(1, values.length - 1);
  const y = value => top + plotHeight - value / maxValue * plotHeight;
  const historyPoints = history.map((item, index) => [x(index), y(item.attacks)]);
  const forecastPoints = forecast.map((item, index) => [x(history.length - 1 + index + 1), y(item.attacks)]);
  const historicalPath = historyPoints.map((point, index) => (index ? "L" : "M") + point[0].toFixed(2) + " " + point[1].toFixed(2)).join(" ");
  const projectedPath = [[historyPoints[historyPoints.length - 1][0], historyPoints[historyPoints.length - 1][1]]]
    .concat(forecastPoints).map((point, index) => (index ? "L" : "M") + point[0].toFixed(2) + " " + point[1].toFixed(2)).join(" ");
  const areaPath = historicalPath + " L " + historyPoints[historyPoints.length - 1][0].toFixed(2) + " " + (top + plotHeight) + " L " + left + " " + (top + plotHeight) + " Z";
  const grid = [];
  for (let tick = 0; tick <= 4; tick += 1) {
    const value = maxValue * tick / 4;
    const yy = y(value);
    grid.push('<line x1="' + left + '" y1="' + yy + '" x2="' + (width - right) + '" y2="' + yy + '" stroke="#edf0f6" stroke-width="1"/>');
    grid.push('<text x="' + (left - 10) + '" y="' + (yy + 3) + '" fill="#a2a9b9" font-size="10" text-anchor="end">' + Math.round(value) + '</text>');
  }
  const labelIndexes = [...new Set([0, Math.round((history.length - 1) / 2), history.length - 1])];
  const labels = labelIndexes.map(index => {
    const item = history[index];
    return '<text x="' + x(index) + '" y="' + (height - 10) + '" fill="#9ba3b4" font-size="10" text-anchor="' + (index === 0 ? "start" : index === history.length - 1 ? "end" : "middle") + '">' + escapeText(item.tick) + '</text>';
  });
  const forecastLabels = forecast.length ? [
    '<text x="' + x(history.length - 1 + forecast.length) + '" y="' + (height - 10) + '" fill="#8e7de0" font-size="10" text-anchor="end">' + escapeText(forecast[forecast.length - 1].tick) + '</text>'
  ] : [];
  const anomalies = history.filter(item => item.alert).map(item =>
    '<circle cx="' + x(history.findIndex(candidate => candidate.index === item.index)) + '" cy="' + y(item.attacks) + '" r="5.3" fill="#fff" stroke="#f4a247" stroke-width="2.5"><title>Flagged observed window: ' + item.attacks + ' attacks</title></circle>'
  ).join("");
  const circles = historyPoints.map((point, index) => {
    const item = history[index];
    const radius = index === history.length - 1 ? 4 : 2.2;
    return '<circle cx="' + point[0] + '" cy="' + point[1] + '" r="' + radius + '" fill="#4569f5" stroke="#fff" stroke-width="1"><title>' + escapeText(item.label) + ': ' + item.attacks + ' attacks</title></circle>';
  }).join("");
  target.innerHTML = '<svg viewBox="0 0 ' + width + ' ' + height + '" role="img" aria-label="Observed hourly attack counts and forecast projection" preserveAspectRatio="xMidYMid meet"><defs><linearGradient id="historyFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#4569f5" stop-opacity=".18"/><stop offset="100%" stop-color="#4569f5" stop-opacity="0"/></linearGradient></defs>' +
    grid.join("") + '<path d="' + areaPath + '" fill="url(#historyFill)"/><path d="' + historicalPath + '" fill="none" stroke="#4569f5" stroke-width="2.7" stroke-linecap="round" stroke-linejoin="round"/><path d="' + projectedPath + '" fill="none" stroke="#9176f7" stroke-width="2.7" stroke-dasharray="5 6" stroke-linecap="round" stroke-linejoin="round"/>' +
    circles + anomalies + labels.join("") + forecastLabels.join("") + '</svg>';
}

function drawMix(data) {
  const target = document.getElementById("attackMix");
  const items = [
    { key: "dos", label: "Denial of service", color: "#4569f5" },
    { key: "probe", label: "Probe", color: "#8e75f4" },
    { key: "r2l", label: "Remote access", color: "#f3a247" },
    { key: "u2r", label: "Privilege escalation", color: "#e56e7c" }
  ];
  const max = Math.max(1, ...items.map(item => data.attack_types[item.key] || 0));
  target.innerHTML = items.map(item => {
    const count = Number(data.attack_types[item.key] || 0);
    const width = Math.round(count / max * 20) * 5;
    return '<div class="mix-row"><div class="mix-label">' + item.label + '</div><div class="mix-track"><div class="mix-fill mix-fill-' + item.key + ' w-' + width + '"></div></div><div class="mix-value">' + formatNumber(count) + '</div></div>';
  }).join("");
}

function drawSignals(data) {
  const target = document.getElementById("signalList");
  const alerts = (data.alerts || []).slice().reverse().slice(0, 4);
  if (!alerts.length) {
    target.innerHTML = '<div class="empty-signals"><span>✓</span><div><strong>No high-volume anomalies in the latest window.</strong><br>Continue monitoring as fresh data arrives.</div></div>';
    return;
  }
  target.innerHTML = alerts.map(item =>
    '<div class="signal-row"><span class="signal-mark">!</span><div><strong>' + escapeText(item.label) + '</strong><small>Observed volume · mean + 2σ threshold</small></div><span class="signal-count">' + formatNumber(item.attacks) + '</span></div>'
  ).join("");
}

async function loadForecast() {
  refreshButton.disabled = true;
  refreshButton.classList.add("busy");
  const refreshLabel = refreshButton.querySelector("span:last-child");
  const originalLabel = refreshLabel.textContent;
  refreshLabel.textContent = "Calculating…";
  try {
    const params = new URLSearchParams({
      n: rowsInput.value,
      horizon: horizonInput.value
    });
    const response = await fetch("/api/forecast?" + params.toString(), {
      headers: { "Accept": "application/json" },
      cache: "no-store"
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Forecast request failed.");
    currentPayload = data;
    updateMetrics(data);
    drawTrend(data);
    drawMix(data);
    drawSignals(data);
    announce("Forecast updated for " + formatNumber(data.rows) + " synthetic records.");
  } catch (error) {
    announce(error.message || "Unable to load the forecast.", true);
  } finally {
    refreshButton.disabled = false;
    refreshButton.classList.remove("busy");
    refreshLabel.textContent = originalLabel;
  }
}

function downloadFile(filename, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function exportCsv() {
  if (!currentPayload) return announce("Load a forecast before exporting.", true);
  const records = [
    ["series", "time", "attack_count", "total_records", "dos", "probe", "r2l", "u2r"],
    ...currentPayload.history.map(item => ["observed", item.label, item.attacks, item.total, item.dos, item.probe, item.r2l, item.u2r]),
    ...currentPayload.forecast.map(item => ["forecast", item.label, item.attacks, "", "", "", "", ""])
  ];
  const csv = records.map(row => row.map(value => '"' + String(value ?? "").replace(/"/g, '""') + '"').join(",")).join("\r\n");
  downloadFile("vectorcast-forecast.csv", csv, "text/csv;charset=utf-8");
  announce("CSV export prepared.");
}

function exportJson() {
  if (!currentPayload) return announce("Load a forecast before exporting.", true);
  const report = {
    product: "VectorCast",
    generated_at: new Date().toISOString(),
    disclaimer: "Synthetic demonstration data. Forecasts are indicative and are not an operational detection system.",
    ...currentPayload
  };
  downloadFile("vectorcast-forecast.json", JSON.stringify(report, null, 2), "application/json");
  announce("JSON report prepared.");
}

rowsInput.addEventListener("input", () => {
  rowsValue.textContent = formatNumber(rowsInput.value);
});
refreshButton.addEventListener("click", loadForecast);
horizonInput.addEventListener("change", loadForecast);
rowsInput.addEventListener("change", loadForecast);
document.getElementById("exportCsv").addEventListener("click", exportCsv);
document.getElementById("exportJson").addEventListener("click", exportJson);

loadForecast();
