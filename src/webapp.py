"""Local-only HTTP interface for the VectorCast forecast console."""
from __future__ import annotations

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
STATIC_FILES = {
    "/web/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/web/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/web/mark.svg": ("mark.svg", "image/svg+xml"),
}


def build_forecast_payload(n: int = 1200, horizon: int = 12) -> dict:
    """Return deterministic demo telemetry and its forecast for the browser UI."""
    if n not in ROW_OPTIONS:
        raise ValueError("rows must be between 400 and 4000 in steps of 200")
    if horizon < 1 or horizon > 24:
        raise ValueError("horizon must be between 1 and 24 hours")

    frame = load_cicids_style(n=n)
    volume = attack_volume_series(frame)
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

    last_time = volume.index[-1] if len(volume) else pd.Timestamp("2024-01-01")
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
        for label in ("dos", "probe", "r2l", "u2r")
    }
    historical_mean = float(recent["attack_count"].mean()) if not recent.empty else 0.0
    predicted_mean = (
        sum(item["attacks"] for item in predictions) / len(predictions)
        if predictions else 0.0
    )
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
        "synthetic": True,
    }


class ForecastHandler(BaseHTTPRequestHandler):
    """Serve fixed local assets and a small JSON forecast endpoint."""

    server_version = "VectorCastLocal/1.0"

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
            self._send_json(200, {"status": "ok", "mode": "local-demo"})
            return
        if parsed.path == "/api/forecast":
            query = parse_qs(parsed.query)
            try:
                n = int(query.get("n", ["1200"])[0])
                horizon = int(query.get("horizon", ["12"])[0])
                if n not in ROW_OPTIONS:
                    raise ValueError("Choose a row count from 400 to 4000 in steps of 200.")
                if horizon not in HORIZON_OPTIONS:
                    raise ValueError("Choose a forecast horizon of 6, 12, 18, or 24 hours.")
                self._send_json(200, build_forecast_payload(n, horizon))
            except (ValueError, TypeError, OverflowError) as error:
                self._send_json(400, {"error": str(error)})
            except Exception:
                self._send_json(500, {"error": "Forecast generation failed. Check the local environment."})
            return
        self._send_json(404, {"error": "Not found"})

    def log_message(self, format_string: str, *args: object) -> None:
        """Log route and status only; the app has no user accounts or remote traffic.""" 
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
