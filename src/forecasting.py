"""Time-series attack volume forecasting + synthetic CICIDS-style loader."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from src.pipeline import generate_synthetic

def load_cicids_style(path: Path | None = None, n: int = 3000) -> pd.DataFrame:
    if path and Path(path).exists():
        return pd.read_csv(path)
    df = generate_synthetic(n=n)
    df["timestamp"] = pd.date_range("2024-01-01", periods=len(df), freq="min")
    return df

def attack_volume_series(df: pd.DataFrame, freq: str = "h") -> pd.DataFrame:
    if "timestamp" not in df.columns:
        df = df.copy()
        df["timestamp"] = pd.date_range("2024-01-01", periods=len(df), freq="min")
    df = df.set_index("timestamp")
    is_attack = (df["label"] != "normal").astype(int)
    vol = is_attack.resample(freq).sum().rename("attack_count").to_frame()
    vol["total"] = df["label"].resample(freq).count()
    for lab in ["dos", "probe", "r2l", "u2r"]:
        vol[lab] = (df["label"] == lab).resample(freq).sum()
    return vol.fillna(0)

def forecast_volumes(vol: pd.DataFrame, horizon: int = 12) -> dict[str, Any]:
    y = vol["attack_count"].values.astype(float)
    if len(y) < 5:
        return {"backend": "none", "forecast": [], "history": y.tolist()}
    window = min(6, len(y) - 1)
    X, yy = [], []
    for i in range(window, len(y)):
        X.append(y[i - window:i]); yy.append(y[i])
    X, yy = np.array(X), np.array(yy)
    backend, model = "moving_average", None
    try:
        from sklearn.ensemble import GradientBoostingRegressor
        model = GradientBoostingRegressor(random_state=42)
        model.fit(X, yy)
        backend = "sklearn_gbr"
    except ImportError:
        pass
    preds, hist = [], list(y[-window:])
    for _ in range(horizon):
        p = float(model.predict([hist[-window:]])[0]) if model is not None else float(np.mean(hist[-window:]))
        p = max(0.0, p); preds.append(p); hist.append(p)
    mu, sigma = float(np.mean(y)), float(np.std(y) + 1e-6)
    alert_start = max(0, len(y) - 24)
    alerts = [{"index": int(alert_start+i), "value": float(v), "level": "high"} for i, v in enumerate(y[-24:]) if v > mu + 2*sigma]
    return {"backend": backend, "forecast": [round(p, 2) for p in preds], "history_tail": [float(x) for x in y[-24:]], "alerts": alerts, "metrics": {"train_points": len(yy), "mean_attack": round(mu, 2)}}

def evaluation_metrics(y_true, y_pred) -> dict[str, float]:
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred)**2)))
    mape = float(np.mean(np.abs((y_true - y_pred)/(np.abs(y_true)+1e-6)))*100)
    return {"mae": round(mae, 4), "rmse": round(rmse, 4), "mape": round(mape, 4)}
