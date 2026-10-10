import csv
import io
import math
from datetime import datetime, timedelta, timezone

import pytest

from src.webapp import build_forecast_payload, build_uploaded_payload


def test_forecast_payload_has_chart_metrics_and_categories():
    result = build_forecast_payload(n=800, horizon=6)

    assert result["rows"] == 800
    assert len(result["forecast"]) == 6
    assert len(result["history"]) >= 5
    assert set(result["attack_types"]) == {"dos", "probe", "r2l", "u2r", "other"}
    assert result["outlook"] in {"Stable", "Watch", "Elevated"}
    assert result["backend_label"]
    assert all(math.isfinite(row["attacks"]) for row in result["forecast"])
    assert result["synthetic"] is True
    assert result["source_label"] == "Synthetic sample"


def _csv_bytes(rows=420, with_timestamp=True, label_header="label", timestamp_header="timestamp"):
    output = io.StringIO()
    headers = [timestamp_header, label_header] if with_timestamp else [label_header]
    writer = csv.writer(output)
    writer.writerow(headers)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    labels = ["BENIGN", "DoS", "PortScan", "Brute Force", "Privilege Escalation", "Custom threat"]
    for index in range(rows):
        label = labels[index % len(labels)]
        record = [label]
        if with_timestamp:
            record = [(start + timedelta(minutes=index)).isoformat(), label]
        writer.writerow(record)
    return output.getvalue().encode("utf-8")


def test_uploaded_csv_returns_forecast_and_normalizes_common_labels():
    result = build_uploaded_payload(_csv_bytes(), horizon=6)

    assert result["rows"] == 420
    assert len(result["forecast"]) == 6
    assert result["synthetic"] is False
    assert result["source_label"] == "Uploaded CSV"
    assert result["attack_types"]["dos"] > 0
    assert result["attack_types"]["probe"] > 0
    assert result["attack_types"]["r2l"] > 0
    assert result["attack_types"]["u2r"] > 0
    assert result["attack_types"]["other"] > 0


def test_uploaded_csv_accepts_header_aliases_and_missing_timestamp():
    result = build_uploaded_payload(
        _csv_bytes(rows=420, with_timestamp=True, label_header="Class", timestamp_header="DateTime"),
        horizon=6,
    )
    assert result["rows"] == 420
    assert result["synthetic"] is False


def test_uploaded_csv_without_timestamp_uses_documented_minute_spacing():
    result = build_uploaded_payload(_csv_bytes(rows=420, with_timestamp=False), horizon=6)
    assert result["rows"] == 420
    assert len(result["forecast"]) == 6


def test_uploaded_csv_requires_a_label_column():
    with pytest.raises(ValueError, match="label column is required"):
        build_uploaded_payload(b"timestamp,src_bytes\n2026-01-01,20\n", horizon=6)


def test_uploaded_csv_rejects_blank_labels():
    with pytest.raises(ValueError, match="blank values"):
        build_uploaded_payload(b"label,unused\nnormal,x\n,x\n", horizon=6)


def test_uploaded_csv_rejects_bad_timestamps():
    with pytest.raises(ValueError, match="timestamps could not be parsed"):
        build_uploaded_payload(b"timestamp,label\nnot-a-time,normal\n", horizon=6)


def test_uploaded_csv_requires_at_least_five_hourly_intervals():
    with pytest.raises(ValueError, match="at least five hourly intervals"):
        build_uploaded_payload(
            b"timestamp,label\n2026-01-01T00:00:00Z,normal\n2026-01-01T00:01:00Z,dos\n",
            horizon=6,
        )


def test_uploaded_csv_rejects_files_over_limit():
    with pytest.raises(ValueError, match="5 MB or smaller"):
        build_uploaded_payload(b"a" * (5 * 1024 * 1024 + 1), horizon=6)


@pytest.mark.parametrize("rows", [0, 399, 401, 4200])
def test_payload_rejects_unsupported_demo_sizes(rows):
    with pytest.raises(ValueError):
        build_forecast_payload(n=rows, horizon=6)


@pytest.mark.parametrize("horizon", [0, 5, 25, -1])
def test_payload_rejects_unsupported_horizons(horizon):
    with pytest.raises(ValueError):
        build_forecast_payload(n=800, horizon=horizon)
