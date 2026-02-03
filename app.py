import streamlit as st
import pandas as pd
import os
import datetime
import calendar
import random

# --- CONFIGURACIÓN ---
COORDINADORES_AUTORIZADOS = {"Samay02": "pass123", "Yape": "yape2024", "Capacity": "capa123", "Samay01": "pass123", "Admin": "admin789"}
DB_FILE = 'especialistas_vFinal.csv'
TURNOS_OPCIONES = ["6am-2pm", "9am-6pm", "6pm-2am", "10pm-6am", "DESCANSO", "VACACIONES"]
POOLS_DISPONIBLES = ["Samay02", "Yape", "proyectos", "Legacy", "Samay01", "SYF", "Capacity"]

def cargar_datos():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        # Columnas necesarias para el bloqueo y vacaciones
        for col in ['Vac_Inicio', 'Vac_Fin', 'Turno_Fijo', 'Estado']:
            if col not in df.columns: 
                df[col] = "Disponible" if col == 'Estado' else ""
        return df
    return pd.DataFrame(columns=['Nombre', 'Pool', 'Coordinador', 'Turno_Fijo', 'Vac_Inicio', 'Vac_Fin', 'Estado'])

def guardar_datos(df):
    df.to_csv(DB_FILE, index=False)

# --- LÓGICA DE GENERACIÓN ---
def generar_rol_base(mes, anio, df_base, coordinador_actual):
    num_dias = calendar.monthrange(anio, mes)[1]
    # Solo toma a los que están asignados a este coordinador actualmente
    df_filt = df_base[df_base['Coordinador'] == coordinador_actual].copy()
    especialistas = df_filt['Nombre'].tolist()
    if not especialistas: return pd.DataFrame()

    dias = [str(d) for d in range(1, num_dias + 1)]
    matriz = pd.DataFrame(index=especialistas, columns=dias)

    for nom in especialistas:
        row = df_filt[df_filt['Nombre'] == nom].iloc[0]
        try:
            v_ini = pd.to_datetime(row['Vac_Inicio']).date() if row['Vac_Inicio'] != "" else None
            v_fin = pd.to_datetime(row['Vac_Fin']).date() if row['Vac_Fin'] != "" else None
        except: v_ini, v_fin = None, None
        
        horas_acum = 0
        for dia in range(1, num_dias + 1):
            fecha_actual = datetime.date(anio, mes, dia)
            if v_ini and v_fin and v_ini <= fecha_actual <= v_fin:
                matriz.loc[nom, str(dia)] = "VACACIONES"
            elif horas_acum + 8 <= 176:
                turno = row['Turno_Fijo'] if row['Turno_Fijo'] in TURNOS_OPCIONES[:4] else random.choice(TURNOS_OPCIONES[:4])
                matriz.loc[nom, str(dia)] = turno
                horas_acum += 8
            else:
                matriz.loc[nom, str(dia)] = "DESCANSO"
    return matriz

# --- INTERFAZ ---
st.set_page_config(page_title="Control 176h & Capacity Lock", layout="wide")
u = st.sidebar.selectbox("Coordinador Actual", list(COORDINADORES_AUTORIZADOS.keys()))
p = st.sidebar.text_input("Contraseña", type="password")

if p == COORDINADORES_AUTORIZADOS.get(u):
    df_base = cargar_datos()
    t1, t2 = st.tabs(["🗓️ Planificación Mensual", "👥 Gestión de Personal"])

    with t2:
        st.subheader("Gestión de Equipo y Bloqueo de Capacity")
        col1, col2 = st.columns(2)
        
        with col1:
            with st.expander("🔄 Solicitar Apoyo de Capacity", expanded=True):
                # FILTRO CLAVE: Solo Capacity que estén "Disponibles"
                libres = df_base[(df_base['Pool'] == 'Capacity') & (df_base['Estado'] == 'Disponible')]
                
                if not libres.empty:
                    seleccionado = st.selectbox("Recursos de Capacity Libres", libres['Nombre'].tolist())
                    if st.button("Bloquear para mi Pool"):
                        df_base.loc[df_base['Nombre'] == seleccionado, 'Coordinador'] = u
                        df_base.loc[df_base['Nombre'] == seleccionado, 'Estado'] = 'Ocupado'
                        guardar_datos(df_base)
                        st.success(f"Has tomado a {seleccionado}. Ahora aparecerá en tu Rol Mensual.")
                        st.rerun()
                else:
                    st.warning("No hay personal de Capacity disponible (todos están apoyando a otros pools).")

            with st.expander("❌ Liberar Recurso / Devolver a Capacity"):
                mis_recursos = df_base[df_base['Coordinador'] == u]
                a_liberar = st.selectbox("Seleccionar para liberar", ["---"] + mis_recursos['Nombre'].tolist())
                if st.button("Devolver a Pool General"):
                    if a_liberar != "---":
                        # Si es de Capacity, lo devolvemos a "Admin" y "Disponible"
                        if df_base.loc[df_base['Nombre'] == a_liberar, 'Pool'].values[0] == 'Capacity':
                            df_base.loc[df_base['Nombre'] == a_liberar, 'Coordinador'] = 'Admin'
                            df_base.loc[df_base['Nombre'] == a_liberar, 'Estado'] = 'Disponible'
                        else:
                            # Si es de tu equipo fijo, simplemente podrías borrarlo o dejarlo
                            st.info("Solo se pueden 'Liberar' recursos del pool de Capacity.")
                        guardar_datos(df_base)
                        st.rerun()

        with col2:
            with st.expander("📅 Vacaciones (Rango)"):
                nombres = df_base[df_base['Coordinador']==u]['Nombre'].tolist()
                if nombres:
                    esp = st.selectbox("Especialista", nombres)
                    f1 = st.date_input("Inicio")
                    f2 = st.date_input("Fin")
                    if st.button("Guardar Vacaciones"):
                        df_base.loc[df_base['Nombre'] == esp, 'Vac_Inicio'] = f1
                        df_base.loc[df_base['Nombre'] == esp, 'Vac_Fin'] = f2
                        guardar_datos(df_base)
                        st.success("Días de vacaciones reservados.")

    with t1:
        st.subheader("Planificación del Mes")
        mes = st.selectbox("Mes", range(1, 13), index=datetime.datetime.now().month-1)
        
        if st.button("🚀 Generar / Actualizar Rol"):
            st.session_state['matriz_final'] = generar_rol_base(mes, 2026, df_base, u)

        if 'matriz_final' in st.session_state:
            # Mostramos el editor. Los Capacity bloqueados aparecerán aquí automáticamente.
            df_editada = st.data_editor(st.session_state['matriz_final'], use_container_width=True)
            
            # Gráfico de cobertura para ver huecos
            st.divider()
            st.subheader("📊 Cobertura Actual (Línea de Atención)")
            conteo = df_editada.apply(pd.Series.value_counts).fillna(0)
            operativos = [t for t in TURNOS_OPCIONES[:4] if t in conteo.index]
            if operativos:
                resumen = conteo.loc[operativos]
                st.dataframe(resumen.style.applymap(lambda v: 'background-color: #e74c3c; color: white' if v == 0 else 'background-color: #2ecc71; color: white'))

else: st.info("🔐 Ingrese credenciales para gestionar el personal.")
