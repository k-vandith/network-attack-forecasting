<p align="center">
  <img src="web/mark.svg" alt="VectorCast logo" width="72">
</p>

<h1 align="center">VectorCast</h1>
<p align="center">Local-first network attack forecasting with CSV upload, time-series projections, and anomaly review.</p>

<p align="center">
  <img src="https://img.shields.io/github/actions/workflow/status/k-vandith/network-attack-forecasting/tests.yml?branch=main&label=CI" alt="CI status">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/License-MIT-777777" alt="MIT License">
</p>

## Quick start

    git clone https://github.com/k-vandith/network-attack-forecasting.git
    cd network-attack-forecasting
    python -m venv .venv

Activate the environment (Windows: .venv\Scripts\Activate.ps1; macOS/Linux: source .venv/bin/activate), then run:

    python -m pip install -r requirements.txt
    python run.py

Open http://127.0.0.1:8501.

## Upload a CSV

Choose or drag a CSV into the dashboard. Required column: label. Optional column: timestamp. Headers such as class, attack_type, category, time, and datetime are also accepted. The file must be 5 MB or smaller and cover at least five hourly intervals. Without timestamps, VectorCast assumes one event per minute, so provide at least 241 rows.

You can also start with **Download sample CSV** in the app or use the demo stream. Change the forecast horizon, run the forecast, and export the results as CSV or JSON.

## Tests

    python -m pip install -r requirements-dev.txt
    pytest -q
    ruff check src/app.py src/ui_theme.py src/webapp.py run.py tests/test_ui_smoke.py tests/test_webapp.py
    bandit -q -r src/app.py src/webapp.py run.py -ll
    pip-audit -r requirements.txt --progress-spinner off

## Privacy

CSV data is processed by the local server in memory and is not saved to disk or sent to an external service. Forecasts and anomaly flags are estimates, not proof of malicious activity.

## License

MIT
