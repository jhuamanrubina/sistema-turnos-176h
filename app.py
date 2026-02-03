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

# --- FUNCIONES DE DATOS ---
def cargar_datos():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        for col in ['Vac_Inicio', 'Vac_Fin', 'Turno_Fijo']:
            if col not in df.columns: df[col] = ""
        return df
    return pd.DataFrame(columns=['Nombre', 'Pool', 'Coordinador', 'Turno_Fijo', 'Vac_Inicio', 'Vac_Fin'])

def guardar_datos(df):
    df.to_csv(DB_FILE, index=False)

def obtener_ruta_rol(coordinador, mes, anio=2026):
    return f'rol_{coordinador}_{mes}_{anio}.csv'

def guardar_rol_editado(df_matriz, coordinador, mes):
    ruta = obtener_ruta_rol(coordinador, mes)
    df_matriz.to_csv(ruta)

def cargar_rol_guardado(coordinador, mes):
    ruta = obtener_ruta_rol(coordinador, mes)
    if os.path.exists(ruta):
        return pd.read_csv(ruta, index_col=0)
    return None

def generar_rol_base(mes, anio, df_base, coordinador_actual):
    num_dias = calendar.monthrange(anio, mes)[1]
    df_filt = df_base[df_base['Coordinador'] == coordinador_actual].copy()
    especialistas = df_filt['Nombre'].tolist()
    if not especialistas: return pd.DataFrame()

    dias = [str(d) for d in range(1, num_dias + 1)]
    matriz = pd.DataFrame(index=especialistas, columns=dias)

    for nom in especialistas:
        row = df_filt[df_filt['Nombre'] == nom].iloc[0]
        v_ini = pd.to_datetime(row['Vac_Inicio']).date() if row['Vac_Inicio'] else None
        v_fin = pd.to_datetime(row['Vac_Fin']).date() if row['Vac_Fin'] else None
        
        horas_acum = 0
        for dia in range(1, num_dias + 1):
            fecha_actual = datetime.date(anio, mes, dia)
            if v_ini and v_fin and v_ini <= fecha_actual <= v_fin:
                matriz.loc[nom, str(dia)] = "VACACIONES"
            else:
                if horas_acum + 8 <= 176:
                    turno = row['Turno_Fijo'] if row['Turno_Fijo'] != "Aleatorio" and row['Turno_Fijo'] != "" else random.choice(TURNOS_OPCIONES[:4])
                    matriz.loc[nom, str(dia)] = turno
                    horas_acum += 8
                else:
                    matriz.loc[nom, str(dia)] = "DESCANSO"
    return matriz

# --- INTERFAZ ---
st.set_page_config(page_title="Sistema de Gestión Operativa", layout="wide")
u = st.sidebar.selectbox("Coordinador Actual", list(COORDINADORES_AUTORIZADOS.keys()))
p = st.sidebar.text_input("Contraseña", type="password")

if p == COORDINADORES_AUTORIZADOS.get(u):
    df_base = cargar_datos()
    t1, t2 = st.tabs(["🗓️ Planificación (Edición Manual)", "👥 Gestión de Personal"])

    with t2:
        st.subheader("Configuración de Especialistas")
        col1, col2 = st.columns(2)
        
        with col1:
            with st.expander("📅 Registrar Rango de Vacaciones"):
                nombres_equipo = df_base[df_base['Coordinador']==u]['Nombre'].tolist()
                if nombres_equipo:
                    esp_sel = st.selectbox("Seleccionar Especialista", nombres_equipo)
                    f_ini = st.date_input("Inicio Vacaciones")
                    f_fin = st.date_input("Fin Vacaciones")
                    if st.button("Actualizar Vacaciones"):
                        df_base.loc[df_base['Nombre'] == esp_sel, 'Vac_Inicio'] = f_ini
                        df_base.loc[df_base['Nombre'] == esp_sel, 'Vac_Fin'] = f_fin
                        guardar_datos(df_base)
                        st.success("Fechas guardadas.")
                else: st.info("No tienes personal a cargo.")

        with col2:
            with st.expander("➕ Alta de Personal"):
                n_nom = st.text_input("Nombre")
                n_pool = st.selectbox("Pool", POOLS_DISPONIBLES)
                n_fijo = st.selectbox("Turno Fijo", ["Aleatorio"] + TURNOS_OPCIONES[:4])
                if st.button("Guardar Registro"):
                    nueva = pd.DataFrame([[n_nom, n_pool, u, n_fijo, "", ""]], 
                                         columns=['Nombre', 'Pool', 'Coordinador', 'Turno_Fijo', 'Vac_Inicio', 'Vac_Fin'])
                    df_base = pd.concat([df_base, nueva], ignore_index=True)
                    guardar_datos(df_base)
                    st.rerun()

    with t1:
        c1, c2 = st.columns([1, 3])
        mes = c1.selectbox("Mes de Trabajo", range(1, 13), index=datetime.datetime.now().month-1)
        
        # Cargar si existe uno previo
        if 'matriz_trabajo' not in st.session_state:
            saved_rol = cargar_rol_guardado(u, mes)
            if saved_rol is not None:
                st.session_state['matriz_trabajo'] = saved_rol
            else:
                st.session_state['matriz_trabajo'] = pd.DataFrame()

        if c2.button("🚀 Reiniciar/Generar Nuevo Rol Base"):
            st.session_state['matriz_trabajo'] = generar_rol_base(mes, 2026, df_base, u)
            guardar_rol_editado(st.session_state['matriz_trabajo'], u, mes)

        if not st.session_state['matriz_trabajo'].empty:
            st.write("### Edición Manual del Rol")
            # El editor manual guarda automáticamente los cambios en el state
            df_editado = st.data_editor(
                st.session_state['matriz_trabajo'],
                use_container_width=True,
                height=400
            )
            
            if st.button("💾 Guardar Cambios Manuales"):
                st.session_state['matriz_trabajo'] = df_editado
                guardar_rol_editado(df_editado, u, mes)
                st.success("¡Cambios guardados correctamente!")

            # --- ANÁLISIS DE COBERTURA ---
            st.divider()
            st.subheader("📊 Análisis de Cobertura y Necesidad de Capacity")
            
            # Conteo de personas por turno cada día
            conteo = df_editado.apply(lambda x: x.value_counts()).fillna(0)
            
            # Solo mostrar los turnos operativos
            turnos_reales = [t for t in TURNOS_OPCIONES[:4] if t in conteo.index]
            if turnos_reales:
                resumen_cob = conteo.loc[turnos_reales]
                
                def estilo_cobertura(val):
                    return 'background-color: #2ecc71; color: white' if val > 0 else 'background-color: #e74c3c; color: white'

                st.write("En **ROJO** los turnos que no tienen a nadie asignado:")
                st.dataframe(resumen_cob.style.applymap(estilo_cobertura))
                
                # Alerta automática
                if (resumen_cob == 0).any().any():
                    st.error("🚨 ALERTA: Tienes turnos vacíos. Debes asignar un recurso de Capacity en los espacios rojos.")
            
else: st.info("🔒 Credenciales requeridas.")
