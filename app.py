import streamlit as st
import pandas as pd
import os
import datetime
import calendar
import random
from io import BytesIO

# --- CONFIGURACIÓN ---
COORDINADORES_AUTORIZADOS = {"Samay02": "pass123", "Yape": "yape2024", "Capacity": "capa123", "Samay01": "pass123", "Admin": "admin789"}
DB_FILE = 'especialistas_vFinal.csv'
TURNOS_OPCIONES = ["6am-2pm", "9am-6pm", "6pm-2am", "10pm-6am"]
POOLS_DISPONIBLES = ["Samay02", "Yape", "proyectos", "Legacy", "Samay01", "SYF", "Capacity"]

def cargar_datos():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        if 'Turno_Fijo' not in df.columns: df['Turno_Fijo'] = "Aleatorio"
        if 'Vacaciones' not in df.columns: df['Vacaciones'] = ""
        if 'Estado' not in df.columns: df['Estado'] = "Disponible"
        return df
    return pd.DataFrame(columns=['Nombre', 'Pool', 'Coordinador', 'Turno_Fijo', 'Vacaciones', 'Estado'])

def guardar_datos(df):
    df.to_csv(DB_FILE, index=False)

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=True, sheet_name='Horario')
    return output.getvalue()

def generar_rol_perfecto(mes, anio, df_base, coordinador_actual):
    num_dias = calendar.monthrange(anio, mes)[1]
    df_filt = df_base[df_base['Coordinador'] == coordinador_actual].copy()
    especialistas = df_filt['Nombre'].tolist()
    
    if not especialistas: return pd.DataFrame(), {}

    mapa_turnos = {}
    mapa_vacaciones = {}
    patron = ["6am-2pm", "9am-6pm", "9am-6pm", "6pm-2am", "10pm-6am"]
    
    for i, row in df_filt.reset_index().iterrows():
        nom = row['Nombre']
        mapa_turnos[nom] = row['Turno_Fijo'] if row['Turno_Fijo'] in TURNOS_OPCIONES else patron[i % len(patron)]
        vacs = str(row['Vacaciones']).split(',')
        mapa_vacaciones[nom] = [int(v) for v in vacs if v.strip().isdigit()]

    asignaciones = []
    horas_totales = {nom: 0 for nom in especialistas}
    dias_seguidos = {nom: 0 for nom in especialistas}
    ultimo_dia_trabajado = {nom: -1 for nom in especialistas}

    for dia in range(1, num_dias + 1):
        for nom in especialistas:
            if dia in mapa_vacaciones[nom]:
                asignaciones.append({"Día": dia, "Especialista": nom, "Turno": "VAC", "Pool": df_filt[df_filt['Nombre']==nom]['Pool'].values[0]})
                ultimo_dia_trabajado[nom] = dia 

        candidatos_dia = sorted(especialistas, key=lambda x: (horas_totales[x], random.random()))
        turnos_cubiertos = {t: 0 for t in TURNOS_OPCIONES}
        
        for nom in candidatos_dia:
            if any(a['Especialista'] == nom and a['Día'] == dia for a in asignaciones): continue
            turno_asig = mapa_turnos[nom]
            minimo_req = 2 if turno_asig == "9am-6pm" else 1
            if horas_totales[nom] + 8 <= 176 and ultimo_dia_trabajado[nom] < dia and dias_seguidos[nom] < 6:
                if turnos_cubiertos[turno_asig] < minimo_req or horas_totales[nom] < (dia/num_dias)*176:
                    asignaciones.append({"Día": dia, "Especialista": nom, "Turno": turno_asig, "Pool": df_filt[df_filt['Nombre']==nom]['Pool'].values[0]})
                    horas_totales[nom] += 8
                    ultimo_dia_trabajado[nom] = dia
                    dias_seguidos[nom] += 1
                    turnos_cubiertos[turno_asig] += 1
            
        hoy_trabajaron = [a['Especialista'] for a in asignaciones if a['Día'] == dia and a['Turno'] != "VAC"]
        for n in especialistas:
            if n not in hoy_trabajaron: dias_seguidos[n] = 0

    return pd.DataFrame(asignaciones), horas_totales

# --- INTERFAZ ---
st.set_page_config(page_title="Gestión 176h PRO", layout="wide")
u = st.sidebar.selectbox("Coordinador", list(COORDINADORES_AUTORIZADOS.keys()))
p = st.sidebar.text_input("Contraseña", type="password")

if p == COORDINADORES_AUTORIZADOS.get(u):
    df_base = cargar_datos()
    t1, t2, t3 = st.tabs(["🗓️ Rol Mensual", "👥 Gestión de Personal", "📊 Auditoría"])

    with t2:
        st.subheader("Configuración de Equipo")
        c_left, c_right = st.columns(2)
        with c_left:
            with st.expander("🔄 Préstamo Capacity (Exclusivo)"):
                libres = df_base[(df_base['Pool'] == 'Capacity') & (df_base['Estado'] == 'Disponible')]
                if not libres.empty:
                    sel = st.selectbox("Especialista de Capacity", libres['Nombre'].tolist())
                    if st.button("Asignar a mi Pool"):
                        df_base.loc[df_base['Nombre'] == sel, ['Coordinador', 'Estado']] = [u, 'Ocupado']
                        guardar_datos(df_base); st.rerun()
        with c_right:
            with st.expander("📅 Marcar Vacaciones"):
                mis_esp = df_base[df_base['Coordinador']==u]['Nombre'].tolist()
                esp_v = st.selectbox("Nombre", mis_esp if mis_esp else ["---"])
                dv = st.text_input("Días (ej: 1,2,3)")
                if st.button("Guardar"):
                    df_base.loc[df_base['Nombre'] == esp_v, 'Vacaciones'] = dv
                    guardar_datos(df_base); st.success("Guardado")

    with t1:
        if not df_base[df_base['Coordinador'] == u].empty:
            mes = st.selectbox("Mes", range(1, 13), index=datetime.datetime.now().month-1)
            if st.button("🚀 GENERAR HORARIO"):
                df_res, hrs = generar_rol_perfecto(mes, 2026, df_base, u)
                st.session_state['r_final'] = df_res
                st.session_state['h_final'] = hrs

            if 'r_final' in st.session_state:
                res = st.session_state['r_final']
                num_dias = calendar.monthrange(2026, mes)[1]
                matriz = res.pivot(index='Especialista', columns='Día', values='Turno').fillna("DESCANSO")
                
                # Alertas de Cobertura
                check_cob = res[res['Turno'] != "VAC"].groupby(['Día', 'Turno']).size().unstack(fill_value=0)
                huecos = [{"Día": d, "Turno": t} for d in range(1, num_dias + 1) for t in TURNOS_OPCIONES 
                          if d not in check_cob.index or t not in check_cob.columns or check_cob.loc[d, t] == 0]
                
                if huecos:
                    st.error(f"⚠️ Faltan {len(huecos)} turnos. Revisa el resumen de Auditoría.")
                
                st.dataframe(matriz.style.applymap(lambda v: f'background-color: {"#FFA500" if v=="VAC" else "#D1FFD7" if v!="DESCANSO" else "#FFD1D1"}'), use_container_width=True)
                
                # --- BOTONES DE DESCARGA ---
                col_ex, col_pdf = st.columns(2)
                with col_ex:
                    st.download_button("📥 Descargar Excel", data=to_excel(matriz), file_name=f"Rol_{u}_{mes}.xlsx")
                with col_pdf:
                    st.caption("Tip: Para PDF usa Ctrl+P en la tabla y guarda como PDF.")

    with t3:
        if 'h_final' in st.session_state:
            st.subheader("Resumen de Faltantes para Capacity")
            if huecos: st.table(pd.DataFrame(huecos))
            else: st.success("Cobertura completa.")
            st.subheader("Horas Acumuladas")
            st.table(pd.DataFrame([{"Especialista": k, "Horas": v} for k, v in st.session_state['h_final'].items()]))

else: st.info("Ingresa credenciales.")
