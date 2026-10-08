# Network Attack Forecasting

ML pipeline for network-traffic attack classification and time-aware attack-rate forecasting.

**Detection** classifies individual flows. **Forecasting** estimates near-term attack rate from recent history. Data leakage is avoided via train/test split before fitting.

If scikit-learn is unavailable, a pure NumPy/Pandas rule-based classifier is used automatically.

## Installation

### Linux / macOS
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Windows PowerShell
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Demo
```bash
python scripts/generate_demo_data.py
python -c "from src.pipeline import *; import pandas as pd; from pathlib import Path; df=pd.read_csv('data/sample/traffic.csv'); print(train(df, Path('models')))"
pytest -v
```

## License
MIT
