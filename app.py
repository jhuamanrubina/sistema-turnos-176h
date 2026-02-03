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
        cols = ['Vac_Inicio', 'Vac_Fin', 'Turno_Fijo', 'Pool']
        for col in cols:
            if col not in df.columns: df[col] = ""
        return df
    return pd.DataFrame(columns=['Nombre', 'Pool', 'Coordinador', 'Turno_Fijo', 'Vac_Inicio', 'Vac_Fin'])

def guardar_datos(df):
    df.to_csv(DB_FILE, index=False)

def generar_rol_base(mes, anio, df_base, coordinador_actual):
    num_dias = calendar.monthrange(anio, mes)[1]
    # Filtrar especialistas del coordinador + los de Capacity disponibles para reemplazo
    df_equipo = df_base[df_base['Coordinador'] == coordinador_actual].copy()
    df_capacity = df_base[df_base['Pool'] == 'Capacity'].copy()
    
    especialistas = df_equipo['Nombre'].tolist()
    if not especialistas: return pd.DataFrame()

    dias_str = [str(d) for d in range(1, num_dias + 1)]
    matriz = pd.DataFrame(index=especialistas, columns=dias_str)

    horas_acum = {nom: 0 for nom in especialistas}
    dias_seguidos = {nom: 0 for nom in especialistas}

    for dia in range(1, num_dias + 1):
        fecha_actual = datetime.date(anio, mes, dia)
        turnos_hoy = {t: 0 for t in TURNOS_OPCIONES[:4]}
        
        # 1. Identificar quiénes están de VACACIONES hoy
        en_vacaciones = []
        for nom in especialistas:
            row = df_equipo[df_equipo['Nombre'] == nom].iloc[0]
            try:
                v_ini = pd.to_datetime(row['Vac_Inicio']).date() if pd.notnull(row['Vac_Inicio']) else None
                v_fin = pd.to_datetime(row['Vac_Fin']).date() if pd.notnull(row['Vac_Fin']) else None
                if v_ini and v_fin and v_ini <= fecha_actual <= v_fin:
                    matriz.loc[nom, str(dia)] = "VACACIONES"
                    en_vacaciones.append(nom)
            except: pass

        # 2. Asignación con Distribución Uniforme (para no agotar horas antes del 30)
        # Mezclamos especialistas para que no siempre descansen los mismos
        candidatos = especialistas.copy()
        random.shuffle(candidatos)
        
        for nom in candidatos:
            if nom in en_vacaciones:
                dias_seguidos[nom] = 0
                continue
            
            row = df_equipo[df_equipo['Nombre'] == nom].iloc[0]
            turno_pref = row['Turno_Fijo'] if row['Turno_Fijo'] in TURNOS_OPCIONES[:4] else random.choice(TURNOS_OPCIONES[:4])
            
            # LÓGICA CLAVE: No trabajar más de lo proporcional al día del mes
            # Ejemplo: El día 15 no deberías llevar más de 88 horas (176 / 2)
            limite_proporcional = (dia / num_dias) * 176 + 8 
            
            if horas_acum[nom] + 8 <= 176 and horas_acum[nom] < limite_proporcional and dias_seguidos[nom] < 6:
                matriz.loc[nom, str(dia)] = turno_pref
                horas_acum[nom] += 8
                dias_seguidos[nom] += 1
                turnos_hoy[turno_pref] += 1
            else:
                matriz.loc[nom, str(dia)] = "DESCANSO"
                dias_seguidos[nom] = 0

    return matriz

# --- INTERFAZ ---
st.set_page_config(page_title="Control 24/7 y Capacity", layout="wide")
u = st.sidebar.selectbox("Coordinador Actual", list(COORDINADORES_AUTORIZADOS.keys()))
p = st.sidebar.text_input("Contraseña", type="password")

if p == COORDINADORES_AUTORIZADOS.get(u):
    df_base = cargar_datos()
    t1, t2 = st.tabs(["🗓️ Rol Mensual y Reemplazos", "👥 Gestión de Personal"])

    with t2:
        st.subheader("Personal y Vacaciones")
        # Mostrar Capacity disponible
        cap_libres = df_base[df_base['Pool'] == 'Capacity']
        if not cap_libres.empty:
            st.write("### Especialistas de Capacity Disponibles:")
            st.dataframe(cap_libres[['Nombre', 'Pool']])

        with st.expander("📅 Asignar Vacaciones"):
            equipo = df_base[df_base['Coordinador'] == u]['Nombre'].tolist()
            if equipo:
                sel = st.selectbox("Especialista", equipo)
                c1, c2 = st.columns(2)
                ini = c1.date_input("Desde")
                fin = c2.date_input("Hasta")
                if st.button("Confirmar Vacaciones"):
                    df_base.loc[df_base['Nombre'] == sel, 'Vac_Inicio'] = ini
                    df_base.loc[df_base['Nombre'] == sel, 'Vac_Fin'] = fin
                    guardar_datos(df_base)
                    st.success("Registrado.")

    with t1:
        mes = st.selectbox("Mes", range(1, 13), index=datetime.datetime.now().month-1)
        if st.button("🚀 Generar Rol (Equilibrado 176h)"):
            st.session_state['matriz_trabajo'] = generar_rol_base(mes, 2026, df_base, u)

        if 'matriz_trabajo' in st.session_state:
            df_edit = st.data_editor(st.session_state['matriz_trabajo'], use_container_width=True)
            
            # --- SECCIÓN DE COBERTURA Y REEMPLAZO CAPACITY ---
            st.divider()
            st.subheader("📊 Monitoreo de Cobertura 24/7")
            
            conteo = df_edit.apply(pd.Series.value_counts).fillna(0)
            turnos_reales = [t for t in TURNOS_OPCIONES[:4] if t in conteo.index]
            
            if turnos_reales:
                cob = conteo.loc[turnos_reales]
                st.dataframe(cob.style.applymap(lambda v: 'background-color: #e74c3c' if v == 0 else 'background-color: #2ecc71'))
                
                # BUSCADOR DE REEMPLAZO
                if (cob == 0).any().any():
                    st.error("🚨 HAY HUECOS EN LA ATENCIÓN. Selecciona un Capacity para cubrir:")
                    cap_nombres = df_base[df_base['Pool'] == 'Capacity']['Nombre'].tolist()
                    col1, col2, col3 = st.columns(3)
                    reemplazo = col1.selectbox("Capacity disponible", cap_nombres)
                    dia_h = col2.selectbox("Día a cubrir", df_edit.columns)
                    turno_h = col3.selectbox("Turno", TURNOS_OPCIONES[:4])
                    
                    if st.button("Asignar Reemplazo"):
                        # Agregar fila si el capacity no está en la tabla
                        if reemplazo not in df_edit.index:
                            new_row = pd.Series(["DESCANSO"]*len(df_edit.columns), index=df_edit.columns, name=reemplazo)
                            df_edit.loc[reemplazo] = new_row
                        
                        df_edit.loc[reemplazo, dia_h] = turno_h
                        st.session_state['matriz_trabajo'] = df_edit
                        st.success(f"{reemplazo} asignado al día {dia_h}")
                        st.rerun()

            if st.button("💾 Guardar Rol Final"):
                df_edit.to_csv(f"rol_{u}_{mes}.csv")
                st.balloons()
