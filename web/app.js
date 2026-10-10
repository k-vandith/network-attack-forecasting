const rowsInput = document.getElementById("rows");
const rowsValue = document.getElementById("rowsValue");
const horizonInput = document.getElementById("horizon");
const runButton = document.getElementById("runForecast");
const csvInput = document.getElementById("csvFile");
const dropZone = document.getElementById("dropZone");
const analyzeButton = document.getElementById("analyzeFile");
const fileName = document.getElementById("fileName");
const toast = document.getElementById("toast");

let mode = "demo";
let selectedFile = null;
let currentPayload = null;
let toastTimer = null;

const number = (value, digits = 0) => Number(value || 0).toLocaleString(undefined, {
  minimumFractionDigits: digits,
  maximumFractionDigits: digits
});

function escapeText(value) {
  return String(value).replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[char]);
}

function announce(message, isError = false) {
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.add("show");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toast.classList.remove("show"), 3300);
}

function setBusy(busy, label) {
  runButton.disabled = busy;
  runButton.classList.toggle("busy", busy);
  runButton.innerHTML = busy
    ? '<span class="run-icon">↻</span> ' + escapeText(label || "Calculating…")
    : '<span class="run-icon">▶</span> Run forecast';
  analyzeButton.disabled = busy || !selectedFile;
}

function setMode(nextMode) {
  mode = nextMode;
  const isUpload = mode === "upload";
  rowsInput.disabled = isUpload;
  rowsInput.closest(".sample-control").classList.toggle("control-disabled", isUpload);
  document.getElementById("workspaceStatus").innerHTML = isUpload
    ? '<i class="status-dot"></i> CSV loaded'
    : '<i class="status-dot"></i> Demo stream active';
  document.getElementById("sourceBadge").textContent = isUpload ? "SOURCE / CSV UPLOAD" : "SOURCE / DEMO";
  document.getElementById("sourceBadge").classList.toggle("uploaded", isUpload);
  document.getElementById("sampleControl").setAttribute("aria-disabled", String(isUpload));
  document.getElementById("resultSource").textContent = isUpload
    ? "Forecast calculated from uploaded data"
    : "Using reproducible synthetic traffic";
}

function updateReadout(data) {
  document.getElementById("outlookWord").textContent = data.outlook;
  document.getElementById("outlookWord").className = "outlook-word " + String(data.outlook || "").toLowerCase();
  const outlookCopy = {
    Stable: "Projected volume stays close to the recent observed baseline.",
    Watch: "Projected volume trends above baseline. Review the upcoming intervals.",
    Elevated: "Projected volume is materially above baseline. Validate against trusted telemetry."
  };
  document.getElementById("outlookText").textContent = outlookCopy[data.outlook] || "Compare the projection against the observed data.";
  document.getElementById("forecastTotal").textContent = number(data.forecast_total);
  document.getElementById("avgAttacks").textContent = number(data.average_attacks, 1);
  document.getElementById("attackShare").textContent = number(data.attack_share, 1) + "%";
  document.getElementById("backend").textContent = data.backend_label || "Unknown";
  document.getElementById("alertCount").textContent = number((data.alerts || []).length);
  document.getElementById("signalBadge").textContent = data.alerts.length ? data.alerts.length + " FLAGGED" : "CLEAR";
  document.getElementById("chartWindow").textContent = data.history.length + "H OBSERVED / " + data.forecast.length + "H PROJECTED";
  const dot = document.getElementById("outlookDot");
  dot.className = "status-dot outlook-" + String(data.outlook || "stable").toLowerCase();
}

function drawTrend(data) {
  const target = document.getElementById("trendChart");
  const history = data.history || [];
  const forecast = data.forecast || [];
  if (!history.length) {
    target.innerHTML = '<div class="chart-loading">Not enough observations to draw a chart.</div>';
    return;
  }
  const width = 980, height = 300, left = 45, right = 15, top = 16, bottom = 35;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const values = history.map(item => Number(item.attacks)).concat(forecast.map(item => Number(item.attacks)));
  const maxValue = Math.max(4, Math.ceil(Math.max(...values, 1) * 1.18));
  const x = index => left + index * plotWidth / Math.max(1, values.length - 1);
  const y = value => top + plotHeight - value / maxValue * plotHeight;
  const historyPoints = history.map((item, index) => [x(index), y(item.attacks)]);
  const forecastPoints = forecast.map((item, index) => [x(history.length - 1 + index + 1), y(item.attacks)]);
  const historicalPath = historyPoints.map((point, index) => (index ? "L" : "M") + point[0].toFixed(2) + " " + point[1].toFixed(2)).join(" ");
  const projectedPoints = [[historyPoints[historyPoints.length - 1][0], historyPoints[historyPoints.length - 1][1]]].concat(forecastPoints);
  const projectedPath = projectedPoints.map((point, index) => (index ? "L" : "M") + point[0].toFixed(2) + " " + point[1].toFixed(2)).join(" ");
  const areaPath = historicalPath + " L " + historyPoints[historyPoints.length - 1][0].toFixed(2) + " " + (top + plotHeight) + " L " + left + " " + (top + plotHeight) + " Z";
  const grid = [];
  for (let tick = 0; tick <= 4; tick += 1) {
    const value = maxValue * tick / 4;
    const yy = y(value);
    grid.push('<line x1="' + left + '" y1="' + yy + '" x2="' + (width - right) + '" y2="' + yy + '" stroke="#253744" stroke-width="1"/>');
    grid.push('<text x="' + (left - 10) + '" y="' + (yy + 3) + '" fill="#718797" font-size="10" text-anchor="end">' + Math.round(value) + '</text>');
  }
  const labelIndexes = [...new Set([0, Math.round((history.length - 1) / 3), Math.round(2 * (history.length - 1) / 3), history.length - 1])];
  const labels = labelIndexes.map(index => {
    const item = history[index];
    const anchor = index === 0 ? "start" : index === history.length - 1 ? "end" : "middle";
    return '<text x="' + x(index) + '" y="' + (height - 10) + '" fill="#8195a5" font-size="10" text-anchor="' + anchor + '">' + escapeText(item.tick) + '</text>';
  });
  if (forecast.length) {
    labels.push('<text x="' + x(history.length + forecast.length - 1) + '" y="' + (height - 10) + '" fill="#87a9ff" font-size="10" text-anchor="end">+' + forecast.length + 'h</text>');
  }
  const anomalies = history.filter(item => item.alert).map(item => {
    const index = history.findIndex(candidate => candidate.index === item.index);
    return '<circle cx="' + x(index) + '" cy="' + y(item.attacks) + '" r="5.3" fill="#0f1820" stroke="#ffc078" stroke-width="2.3"><title>Flagged interval: ' + item.attacks + ' attacks</title></circle>';
  }).join("");
  const circles = historyPoints.map((point, index) => {
    const item = history[index];
    return '<circle cx="' + point[0] + '" cy="' + point[1] + '" r="' + (index === history.length - 1 ? 3.7 : 2) + '" fill="#8de3b9" stroke="#0f1820" stroke-width="1"><title>' + escapeText(item.label) + ': ' + item.attacks + ' attacks</title></circle>';
  }).join("");
  target.innerHTML = '<svg viewBox="0 0 ' + width + ' ' + height + '" role="img" aria-label="Observed attack volume and forecast projection" preserveAspectRatio="xMidYMid meet">' +
    '<defs><linearGradient id="volumeFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#8de3b9" stop-opacity=".19"/><stop offset="100%" stop-color="#8de3b9" stop-opacity="0"/></linearGradient></defs>' +
    grid.join("") + '<path d="' + areaPath + '" fill="url(#volumeFill)"/><path d="' + historicalPath + '" fill="none" stroke="#8de3b9" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/><path d="' + projectedPath + '" fill="none" stroke="#87a9ff" stroke-width="2.4" stroke-dasharray="5 6" stroke-linecap="round" stroke-linejoin="round"/>' +
    circles + anomalies + labels.join("") + '</svg>';
}

function drawMix(data) {
  const target = document.getElementById("attackMix");
  const items = [
    { key: "dos", label: "Denial of service" },
    { key: "probe", label: "Probe / scan" },
    { key: "r2l", label: "Remote access" },
    { key: "u2r", label: "Privilege escalation" },
    { key: "other", label: "Other labels" }
  ];
  const totals = items.map(item => Number(data.attack_types[item.key] || 0));
  const max = Math.max(1, ...totals);
  target.innerHTML = items.map(item => {
    const count = Number(data.attack_types[item.key] || 0);
    const width = Math.round(count / max * 20) * 5;
    return '<div class="mix-row"><div class="mix-label">' + item.label + '</div><div class="mix-track"><div class="mix-fill mix-fill-' + item.key + ' w-' + width + '"></div></div><div class="mix-value">' + number(count) + '</div></div>';
  }).join("");
}

function drawSignals(data) {
  const target = document.getElementById("signalList");
  const alerts = (data.alerts || []).slice().reverse().slice(0, 5);
  if (!alerts.length) {
    target.innerHTML = '<div class="empty-signals"><span>✓</span><div><strong>No flagged intervals in the recent window.</strong><br>Keep monitoring as data changes.</div></div>';
    return;
  }
  target.innerHTML = alerts.map(item =>
    '<div class="signal-row"><span class="signal-mark">!</span><div><strong>' + escapeText(item.label) + '</strong><small>Observed volume · baseline threshold exceeded</small></div><span class="signal-count">' + number(item.attacks) + '</span></div>'
  ).join("");
}

function renderPayload(data) {
  currentPayload = data;
  updateReadout(data);
  drawTrend(data);
  drawMix(data);
  drawSignals(data);
  document.getElementById("resultSource").textContent = data.synthetic
    ? "Using reproducible synthetic traffic"
    : "Forecast calculated from uploaded CSV data";
}

async function runDemo() {
  setBusy(true, "Calculating…");
  try {
    const params = new URLSearchParams({ n: rowsInput.value, horizon: horizonInput.value });
    const response = await fetch("/api/forecast?" + params.toString(), {
      headers: { "Accept": "application/json" },
      cache: "no-store"
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Forecast request failed.");
    setMode("demo");
    renderPayload(data);
    announce("Demo forecast updated.");
  } catch (error) {
    announce(error.message || "Could not calculate the demo forecast.", true);
  } finally {
    setBusy(false);
  }
}

async function runUploaded() {
  if (!selectedFile) {
    announce("Choose a CSV file first.", true);
    return;
  }
  setBusy(true, "Analyzing CSV…");
  try {
    const params = new URLSearchParams({ horizon: horizonInput.value });
    const response = await fetch("/api/forecast/upload?" + params.toString(), {
      method: "POST",
      headers: { "Content-Type": "text/csv", "Accept": "application/json" },
      body: selectedFile,
      cache: "no-store"
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "CSV analysis failed.");
    setMode("upload");
    renderPayload(data);
    announce("Analyzed " + number(data.rows) + " rows from " + selectedFile.name + ".");
  } catch (error) {
    announce(error.message || "Could not analyze this CSV.", true);
  } finally {
    setBusy(false);
  }
}

async function runCurrent() {
  if (mode === "upload" && selectedFile) return runUploaded();
  return runDemo();
}

function chooseFile(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".csv")) {
    announce("Choose a .csv file.", true);
    return;
  }
  if (file.size <= 0) {
    announce("The selected file is empty.", true);
    return;
  }
  if (file.size > 5 * 1024 * 1024) {
    announce("CSV files must be 5 MB or smaller.", true);
    return;
  }
  selectedFile = file;
  fileName.textContent = file.name + " · " + number(file.size) + " bytes";
  fileName.classList.add("visible");
  dropZone.classList.add("has-file");
  analyzeButton.disabled = false;
  announce("CSV selected. Choose Analyze uploaded CSV to build the forecast.");
}

function downloadFile(filename, content, type) {
  const blob = new Blob([content], { type: type });
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
  if (!currentPayload) return announce("Run a forecast before exporting.", true);
  const records = [
    ["series", "time", "attack_count", "total_records", "dos", "probe", "r2l", "u2r", "other"],
    ...currentPayload.history.map(item => ["observed", item.label, item.attacks, item.total, item.dos, item.probe, item.r2l, item.u2r, ""]),
    ...currentPayload.forecast.map(item => ["forecast", item.label, item.attacks, "", "", "", "", "", ""])
  ];
  const csv = records.map(row => row.map(value => '"' + String(value ?? "").replace(/"/g, '""') + '"').join(",")).join("\r\n");
  downloadFile("vectorcast-forecast.csv", csv, "text/csv;charset=utf-8");
  announce("Forecast CSV exported.");
}

function exportJson() {
  if (!currentPayload) return announce("Run a forecast before exporting.", true);
  const report = {
    product: "VectorCast",
    generated_at: new Date().toISOString(),
    disclaimer: "Forecasts and threshold flags are illustrative and are not operational detections.",
    ...currentPayload
  };
  downloadFile("vectorcast-forecast.json", JSON.stringify(report, null, 2), "application/json");
  announce("JSON report exported.");
}

function downloadTemplate() {
  const rows = [["timestamp", "label"]];
  const categories = ["normal", "normal", "normal", "normal", "dos", "normal", "probe", "normal", "r2l", "u2r"];
  const start = Date.UTC(2026, 0, 1, 0, 0, 0);
  for (let index = 0; index < 360; index += 1) {
    const timestamp = new Date(start + index * 60000).toISOString();
    rows.push([timestamp, categories[index % categories.length]]);
  }
  const csv = rows.map(row => row.map(value => '"' + value.replace(/"/g, '""') + '"').join(",")).join("\r\n");
  downloadFile("vectorcast-sample-traffic.csv", csv, "text/csv;charset=utf-8");
  announce("Sample CSV downloaded.");
}

function useDemo() {
  selectedFile = null;
  csvInput.value = "";
  fileName.textContent = "No file selected · demo is ready";
  fileName.classList.remove("visible");
  dropZone.classList.remove("has-file", "dragging");
  analyzeButton.disabled = true;
  setMode("demo");
  runDemo();
}

rowsInput.addEventListener("input", () => {
  rowsValue.textContent = number(rowsInput.value) + " rows";
});
rowsInput.addEventListener("change", () => {
  if (mode === "demo") runDemo();
});
horizonInput.addEventListener("change", runCurrent);
runButton.addEventListener("click", runCurrent);
analyzeButton.addEventListener("click", runUploaded);
document.getElementById("useDemo").addEventListener("click", useDemo);
document.getElementById("downloadTemplate").addEventListener("click", downloadTemplate);
document.getElementById("exportCsv").addEventListener("click", exportCsv);
document.getElementById("exportJson").addEventListener("click", exportJson);
document.getElementById("browseCsv").addEventListener("click", event => {
  event.stopPropagation();
  csvInput.click();
});
csvInput.addEventListener("change", () => chooseFile(csvInput.files && csvInput.files[0]));
dropZone.addEventListener("click", event => {
  if (event.target.closest("button")) return;
  csvInput.click();
});
dropZone.addEventListener("keydown", event => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    csvInput.click();
  }
});
dropZone.addEventListener("dragover", event => {
  event.preventDefault();
  dropZone.classList.add("dragging");
});
dropZone.addEventListener("dragleave", event => {
  if (!dropZone.contains(event.relatedTarget)) dropZone.classList.remove("dragging");
});
dropZone.addEventListener("drop", event => {
  event.preventDefault();
  dropZone.classList.remove("dragging");
  const file = event.dataTransfer && event.dataTransfer.files[0];
  if (file) chooseFile(file);
});

runDemo();
