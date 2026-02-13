import streamlit as st
import pandas as pd
import os
import datetime
import calendar

# Mostrar errores reales (puedes quitarlo luego)
st.set_option('client.showErrorDetails', True)

# ---------------- CONFIGURACIÓN ----------------

COORDINADORES_AUTORIZADOS = {
    "Samay02": "pass123",
    "Yape": "yape2024",
    "Capacity": "capa123",
    "Samay01": "pass123",
    "Admin": "admin789"
}

DB_FILE = 'especialistas_vFinal.csv'

TURNOS_OPCIONES = ["6am-2pm", "9am-6pm", "6pm-2am", "10pm-6am"]

POOLS_DISPONIBLES = [
    "Samay02", "Yape", "proyectos",
    "Legacy", "Samay01", "SYF", "Capacity"
]

# ---------------- FUNCIONES BASE ----------------

def cargar_datos():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        if 'Turno_Fijo' not in df.columns:
            df['Turno_Fijo'] = "Aleatorio"
        return df
    return pd.DataFrame(columns=['Nombre', 'Pool', 'Coordinador', 'Turno_Fijo'])


def guardar_datos(df):
    df.to_csv(DB_FILE, index=False)


# ---------------- GENERADOR MENSUAL 176H ----------------

def generar_rol_perfecto(mes, anio, df_base, coordinador_actual):

    num_dias = calendar.monthrange(anio, mes)[1]
    df_filt = df_base[df_base['Coordinador'] == coordinador_actual].copy()
    especialistas = df_filt['Nombre'].tolist()

    if not especialistas:
        return pd.DataFrame(), {}

    DIAS_OBJETIVO = 176 // 8  # 22 días obligatorios

    asignaciones = []
    horas_totales = {nom: 0 for nom in especialistas}
    dias_trabajados = {nom: 0 for nom in especialistas}
    dias_seguidos = {nom: 0 for nom in especialistas}

    # ---- ASIGNAR TURNO FIJO MENSUAL ----
    mapa_turnos = {}
    for i, nom in enumerate(especialistas):
        turno_pref = df_filt[df_filt['Nombre'] == nom]['Turno_Fijo'].values[0]
        if turno_pref in TURNOS_OPCIONES:
            mapa_turnos[nom] = turno_pref
        else:
            mapa_turnos[nom] = TURNOS_OPCIONES[i % len(TURNOS_OPCIONES)]

    # ---- GENERAR MES COMPLETO ----
    for dia in range(1, num_dias + 1):

        candidatos = sorted(especialistas, key=lambda x: dias_trabajados[x])
        trabajaron_hoy = []

        for nom in candidatos:

            if dias_trabajados[nom] >= DIAS_OBJETIVO:
                continue

            if dias_seguidos[nom] >= 6:
                dias_seguidos[nom] = 0
                continue

            asignaciones.append({
                "Día": dia,
                "Especialista": nom,
                "Turno": mapa_turnos[nom],
                "Pool": df_filt[df_filt['Nombre'] == nom]['Pool'].values[0]
            })

            dias_trabajados[nom] += 1
            dias_seguidos[nom] += 1
            horas_totales[nom] += 8
            trabajaron_hoy.append(nom)

        # Reiniciar contador si descansó
        for nom in especialistas:
            if nom not in trabajaron_hoy:
                dias_seguidos[nom] = 0

    return pd.DataFrame(asignaciones), horas_totales


# ---------------- INTERFAZ STREAMLIT ----------------

st.set_page_config(page_title="Control 176h - Rol Mensual", layout="wide")

u = st.sidebar.selectbox("Coordinador Actual", list(COORDINADORES_AUTORIZADOS.keys()))
p = st.sidebar.text_input("Contraseña", type="password")

if p == COORDINADORES_AUTORIZADOS.get(u):

    df_base = cargar_datos()

    t1, t2, t3 = st.tabs(["🗓️ Rol Mensual", "👥 Gestión de Personal", "📊 Auditoría"])

    # ---------------- TAB PERSONAL ----------------
    with t2:

        st.subheader("Gestión de Personal")

        c1, c2, c3 = st.columns(3)

        n_nom = c1.text_input("Nombre Nuevo")
        n_pool = c2.selectbox("Pool Origen", POOLS_DISPONIBLES)
        n_fijo = c3.selectbox("Turno", ["Aleatorio"] + TURNOS_OPCIONES)

        if st.button("Guardar Registro"):
            if n_nom.strip() != "":
                nueva = pd.DataFrame([[n_nom, n_pool, u, n_fijo]],
                                     columns=['Nombre', 'Pool', 'Coordinador', 'Turno_Fijo'])
                df_base = pd.concat([df_base, nueva], ignore_index=True)
                guardar_datos(df_base)
                st.rerun()

        st.divider()

        esp_eliminar = st.selectbox(
            "Seleccionar para retirar",
            ["---"] + df_base[df_base['Coordinador'] == u]['Nombre'].tolist()
        )

        if st.button("Eliminar"):
            if esp_eliminar != "---":
                df_base = df_base[df_base['Nombre'] != esp_eliminar]
                guardar_datos(df_base)
                st.rerun()

        mis_esp = df_base[df_base['Coordinador'] == u]
        st.write("### Mi equipo:")
        st.dataframe(mis_esp[['Nombre', 'Pool', 'Turno_Fijo']], use_container_width=True)

    # ---------------- TAB ROL ----------------
    with t1:

        mis_esp = df_base[df_base['Coordinador'] == u]

        if not mis_esp.empty:

            mes = st.selectbox(
                "Mes de Planificación",
                range(1, 13),
                index=datetime.datetime.now().month - 1
            )

            if st.button("🚀 GENERAR HORARIO MENSUAL"):
                df_res, hrs = generar_rol_perfecto(mes, 2026, df_base, u)
                st.session_state['r_final'] = df_res
                st.session_state['h_final'] = hrs

            if 'r_final' in st.session_state and not st.session_state['r_final'].empty:

                matriz = st.session_state['r_final'].pivot_table(
                    index='Especialista',
                    columns='Día',
                    values='Turno',
                    aggfunc='first'
                ).fillna("DESCANSO")

                def color_turnos(val):
                    colors = {
                        "6am-2pm": "#D1E9F6",
                        "9am-6pm": "#FFF9BF",
                        "6pm-2am": "#F1D3FF",
                        "10pm-6am": "#D1FFD7",
                        "DESCANSO": "#FFD1D1"
                    }
                    return f'background-color: {colors.get(val, "white")}'

                st.dataframe(
                    matriz.style.applymap(color_turnos),
                    use_container_width=True
                )
            else:
                st.warning("No se generaron asignaciones para este mes.")

    # ---------------- TAB AUDITORÍA ----------------
    with t3:

        if 'h_final' in st.session_state:

            st.subheader("Horas Totales (Debe ser 176)")
            st.table(pd.DataFrame([
                {"Especialista": k, "Horas": v}
                for k, v in st.session_state['h_final'].items()
            ]))

        if 'r_final' in st.session_state and not st.session_state['r_final'].empty:

            st.subheader("Cobertura por Turno")

            cob = st.session_state['r_final'].groupby(
                ['Día', 'Turno']
            ).size().unstack(fill_value=0)

            st.dataframe(
                cob.T.style.applymap(
                    lambda x: f'background-color: {"#2ecc71" if x > 0 else "#e74c3c"}; color: white'
                ),
                use_container_width=True
            )

else:
    st.info("Credenciales requeridas.")
