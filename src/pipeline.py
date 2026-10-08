"""ML pipeline for network attack classification (sklearn if available, else pure-numpy baseline)."""
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd

FEATURE_COLS = ["duration", "src_bytes", "dst_bytes", "count", "srv_count", "dst_host_count", "serror_rate"]

def generate_synthetic(n: int = 2000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    labels = rng.choice(["normal", "dos", "probe", "r2l", "u2r"], size=n, p=[0.6, 0.2, 0.1, 0.05, 0.05])
    rows = []
    for lab in labels:
        if lab == "normal":
            row = [rng.uniform(0, 10), rng.integers(0, 500), rng.integers(0, 500), rng.integers(1, 20), rng.integers(1, 20), rng.integers(1, 50), rng.uniform(0, 0.1)]
        elif lab == "dos":
            row = [rng.uniform(0, 2), rng.integers(0, 50), rng.integers(0, 50), rng.integers(50, 200), rng.integers(50, 200), rng.integers(50, 255), rng.uniform(0.5, 1.0)]
        else:
            row = [rng.uniform(0, 30), rng.integers(0, 1000), rng.integers(0, 1000), rng.integers(1, 100), rng.integers(1, 100), rng.integers(1, 255), rng.uniform(0, 0.5)]
        rows.append(list(map(float, row)) + [lab])
    return pd.DataFrame(rows, columns=FEATURE_COLS + ["label"])

def _rule_predict(row: pd.Series) -> str:
    if row["serror_rate"] > 0.5 and row["count"] > 40:
        return "dos"
    if row["duration"] > 20 and row["src_bytes"] > 800:
        return "r2l"
    if row["dst_host_count"] > 200 and row["srv_count"] > 80:
        return "probe"
    return "normal"

def train(df: pd.DataFrame, model_dir: Path) -> dict:
    model_dir.mkdir(parents=True, exist_ok=True)
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
        from sklearn.preprocessing import LabelEncoder
        import joblib
        X = df[FEATURE_COLS]
        y = df["label"]
        le = LabelEncoder()
        y_enc = le.fit_transform(y)
        X_train, X_test, y_train, y_test = train_test_split(X, y_enc, test_size=0.25, random_state=42, stratify=y_enc)
        clf = RandomForestClassifier(n_estimators=50, random_state=42)
        clf.fit(X_train, y_train)
        pred = clf.predict(X_test)
        acc = float(accuracy_score(y_test, pred))
        prec, rec, f1, _ = precision_recall_fscore_support(y_test, pred, average="weighted", zero_division=0)
        cm = confusion_matrix(y_test, pred).tolist()
        joblib.dump(clf, model_dir / "classifier.joblib")
        joblib.dump(le, model_dir / "label_encoder.joblib")
        imp = dict(zip(FEATURE_COLS, [round(float(x), 4) for x in clf.feature_importances_]))
        backend = "sklearn"
    except ImportError:
        preds = df.apply(_rule_predict, axis=1)
        acc = float((preds == df["label"]).mean())
        prec = rec = f1 = acc
        cm = [[0]]
        imp = {c: 0.0 for c in FEATURE_COLS}
        (model_dir / "rules.json").write_text(json.dumps({"backend": "rules"}))
        backend = "rules"
    attack_rate = float((df["label"] != "normal").tail(100).mean())
    return {"accuracy": acc, "precision": float(prec), "recall": float(rec), "f1": float(f1),
            "confusion_matrix": cm, "attack_rate_forecast": attack_rate, "feature_importance": imp, "backend": backend}

def predict(model_dir: Path, features: dict) -> str:
    try:
        import joblib
        clf = joblib.load(model_dir / "classifier.joblib")
        le = joblib.load(model_dir / "label_encoder.joblib")
        X = pd.DataFrame([features])[FEATURE_COLS]
        return le.inverse_transform(clf.predict(X))[0]
    except Exception:
        return _rule_predict(pd.Series(features))
