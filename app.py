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
        # Asegurar que todas las columnas nuevas existan
        for col in ['Vac_Inicio', 'Vac_Fin', 'Turno_Fijo', 'Estado']:
            if col not in df.columns: 
                df[col] = "Disponible" if col == 'Estado' else ""
        return df
    return pd.DataFrame(columns=['Nombre', 'Pool', 'Coordinador', 'Turno_Fijo', 'Vac_Inicio', 'Vac_Fin', 'Estado'])

def guardar_datos(df):
    df.to_csv(DB_FILE, index=False)

def generar_rol_base(mes, anio, df_base, coordinador_actual):
    num_dias = calendar.monthrange(anio, mes)[1]
    # Solo especialistas asignados a este coordinador (incluye Capacity bloqueados)
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
            # Prioridad 1: Vacaciones
            if v_ini and v_fin and v_ini <= fecha_actual <= v_fin:
                matriz.loc[nom, str(dia)] = "VACACIONES"
            # Prioridad 2: Trabajo hasta 176h
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
        st.subheader("Configuración de Equipo y Capacity Lock")
        col1, col2 = st.columns(2)
        
        with col1:
            with st.expander("🔄 Solicitar Apoyo de Capacity (Lock)", expanded=True):
                # Solo mostrar Capacity que no estén siendo usados por nadie
                libres = df_base[(df_base['Pool'] == 'Capacity') & (df_base['Estado'] == 'Disponible')]
                if not libres.empty:
                    seleccionado = st.selectbox("Recursos Libres", libres['Nombre'].tolist())
                    if st.button("Asignar a mi Pool"):
                        df_base.loc[df_base['Nombre'] == seleccionado, ['Coordinador', 'Estado']] = [u, 'Ocupado']
                        guardar_datos(df_base)
                        st.success(f"{seleccionado} bloqueado con éxito.")
                        st.rerun()
                else:
                    st.warning("No hay personal de Capacity disponible.")

            with st.expander("❌ Liberar / Devolver Recurso"):
                # Solo permite liberar si es de Capacity y es tuyo
                mis_recursos = df_base[(df_base['Coordinador'] == u) & (df_base['Pool'] == 'Capacity')]
                if not mis_recursos.empty:
                    a_liberar = st.selectbox("Seleccionar para devolver", mis_recursos['Nombre'].tolist())
                    if st.button("Liberar Recurso"):
                        df_base.loc[df_base['Nombre'] == a_liberar, ['Coordinador', 'Estado']] = ['Admin', 'Disponible']
                        guardar_datos(df_base)
                        st.rerun()
                else:
                    st.info("No tienes recursos de Capacity para liberar.")

        with col2:
            with st.expander("📅 Vacaciones por Rango"):
                nombres_eq = df_base[df_base['Coordinador'] == u]['Nombre'].tolist()
                if nombres_eq:
                    esp_v = st.selectbox("Especialista", nombres_eq)
                    c_ini, c_fin = st.columns(2)
                    v_inicio = c_ini.date_input("Fecha Inicio")
                    v_final = c_fin.date_input("Fecha Fin")
                    if st.button("Guardar Rango"):
                        df_base.loc[df_base['Nombre'] == esp_v, ['Vac_Inicio', 'Vac_Fin']] = [v_inicio, v_final]
                        guardar_datos(df_base)
                        st.success("Vacaciones registradas.")

        st.divider()
        # TABLA DE MI EQUIPO ACTUAL
        mis_esp = df_base[df_base['Coordinador'] == u]
        if not mis_esp.empty:
            st.write(f"### Mi equipo para este mes ({len(mis_esp)} integrantes):")
            def resaltar_capacity(row):
                return ['background-color: #e8f4f8' if row.Pool == 'Capacity' else '' for _ in row]
            st.dataframe(mis_esp[['Nombre', 'Pool', 'Turno_Fijo', 'Estado']].style.apply(resaltar_capacity, axis=1), use_container_width=True)
        
    with t1:
        mes = st.selectbox("Mes de Planificación", range(1, 13), index=datetime.datetime.now().month-1)
        if st.button("🚀 GENERAR ROL BASE"):
            st.session_state['matriz_edicion'] = generar_rol_base(mes, 2026, df_base, u)
        
        if 'matriz_edicion' in st.session_state:
            st.write("### Edición Manual y Reemplazos")
            # El editor permite cambiar cualquier turno si alguien se queda sin horas
            df_edit = st.data_editor(st.session_state['matriz_edicion'], use_container_width=True)
            st.session_state['matriz_edicion'] = df_edit
            
            # --- ANÁLISIS DE COBERTURA ---
            st.divider()
            st.subheader("📊 Monitoreo de Línea de Atención (24/7)")
            conteo = df_edit.apply(pd.Series.value_counts).fillna(0)
            operativos = [t for t in TURNOS_OPCIONES[:4] if t in conteo.index]
            
            if operativos:
                cob = conteo.loc[operativos]
                st.dataframe(cob.style.applymap(lambda v: 'background-color: #e74c3c; color: white' if v == 0 else 'background-color: #2ecc71; color: white'))
                if (cob == 0).any().any():
                    st.error("🚨 ATENCIÓN: Tienes turnos vacíos (en rojo). Usa el editor manual para cubrirlos.")

else:
    st.info("🔑 Ingrese credenciales en la barra lateral para comenzar.")
