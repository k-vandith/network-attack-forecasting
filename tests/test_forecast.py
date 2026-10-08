from src.forecasting import load_cicids_style, attack_volume_series, forecast_volumes, evaluation_metrics
import numpy as np
def test_forecast():
    df = load_cicids_style(n=500)
    vol = attack_volume_series(df, freq="h")
    out = forecast_volumes(vol, horizon=5)
    assert len(out["forecast"]) == 5
    assert "mae" in evaluation_metrics(np.array([1.,2.,3.]), np.array([1.,2.,2.]))
