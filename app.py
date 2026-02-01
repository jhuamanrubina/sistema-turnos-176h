import streamlit as st
import pandas as pd
import os
import datetime
import calendar
import random

# --- CONFIGURACIÓN ---
COORDINADORES_AUTORIZADOS = {"Samay02": "pass123", "Yape": "yape2024", "Admin": "admin789"}
DB_FILE = 'especialistas_vFinal.csv'
TURNOS_OPCIONES = ["6am-2pm", "9am-6pm", "6pm-2am", "10pm-6am"]
POOLS_DISPONIBLES = ["Samay02", "Yape", "proyectos", "Legacy", "Samay01", "SYF"]

def cargar_datos():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        if 'Turno_Fijo' not in df.columns: df['Turno_Fijo'] = "Aleatorio"
        return df
    return pd.DataFrame(columns=['Nombre', 'Pool', 'Coordinador', 'Turno_Fijo'])

def guardar_datos(df):
    df.to_csv(DB_FILE, index=False)

# --- MOTOR CON TECHO RÍGIDO DE 176H ---
def generar_rol_perfecto(mes, anio, df_base, coordinador_actual):
    num_dias = calendar.monthrange(anio, mes)[1]
    df_filt = df_base[df_base['Coordinador'] == coordinador_actual].copy()
    especialistas = df_filt['Nombre'].tolist()
    
    if not especialistas: return pd.DataFrame(), {}

    # Asignación de turnos fijos equilibrada
    mapa_turnos = {}
    patron = ["6am-2pm", "9am-6pm", "9am-6pm", "6pm-2am", "10pm-6am"]
    for i, nom in enumerate(especialistas):
        pref = df_filt[df_filt['Nombre'] == nom]['Turno_Fijo'].values[0]
        mapa_turnos[nom] = pref if pref in TURNOS_OPCIONES else patron[i % len(patron)]

    asignaciones = []
    horas_totales = {nom: 0 for nom in especialistas}
    dias_seguidos = {nom: 0 for nom in especialistas}
    ultimo_dia_trabajado = {nom: -1 for nom in especialistas}

    for dia in range(1, num_dias + 1):
        # Cada día, ordenamos a los especialistas por quién tiene MENOS horas
        # Esto hace que los que van "atrás" trabajen y los que ya cumplieron descansen
        candidatos_dia = sorted(especialistas, key=lambda x: (horas_totales[x], random.random()))
        
        turnos_cubiertos = {t: 0 for t in TURNOS_OPCIONES}
        
        for nom in candidatos_dia:
            turno_asig = mapa_turnos[nom]
            # Meta de seguridad para el 9am-6pm
            minimo_req = 2 if turno_asig == "9am-6pm" else 1
            
            # CONDICIÓN DE ORO: No pasarse de 176h bajo ninguna circunstancia
            pueder_trabajar = (
                horas_totales[nom] + 8 <= 176 and 
                ultimo_dia_trabajado[nom] < dia and 
                dias_seguidos[nom] < 6
            )
            
            # Solo trabaja si puede y si el turno aún necesita gente
            if pueder_trabajar:
                # Si el turno ya tiene su mínimo, pero el trabajador está muy bajo en horas, lo dejamos trabajar
                # para que no se quede atrás, SIEMPRE QUE no falte gente en otro lado.
                if turnos_cubiertos[turno_asig] < minimo_req or horas_totales[nom] < (dia/num_dias)*176:
                    asignaciones.append({
                        "Día": dia, "Especialista": nom, "Turno": turno_asig,
                        "Pool": df_filt[df_filt['Nombre']==nom]['Pool'].values[0]
                    })
                    horas_totales[nom] += 8
                    ultimo_dia_trabajado[nom] = dia
                    dias_seguidos[nom] += 1
                    turnos_cubiertos[turno_asig] += 1
            
        # Reset de descansos
        hoy_trabajaron = [a['Especialista'] for a in asignaciones if a['Día'] == dia]
        for n in especialistas:
            if n not in hoy_trabajaron: dias_seguidos[n] = 0

    return pd.DataFrame(asignaciones), horas_totales

# --- INTERFAZ ---
st.set_page_config(page_title="Control Exacto 176h", layout="wide")
u = st.sidebar.selectbox("Coordinador", list(COORDINADORES_AUTORIZADOS.keys()))
p = st.sidebar.text_input("Contraseña", type="password")

if p == COORDINADORES_AUTORIZADOS.get(u):
    df_base = cargar_datos()
    mis_esp = df_base[df_base['Coordinador'] == u].reset_index(drop=True)
    t1, t2, t3 = st.tabs(["🗓️ Rol Mensual", "👥 Gestión Personal", "📊 Auditoría Horas"])

    with t2:
        with st.expander("➕ Registrar Nuevo"):
            with st.form("reg_form", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                n_nom = c1.text_input("Nombre")
                n_pool = col2 = c2.selectbox("Pool", POOLS_DISPONIBLES)
                n_fijo = col3 = c3.selectbox("Turno Fijo", ["Aleatorio"] + TURNOS_OPCIONES)
                if st.form_submit_button("Guardar"):
                    if n_nom:
                        nueva = pd.DataFrame([[n_nom, n_pool, u, n_fijo]], columns=['Nombre', 'Pool', 'Coordinador', 'Turno_Fijo'])
                        df_base = pd.concat([df_base, nueva], ignore_index=True)
                        guardar_datos(df_base)
                        st.rerun()
        if not mis_esp.empty:
            ed = st.data_editor(mis_esp[['Nombre', 'Pool', 'Turno_Fijo']], use_container_width=True)
            if st.button("💾 Guardar"):
                df_o = df_base[df_base['Coordinador'] != u]
                ed['Coordinador'] = u
                guardar_datos(pd.concat([df_o, ed.dropna()], ignore_index=True))
                st.rerun()

    with t1:
        if not mis_esp.empty:
            mes = st.selectbox("Mes", range(1, 13), index=datetime.datetime.now().month-1)
            if st.button("🚀 GENERAR HORARIO "):
                df_res, hrs = generar_rol_perfecto(mes, 2026, df_base, u)
                st.session_state['r_final'] = df_res
                st.session_state['h_final'] = hrs
            
            if 'r_final' in st.session_state:
                
                matriz = st.session_state['r_final'].pivot(index='Especialista', columns='Día', values='Turno').fillna("DESCANSO")
                def estilo(val):
                    colors = {"6am-2pm":"#D1E9F6","9am-6pm":"#FFF9BF","6pm-2am":"#F1D3FF","10pm-6am":"#D1FFD7","DESCANSO":"#FFD1D1"}
                    return f'background-color: {colors.get(val, "white")}'
                st.dataframe(matriz.style.applymap(estilo), use_container_width=True)
                

            

    with t3:
        if 'h_final' in st.session_state:
            st.subheader("Verificación de Horas (Límite 176h)")
            # Mostramos las horas finales
            res_horas = pd.DataFrame([{"Especialista": k, "Horas": v} for k, v in st.session_state['h_final'].items()])
            st.table(res_horas)
            
            # Verificación de cobertura 24/7
            st.subheader("Cobertura por Turno")
            cob = st.session_state['r_final'].groupby(['Día', 'Turno']).size().unstack(fill_value=0)
            st.dataframe(cob.T.style.applymap(lambda x: f'background-color: {"#2ecc71" if x > 0 else "#e74c3c"}; color: white'), use_container_width=True)

else: st.info("Credenciales requeridas.")