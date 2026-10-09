# Network Attack Forecasting

Machine-learning pipeline for forecasting network attack likelihood from feature tables, with a rules-based fallback when sklearn models are unavailable.

## Problem Statement

SOC teams need early indicators of elevated attack risk from historical telemetry features. Many environments cannot train deep models; a portable pipeline with transparent fallbacks is required.

## Overview

Train a classifier on synthetic or provided feature CSVs, score new windows, and visualise forecasts in Streamlit. If scikit-learn is missing, deterministic rules still produce risk labels.

## Features

- **Feature-table training** – CSV in, model out
- **Sklearn classifiers** with joblib persistence
- **Rules fallback** – works without heavy ML deps
- **Streamlit dashboard** – train / score / plot
- **Demo dataset generator**

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Streamlit  │────▶│   Pipeline   │────▶│ Sklearn or  │
│     UI      │     │              │     │ Rules engine│
└─────────────┘     └──────┬───────┘     └─────────────┘
                           │
                    ┌──────▼───────┐
                    │ models/ + CSV│
                    └──────────────┘
```

## Tech Stack

- Python 3.11+
- Pandas / NumPy
- scikit-learn (optional)
- Streamlit + Plotly
- joblib
- pytest

## Repository Structure

```
network-attack-forecasting/
├── README.md
├── requirements.txt
├── src/
│   └── pipeline.py
├── tests/
│   └── test_pipeline.py
├── models/
├── data/
├── scripts/
│   ├── setup_env.py
│   ├── setup.sh
│   ├── setup.ps1
│   └── generate_demo_data.py
└── docs/
```

## System Requirements

| Mode | CPU | RAM | Disk | GPU |
|------|-----|-----|------|-----|
| Demo | Any | 2 GB | 1 GB | Not needed |

## Installation

### Recommended (all platforms) — automated bootstrap

Handles missing `ensurepip`, symlink restrictions, and installs dependencies into `.venv`:

```bash
git clone https://github.com/k-vandith/network-attack-forecasting.git
cd network-attack-forecasting
python3 scripts/setup_env.py    # or:  python scripts/setup_env.py
```

Then activate:

```bash
# Linux / macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

### Manual setup

#### Windows (PowerShell)

```powershell
git clone https://github.com/k-vandith/network-attack-forecasting.git
cd network-attack-forecasting
python -m venv .venv --copies
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

#### Linux / macOS

```bash
git clone https://github.com/k-vandith/network-attack-forecasting.git
cd network-attack-forecasting
# If venv fails with ensurepip errors:
#   sudo apt install python3-venv python3-pip
python3 -m venv .venv --copies
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Why `--copies`?

Some environments cannot create symlinks inside a venv (`Operation not permitted` on `lib64 → lib`). Using `--copies` avoids that. `scripts/setup_env.py` tries `--copies` first automatically.

## Environment Variables

None required.

## Dataset / Demo Mode

```bash
python scripts/generate_demo_data.py
```

## Running the Application

```bash
streamlit run src/pipeline.py
```

## API Usage

```python
from src.pipeline import train_and_predict
result = train_and_predict("data/demo_features.csv")
print(result)
```

## Testing

```bash
pytest -v
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError: src` | Run from project root; ensure `PYTHONPATH=.` |
| `venv` / ensurepip fails | Run `python3 scripts/setup_env.py` or install `python3-venv` |
| `Operation not permitted` on lib64 | Use `python3 -m venv .venv --copies` |
| Missing dependency | Activate `.venv` and re-run `pip install -r requirements.txt` |

## Limitations

- Forecasts are correlational, not causal certainty.
- Rules fallback is intentionally simple for offline demos.
- Not a substitute for full NDR / SIEM correlation.

## Security / Privacy

- Defensive forecasting only.
- Keep production telemetry offline and access-controlled.

## Future Improvements

- Time-series models (LSTM / Prophet optional)
- Online learning adapters
- SIEM export connectors

## License

MIT

## Interface

```bash
python run.py
```

Opens the local Streamlit workspace on port 8501. Demo paths work without GPU, webcam, or a paid API. `streamlit run src/app.py` is equivalent.
