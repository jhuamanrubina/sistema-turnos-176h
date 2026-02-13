import streamlit as st
import pandas as pd
import os
import datetime
import calendar
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import landscape, A4

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


# ---------------- GENERADOR MENSUAL ----------------

def generar_rol_perfecto(mes, anio, df_base, coordinador_actual):

    num_dias = calendar.monthrange(anio, mes)[1]
    df_filt = df_base[df_base['Coordinador'] == coordinador_actual].copy()
    especialistas = df_filt['Nombre'].tolist()

    if not especialistas:
        return pd.DataFrame(), {}

    DIAS_OBJETIVO = 176 // 8

    asignaciones = []
    horas_totales = {nom: 0 for nom in especialistas}
    dias_trabajados = {nom: 0 for nom in especialistas}
    dias_seguidos = {nom: 0 for nom in especialistas}

    mapa_turnos = {}
    for i, nom in enumerate(especialistas):
        turno_pref = df_filt[df_filt['Nombre'] == nom]['Turno_Fijo'].values[0]
        if turno_pref in TURNOS_OPCIONES:
            mapa_turnos[nom] = turno_pref
        else:
            mapa_turnos[nom] = TURNOS_OPCIONES[i % len(TURNOS_OPCIONES)]

    desfase_inicio = {nom: i % 7 for i, nom in enumerate(especialistas)}

    for dia in range(1, num_dias + 1):

        trabajaron_hoy = []

        for nom in especialistas:

            if dia <= desfase_inicio[nom]:
                continue

            if dias_trabajados[nom] >= DIAS_OBJETIVO:
                continue

            if dias_seguidos[nom] >= 6:
                dias_seguidos[nom] = 0
                continue

            asignaciones.append({
                "Día": dia,
                "Especialista": nom,
                "Turno": mapa_turnos[nom],
            })

            dias_trabajados[nom] += 1
            dias_seguidos[nom] += 1
            horas_totales[nom] += 8
            trabajaron_hoy.append(nom)

        if not trabajaron_hoy:
            candidatos = sorted(
                [n for n in especialistas if dias_trabajados[n] < DIAS_OBJETIVO],
                key=lambda x: dias_trabajados[x]
            )
            if candidatos:
                nom = candidatos[0]
                asignaciones.append({
                    "Día": dia,
                    "Especialista": nom,
                    "Turno": mapa_turnos[nom],
                })
                dias_trabajados[nom] += 1
                dias_seguidos[nom] = 1
                horas_totales[nom] += 8

        for nom in especialistas:
            if nom not in trabajaron_hoy:
                dias_seguidos[nom] = 0

    return pd.DataFrame(asignaciones), horas_totales


# ---------------- EXPORTAR PDF ----------------

def exportar_pdf(df_matriz, mes, anio):

    archivo = "rol_mensual.pdf"
    doc = SimpleDocTemplate(
        archivo,
        pagesize=landscape(A4)
    )

    elementos = []
    estilos = getSampleStyleSheet()

    titulo = Paragraph(f"Rol Mensual - {mes}/{anio}", estilos['Heading1'])
    elementos.append(titulo)
    elementos.append(Spacer(1, 12))

    data = [df_matriz.reset_index().columns.tolist()] + df_matriz.reset_index().values.tolist()

    tabla = Table(data)

    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 6)
    ]))

    elementos.append(tabla)
    doc.build(elementos)

    return archivo


# ---------------- INTERFAZ ----------------

st.set_page_config(page_title="Control 176h - Rol Mensual", layout="wide")

u = st.sidebar.selectbox("Coordinador", list(COORDINADORES_AUTORIZADOS.keys()))
p = st.sidebar.text_input("Contraseña", type="password")

if p == COORDINADORES_AUTORIZADOS.get(u):

    df_base = cargar_datos()

    st.title("📅 Generador de Rol Mensual")

    mes = st.selectbox("Mes", range(1, 13), index=datetime.datetime.now().month - 1)

    if st.button("Generar Rol"):

        df_res, horas = generar_rol_perfecto(mes, 2026, df_base, u)
        st.session_state['rol'] = df_res
        st.session_state['horas'] = horas

    if 'rol' in st.session_state and not st.session_state['rol'].empty:

        matriz = st.session_state['rol'].pivot_table(
            index='Especialista',
            columns='Día',
            values='Turno',
            aggfunc='first'
        ).fillna("DESCANSO")

        st.dataframe(matriz, use_container_width=True)

        st.subheader("Horas Totales")
        st.table(pd.DataFrame([
            {"Especialista": k, "Horas": v}
            for k, v in st.session_state['horas'].items()
        ]))

        if st.button("📄 Exportar a PDF"):
            archivo = exportar_pdf(matriz, mes, 2026)
            with open(archivo, "rb") as f:
                st.download_button(
                    "Descargar PDF",
                    f,
                    file_name="rol_mensual.pdf",
                    mime="application/pdf"
                )

else:
    st.warning("Ingrese credenciales válidas.")
