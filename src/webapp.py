"""Local-only HTTP API for the VectorCast forecasting console."""
from __future__ import annotations

import io
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd

from src.forecasting import attack_volume_series, forecast_volumes, load_cicids_style

ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"
ROW_OPTIONS = set(range(400, 4001, 200))
HORIZON_OPTIONS = {6, 12, 18, 24}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_UPLOAD_ROWS = 100_000
STATIC_FILES = {
    "/web/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/web/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/web/mark.svg": ("mark.svg", "image/svg+xml"),
}

LABEL_HEADERS = {"label", "class", "attack", "attack_type", "category", "target", "y"}
TIME_HEADERS = {"timestamp", "time", "datetime", "date_time", "event_time", "date"}


def _header_key(value: object) -> str:
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")


def _canonical_label(value: object) -> str:
    label = str(value).strip().lower()
    compact = label.replace("_", " ").replace("-", " ")
    if compact in {"normal", "normal.", "benign", "benign.", "benign traffic", "legitimate", "0", "false"}:
        return "normal"
    if any(token in compact for token in ("ddos", "dos", "denial of service", "slowloris", "slow http", "hulk", "goldeneye", "syn flood", "udp flood")):
        return "dos"
    if any(token in compact for token in ("probe", "portscan", "port scan", "scan", "reconnaissance")):
        return "probe"
    if any(token in compact for token in ("u2r", "privilege", "escalation", "rootkit", "local exploit")):
        return "u2r"
    if any(token in compact for token in ("r2l", "remote to local", "brute", "patator", "credential", "password", "ftp write", "ssh attack")):
        return "r2l"
    return "other"


def _prepare_csv(raw: bytes) -> pd.DataFrame:
    """Parse and normalize uploaded CSV bytes without writing them to disk."""
    if not raw:
        raise ValueError("The selected CSV is empty.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError("CSV files must be 5 MB or smaller.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("CSV must use UTF-8 text encoding.") from error

    try:
        frame = pd.read_csv(io.StringIO(text), nrows=MAX_UPLOAD_ROWS + 1)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError) as error:
        raise ValueError("Could not read this CSV. Check the headers and row formatting.") from error

    if frame.empty:
        raise ValueError("The CSV has a header but no data rows.")
    if len(frame) > MAX_UPLOAD_ROWS:
        raise ValueError(f"CSV files can contain at most {MAX_UPLOAD_ROWS:,} rows.")

    normalized_headers = {_header_key(column): column for column in frame.columns}
    label_column = next((normalized_headers[key] for key in LABEL_HEADERS if key in normalized_headers), None)
    if label_column is None:
        raise ValueError("A label column is required. Use label, class, attack_type, category, or target.")

    labels = frame[label_column].astype("string").str.strip()
    if labels.isna().any() or labels.eq("").any():
        raise ValueError("The label column contains blank values. Remove or fill those rows.")
    prepared = pd.DataFrame({"label": labels.map(_canonical_label).astype(str)})

    time_column = next((normalized_headers[key] for key in TIME_HEADERS if key in normalized_headers), None)
    if time_column is not None:
        timestamps = pd.to_datetime(frame[time_column], errors="coerce", utc=True)
        if timestamps.isna().any():
            raise ValueError("Some timestamps could not be parsed. Use consistent date/time values or remove the timestamp column.")
        prepared["timestamp"] = timestamps
        prepared = prepared.sort_values("timestamp", kind="stable").reset_index(drop=True)
    else:
        # Without timestamps, assume one event per minute and state this in the UI.
        prepared["timestamp"] = pd.date_range("2026-01-01", periods=len(prepared), freq="min", tz="UTC")

    return prepared


def _build_payload(frame: pd.DataFrame, horizon: int, synthetic: bool) -> dict:
    if horizon not in HORIZON_OPTIONS:
        raise ValueError("Choose a forecast horizon of 6, 12, 18, or 24 hours.")

    volume = attack_volume_series(frame)
    if len(volume) < 5:
        raise ValueError(
            "The CSV must cover at least five hourly intervals. Include timestamps spanning five hours, "
            "or omit timestamps and provide at least 241 event rows."
        )

    result = forecast_volumes(volume, horizon=horizon)
    recent = volume.tail(24)
    raw_alerts = result.get("alerts") or []
    alert_indexes = {int(item["index"]) for item in raw_alerts}
    first_index = len(volume) - len(recent)

    history = []
    for offset, (timestamp, row) in enumerate(recent.iterrows()):
        absolute_index = first_index + offset
        history.append({
            "index": absolute_index,
            "label": timestamp.strftime("%b %d %H:%M"),
            "tick": timestamp.strftime("%H:%M"),
            "attacks": int(row["attack_count"]),
            "total": int(row["total"]),
            "dos": int(row["dos"]),
            "probe": int(row["probe"]),
            "r2l": int(row["r2l"]),
            "u2r": int(row["u2r"]),
            "alert": absolute_index in alert_indexes,
        })

    last_time = volume.index[-1]
    predictions = [
        {
            "label": (last_time + pd.Timedelta(hours=step)).strftime("%b %d %H:%M"),
            "tick": f"+{step}h",
            "attacks": float(value),
        }
        for step, value in enumerate(result.get("forecast") or [], start=1)
    ]

    attack_total = int((frame["label"] != "normal").sum())
    type_totals = {
        label: int((frame["label"] == label).sum())
        for label in ("dos", "probe", "r2l", "u2r", "other")
    }
    historical_mean = float(recent["attack_count"].mean()) if not recent.empty else 0.0
    predicted_mean = sum(item["attacks"] for item in predictions) / len(predictions) if predictions else 0.0

    if historical_mean > 0 and predicted_mean >= historical_mean * 1.12:
        outlook = "Elevated"
    elif historical_mean > 0 and predicted_mean >= historical_mean * 1.04:
        outlook = "Watch"
    else:
        outlook = "Stable"

    backend = result.get("backend", "none")
    backend_labels = {
        "sklearn_gbr": "Gradient boosting",
        "moving_average": "Moving-average baseline",
        "none": "Insufficient history",
    }
    metrics = result.get("metrics") or {}
    return {
        "rows": int(len(frame)),
        "history": history,
        "forecast": predictions,
        "attack_types": type_totals,
        "attack_events": attack_total,
        "attack_share": round(attack_total / max(1, len(frame)) * 100, 1),
        "average_attacks": round(historical_mean, 2),
        "forecast_average": round(predicted_mean, 2),
        "forecast_total": round(sum(item["attacks"] for item in predictions)),
        "outlook": outlook,
        "backend": backend,
        "backend_label": backend_labels.get(backend, backend.replace("_", " ").title()),
        "train_points": int(metrics.get("train_points", 0)),
        "alerts": [item for item in history if item["alert"]],
        "synthetic": synthetic,
        "source_label": "Synthetic sample" if synthetic else "Uploaded CSV",
    }


def build_forecast_payload(n: int = 1200, horizon: int = 12) -> dict:
    """Return a deterministic forecast using generated sample traffic."""
    if n not in ROW_OPTIONS:
        raise ValueError("rows must be between 400 and 4000 in steps of 200")
    if horizon not in HORIZON_OPTIONS:
        raise ValueError("Choose a forecast horizon of 6, 12, 18, or 24 hours.")
    return _build_payload(load_cicids_style(n=n), horizon, synthetic=True)


def build_uploaded_payload(raw: bytes, horizon: int = 12) -> dict:
    """Forecast an uploaded CSV without retaining the file on disk."""
    frame = _prepare_csv(raw)
    return _build_payload(frame, horizon, synthetic=False)


class ForecastHandler(BaseHTTPRequestHandler):
    """Serve fixed local assets and validated forecast endpoints."""

    server_version = "VectorCastLocal/1.1"

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
            "form-action 'none'; frame-ancestors 'none'",
        )
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, value: dict) -> None:
        body = json.dumps(value, separators=(",", ":"), allow_nan=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send(200, (WEB_ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
            return
        if parsed.path in STATIC_FILES:
            filename, content_type = STATIC_FILES[parsed.path]
            self._send(200, (WEB_ROOT / filename).read_bytes(), content_type)
            return
        if parsed.path == "/api/health":
            self._send_json(200, {"status": "ok", "mode": "local-only"})
            return
        if parsed.path == "/api/forecast":
            query = parse_qs(parsed.query)
            try:
                n = int(query.get("n", ["1200"])[0])
                horizon = int(query.get("horizon", ["12"])[0])
                self._send_json(200, build_forecast_payload(n, horizon))
            except (ValueError, TypeError, OverflowError) as error:
                self._send_json(400, {"error": str(error)})
            except Exception:
                self._send_json(500, {"error": "Forecast generation failed. Check the local environment."})
            return
        self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/forecast/upload":
            self._send_json(404, {"error": "Not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": "Invalid request size."})
            return
        if content_length <= 0:
            self._send_json(400, {"error": "Select a CSV file to upload."})
            return
        if content_length > MAX_UPLOAD_BYTES:
            self._send_json(413, {"error": "CSV files must be 5 MB or smaller."})
            return
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type not in {"text/csv", "application/vnd.ms-excel", "application/octet-stream"}:
            self._send_json(415, {"error": "Upload a CSV file using the CSV file picker."})
            return

        raw = self.rfile.read(content_length)
        query = parse_qs(parsed.query)
        try:
            horizon = int(query.get("horizon", ["12"])[0])
            payload = build_uploaded_payload(raw, horizon)
            self._send_json(200, payload)
        except (ValueError, TypeError, OverflowError) as error:
            self._send_json(400, {"error": str(error)})
        except Exception:
            self._send_json(500, {"error": "CSV forecast failed. Check the headers and timestamp values."})

    def log_message(self, format_string: str, *args: object) -> None:
        """Log the route and status without logging upload contents."""
        print(f"[VectorCast] {self.address_string()} - {format_string % args}")


def main() -> None:
    """Start the dashboard on the loopback interface only."""
    try:
        port = int(os.environ.get("PORT", "8501"))
    except ValueError as error:
        raise SystemExit("PORT must be a valid integer.") from error
    if not 1 <= port <= 65535:
        raise SystemExit("PORT must be between 1 and 65535.")
    server = ThreadingHTTPServer(("127.0.0.1", port), ForecastHandler)
    print(f"VectorCast is ready at http://127.0.0.1:{port} (local-only)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping VectorCast.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
