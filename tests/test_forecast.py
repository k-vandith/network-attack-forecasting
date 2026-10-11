from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.forecasting import (
    attack_volume_series,
    evaluation_metrics,
    forecast_volumes,
    load_cicids_style,
)


def test_forecast():
    df = load_cicids_style(n=500)
    vol = attack_volume_series(df, freq="h")
    out = forecast_volumes(vol, horizon=5)
    assert len(out["forecast"]) == 5
    assert all(0 <= item["index"] < len(vol) for item in out.get("alerts", []))
    assert "mae" in evaluation_metrics(np.array([1., 2., 3.]), np.array([1., 2., 2.]))


def test_file_loader_and_time_series_normalize_cicids_labels_and_sort_timestamps(tmp_path: Path):
    path = tmp_path / "sample.csv"
    pd.DataFrame(
        {
            "Timestamp": [
                "2024-01-01T05:00:00Z",
                "2024-01-01T02:00:00Z",
                "2024-01-01T00:00:00Z",
                "2024-01-01T04:00:00Z",
                "2024-01-01T01:00:00Z",
                "2024-01-01T03:00:00Z",
            ],
            "Label": [
                "Privilege Escalation",
                "DoS",
                "BENIGN",
                "Brute Force",
                "BENIGN",
                "PortScan",
            ],
        }
    ).to_csv(path, index=False)

    loaded = load_cicids_style(path)
    volume = attack_volume_series(loaded)

    assert loaded["label"].tolist() == ["normal", "normal", "dos", "probe", "r2l", "u2r"]
    assert volume["attack_count"].tolist() == [0, 0, 1, 1, 1, 1]
    assert volume["total"].tolist() == [1, 1, 1, 1, 1, 1]
    assert volume["dos"].sum() == volume["probe"].sum() == volume["r2l"].sum() == volume["u2r"].sum() == 1


def test_attack_volume_series_parses_string_timestamps_and_normalizes_benign():
    frame = pd.DataFrame(
        {
            "timestamp": ["2025-01-01 01:00", "2025-01-01 00:00", "2025-01-01 01:01"],
            "label": ["BENIGN", "Normal", "DoS"],
        }
    )

    volume = attack_volume_series(frame)

    assert volume["total"].tolist() == [1, 2]
    assert volume["attack_count"].tolist() == [0, 1]


def test_attack_volume_series_rejects_invalid_timestamp_and_missing_label():
    with pytest.raises(ValueError, match="timestamps could not be parsed"):
        attack_volume_series(pd.DataFrame({"timestamp": ["not-a-date"], "label": ["DoS"]}))
    with pytest.raises(ValueError, match="label column is required"):
        attack_volume_series(pd.DataFrame({"timestamp": ["2025-01-01"]}))


@pytest.mark.parametrize("horizon", [0, -1, 1.5, True])
def test_forecast_volumes_rejects_invalid_horizon(horizon):
    with pytest.raises(ValueError, match="positive integer"):
        forecast_volumes(pd.DataFrame({"attack_count": [1, 2, 3, 4, 5]}), horizon=horizon)


def test_forecast_volumes_rejects_nonfinite_attack_counts():
    with pytest.raises(ValueError, match="non-finite"):
        forecast_volumes(pd.DataFrame({"attack_count": [1, 2, np.nan, 4, 5]}), horizon=5)


@pytest.mark.parametrize(
    "actual,predicted,match",
    [
        ([], [], "non-empty"),
        ([1, 2], [1], "same length"),
        ([1, float("nan")], [1, 2], "finite"),
        ([[1, 2]], [[1, 2]], "one-dimensional"),
    ],
)
def test_evaluation_metrics_validate_inputs(actual, predicted, match):
    with pytest.raises(ValueError, match=match):
        evaluation_metrics(actual, predicted)



def test_requested_missing_dataset_does_not_fall_back_to_synthetic(tmp_path: Path):
    missing = tmp_path / "typoed-dataset.csv"

    with pytest.raises(FileNotFoundError, match="Dataset file not found"):
        load_cicids_style(missing)


@pytest.mark.parametrize("rows", [0, -1, 1.5, True])
def test_synthetic_loader_rejects_invalid_row_counts(rows):
    with pytest.raises(ValueError, match="positive integer"):
        load_cicids_style(n=rows)

def test_file_loader_prefers_canonical_label_and_timestamp_columns_when_aliases_coexist():
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=8, freq="h", tz="UTC"),
            "datetime": ["not-a-timestamp"] * 8,
            "label": ["BENIGN"] * 8,
            "class": ["DoS"] * 8,
        }
    )

    volume = attack_volume_series(frame)

    assert int(volume["total"].sum()) == 8
    assert int(volume["attack_count"].sum()) == 0
    assert int(volume["dos"].sum()) == 0
