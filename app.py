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
POOLS_DISPONIBLES = ["Samay02", "Yape", "proyectos", "Legacy", "Samay01", "SYF", "Capacity"]

def cargar_datos():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        if 'Turno_Fijo' not in df.columns: df['Turno_Fijo'] = "Aleatorio"
        return df
    return pd.DataFrame(columns=['Nombre', 'Pool', 'Coordinador', 'Turno_Fijo'])

def guardar_datos(df):
    df.to_csv(DB_FILE, index=False)

def generar_rol_perfecto(mes, anio, df_base, coordinador_actual):
    num_dias = calendar.monthrange(anio, mes)[1]
    # Filtra especialistas asignados a ti (incluye los que te prestaron de Capacity)
    df_filt = df_base[df_base['Coordinador'] == coordinador_actual].copy()
    especialistas = df_filt['Nombre'].tolist()
    
    if not especialistas: return pd.DataFrame(), {}

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
        candidatos_dia = sorted(especialistas, key=lambda x: (horas_totales[x], random.random()))
        turnos_cubiertos = {t: 0 for t in TURNOS_OPCIONES}
        
        for nom in candidatos_dia:
            turno_asig = mapa_turnos[nom]
            minimo_req = 2 if turno_asig == "9am-6pm" else 1
            if horas_totales[nom] + 8 <= 176 and ultimo_dia_trabajado[nom] < dia and dias_seguidos[nom] < 6:
                if turnos_cubiertos[turno_asig] < minimo_req or horas_totales[nom] < (dia/num_dias)*176:
                    asignaciones.append({
                        "Día": dia, "Especialista": nom, "Turno": turno_asig,
                        "Pool": df_filt[df_filt['Nombre']==nom]['Pool'].values[0]
                    })
                    horas_totales[nom] += 8
                    ultimo_dia_trabajado[nom] = dia
                    dias_seguidos[nom] += 1
                    turnos_cubiertos[turno_asig] += 1
            
        hoy_trabajaron = [a['Especialista'] for a in asignaciones if a['Día'] == dia]
        for n in especialistas:
            if n not in hoy_trabajaron: dias_seguidos[n] = 0

    return pd.DataFrame(asignaciones), horas_totales

# --- INTERFAZ ---
st.set_page_config(page_title="Control 176h - Gestión de Reemplazos", layout="wide")
u = st.sidebar.selectbox("Coordinador Actual", list(COORDINADORES_AUTORIZADOS.keys()))
p = st.sidebar.text_input("Contraseña", type="password")

if p == COORDINADORES_AUTORIZADOS.get(u):
    df_base = cargar_datos()
    
    t1, t2, t3 = st.tabs(["🗓️ Rol Mensual", "👥 Gestión de Personal", "📊 Auditoría"])

    with t2:
        st.subheader("Panel de Personal y Préstamos de Capacity")
        
        # SECCIÓN 1: CAPACIDAD DE PRÉSTAMO
        with st.expander("🔄 Solicitar Apoyo de Capacity (Préstamo)"):
            recursos_capacity = df_base[df_base['Pool'] == 'Capacity']
            if not recursos_capacity.empty:
                seleccionado = st.selectbox("Especialista disponible en Capacity", recursos_capacity['Nombre'].tolist())
                if st.button("Asignar a mi Pool temporalmente"):
                    df_base.loc[df_base['Nombre'] == seleccionado, 'Coordinador'] = u
                    guardar_datos(df_base)
                    st.success(f"{seleccionado} ahora está bajo tu coordinación.")
                    st.rerun()
            else:
                st.info("No hay recursos en el pool de Capacity actualmente.")

        # SECCIÓN 2: REGISTRO Y ELIMINACIÓN
        with st.expander("➕ Registrar/Retirar Especialista"):
            c1, c2, c3 = st.columns(3)
            n_nom = c1.text_input("Nombre Nuevo")
            n_pool = c2.selectbox("Pool Origen", POOLS_DISPONIBLES)
            n_fijo = c3.selectbox("Turno", ["Aleatorio"] + TURNOS_OPCIONES)
            if st.button("Guardar Registro"):
                nueva = pd.DataFrame([[n_nom, n_pool, u, n_fijo]], columns=['Nombre', 'Pool', 'Coordinador', 'Turno_Fijo'])
                df_base = pd.concat([df_base, nueva], ignore_index=True)
                guardar_datos(df_base)
                st.rerun()
            
            st.divider()
            esp_eliminar = st.selectbox("Seleccionar para retirar (Baja/Vacaciones)", ["---"] + df_base[df_base['Coordinador']==u]['Nombre'].tolist())
            if st.button("❌ Confirmar Salida"):
                if esp_eliminar != "---":
                    # Si es de Capacity, lo devolvemos a su pool original en lugar de borrarlo
                    if df_base.loc[df_base['Nombre'] == esp_eliminar, 'Pool'].values[0] == 'Capacity':
                        df_base.loc[df_base['Nombre'] == esp_eliminar, 'Coordinador'] = "Admin" # O el coord de Capacity
                        st.info(f"{esp_eliminar} regresó al pool de Capacity.")
                    else:
                        df_base = df_base[df_base['Nombre'] != esp_eliminar]
                        st.warning(f"{esp_eliminar} eliminado del sistema.")
                    guardar_datos(df_base)
                    st.rerun()

        # TABLA DE MI EQUIPO ACTUAL
        mis_esp = df_base[df_base['Coordinador'] == u]
        st.write("### Mi equipo para este mes:")
        st.dataframe(mis_esp[['Nombre', 'Pool', 'Turno_Fijo']], use_container_width=True)

    with t1:
        if not mis_esp.empty:
            mes = st.selectbox("Mes de Planificación", range(1, 13), index=datetime.datetime.now().month-1)
            if st.button("🚀 GENERAR HORARIO CON REEMPLAZOS"):
                df_res, hrs = generar_rol_perfecto(mes, 2026, df_base, u)
                st.session_state['r_final'] = df_res
                st.session_state['h_final'] = hrs
            
            if 'r_final' in st.session_state:
                matriz = st.session_state['r_final'].pivot(index='Especialista', columns='Día', values='Turno').fillna("DESCANSO")
                st.dataframe(matriz, use_container_width=True)

    with t3:
        if 'h_final' in st.session_state:
            st.table(pd.DataFrame([{"Especialista": k, "Horas": v} for k, v in st.session_state['h_final'].items()]))

else: st.info("Credenciales requeridas.")
