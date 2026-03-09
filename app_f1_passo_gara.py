import streamlit as st
import fastf1
import fastf1.plotting
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import pandas as pd
import numpy as np

# --- CONFIGURAZIONE ---
cache_dir = 'f1_cache_v21_2'
if not os.path.exists(cache_dir): os.makedirs(cache_dir)
fastf1.Cache.enable_cache(cache_dir)

st.set_page_config(page_title="F1 Mobile Pro", layout="wide", initial_sidebar_state="collapsed")

# --- FORMATTAZIONE ---
def format_laptime(seconds):
    if pd.isna(seconds) or seconds <= 0: return "N/A"
    minutes = int(seconds // 60)
    remainder = seconds % 60
    return f"{minutes}:{remainder:06.3f}"

def format_time_td(td):
    if pd.isna(td) or td is None: return "N/A"
    return format_laptime(td.total_seconds())

def format_sector(td):
    if pd.isna(td) or td is None: return "N/A"
    return f"{td.total_seconds():.3f}s"

def get_cleaned_laps(laps_driver):
    if laps_driver is None or len(laps_driver) == 0: return pd.DataFrame()
    quick_laps = laps_driver.pick_quicklaps().dropna(subset=['LapTime']).copy()
    if quick_laps.empty: return quick_laps
    median_val = quick_laps['LapTime'].dt.total_seconds().median()
    return quick_laps[quick_laps['LapTime'].dt.total_seconds() < (median_val * 1.10)]

# --- SIDEBAR ---
st.sidebar.title("🏎️ Menu")
tipo_mode = st.sidebar.radio("MODALITÀ:", ["🚀 Giro Veloce", "📈 Passo Gara"])
anno = st.sidebar.selectbox("Anno", [2026, 2025, 2024], index=1)
pista = st.sidebar.text_input("Circuito", "Monza")
sessione_tipo = st.sidebar.selectbox("Sessione", ["R", "Q", "FP2", "FP1", "FP3"])

if 'ss' not in st.session_state: st.session_state.ss = None
if 'data_ready' not in st.session_state: st.session_state.data_ready = False

if st.sidebar.button("CARICA DATI"):
    with st.spinner('Sincronizzazione...'):
        try:
            session = fastf1.get_session(anno, pista.strip(), sessione_tipo)
            session.load(telemetry=True, laps=True, weather=False)
            st.session_state.ss = session
            st.session_state.data_ready = True
            st.rerun()
        except Exception as e:
            st.error(f"Errore: {e}")

# --- DASHBOARD ---
if st.session_state.data_ready and st.session_state.ss is not None:
    ss = st.session_state.ss
    try:
        laps_all = ss.laps
    except:
        st.error("Dati non caricati. Ricarica.")
        st.stop()

    drivers = sorted(laps_all['Driver'].unique().tolist())
    col_p1, col_p2 = st.columns(2)
    p1 = col_p1.selectbox("Pilota 1", drivers, index=0)
    p2 = col_p2.selectbox("Pilota 2", drivers, index=1 if len(drivers)>1 else 0)
    
    c1 = fastf1.plotting.get_driver_color(p1, session=ss)
    c2 = fastf1.plotting.get_driver_color(p2, session=ss)

    st.markdown(f"### {ss.event['EventName']} {anno}")

    # ==========================================
    # 📈 MODALITÀ PASSO GARA (Responsive)
    # ==========================================
    if "Passo Gara" in tipo_mode:
        l1 = get_cleaned_laps(laps_all.pick_driver(p1))
        l2 = get_cleaned_laps(laps_all.pick_driver(p2))

        avg1 = l1['LapTime'].dt.total_seconds().mean()
        avg2 = l2['LapTime'].dt.total_seconds().mean()
        
        m1, m2 = st.columns(2)
        m1.metric(p1, format_laptime(avg1))
        m2.metric(p2, format_laptime(avg2))
        st.metric("Delta Medio", f"{(avg1-avg2):+.3f}s", delta_color="inverse")

        fig = go.Figure()
        for p, l, color in [(p1, l1, c1), (p2, l2, c2)]:
            t_s = l['LapTime'].dt.total_seconds()
            fig.add_trace(go.Scatter(x=l['LapNumber'], y=t_s, name=p, line=dict(color=color, width=2),
                                     customdata=[format_laptime(t) for t in t_s], hovertemplate="%{customdata}"))
        
        all_t = pd.concat([l1['LapTime'].dt.total_seconds(), l2['LapTime'].dt.total_seconds()])
        tick_vals = np.arange(np.floor(all_t.min()), np.ceil(all_t.max()) + 1, 0.5)
        fig.update_layout(template="plotly_dark", height=380, margin=dict(l=5, r=5, t=10, b=10),
                          yaxis=dict(tickmode='array', tickvals=tick_vals, ticktext=[format_laptime(t) for t in tick_vals]),
                          legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

        with st.expander("🧪 Dettagli Mescole"):
            l_c = pd.concat([l1, l2]).copy()
            l_c['Secs'] = l_c['LapTime'].dt.total_seconds()
            summ = l_c.groupby(['Driver', 'Compound'])['Secs'].mean().reset_index()
            summ['Media'] = summ['Secs'].apply(format_laptime)
            st.dataframe(summ[['Driver', 'Compound', 'Media']], use_container_width=True, hide_index=True)

    # ==========================================
    # 🚀 MODALITÀ GIRO VELOCE (Dati Reintegrati)
    # ==========================================
    else:
        b1 = laps_all.pick_driver(p1).pick_fastest()
        b2 = laps_all.pick_driver(p2).pick_fastest()
        
        # 1. Metriche in alto (Tempi + Settori)
        m1, m2 = st.columns(2)
        with m1:
            st.metric(f"Best {p1}", format_time_td(b1.LapTime))
            st.caption(f"S1: {format_sector(b1.Sector1Time)} | S2: {format_sector(b1.Sector2Time)} | S3: {format_sector(b1.Sector3Time)}")
        with m2:
            st.metric(f"Best {p2}", format_time_td(b2.LapTime))
            st.caption(f"S1: {format_sector(b2.Sector1Time)} | S2: {format_sector(b2.Sector2Time)} | S3: {format_sector(b2.Sector3Time)}")
        
        st.metric("Gap Finale", f"{(b1.LapTime - b2.LapTime).total_seconds():+.3f}s", delta_color="inverse")

        # 2. Telemetria e Delta
        t1 = b1.get_telemetry().add_distance()
        t2 = b2.get_telemetry().add_distance()
        delta, ref_t, _ = fastf1.utils.delta_time(b1, b2)

        # Grafico Telemetria (Compatto per Mobile)
        fig_tel = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                                subplot_titles=("DELTA TIME (s)", "VELOCITÀ (km/h)"))
        
        fig_tel.add_trace(go.Scatter(x=ref_t['Distance'], y=delta, name="Gap", fill='tozeroy', line=dict(color='red')), row=1, col=1)
        fig_tel.add_trace(go.Scatter(x=t1['Distance'], y=t1['Speed'], name=p1, line=dict(color=c1)), row=2, col=1)
        fig_tel.add_trace(go.Scatter(x=t2['Distance'], y=t2['Speed'], name=p2, line=dict(color=c2)), row=2, col=1)

        fig_tel.update_layout(template="plotly_dark", height=450, margin=dict(l=5, r=5, t=25, b=10), showlegend=False)
        st.plotly_chart(fig_tel, use_container_width=True)

        # 3. Mappa (In un expander per non allungare troppo la pagina su mobile)
        with st.expander("🗺️ Mappa del Circuito"):
            fig_map = go.Figure()
            fig_map.add_trace(go.Scatter(x=t1['X'], y=t1['Y'], name="Track", line=dict(color='#1f77b4', width=3)))
            fig_map.add_trace(go.Scatter(x=[t1['X'].iloc[0]], y=[t1['Y'].iloc[0]], mode='markers', 
                                         marker=dict(symbol='diamond', size=12, color='white', line=dict(color='red'))))
            fig_map.update_layout(template="plotly_dark", height=300, margin=dict(l=0, r=0, t=0, b=0), xaxis_visible=False, yaxis_visible=False)
            st.plotly_chart(fig_map, use_container_width=True)

else:
    st.info("👈 Apri il menu e clicca su 'CARICA DATI'")