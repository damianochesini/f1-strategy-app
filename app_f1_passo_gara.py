import streamlit as st
import fastf1
import fastf1.plotting
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import pandas as pd
import numpy as np
from datetime import datetime

# --- CONFIGURAZIONE ---
cache_dir = 'f1_cache_v22_9'
if not os.path.exists(cache_dir): os.makedirs(cache_dir)
fastf1.Cache.enable_cache(cache_dir)

st.set_page_config(page_title="F1 Pit-Wall Pro v22.9", layout="wide", initial_sidebar_state="collapsed")

# --- FUNZIONI DI FORMATTAZIONE ---
def format_laptime(seconds):
    if pd.isna(seconds) or seconds <= 0: return "N/A"
    minutes = int(seconds // 60)
    remainder = seconds % 60
    return f"{minutes}:{remainder:06.3f}"

def format_time_td(td):
    return format_laptime(td.total_seconds()) if pd.notna(td) else "N/A"

def get_cleaned_laps(laps_driver):
    if laps_driver is None or len(laps_driver) == 0: return pd.DataFrame()
    quick_laps = laps_driver.pick_quicklaps().dropna(subset=['LapTime']).copy()
    if quick_laps.empty: return quick_laps
    median_val = quick_laps['LapTime'].dt.total_seconds().median()
    return quick_laps[quick_laps['LapTime'].dt.total_seconds() < (median_val * 1.10)]

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Setup Sessione")
    anno = st.selectbox("Anno", [2026, 2025, 2024], index=1)
    
    try:
        schedule = fastf1.get_event_schedule(anno)
        eventi = schedule[schedule['EventName'].str.contains("Grand Prix", na=False)]['EventName'].tolist()
        if not eventi: eventi = ["Monza", "Monaco", "Silverstone", "Spa"]
    except Exception:
        eventi = ["Monza", "Monaco", "Silverstone", "Spa"]
    
    pista_scelta = st.selectbox("Circuito", eventi)
    sessione_tipo = st.selectbox("Sessione", ["R", "Q", "FP2", "FP1", "FP3"])
    
    st.divider()
    st.subheader("🛠️ Telemetria")
    show_delta = st.checkbox("Delta Time Chart", value=True)
    show_speed = st.checkbox("Velocità", value=True)
    show_throttle = st.checkbox("Acceleratore", value=True)
    show_brake = st.checkbox("Freno", value=True)

    if st.button("🚀 AGGIORNA DATI", use_container_width=True):
        with st.spinner('Scaricamento dati FIA...'):
            try:
                session = fastf1.get_session(anno, pista_scelta, sessione_tipo)
                session.load()
                st.session_state.ss = session
                st.session_state.data_ready = True
                st.rerun()
            except Exception as e:
                st.error(f"Errore: {e}")

# --- DASHBOARD ---
if 'data_ready' in st.session_state and st.session_state.data_ready:
    ss = st.session_state.ss
    laps_all = ss.laps
    
    absolute_best_lap = laps_all.pick_fastest()
    abs_best_time = absolute_best_lap.LapTime.total_seconds()
    abs_best_driver = absolute_best_lap.Driver

    # Header
    c_col1, c_col2 = st.columns([2, 1])
    with c_col1:
        st.subheader(f"🏁 {ss.event['EventName'].upper()}")
        st.caption(f"📍 {ss.event['Location']} | {sessione_tipo} {anno}")
    with c_col2:
        try:
            best_t = absolute_best_lap.get_telemetry()
            fig_map = go.Figure(go.Scatter(x=best_t['X'], y=best_t['Y'], line=dict(color='#9467bd', width=2), hoverinfo='skip'))
            fig_map.update_layout(height=80, margin=dict(l=0,r=0,t=0,b=0), xaxis_visible=False, yaxis_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_map, use_container_width=True, config={'displayModeBar': False})
        except: st.caption("Mappa N/A")

    st.divider()

    drivers = sorted(laps_all['Driver'].unique().tolist())
    p_col1, p_col2 = st.columns(2)
    p1 = p_col1.selectbox("Pilota 1", drivers, index=0)
    p2 = p_col2.selectbox("Pilota 2", drivers, index=1 if len(drivers)>1 else 0)
    
    try:
        c1 = fastf1.plotting.get_driver_color(p1, session=ss)
        c2 = fastf1.plotting.get_driver_color(p2, session=ss)
    except:
        c1, c2 = "#00D2BE", "#0600EF"

    tab_fast, tab_pace = st.tabs(["🚀 GIRO VELOCE", "📈 PASSO GARA"])

    # --- TAB GIRO VELOCE ---
    with tab_fast:
        st.info(f"🟣 **Session Best:** {abs_best_driver} | **{format_laptime(abs_best_time)}**")
        b1 = laps_all.pick_driver(p1).pick_fastest()
        b2 = laps_all.pick_driver(p2).pick_fastest()

        st.markdown("### ⏱️ Analisi Distacchi")
        g_col1, g_col2, g_col3 = st.columns(3)
        if not b1.empty and not b2.empty:
            gap_p1_abs = b1.LapTime.total_seconds() - abs_best_time
            gap_p2_abs = b2.LapTime.total_seconds() - abs_best_time
            gap_rel = b1.LapTime.total_seconds() - b2.LapTime.total_seconds()
            g_col1.metric(f"{p1} vs Purple", f"{gap_p1_abs:+.3f}s", delta_color="inverse")
            g_col2.metric(f"{p2} vs Purple", f"{gap_p2_abs:+.3f}s", delta_color="inverse")
            g_col3.metric(f"{p1} vs {p2}", f"{gap_rel:+.3f}s", delta_color="off")

            active_rows = []
            if show_delta: active_rows.append("DELTA (s)")
            if show_speed: active_rows.append("VELOCITÀ (km/h)")
            if show_throttle: active_rows.append("GAS (%)")
            if show_brake: active_rows.append("FRENO")

            if active_rows:
                t1 = b1.get_telemetry().add_distance()
                t2 = b2.get_telemetry().add_distance()
                dt, ref_t, _ = fastf1.utils.delta_time(b1, b2)
                fig_tel = make_subplots(rows=len(active_rows), cols=1, shared_xaxes=True, vertical_spacing=0.05, subplot_titles=active_rows)
                curr = 1
                if show_delta:
                    fig_tel.add_trace(go.Scatter(x=ref_t['Distance'], y=dt, name="Gap", fill='tozeroy', line=dict(color='white')), row=curr, col=1)
                    curr += 1
                if show_speed:
                    fig_tel.add_trace(go.Scatter(x=t1['Distance'], y=t1['Speed'], name=p1, line=dict(color=c1)), row=curr, col=1)
                    fig_tel.add_trace(go.Scatter(x=t2['Distance'], y=t2['Speed'], name=p2, line=dict(color=c2)), row=curr, col=1)
                    curr += 1
                if show_throttle:
                    fig_tel.add_trace(go.Scatter(x=t1['Distance'], y=t1['Throttle'], name=p1, line=dict(color=c1, dash='dot')), row=curr, col=1)
                    fig_tel.add_trace(go.Scatter(x=t2['Distance'], y=t2['Throttle'], name=p2, line=dict(color=c2, dash='dot')), row=curr, col=1)
                    curr += 1
                if show_brake:
                    fig_tel.add_trace(go.Scatter(x=t1['Distance'], y=t1['Brake'], name=p1, line=dict(color=c1)), row=curr, col=1)
                    fig_tel.add_trace(go.Scatter(x=t2['Distance'], y=t2['Brake'], name=p2, line=dict(color=c2)), row=curr, col=1)
                fig_tel.update_layout(template="plotly_dark", height=230*len(active_rows), margin=dict(l=0,r=0,t=30,b=0), showlegend=False)
                st.plotly_chart(fig_tel, use_container_width=True)

    # --- TAB PASSO GARA ---
    with tab_pace:
        laps_p1 = laps_all.pick_driver(p1)
        laps_p2 = laps_all.pick_driver(p2)
        clean_p1 = get_cleaned_laps(laps_p1)
        clean_p2 = get_cleaned_laps(laps_p2)
        
        # --- RIPRISTINO METRICA GAP MEDIO PASSO GARA ---
        if not clean_p1.empty and not clean_p2.empty:
            avg1 = clean_p1['LapTime'].dt.total_seconds().mean()
            avg2 = clean_p2['LapTime'].dt.total_seconds().mean()
            delta_medio = avg1 - avg2
            st.metric("Delta Medio Passo Gara", f"{delta_medio:+.3f}s", delta_color="inverse", help=f"Media {p1} vs Media {p2}")

        s1 = int(laps_p1['Stint'].max() - 1) if not laps_p1.empty else 0
        s2 = int(laps_p2['Stint'].max() - 1) if not laps_p2.empty else 0
        st.write(f"📊 **Soste:** {p1}: `{s1}` | {p2}: `{s2}`")

        fig_pg = go.Figure()
        all_s = []
        for p, l, col in [(p1, clean_p1, c1), (p2, clean_p2, c2)]:
            if not l.empty:
                s = l['LapTime'].dt.total_seconds()
                all_s.extend(s.tolist())
                fig_pg.add_trace(go.Scatter(x=l['LapNumber'], y=s, name=p, line=dict(color=col, width=3), mode='lines+markers',
                                            customdata=[format_laptime(v) for v in s], hovertemplate="Giro %{x}: %{customdata}"))
        
        if all_s:
            ticks = np.arange(np.floor(min(all_s)), np.ceil(max(all_s)) + 1, 0.5)
            fig_pg.update_layout(yaxis=dict(tickmode='array', tickvals=ticks, ticktext=[format_laptime(v) for v in ticks]))
        fig_pg.update_layout(template="plotly_dark", height=400, margin=dict(l=0,r=0,t=10,b=0), legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig_pg, use_container_width=True)

        st.subheader(f"🧪 Riepilogo Compound ({p1} vs {p2})")
        l_focused = pd.concat([clean_p1, clean_p2]).copy()
        if not l_focused.empty:
            l_focused['Secs'] = l_focused['LapTime'].dt.total_seconds()
            summ = l_focused.groupby(['Driver', 'Compound'])['Secs'].agg(['mean', 'count']).reset_index()
            summ['Passo Medio'] = summ['mean'].apply(format_laptime)
            st.dataframe(summ[['Driver', 'Compound', 'Passo Medio', 'count']].rename(columns={'count':'Giri'}), use_container_width=True, hide_index=True)

        with st.expander(f"📋 Log Giri Dettagliato ({p1} & {p2})"):
            log_f = pd.concat([laps_p1, laps_p2])[['Driver', 'LapNumber', 'LapTime', 'Compound', 'TyreLife']].copy()
            log_f['LapTime'] = log_f['LapTime'].dt.total_seconds().apply(format_laptime)
            st.dataframe(log_f.sort_values(['LapNumber', 'Driver'], ascending=[False, True]), use_container_width=True, hide_index=True)

else:
    st.info("👈 Configura la sessione e clicca su AGGIORNA DATI")
