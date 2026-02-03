import streamlit as st
import pandas as pd
import os
import datetime
import calendar
import random
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

# ================= CONFIG =================
COORDINADORES_AUTORIZADOS = {
    "Samay02": "pass123",
    "Yape": "yape2024",
    "Capacity": "capa123",
    "Samay01": "pass123",
    "Admin": "admin789"
}

DB_FILE = "especialistas_vFinal.csv"
TURNOS_MANUAL_FILE = "turnos_manual.csv"
HISTORICO_DIR = "historico_roles"

TURNOS_OPCIONES = ["6am-2pm", "9am-6pm", "6pm-2am", "10pm-6am"]

# ================= DATA =================
def cargar_datos():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        if "Turno_Fijo" not in df.columns:
            df["Turno_Fijo"] = "Aleatorio"
        return df
    return pd.DataFrame(columns=["Nombre", "Pool", "Coordinador", "Turno_Fijo"])

def cargar_turnos_manual():
    if os.path.exists(TURNOS_MANUAL_FILE):
        return pd.read_csv(TURNOS_MANUAL_FILE)
    return pd.DataFrame(columns=["Coordinador", "Especialista", "Día", "Turno"])

def guardar_turnos_manual(df):
    df.to_csv(TURNOS_MANUAL_FILE, index=False)

def guardar_historico(df, coord, mes, anio):
    os.makedirs(HISTORICO_DIR, exist_ok=True)
    ruta = f"{HISTORICO_DIR}/rol_{coord}_{anio}_{str(mes).zfill(2)}.csv"
    df.to_csv(ruta, index=False)
    return ruta

# ================= GENERADOR =================
def generar_rol(mes, anio, df_base, coord):
    manual = cargar_turnos_manual()
    dias = calendar.monthrange(anio, mes)[1]
    df = df_base[df_base["Coordinador"] == coord]
    esp = df["Nombre"].tolist()

    horas = {e: 0 for e in esp}
    seguidos = {e: 0 for e in esp}
    asignaciones = []

    for d in range(1, dias + 1):
        cobertura = {t: [] for t in TURNOS_OPCIONES}
        random.shuffle(esp)

        for turno in TURNOS_OPCIONES:
            minimo = 2 if turno == "9am-6pm" else 1

            for e in esp:
                if horas[e] >= 176 or seguidos[e] >= 6:
                    continue
                if len(cobertura[turno]) >= minimo:
                    break

                m = manual[
                    (manual["Coordinador"] == coord) &
                    (manual["Especialista"] == e) &
                    (manual["Día"] == d)
                ]

                turno_final = m["Turno"].values[0] if not m.empty else turno

                asignaciones.append({
                    "Día": d,
                    "Especialista": e,
                    "Turno": turno_final
                })

                horas[e] += 8
                seguidos[e] += 1
                cobertura[turno].append(e)

        trabajaron = [a["Especialista"] for a in asignaciones if a["Día"] == d]
        for e in esp:
            if e not in trabajaron:
                seguidos[e] = 0

    return pd.DataFrame(asignaciones), horas

# ================= PDF =================
def generar_pdf(df, coord, mes, anio):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)

    data = [["Especialista"] + list(df.columns[1:])]
    for _, r in df.iterrows():
        data.append([r["Especialista"]] + list(r[1:]))

    tabla = Table(data, repeatRows=1)
    tabla.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey)
    ]))

    elementos = [
        Image("logo.png", width=120, height=50),
        tabla,
        Image("firma.png", width=120, height=50)
    ]

    doc.build(elementos)
    buffer.seek(0)
    return buffer

# ================= UI =================
st.set_page_config("Gestión 176h", layout="wide")
u = st.sidebar.selectbox("Usuario", COORDINADORES_AUTORIZADOS.keys())
p = st.sidebar.text_input("Contraseña", type="password")
ES_ADMIN = (u == "Admin")

if p == COORDINADORES_AUTORIZADOS[u]:

    df_base = cargar_datos()
    if not ES_ADMIN:
        df_base = df_base[df_base["Coordinador"] == u]

    t1, t2, t3 = st.tabs(["🗓️ Rol", "✏️ Manual", "📊 SLA"])

    # ---- ROL ----
    with t1:
        mes = st.selectbox("Mes", range(1,13), datetime.datetime.now().month-1)
        if st.button("Generar Rol"):
            rol, horas = generar_rol(mes, 2026, df_base, u)
            st.session_state["rol"] = rol
            st.session_state["horas"] = horas
            guardar_historico(rol, u, mes, 2026)

        if "rol" in st.session_state:
            matriz = st.session_state["rol"].pivot(
                index="Especialista", columns="Día", values="Turno"
            ).fillna("DESCANSO")
            st.dataframe(matriz)

            pdf = generar_pdf(matriz.reset_index(), u, mes, 2026)
            st.download_button("📄 Descargar PDF", pdf, "rol.pdf")

    # ---- MANUAL ----
    with t2:
        df_manual = cargar_turnos_manual()
        esp = st.selectbox("Especialista", df_base["Nombre"])
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

    # ---- SLA ----
    with t3:
        if "rol" in st.session_state:
            total_dias = len(st.session_state["rol"])
            cobertura = st.session_state["rol"].groupby(["Día","Turno"]).size()
            st.metric("Cobertura %", round((cobertura > 0).mean() * 100, 2))

else:
    st.info("Credenciales incorrectas")
