"""Attack volume forecast workspace."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import plotly.graph_objects as go
import streamlit as st
from src.forecasting import attack_volume_series, forecast_volumes, load_cicids_style
from src.ui_theme import theme_css

@st.cache_data
def _bundle(n: int) -> dict:
    df = load_cicids_style(n=n)
    vol = attack_volume_series(df)
    fc = forecast_volumes(vol, horizon=12)
    return {"rows": len(df), "vol": vol.reset_index().to_dict(orient="list"), "fc": fc}

def main() -> None:
    st.set_page_config(page_title="Attack forecast", layout="wide")
    st.markdown(theme_css("#6fbfa0"), unsafe_allow_html=True)
    st.markdown('<div class="top"><div><div class="kicker">Observability</div><p class="title">Network attack forecasting</p></div><div class="pill">Synthetic traffic · CPU</div></div>', unsafe_allow_html=True)
    n = st.sidebar.slider("Synthetic rows", 400, 4000, 1200, 200)
    data = _bundle(n)
    fc = data["fc"]
    hist = fc.get("history_tail") or []
    pred = fc.get("forecast") or []
    st.markdown(f'<div class="panel"><div class="kicker">Model</div><p class="title">{fc.get("backend")}</p><p class="muted">{data["rows"]} rows · mean attacks {fc.get("metrics", {}).get("mean_attack", "n/a")}. Solid line is observed. Dashed line is the forecast.</p></div>', unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=hist, name="Observed", line=dict(color="#6fbfa0")))
    if pred:
        fig.add_trace(go.Scatter(x=list(range(len(hist), len(hist)+len(pred))), y=pred, name="Forecast", line=dict(color="#e0b15a", dash="dash")))
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#e7ecf3", height=380, title="Hourly attack counts")
    st.plotly_chart(fig, width="stretch")
    alerts = fc.get("alerts") or []
    if alerts:
        st.warning(f"{len(alerts)} observed hours sit above mean + 2σ.")
    else:
        st.success("No high-volume anomalies in the recent window.")

if __name__ == "__main__":
    main()
