"""Time-series attack volume forecasting + synthetic CICIDS-style loader."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.labels import canonical_label
from src.pipeline import generate_synthetic

# Prefer the canonical field first when a source provides multiple accepted aliases.
_LABEL_HEADERS = ("label", "class", "attack", "attack_type", "category", "target", "y")
_TIME_HEADERS = ("timestamp", "datetime", "date_time", "event_time", "time", "date")


def _header_key(value: object) -> str:
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")


def _normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize a CICIDS-style frame for the forecasting helpers."""
    if df.empty:
        raise ValueError("The input dataset has no rows.")

    result = df.copy()
    normalized = {_header_key(column): column for column in result.columns}
    label_column = next((normalized[key] for key in _LABEL_HEADERS if key in normalized), None)
    if label_column is None:
        raise ValueError("A label column is required. Use label, class, attack_type, category, or target.")
    result = result.rename(columns={label_column: "label"})
    labels = result["label"].astype("string").str.strip()
    if labels.isna().any() or labels.eq("").any():
        raise ValueError("The label column contains blank values. Remove or fill those rows.")
    result["label"] = labels.map(canonical_label).astype(str)

    normalized = {_header_key(column): column for column in result.columns}
    timestamp_column = next((normalized[key] for key in _TIME_HEADERS if key in normalized), None)
    if timestamp_column is not None and timestamp_column != "timestamp":
        result = result.rename(columns={timestamp_column: "timestamp"})
    if "timestamp" in result.columns:
        timestamps = pd.to_datetime(result["timestamp"], errors="coerce", utc=True)
        if timestamps.isna().any():
            raise ValueError("Some timestamps could not be parsed. Use consistent date/time values or remove the timestamp column.")
        result["timestamp"] = timestamps
        result = result.sort_values("timestamp", kind="stable").reset_index(drop=True)
    else:
        result["timestamp"] = pd.date_range(
            "2024-01-01", periods=len(result), freq="min", tz="UTC"
        )
    return result


def load_cicids_style(path: Path | None = None, n: int = 3000) -> pd.DataFrame:
    """Load and normalize a file or make a deterministic synthetic example."""
    if path is not None:
        source = Path(path).expanduser()
        if not source.is_file():
            raise FileNotFoundError(f"Dataset file not found: {source}")
        return _normalize_frame(pd.read_csv(source))
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise ValueError("Synthetic row count must be a positive integer.")
    df = generate_synthetic(n=n)
    df["timestamp"] = pd.date_range(
        "2024-01-01", periods=len(df), freq="min", tz="UTC"
    )
    return _normalize_frame(df)


def attack_volume_series(df: pd.DataFrame, freq: str = "h") -> pd.DataFrame:
    """Aggregate canonical attack labels into time buckets in chronological order."""
    prepared = _normalize_frame(df)
    indexed = prepared.set_index("timestamp").sort_index(kind="stable")
    is_attack = (indexed["label"] != "normal").astype(int)
    try:
        vol = is_attack.resample(freq).sum().rename("attack_count").to_frame()
        vol["total"] = indexed["label"].resample(freq).count()
        for label in ("dos", "probe", "r2l", "u2r"):
            vol[label] = (indexed["label"] == label).resample(freq).sum()
    except (TypeError, ValueError) as error:
        raise ValueError(f"Unsupported time-series frequency: {freq!r}.") from error
    return vol.fillna(0)


def forecast_volumes(vol: pd.DataFrame, horizon: int = 12) -> dict[str, Any]:
    if not isinstance(horizon, int) or isinstance(horizon, bool) or horizon < 1:
        raise ValueError("Forecast horizon must be a positive integer.")
    if "attack_count" not in vol.columns:
        raise ValueError("Volume data must include an 'attack_count' column.")

    y = pd.to_numeric(vol["attack_count"], errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(y).all():
        raise ValueError("Attack-volume history contains missing or non-finite values.")
    if (y < 0).any():
        raise ValueError("Attack-volume history cannot contain negative counts.")
    if len(y) < 5:
        return {"backend": "none", "forecast": [], "history": y.tolist()}

    window = min(6, len(y) - 1)
    X, yy = [], []
    for i in range(window, len(y)):
        X.append(y[i - window:i])
        yy.append(y[i])
    X, yy = np.array(X), np.array(yy)
    backend, model = "moving_average", None
    try:
        from sklearn.ensemble import GradientBoostingRegressor

        model = GradientBoostingRegressor(random_state=42)
        model.fit(X, yy)
        backend = "sklearn_gbr"
    except ImportError:
        pass

    predictions, history = [], list(y[-window:])
    for _ in range(horizon):
        value = (
            float(model.predict([history[-window:]])[0])
            if model is not None
            else float(np.mean(history[-window:]))
        )
        value = max(0.0, value)
        predictions.append(value)
        history.append(value)

    mean = float(np.mean(y))
    sigma = float(np.std(y) + 1e-6)
    alert_start = max(0, len(y) - 24)
    alerts = [
        {"index": int(alert_start + i), "value": float(value), "level": "high"}
        for i, value in enumerate(y[-24:])
        if value > mean + 2 * sigma
    ]
    return {
        "backend": backend,
        "forecast": [round(value, 2) for value in predictions],
        "history_tail": [float(value) for value in y[-24:]],
        "alerts": alerts,
        "metrics": {"train_points": len(yy), "mean_attack": round(mean, 2)},
    }


def evaluation_metrics(y_true, y_pred) -> dict[str, float]:
    actual = np.asarray(y_true, dtype=float)
    predicted = np.asarray(y_pred, dtype=float)
    if actual.ndim != 1 or predicted.ndim != 1 or actual.size == 0:
        raise ValueError("Evaluation inputs must be non-empty one-dimensional arrays.")
    if actual.shape != predicted.shape:
        raise ValueError("Actual and predicted arrays must have the same length.")
    if not np.isfinite(actual).all() or not np.isfinite(predicted).all():
        raise ValueError("Evaluation inputs must contain only finite values.")

    mae = float(np.mean(np.abs(actual - predicted)))
    rmse = float(np.sqrt(np.mean((actual - predicted) ** 2)))
    mape = float(np.mean(np.abs((actual - predicted) / (np.abs(actual) + 1e-6))) * 100)
    return {"mae": round(mae, 4), "rmse": round(rmse, 4), "mape": round(mape, 4)}
