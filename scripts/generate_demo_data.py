from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.pipeline import generate_synthetic
ROOT = Path(__file__).resolve().parents[1]
df = generate_synthetic(1500)
out = ROOT / "data" / "sample" / "traffic.csv"
out.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(out, index=False)
print("Wrote", out, "rows=", len(df))
