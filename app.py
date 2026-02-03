import streamlit as st
import pandas as pd
import os
import datetime
import calendar
import random

# --- CONFIGURACIÓN ---
COORDINADORES_AUTORIZADOS = {
    "Samay02": "pass123", 
    "Yape": "yape2024", 
    "Capacity": "capa123", 
    "Samay01": "pass123", 
    "Admin": "admin789"
}
DB_FILE = 'especialistas_vFinal.csv'
TURNOS_OPCIONES = ["6am-2pm", "9am-6pm", "6pm-2am", "10pm-6am", "DESCANSO", "VACACIONES"]
POOLS_DISPONIBLES = ["Samay02", "Yape", "proyectos", "Legacy", "Samay01", "SYF", "Capacity"]

# --- FUNCIONES DE PERSISTENCIA ---
def cargar_datos():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        for col in ['Vac_Inicio', 'Vac_Fin', 'Turno_Fijo', 'Estado']:
            if col not in df.columns: 
                df[col] = "Disponible" if col == 'Estado' else ""
        return df
    return pd.DataFrame(columns=['Nombre', 'Pool', 'Coordinador', 'Turno_Fijo', 'Vac_Inicio', 'Vac_Fin', 'Estado'])

def guardar_datos(df):
    df.to_csv(DB_FILE, index=False)

def generar_rol_base(mes, anio, df_base, coordinador_actual):
    num_dias = calendar.monthrange(anio, mes)[1]
    df_filt = df_base[df_base['Coordinador'] == coordinador_actual].copy()
    especialistas = df_filt['Nombre'].tolist()
    if not especialistas: return pd.DataFrame()

    dias = [str(d) for d in range(1, num_dias + 1)]
    matriz = pd.DataFrame(index=especialistas, columns=dias)

    for nom in especialistas:
        row = df_filt[df_filt['Nombre'] == nom].iloc[0]
        try:
            v_ini = pd.to_datetime(row['Vac_Inicio']).date() if pd.notnull(row['Vac_Inicio']) and row['Vac_Inicio'] != "" else None
            v_fin = pd.to_datetime(row['Vac_Fin']).date() if pd.notnull(row['Vac_Fin']) and row['Vac_Fin'] != "" else None
        except: v_ini, v_fin = None, None
        
        horas_acum = 0
        for dia in range(1, num_dias + 1):
            fecha_actual = datetime.date(anio, mes, dia)
            if v_ini and v_fin and v_ini <= fecha_actual <= v_fin:
                matriz.loc[nom, str(dia)] = "VACACIONES"
            elif horas_acum + 8 <= 176:
                turno_p = row['Turno_Fijo']
                turno = turno_p if turno_p in TURNOS_OPCIONES[:4] else random.choice(TURNOS_OPCIONES[:4])
                matriz.loc[nom, str(dia)] = turno
                horas_acum += 8
            else:
                matriz.loc[nom, str(dia)] = "DESCANSO"
    return matriz

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="Control 176h & Capacity Lock", layout="wide")
u = st.sidebar.selectbox("Coordinador Actual", list(COORDINADORES_AUTORIZADOS.keys()))
p = st.sidebar.text_input("Contraseña", type="password")

if p == COORDINADORES_AUTORIZADOS.get(u):
    df_base = cargar_datos()
    t1, t2 = st.tabs(["🗓️ Rol Mensual", "👥 Gestión de Personal"])

    with t2:
        st.subheader("Panel de Gestión de Equipo")
        
        # --- FILA 1: ALTAS Y CAPACITY ---
        col_alta, col_cap = st.columns(2)
        
        with col_alta:
            with st.expander("➕ Registrar Nuevo Especialista (Fijo)", expanded=False):
                with st.form("form_alta"):
                    n_nombre = st.text_input("Nombre Completo")
                    n_pool = st.selectbox("Pool de Origen", POOLS_DISPONIBLES)
                    n_turno = st.selectbox("Turno Asignado", ["Aleatorio"] + TURNOS_OPCIONES[:4])
                    submit = st.form_submit_button("Guardar en mi Equipo")
                    if submit and n_nombre:
                        nueva_fila = {
                            'Nombre': n_nombre, 'Pool': n_pool, 'Coordinador': u,
                            'Turno_Fijo': n_turno, 'Vac_Inicio': '', 'Vac_Fin': '', 'Estado': 'Ocupado'
                        }
                        df_base = pd.concat([df_base, pd.DataFrame([nueva_fila])], ignore_index=True)
                        guardar_datos(df_base)
                        st.success(f"{n_nombre} registrado.")
                        st.rerun()

        with col_cap:
            with st.expander("🔄 Solicitar Apoyo de Capacity (Lock)", expanded=False):
                libres = df_base[(df_base['Pool'] == 'Capacity') & (df_base['Estado'] == 'Disponible')]
                if not libres.empty:
                    seleccionado = st.selectbox("Recursos Libres", libres['Nombre'].tolist())
                    if st.button("Asignar a mi Pool"):
                        df_base.loc[df_base['Nombre'] == seleccionado, ['Coordinador', 'Estado']] = [u, 'Ocupado']
                        guardar_datos(df_base)
                        st.rerun()
                else:
                    st.warning("No hay personal de Capacity disponible.")

        # --- FILA 2: VACACIONES Y BAJAS ---
        col_vac, col_baja = st.columns(2)
        
        with col_vac:
            with st.expander("📅 Registrar Rango de Vacaciones"):
                nombres_eq = df_base[df_base['Coordinador'] == u]['Nombre'].tolist()
                if nombres_eq:
                    esp_v = st.selectbox("Especialista", nombres_eq)
                    v_inicio = st.date_input("Fecha Inicio", key="v_ini")
                    v_final = st.date_input("Fecha Fin", key="v_fin")
                    if st.button("Guardar Vacaciones"):
                        df_base.loc[df_base['Nombre'] == esp_v, ['Vac_Inicio', 'Vac_Fin']] = [v_inicio, v_final]
                        guardar_datos(df_base)
                        st.success("Rango guardado.")
        
        with col_baja:
            with st.expander("❌ Retirar Especialista / Liberar"):
                mis_esp_nombres = df_base[df_base['Coordinador'] == u]['Nombre'].tolist()
                esp_elim = st.selectbox("Seleccionar Especialista", ["---"] + mis_esp_nombres)
                if st.button("Confirmar Salida"):
                    if esp_elim != "---":
                        idx = df_base[df_base['Nombre'] == esp_elim].index[0]
                        # Si es Capacity, vuelve al pool general. Si es fijo, se elimina.
                        if df_base.loc[idx, 'Pool'] == 'Capacity':
                            df_base.loc[idx, ['Coordinador', 'Estado']] = ['Admin', 'Disponible']
                        else:
                            df_base = df_base.drop(idx)
                        guardar_datos(df_base)
                        st.rerun()

        st.divider()
        # VISUALIZACIÓN DE EQUIPO
        mis_esp = df_base[df_base['Coordinador'] == u]
        if not mis_esp.empty:
            st.write(f"### Mi equipo actual ({len(mis_esp)} integrantes):")
            def estilo_eq(row):
                return ['background-color: #e8f4f8' if row.Pool == 'Capacity' else '' for _ in row]
            st.dataframe(mis_esp[['Nombre', 'Pool', 'Turno_Fijo', 'Vac_Inicio', 'Vac_Fin']].style.apply(estilo_eq, axis=1), use_container_width=True)
        
    with t1:
        st.subheader("Planificación Mensual")
        mes = st.selectbox("Mes", range(1, 13), index=datetime.datetime.now().month-1)
        if st.button("🚀 GENERAR ROL BASE"):
            st.session_state['matriz_edicion'] = generar_rol_base(mes, 2026, df_base, u)
        
        if 'matriz_edicion' in st.session_state:
            df_edit = st.data_editor(st.session_state['matriz_edicion'], use_container_width=True)
            st.session_state['matriz_edicion'] = df_edit
            
            st.divider()
            st.subheader("📊 Monitoreo de Cobertura (Turnos Críticos)")
            conteo = df_edit.apply(pd.Series.value_counts).fillna(0)
            operativos = [t for t in TURNOS_OPCIONES[:4] if t in conteo.index]
            
            if operativos:
                cob = conteo.loc[operativos]
                st.dataframe(cob.style.applymap(lambda v: 'background-color: #e74c3c; color: white' if v == 0 else 'background-color: #2ecc71; color: white'))
                if (cob == 0).any().any():
                    st.error("⚠️ Tienes huecos sin cubrir. Reasigna turnos manualmente en la tabla superior.")

else:
    st.info("🔐 Ingrese credenciales para comenzar.")
