from pathlib import Path
from src.pipeline import generate_synthetic, train, predict

def test_train_predict(tmp_path):
    df = generate_synthetic(400)
    metrics = train(df, tmp_path)
    assert metrics["accuracy"] > 0.5
    label = predict(tmp_path, {c: 1.0 for c in ["duration","src_bytes","dst_bytes","count","srv_count","dst_host_count","serror_rate"]})
    assert isinstance(label, str)
