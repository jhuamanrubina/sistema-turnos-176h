import streamlit as st
import pandas as pd
import os
import datetime
import calendar
import random
from io import BytesIO

# ================= CONFIGURACIÓN =================
COORDINADORES_AUTORIZADOS = {
    "Samay02": "pass123",
    "Yape": "yape2024",
    "Capacity": "capa123",
    "Samay01": "pass123",
    "Admin": "admin789"
}

DB_FILE = "especialistas_vFinal.csv"
TURNOS_MANUAL_FILE = "turnos_manual.csv"

TURNOS_OPCIONES = ["6am-2pm", "9am-6pm", "6pm-2am", "10pm-6am"]
POOLS_DISPONIBLES = ["Samay02", "Yape", "proyectos", "Legacy", "Samay01", "SYF", "Capacity"]

# ================= DATOS =================
def cargar_datos():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        if "Turno_Fijo" not in df.columns:
            df["Turno_Fijo"] = "Aleatorio"
        return df
    return pd.DataFrame(columns=["Nombre", "Pool", "Coordinador", "Turno_Fijo"])

def guardar_datos(df):
    df.to_csv(DB_FILE, index=False)

def cargar_turnos_manual():
    if os.path.exists(TURNOS_MANUAL_FILE):
        return pd.read_csv(TURNOS_MANUAL_FILE)
    return pd.DataFrame(columns=["Coordinador", "Especialista", "Día", "Turno"])

def guardar_turnos_manual(df):
    df.to_csv(TURNOS_MANUAL_FILE, index=False)

# ================= GENERADOR =================
def generar_rol_perfecto(mes, anio, df_base, coordinador):
    df_manual = cargar_turnos_manual()
    num_dias = calendar.monthrange(anio, mes)[1]

    df_filt = df_base[df_base["Coordinador"] == coordinador]
    especialistas = df_filt["Nombre"].tolist()

    if not especialistas:
        return pd.DataFrame(), {}

    patron = ["6am-2pm", "9am-6pm", "6pm-2am", "10pm-6am"]
    mapa_turnos = {
        n: (
            df_filt.loc[df_filt["Nombre"] == n, "Turno_Fijo"].values[0]
            if df_filt.loc[df_filt["Nombre"] == n, "Turno_Fijo"].values[0] in TURNOS_OPCIONES
            else patron[i % len(patron)]
        )
        for i, n in enumerate(especialistas)
    }

    asignaciones = []
    horas = {n: 0 for n in especialistas}
    dias_seguidos = {n: 0 for n in especialistas}
    ultimo_dia = {n: 0 for n in especialistas}

    for dia in range(1, num_dias + 1):
        cobertura = {t: [] for t in TURNOS_OPCIONES}
        random.shuffle(especialistas)

        for turno in TURNOS_OPCIONES:
            minimo = 2 if turno == "9am-6pm" else 1

            for n in especialistas:
                if horas[n] >= 176:
                    continue
                if ultimo_dia[n] == dia:
                    continue
                if dias_seguidos[n] >= 6:
                    continue
                if len(cobertura[turno]) >= minimo:
                    break

                manual = df_manual[
                    (df_manual["Coordinador"] == coordinador) &
                    (df_manual["Especialista"] == n) &
                    (df_manual["Día"] == dia)
                ]

                turno_final = manual["Turno"].values[0] if not manual.empty else turno

                asignaciones.append({
                    "Día": dia,
                    "Especialista": n,
                    "Turno": turno_final,
                    "Pool": df_filt.loc[df_filt["Nombre"] == n, "Pool"].values[0]
                })

                horas[n] += 8
                dias_seguidos[n] += 1
                ultimo_dia[n] = dia
                cobertura[turno].append(n)

        trabajaron = [a["Especialista"] for a in asignaciones if a["Día"] == dia]
        for n in especialistas:
            if n not in trabajaron:
                dias_seguidos[n] = 0

    for n in especialistas:
        while horas[n] < 176:
            for dia in range(1, num_dias + 1):
                ya = any(a["Día"] == dia and a["Especialista"] == n for a in asignaciones)
                if ya:
                    continue
                asignaciones.append({
                    "Día": dia,
                    "Especialista": n,
                    "Turno": mapa_turnos[n],
                    "Pool": df_filt.loc[df_filt["Nombre"] == n, "Pool"].values[0]
                })
                horas[n] += 8
                break

    return pd.DataFrame(asignaciones), horas

# ================= UI =================
st.set_page_config("Control 176h", layout="wide")

u = st.sidebar.selectbox("Coordinador", list(COORDINADORES_AUTORIZADOS.keys()))
p = st.sidebar.text_input("Contraseña", type="password")
ES_ADMIN = (u == "Admin")

if p == COORDINADORES_AUTORIZADOS.get(u):

    df_base = cargar_datos()
    if not ES_ADMIN:
        df_base = df_base[df_base["Coordinador"] == u]

    t1, t2, t3 = st.tabs(["🗓️ Rol", "👥 Personal", "📊 Auditoría"])

    # ---------- PERSONAL ----------
    with t2:
        st.subheader("Gestión de Personal")

        if ES_ADMIN:
            st.success("Modo Administrador")

        with st.expander("✏️ Cambio manual de turno"):
            df_manual = cargar_turnos_manual()
            esp = st.selectbox("Especialista", df_base["Nombre"].unique())
            dia = st.number_input("Día", 1, 31, 1)
            turno = st.selectbox("Turno", TURNOS_OPCIONES)

            if st.button("Guardar cambio"):
                df_manual = df_manual[
                    ~((df_manual["Especialista"] == esp) & (df_manual["Día"] == dia))
                ]
                df_manual = pd.concat([df_manual, pd.DataFrame([{
                    "Coordinador": u,
                    "Especialista": esp,
                    "Día": dia,
                    "Turno": turno
                }])])
                guardar_turnos_manual(df_manual)
                st.success("Cambio guardado")

    # ---------- ROL ----------
    with t1:
        mes = st.selectbox("Mes", range(1, 13), datetime.datetime.now().month - 1)
        if st.button("🚀 Generar Rol"):
            r, h = generar_rol_perfecto(mes, 2026, df_base, u)
            st.session_state["rol"] = r
            st.session_state["horas"] = h

        if "rol" in st.session_state:
            matriz = st.session_state["rol"].pivot(
                index="Especialista", columns="Día", values="Turno"
            ).fillna("DESCANSO")

            def color_turnos(val):
                colores = {
                    "6am-2pm": "#D1E9F6",
                    "9am-6pm": "#FFF9BF",
                    "6pm-2am": "#F1D3FF",
                    "10pm-6am": "#D1FFD7",
                    "DESCANSO": "#FFD1D1"
                }
                return f"background-color: {colores.get(val, 'white')}"

            st.dataframe(matriz.style.applymap(color_turnos), use_container_width=True)

            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                matriz.to_excel(writer)
            st.download_button(
                "📥 Descargar Excel",
                buffer.getvalue(),
                "rol_mensual.xlsx"
            )

    # ---------- AUDITORÍA ----------
    with t3:
        if "horas" in st.session_state:
            st.subheader("Horas por especialista")
            for k, v in st.session_state["horas"].items():
                if v > 176:
                    st.error(f"{k}: {v}h (exceso)")
                elif v < 176:
                    st.warning(f"{k}: {v}h (incompleto)")
                else:
                    st.success(f"{k}: 176h OK")

else:
    st.info("Ingrese credenciales")
