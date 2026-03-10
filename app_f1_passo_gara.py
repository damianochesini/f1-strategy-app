import streamlit as st
import fastf1
import fastf1.plotting
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import pandas as pd
import numpy as np

# --- CONFIGURAZIONE CACHE ---
cache_dir = 'f1_cache_v21_6'
if not os.path.exists(cache_dir): os.makedirs(cache_dir)
fastf1.Cache.enable_cache(cache_dir)

st.set_page_config(page_title="F1 Mobile Pro v21.6", layout="wide", initial_sidebar_state="collapsed")

# --- FUNZIONI FORMATTAZIONE ---
def format_laptime(seconds):
    if pd.isna(seconds) or seconds <= 0: return "N/A"
    minutes = int(seconds // 60)
    remainder = seconds % 60
    return f"{minutes}:{remainder:06.3f}"

def format_time_td(td):
    return format_laptime(td.total_seconds()) if pd.notna(td) else "N/A"

def format_sector(td):
    return f"{td.total_seconds():.3f}s" if pd.notna(td) else "N/A"

def get_cleaned_laps(laps_driver):
    if laps_driver is None or len(laps_driver) == 0: return pd.DataFrame()
    quick_laps = laps_driver.pick_quicklaps().dropna(subset=['LapTime']).copy()
    if quick_laps.empty: return quick_laps
    median_val = quick_laps['LapTime'].dt.total_seconds().median()
    return quick_laps[quick_laps['LapTime'].dt.total_seconds() < (median_val * 1.10)]

# --- SIDEBAR ---
st.sidebar.title("🏎️ F1 Analysis")
tipo_mode = st.sidebar.radio("MODALITÀ:", ["🚀 Giro Veloce", "📈 Passo Gara"])

# Configurazione Telemetria
show_delta = show_speed = show_throttle = show_brake = True
if "Giro Veloce" in tipo_mode:
    st.sidebar.subheader("Grafici Telemetria:")
    show_delta = st.sidebar.checkbox("Delta Time", value=True)
    show_speed = st.sidebar.checkbox("Velocità", value=True)
    show_throttle = st.sidebar.checkbox("Acceleratore", value=True)
    show_brake = st.sidebar.checkbox("Freno", value=True)

st.sidebar.divider()
anno = st.sidebar.selectbox("Anno", [2026, 2025, 2024], index=1)
pista_input = st.sidebar.text_input("Circuito", "Monza")
sessione_tipo = st.sidebar.selectbox("Sessione", ["R", "Q", "FP2", "FP1", "FP3"])

if 'ss' not in st.session_state: st.session_state.ss = None
if 'data_ready' not in st.session_state: st.session_state.data_ready = False

if st.sidebar.button("CARICA / AGGIORNA DATI"):
    with st.spinner('Sincronizzazione dati...'):
        try:
            session = fastf1.get_session(anno, pista_input.strip(), sessione_tipo)
            session.load()
            st.session_state.ss = session
            st.session_state.data_ready = True
            st.rerun()
        except Exception as e:
            st.error(f"Errore: {e}")

# --- DASHBOARD ---
if st.session_state.data_ready and st.session_state.ss is not None:
    ss = st.session_state.ss
    laps_all = ss.laps
    
    # Intestazione Circuito
    col_t1, col_t2 = st.columns([2, 1])
    with col_t1:
        st.markdown(f"## {ss.event['EventName'].upper()}")
        st.markdown(f"**📍 {ss.event['Location']}** | {sessione_tipo} {anno}")
    with col_t2:
        best_lap_ever = laps_all.pick_fastest()
        t_map = best_lap_ever.get_telemetry()
        fig_mini_map = go.Figure()
        fig_mini_map.add_trace(go.Scatter(x=t_map['X'], y=t_map['Y'], line=dict(color='#e10600', width=3), hoverinfo='skip'))
        fig_mini_map.update_layout(height=100, margin=dict(l=0,r=0,t=0,b=0), xaxis_visible=False, yaxis_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_mini_map, use_container_width=True, config={'displayModeBar': False})
    
    st.divider()

    drivers = sorted(laps_all['Driver'].unique().tolist())
    col_p1, col_p2 = st.columns(2)
    p1 = col_p1.selectbox("Pilota 1", drivers, index=0)
    p2 = col_p2.selectbox("Pilota 2", drivers, index=1 if len(drivers)>1 else 0)
    
    c1 = fastf1.plotting.get_driver_color(p1, session=ss)
    c2 = fastf1.plotting.get_driver_color(p2, session=ss)

    if "Giro Veloce" in tipo_mode:
        # (Codice Giro Veloce - Invariato)
        b1 = laps_all.pick_driver(p1).pick_fastest()
        b2 = laps_all.pick_driver(p2).pick_fastest()
        m1, m2 = st.columns(2)
        with m1:
            st.metric(f"Best {p1}", format_time_td(b1.LapTime))
            st.caption(f"S1: {format_sector(b1.Sector1Time)} | S2: {format_sector(b1.Sector2Time)} | S3: {format_sector(b1.Sector3Time)}")
        with m2:
            st.metric(f"Best {p2}", format_time_td(b2.LapTime))
            st.caption(f"S1: {format_sector(b2.Sector1Time)} | S2: {format_sector(b2.Sector2Time)} | S3: {format_sector(b2.Sector3Time)}")

        active_plots = []
        if show_delta: active_plots.append("DELTA TIME (s)")
        if show_speed: active_plots.append("VELOCITÀ (km/h)")
        if show_throttle: active_plots.append("GAS (%)")
        if show_brake: active_plots.append("FRENO")

        if active_plots:
            t1 = b1.get_telemetry().add_distance()
            t2 = b2.get_telemetry().add_distance()
            delta, ref_t, _ = fastf1.utils.delta_time(b1, b2)
            fig = make_subplots(rows=len(active_plots), cols=1, shared_xaxes=True, vertical_spacing=0.05, subplot_titles=active_plots)
            curr_row = 1
            if show_delta:
                fig.add_trace(go.Scatter(x=ref_t['Distance'], y=delta, name="Delta", fill='tozeroy', line=dict(color='white')), row=curr_row, col=1)
                curr_row += 1
            if show_speed:
                fig.add_trace(go.Scatter(x=t1['Distance'], y=t1['Speed'], name=p1, line=dict(color=c1)), row=curr_row, col=1)
                fig.add_trace(go.Scatter(x=t2['Distance'], y=t2['Speed'], name=p2, line=dict(color=c2)), row=curr_row, col=1)
                curr_row += 1
            if show_throttle:
                fig.add_trace(go.Scatter(x=t1['Distance'], y=t1['Throttle'], name=f"Gas {p1}", line=dict(color=c1, dash='dot')), row=curr_row, col=1)
                fig.add_trace(go.Scatter(x=t2['Distance'], y=t2['Throttle'], name=f"Gas {p2}", line=dict(color=c2, dash='dot')), row=curr_row, col=1)
                curr_row += 1
            if show_brake:
                fig.add_trace(go.Scatter(x=t1['Distance'], y=t1['Brake'], name=f"Freno {p1}", line=dict(color=c1)), row=curr_row, col=1)
                fig.add_trace(go.Scatter(x=t2['Distance'], y=t2['Brake'], name=f"Freno {p2}", line=dict(color=c2)), row=curr_row, col=1)
            fig.update_layout(template="plotly_dark", height=250*len(active_plots), showlegend=False, margin=dict(l=5, r=5, t=30, b=10))
            st.plotly_chart(fig, use_container_width=True)

    else:
        # ==========================================
        # 📈 MODALITÀ PASSO GARA (TABELLE RIPRISTINATE)
        # ==========================================
        l1 = get_cleaned_laps(laps_all.pick_driver(p1))
        l2 = get_cleaned_laps(laps_all.pick_driver(p2))

        avg1 = l1['LapTime'].dt.total_seconds().mean()
        avg2 = l2['LapTime'].dt.total_seconds().mean()
        
        st.metric("Delta Medio Generale", f"{(avg1-avg2):+.3f}s", delta_color="inverse")
        m1, m2 = st.columns(2)
        m1.metric(f"Media {p1}", format_laptime(avg1))
        m2.metric(f"Media {p2}", format_laptime(avg2))

        # --- TABELLA COMPOUND ---
        st.subheader("🧪 Passo per Mescola")
        l_combined = pd.concat([l1, l2]).copy()
        l_combined['Secs'] = l_combined['LapTime'].dt.total_seconds()
        comp_summary = l_combined.groupby(['Driver', 'Compound'])['Secs'].agg(['mean', 'count']).reset_index()
        comp_summary['Passo Medio'] = comp_summary['mean'].apply(format_laptime)
        st.dataframe(comp_summary[['Driver', 'Compound', 'Passo Medio', 'count']].rename(columns={'count':'Giri'}), 
                     use_container_width=True, hide_index=True)

        # --- GRAFICO ---
        fig_pg = go.Figure()
        for p, l, color in [(p1, l1, c1), (p2, l2, c2)]:
            t_s = l['LapTime'].dt.total_seconds()
            fig_pg.add_trace(go.Scatter(x=l['LapNumber'], y=t_s, name=p, line=dict(color=color, width=2),
                                        customdata=[format_laptime(t) for t in t_s], hovertemplate="%{customdata}"))
        fig_pg.update_layout(template="plotly_dark", height=400, margin=dict(l=5, r=5, t=10, b=10), legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig_pg, use_container_width=True)

        # --- LOG DETTAGLIATO ---
        with st.expander("📋 Log Giri Completo"):
            full_log = pd.concat([l1, l2])[['Driver', 'LapNumber', 'LapTime', 'Compound', 'TyreLife']].copy()
            full_log['LapTime'] = full_log['LapTime'].dt.total_seconds().apply(format_laptime)
            full_log.columns = ['Pilota', 'Giro', 'Tempo', 'Gomma', 'Età']
            st.dataframe(full_log.sort_values(['Giro', 'Pilota'], ascending=[False, True]), 
                         use_container_width=True, hide_index=True)

else:
    st.info("👈 Apri il menu e clicca su 'CARICA DATI'")
