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
TURNOS_ESPECIALES_FILE = 'turnos_especiales.csv'

TURNOS_OPCIONES = ["6am-2pm", "9am-6pm", "6pm-2am", "10pm-6am"]
POOLS_DISPONIBLES = ["Samay02", "Yape", "proyectos", "Legacy", "Samay01", "SYF", "Capacity"]

# --- DATOS ---
def cargar_datos():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        if 'Turno_Fijo' not in df.columns:
            df['Turno_Fijo'] = "Aleatorio"
        if 'Prestado_A' not in df.columns:
            df['Prestado_A'] = ""
        return df
    return pd.DataFrame(columns=['Nombre', 'Pool', 'Coordinador', 'Turno_Fijo', 'Prestado_A'])

def guardar_datos(df):
    df.to_csv(DB_FILE, index=False)

def cargar_turnos_especiales():
    if os.path.exists(TURNOS_ESPECIALES_FILE):
        return pd.read_csv(TURNOS_ESPECIALES_FILE)
    return pd.DataFrame(columns=['Coordinador', 'Día', 'Turno'])

def guardar_turnos_especiales(df):
    df.to_csv(TURNOS_ESPECIALES_FILE, index=False)

# --- GENERADOR ---
def generar_rol_perfecto(mes, anio, df_base, coordinador_actual):
    df_turnos_especiales = cargar_turnos_especiales()
    num_dias = calendar.monthrange(anio, mes)[1]

    df_filt = df_base[df_base['Coordinador'] == coordinador_actual].copy()
    especialistas = df_filt['Nombre'].tolist()
    if not especialistas:
        return pd.DataFrame(), {}

    patron = ["6am-2pm", "9am-6pm", "9am-6pm", "6pm-2am", "10pm-6am"]
    mapa_turnos = {
        nom: (
            df_filt[df_filt['Nombre'] == nom]['Turno_Fijo'].values[0]
            if df_filt[df_filt['Nombre'] == nom]['Turno_Fijo'].values[0] in TURNOS_OPCIONES
            else patron[i % len(patron)]
        )
        for i, nom in enumerate(especialistas)
    }

    asignaciones = []
    horas_totales = {n: 0 for n in especialistas}
    dias_seguidos = {n: 0 for n in especialistas}
    ultimo_dia = {n: -1 for n in especialistas}

    for dia in range(1, num_dias + 1):
        turno_forzado = df_turnos_especiales[
            (df_turnos_especiales['Coordinador'] == coordinador_actual) &
            (df_turnos_especiales['Día'] == dia)
        ]

        candidatos = sorted(especialistas, key=lambda x: (horas_totales[x], random.random()))
        turnos_cubiertos = {t: 0 for t in TURNOS_OPCIONES}

        for nom in candidatos:
            turno_asig = (
                turno_forzado['Turno'].values[0]
                if not turno_forzado.empty
                else mapa_turnos[nom]
            )

            minimo_req = 2 if turno_asig == "9am-6pm" else 1

            if (
                horas_totales[nom] + 8 <= 176 and
                ultimo_dia[nom] < dia and
                dias_seguidos[nom] < 6
            ):
                if turnos_cubiertos[turno_asig] < minimo_req:
                    asignaciones.append({
                        "Día": dia,
                        "Especialista": nom,
                        "Turno": turno_asig,
                        "Pool": df_filt[df_filt['Nombre'] == nom]['Pool'].values[0]
                    })
                    horas_totales[nom] += 8
                    ultimo_dia[nom] = dia
                    dias_seguidos[nom] += 1
                    turnos_cubiertos[turno_asig] += 1

        hoy = [a['Especialista'] for a in asignaciones if a['Día'] == dia]
        for n in especialistas:
            if n not in hoy:
                dias_seguidos[n] = 0

    return pd.DataFrame(asignaciones), horas_totales

# --- UI ---
st.set_page_config("Control 176h - Gestión de Reemplazos", layout="wide")

u = st.sidebar.selectbox("Coordinador Actual", list(COORDINADORES_AUTORIZADOS.keys()))
p = st.sidebar.text_input("Contraseña", type="password")

if p == COORDINADORES_AUTORIZADOS.get(u):
    df_base = cargar_datos()

    t1, t2, t3 = st.tabs(["🗓️ Rol Mensual", "👥 Gestión de Personal", "📊 Auditoría"])

    # --- PERSONAL ---
    with t2:
        st.subheader("Panel de Personal y Capacity")

        with st.expander("🔄 Solicitar apoyo de Capacity"):
            recursos = df_base[
                (df_base['Pool'] == 'Capacity') &
                (df_base['Prestado_A'] == "")
            ]

            if not recursos.empty:
                sel = st.selectbox("Especialista", recursos['Nombre'].tolist())
                if st.button("Asignar a mi pool"):
                    df_base.loc[df_base['Nombre'] == sel, 'Prestado_A'] = u
                    df_base.loc[df_base['Nombre'] == sel, 'Coordinador'] = u
                    guardar_datos(df_base)
                    st.success(f"{sel} asignado exclusivamente a tu pool")
                    st.rerun()
            else:
                st.info("No hay Capacity disponibles")

        with st.expander("➕ Registrar / Retirar"):
            c1, c2, c3 = st.columns(3)
            n = c1.text_input("Nombre")
            p0 = c2.selectbox("Pool", POOLS_DISPONIBLES)
            t = c3.selectbox("Turno", ["Aleatorio"] + TURNOS_OPCIONES)

            if st.button("Guardar"):
                df_base = pd.concat([
                    df_base,
                    pd.DataFrame([[n, p0, u, t, ""]],
                        columns=df_base.columns)
                ])
                guardar_datos(df_base)
                st.rerun()

            st.divider()
            baja = st.selectbox(
                "Seleccionar",
                ["---"] + df_base[df_base['Coordinador'] == u]['Nombre'].tolist()
            )

            if st.button("❌ Confirmar salida"):
                if baja != "---":
                    if df_base.loc[df_base['Nombre'] == baja, 'Pool'].values[0] == 'Capacity':
                        df_base.loc[df_base['Nombre'] == baja, ['Prestado_A', 'Coordinador']] = ["", "Admin"]
                    else:
                        df_base = df_base[df_base['Nombre'] != baja]
                    guardar_datos(df_base)
                    st.rerun()

        st.dataframe(
            df_base[df_base['Coordinador'] == u][['Nombre', 'Pool', 'Turno_Fijo']],
            use_container_width=True
        )

    # --- ROL ---
    with t1:
        st.subheader("Turno forzado por día (todo el equipo)")
        df_turnos = cargar_turnos_especiales()
        d = st.number_input("Día", 1, 31)
        tr = st.selectbox("Turno", TURNOS_OPCIONES)

        if st.button("Aplicar turno"):
            df_turnos = df_turnos[
                ~((df_turnos['Coordinador'] == u) & (df_turnos['Día'] == d))
            ]
            df_turnos = pd.concat([
                df_turnos,
                pd.DataFrame([[u, d, tr]], columns=df_turnos.columns)
            ])
            guardar_turnos_especiales(df_turnos)
            st.success("Turno aplicado")

        mes = st.selectbox("Mes", range(1, 13), index=datetime.datetime.now().month - 1)

        if st.button("🚀 Generar horario"):
            r, h = generar_rol_perfecto(mes, 2026, df_base, u)
            st.session_state['r'] = r
            st.session_state['h'] = h

        if 'r' in st.session_state:
            mat = st.session_state['r'].pivot(
                index='Especialista', columns='Día', values='Turno'
            ).fillna("DESCANSO")

            st.dataframe(mat, use_container_width=True)

    # --- AUDITORÍA ---
    with t3:
        if 'h' in st.session_state:
            st.table(pd.DataFrame(
                [{"Especialista": k, "Horas": v} for k, v in st.session_state['h'].items()]
            ))

else:
    st.info("Credenciales requeridas")
