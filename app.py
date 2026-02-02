import streamlit as st
import pandas as pd
import os
import datetime
import calendar
import random
import io

# --- CONFIGURACIÓN ---
COORDINADORES_AUTORIZADOS = {"Samay02": "pass123", "Yape": "yape2024", "Admin": "admin789"}
DB_FILE = 'especialistas_vFinal.csv'
AUSENCIAS_FILE = 'ausencias_v1.csv'
TURNOS_OPCIONES = ["6am-2pm", "9am-6pm", "6pm-2am", "10pm-6am"]
POOLS_DISPONIBLES = ["Samay02", "Yape", "proyectos", "Legacy", "Samay01", "SYF", "Capacity"]

# --- FUNCIONES DE DATOS ---
def cargar_datos():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        if 'Turno_Fijo' not in df.columns: df['Turno_Fijo'] = "Aleatorio"
        return df
    return pd.DataFrame(columns=['Nombre', 'Pool', 'Coordinador', 'Turno_Fijo'])

def cargar_ausencias():
    if os.path.exists(AUSENCIAS_FILE):
        return pd.read_csv(AUSENCIAS_FILE)
    return pd.DataFrame(columns=['Nombre', 'Inicio', 'Fin'])

def guardar_datos(df, archivo):
    df.to_csv(archivo, index=False)

def es_ausente(nombre, dia, mes, anio, df_aus):
    fecha = datetime.date(anio, mes, dia)
    ausencia = df_aus[df_aus['Nombre'] == nombre]
    for _, fila in ausencia.iterrows():
        try:
            inicio = pd.to_datetime(fila['Inicio']).date()
            fin = pd.to_datetime(fila['Fin']).date()
            if inicio <= fecha <= fin: return True
        except: continue
    return False

# --- MOTOR DE HORARIOS MENSUALES ---
def generar_rol_perfecto(mes, anio, df_base, coordinador_actual, df_aus):
    num_dias = calendar.monthrange(anio, mes)[1]
    df_propios = df_base[df_base['Coordinador'] == coordinador_actual].copy()
    df_capacity = df_base[df_base['Pool'] == 'Capacity'].copy()
    
    especialistas_propios = df_propios['Nombre'].tolist()
    especialistas_capacity = df_capacity['Nombre'].tolist()
    todos = especialistas_propios + especialistas_capacity
    
    if not especialistas_propios: return pd.DataFrame(), {}

    mapa_turnos = {}
    for _, fila in pd.concat([df_propios, df_capacity]).iterrows():
        mapa_turnos[fila['Nombre']] = fila['Turno_Fijo']

    asignaciones = []
    horas_totales = {nom: 0 for nom in todos}
    dias_seguidos = {nom: 0 for nom in todos}
    ultimo_dia = {nom: -1 for nom in todos}

    for dia in range(1, num_dias + 1):
        faltantes_hoy = [n for n in especialistas_propios if es_ausente(n, dia, mes, anio, df_aus)]
        disponibles_hoy = [n for n in especialistas_propios if n not in faltantes_hoy]
        
        # Si falta alguien, habilitamos a los de Capacity
        if faltantes_hoy:
            disponibles_hoy.extend(especialistas_capacity)

        candidatos = sorted(disponibles_hoy, key=lambda x: (horas_totales[x], random.random()))
        turnos_cubiertos = {t: 0 for t in TURNOS_OPCIONES}

        for nom in candidatos:
            t_pref = mapa_turnos.get(nom, "Aleatorio")
            t_asig = t_pref if t_pref in TURNOS_OPCIONES else random.choice(TURNOS_OPCIONES)
            
            # Condición de 176h y descanso
            if horas_totales[nom] + 8 <= 176 and ultimo_dia[nom] < dia and dias_seguidos[nom] < 6:
                asignaciones.append({"Día": dia, "Especialista": nom, "Turno": t_asig})
                horas_totales[nom] += 8
                ultimo_dia[nom] = dia
                dias_seguidos[nom] += 1
                turnos_cubiertos[t_asig] += 1
        
        # Registrar visualmente las vacaciones
        for nom in faltantes_hoy:
            asignaciones.append({"Día": dia, "Especialista": nom, "Turno": "VACACIONES"})
            dias_seguidos[nom] = 0

    return pd.DataFrame(asignaciones), horas_totales

# --- INTERFAZ ---
st.set_page_config(page_title="Control 176h PRO", layout="wide")
u = st.sidebar.selectbox("Coordinador", list(COORDINADORES_AUTORIZADOS.keys()))
p = st.sidebar.text_input("Password", type="password")

if p == COORDINADORES_AUTORIZADOS.get(u):
    df_base = cargar_datos()
    df_aus = cargar_ausencias()
    
    t1, t2, t3 = st.tabs(["🗓️ Rol Mensual", "👥 Gestión de Equipo", "📊 Auditoría"])

    with t2:
        # AQUÍ REGRESA EL REGISTRO DE ESPECIALISTAS
        st.subheader("Gestión de Personal")
        with st.expander("➕ Registrar Nuevo Especialista"):
            with st.form("nuevo_esp", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                n_nom = c1.text_input("Nombre")
                n_pool = c2.selectbox("Pool", POOLS_DISPONIBLES)
                n_fijo = c3.selectbox("Turno Fijo", ["Aleatorio"] + TURNOS_OPCIONES)
                if st.form_submit_button("Guardar Especialista"):
                    if n_nom:
                        nueva = pd.DataFrame([[n_nom, n_pool, u, n_fijo]], columns=['Nombre', 'Pool', 'Coordinador', 'Turno_Fijo'])
                        df_base = pd.concat([df_base, nueva], ignore_index=True)
                        guardar_datos(df_base, DB_FILE)
                        st.success(f"{n_nom} registrado.")
                        st.rerun()

        # SECCIÓN DE VACACIONES
        st.subheader("Control de Vacaciones (Días específicos)")
        with st.expander("📅 Registrar Ausencia"):
            c1, c2, c3 = st.columns(3)
            quien_v = c1.selectbox("Especialista", df_base[df_base['Coordinador']==u]['Nombre'].tolist() if not df_base.empty else [])
            f_ini = c2.date_input("Inicio")
            f_fin = c3.date_input("Fin")
            if st.button("Guardar Vacaciones"):
                nueva_v = pd.DataFrame([[quien_v, str(f_ini), str(f_fin)]], columns=['Nombre', 'Inicio', 'Fin'])
                df_aus = pd.concat([df_aus, nueva_v], ignore_index=True)
                guardar_datos(df_aus, AUSENCIAS_FILE)
                st.success("Registrado correctamente.")
                st.rerun()
        
        if st.button("🗑️ Limpiar todas las vacaciones"):
            guardar_datos(pd.DataFrame(columns=['Nombre', 'Inicio', 'Fin']), AUSENCIAS_FILE)
            st.rerun()

    with t1:
        # EL HORARIO REGRESA A SER MENSUAL COMPLETO
        st.subheader("Generación de Rol Mensual")
        mes = st.selectbox("Seleccione el Mes", range(1, 13), index=datetime.datetime.now().month-1)
        
        if st.button("🚀 GENERAR HORARIO COMPLETO"):
            df_res, hrs = generar_rol_perfecto(mes, 2026, df_base, u, df_aus)
            st.session_state['r_final'] = df_res
            st.session_state['h_final'] = hrs

        if 'r_final' in st.session_state and not st.session_state['r_final'].empty:
            matriz = st.session_state['r_final'].pivot(index='Especialista', columns='Día', values='Turno').fillna("DESCANSO")
            
            # Botón de Excel Arreglado
            csv = matriz.to_csv(index=True, sep=';', encoding='utf-8-sig')
            st.download_button("📥 Descargar Excel (.csv)", csv, f"Rol_{u}_Mes_{mes}.csv", "text/csv")

            def estilo(val):
                colors = {"6am-2pm":"#D1E9F6","9am-6pm":"#FFF9BF","6pm-2am":"#F1D3FF","10pm-6am":"#D1FFD7","VACACIONES":"#FFB347","DESCANSO":"#FFD1D1"}
                return f'background-color: {colors.get(val, "white")}'

            st.dataframe(matriz.style.applymap(estilo), use_container_width=True)

    with t3:
        if 'h_final' in st.session_state:
            st.write("### Horas Totales Mensuales")
            res_h = pd.DataFrame([{"Especialista": k, "Horas": v} for k, v in st.session_state['h_final'].items()])
            st.table(res_h)

else: st.info("Credenciales requeridas.")
