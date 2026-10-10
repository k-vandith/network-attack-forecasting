import math

import pytest

from src.webapp import build_forecast_payload


def test_forecast_payload_has_chart_metrics_and_categories():
    result = build_forecast_payload(n=800, horizon=6)

    assert result["rows"] == 800
    assert len(result["forecast"]) == 6
    assert len(result["history"]) >= 5
    assert set(result["attack_types"]) == {"dos", "probe", "r2l", "u2r"}
    assert result["outlook"] in {"Stable", "Watch", "Elevated"}
    assert result["backend_label"]
    assert all(math.isfinite(row["attacks"]) for row in result["forecast"])
    assert result["synthetic"] is True


@pytest.mark.parametrize("rows", [0, 399, 401, 4200])
def test_payload_rejects_unsupported_dataset_sizes(rows):
    with pytest.raises(ValueError):
        build_forecast_payload(n=rows, horizon=6)


@pytest.mark.parametrize("horizon", [0, 25, -1])
def test_payload_rejects_invalid_horizons(horizon):
    with pytest.raises(ValueError):
        build_forecast_payload(n=800, horizon=horizon)
