import json
import os
import urllib.request
from contextlib import closing
from datetime import datetime

import pandas as pd
import psycopg2
from psycopg2.errors import UniqueViolation
from psycopg2.extras import RealDictCursor
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
CLAVE_CANCELACION = os.getenv("CLAVE_CANCELACION", "")
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "").strip()

ESPACIOS_LISTA = [
    "Salón de Usos Múltiples (SUM)",
    "Sala de Informática",
    "Sala de Conferencia",
]

TURNOS = [
    "07:00 AM - 08:20 AM (Módulos 1 y 2 - Mañana)",
    "08:30 AM - 09:50 AM (Módulos 3 y 4 - Mañana)",
    "10:00 AM - 11:20 AM (Módulos 5 y 6 - Mañana)",
    "11:20 AM - 12:00 PM (Módulos 7 y 8 - Mañana)",
    "12:00 PM - 12:40 PM (Módulo 9 Final - Mañana)",
    "01:00 PM - 02:20 PM (Módulos 1 y 2 - Tarde)",
    "02:30 PM - 03:50 PM (Módulos 3 y 4 - Tarde)",
    "04:00 PM - 05:20 PM (Módulos 5 y 6 - Tarde)",
    "05:20 PM - 06:00 PM (Módulos 7 y 8 - Tarde)",
    "06:00 PM - 06:40 PM (Módulo 9 Final - Tarde)",
]


def conectar_db():
    if not DATABASE_URL:
        raise RuntimeError("Falta configurar DATABASE_URL.")
    return psycopg2.connect(DATABASE_URL, sslmode="require", connect_timeout=10)


def enviar_correo_confirmacion(destinatario, reserva):
    if not BREVO_API_KEY or not destinatario:
        return False

    html_contenido = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; color: #333; padding: 20px; border: 1px solid #00B4D8; border-radius: 10px;">
        <h2 style="color: #0077B6;">Instituto Superior Santa Catalina</h2>
        <h3 style="color: #00B4D8;">Confirmación de Reserva - Espacios y Aulas Especiales</h3>
        <p>Estimado/a <b>{reserva['profesor']}</b>,</p>
        <p>Su solicitud ha sido registrada con éxito en el sistema digital.</p>
        <hr style="border: 0; border-top: 1px solid #eee;">
        <ul>
            <li><b>Espacio:</b> {reserva['espacio']}</li>
            <li><b>Fecha:</b> {reserva['fecha']}</li>
            <li><b>Bloque Horario:</b> {reserva['turno']}</li>
            <li><b>Estado:</b> SOLICITADO</li>
        </ul>
        <p style="font-size: 0.9em; color: #7f8c8d;">Mensaje automático del sistema de reservas escolares.</p>
    </div>
    """

    payload = {
        "sender": {"name": "Reservas Santa Catalina", "email": "alanaco374@gmail.com"},
        "to": [{"email": destinatario}],
        "subject": f"Reserva Confirmada: {reserva['espacio']} ({reserva['fecha']})",
        "htmlContent": html_contenido,
    }

    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "api-key": BREVO_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status in [200, 201]
    except Exception as e:
        print(f"Error al enviar correo: {e}")
        return False


@st.cache_data(ttl=60)
def cargar_datos():
    consulta = """
        SELECT id, profesor, email,
               TO_CHAR(fecha, 'YYYY-MM-DD') AS fecha,
               espacio, turno,
               TO_CHAR(registro AT TIME ZONE 'America/Argentina/Buenos_Aires', 'DD/MM/YYYY HH24:MI') AS registro
        FROM public.reservas_espacios
        ORDER BY fecha, turno, id
    """
    with closing(conectar_db()) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(consulta)
            return [dict(fila) for fila in cur.fetchall()]


def guardar_datos(datos):
    consulta = """
        INSERT INTO public.reservas_espacios (profesor, email, fecha, espacio, turno)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, TO_CHAR(fecha, 'YYYY-MM-DD') AS fecha
    """
    with closing(conectar_db()) as conn:
        try:
            with conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        consulta,
                        (
                            datos["profesor"],
                            datos["email"],
                            datos["fecha"],
                            datos["espacio"],
                            datos["turno"],
                        ),
                    )
                    guardada = dict(cur.fetchone())
            datos.update(guardada)
            return datos
        except UniqueViolation:
            return None


def eliminar_registro(registro_id):
    with closing(conectar_db()) as conn:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM public.reservas_espacios WHERE id = %s", (registro_id,)
                )
                return cur.rowcount == 1


st.set_page_config(
    page_title="Gestión de Espacios y Aulas - Santa Catalina",
    page_icon="🏛️",
    layout="centered",
)

st.markdown(
    """
    <style>
    .stApp, * { font-family: 'Segoe UI', sans-serif !important; }
    .stApp { background-color: #F8F9FA; color: #212529 !important; }
    .stTextInput input, .stSelectbox select, .stDateInput input {
        background-color: #FFFFFF !important; color: #1E293B !important;
        border: 1px solid #CBD5E1 !important; border-radius: 6px !important;
    }
    .stTextInput label, .stSelectbox label, .stDateInput label {
        color: #0F172A !important; font-weight: 600 !important;
    }
    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        background-color: #FFFFFF; border: 1px solid #CBD5E1 !important;
        border-radius: 10px; padding: 20px; box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    }
    button[kind="primary"] {
        background-color: #00B4D8 !important; color: white !important; border-radius: 6px !important; font-weight: 600 !important;
    }
    button[kind="secondary"] {
        background-color: #FFFFFF !important; color: #1E293B !important; border: 1px solid #CBD5E1 !important; border-radius: 6px !important; font-weight: 600 !important;
    }
    button[aria-label="Show password"], button[aria-label="Hide password"] {
        display: none !important;
    }
    img {
        image-rendering: -webkit-optimize-contrast;
        image-rendering: crisp-edges;
    }
    /* Ocultar cualquier texto huérfano de iconos del sistema */
    [data-testid="stSidebarNav"] span {
        font-family: 'Segoe UI', sans-serif !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Encabezado principal con logos
col_img1, col_texto, col_img2 = st.columns([1, 2.7, 1])

with col_img1:
    if os.path.exists("IMG.jpg"):
        st.image("IMG.jpg", width=115)

with col_texto:
    st.markdown(
        """
        <div style='padding-top: 5px; text-align: center;'>
            <h3 style='color: #343A40; margin-bottom: 0px; font-weight: 700; font-size: 1.15rem;'>INSTITUTO SUPERIOR</h3>
            <h1 style='color: #00B4D8; margin-top: 0px; font-weight: 800; font-size: 1.85rem;'>SANTA CATALINA</h1>
            <p style='color: #6C757D; letter-spacing: 1.2px; font-size: 0.7rem; margin-top: 2px; font-weight: 600;'>SISTEMA DE GESTIÓN DE ESPACIOS Y AULAS</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_img2:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=130)
    elif os.path.exists("logo.jpg"):
        st.image("logo.jpg", width=130)

st.markdown("<hr style='border: 0; border-top: 2px solid #CBD5E1; margin-top: 15px; margin-bottom: 20px;'>", unsafe_allow_html=True)

# --- CONTROL DE ACCESO / PANTALLA DE LOGIN INSTITUCIONAL ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.markdown("<br>", unsafe_allow_html=True)
    col_l1, col_l2, col_l3 = st.columns([1, 2.2, 1])
    with col_l2:
        with st.container(border=True):
            st.markdown(
                """
                <div style='text-align: center; margin-bottom: 15px;'>
                    <h4 style='color: #03045E; font-size: 1.2rem; font-weight: 700; margin-bottom: 5px;'>🔒 Acceso Restringido</h4>
                    <p style='color: #64748B; font-size: 0.85rem;'>Ingrese la clave institucional para operar el sistema de reservas.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            pass_input = st.text_input("Clave de Acceso:", type="password", key="login_pass", label_visibility="collapsed")
            st.markdown("<div style='height: 5px;'></div>", unsafe_allow_html=True)
            if st.button("Ingresar al Sistema", type="primary", use_container_width=True, key="btn_login"):
                if pass_input == CLAVE_CANCELACION:
                    st.session_state.autenticado = True
                    st.rerun()
                else:
                    st.error("❌ Clave institucional incorrecta.")
    st.stop()

# --- BOTÓN DE CERRAR SESIÓN (Sidebar) ---
with st.sidebar:
    st.markdown("### Sesión Activa")
    if st.button("🔒 Cerrar Sesión", use_container_width=True):
        st.session_state.autenticado = False
        st.rerun()

# --- CARGA DE DATOS ---
try:
    registros_actuales = cargar_datos()
except Exception as error:
    st.error("No se pudo conectar con la base de datos en Supabase.")
    st.exception(error)
    st.stop()

if "pestana_espacios" not in st.session_state:
    st.session_state.pestana_espacios = "Nueva Reserva"

col_b1, col_b2, col_b3 = st.columns(3)
with col_b1:
    if st.button("📝 Nueva Reserva", use_container_width=True, type="primary" if st.session_state.pestana_espacios == "Nueva Reserva" else "secondary", key="e1"):
        st.session_state.pestana_espacios = "Nueva Reserva"
        st.rerun()
with col_b2:
    if st.button("📋 Planilla de Disponibilidad", use_container_width=True, type="primary" if st.session_state.pestana_espacios == "Planilla de Disponibilidad" else "secondary", key="e2"):
        st.session_state.pestana_espacios = "Planilla de Disponibilidad"
        st.rerun()
with col_b3:
    if st.button("❌ Cancelar Reserva", use_container_width=True, type="primary" if st.session_state.pestana_espacios == "Cancelar Reserva" else "secondary", key="e3"):
        st.session_state.pestana_espacios = "Cancelar Reserva"
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

if st.session_state.pestana_espacios == "Nueva Reserva":
    st.markdown("<h4 style='color: #03045E; font-size: 1.15rem; margin-bottom: 10px;'>Solicitud de Espacios y Aulas Especiales</h4>", unsafe_allow_html=True)
    with st.container(border=True):
        nombre_profesor = st.text_input("Nombre y Apellido del Docente:")
        email_profesor = st.text_input("Correo Electrónico de Confirmación:")
        col1, col2 = st.columns(2)
        with col1:
            fecha_sel = st.date_input("Fecha:", min_value=datetime.today().date())
            fecha_str = fecha_sel.strftime("%Y-%m-%d")
        with col2:
            item_sel = st.selectbox("Seleccionar Espacio:", ESPACIOS_LISTA)
        turno_sel = st.selectbox("Bloque Horario Escolar:", TURNOS)
        es_fin_semana = fecha_sel.weekday() in [5, 6]

    if es_fin_semana:
        st.error("🔒 El establecimiento no registra turnos los fines de semana.")
    elif st.button("Confirmar y Bloquear Horario", type="primary", use_container_width=True, key="btn_conf_esp"):
        if not nombre_profesor.strip():
            st.toast("⚠️ Complete su nombre.", icon="👤")
        elif not email_profesor.strip() or "@" not in email_profesor:
            st.toast("⚠️ Ingrese un correo válido.", icon="📧")
        else:
            nueva = {
                "profesor": nombre_profesor.strip().title(),
                "email": email_profesor.strip().lower(),
                "fecha": fecha_str,
                "espacio": item_sel,
                "turno": turno_sel,
            }
            guardado = guardar_datos(nueva)
            if guardado is None:
                st.error("❌ Conflicto: El espacio seleccionado ya está ocupado en ese horario.")
            else:
                enviar_correo_confirmacion(email_profesor.strip().lower(), guardado)
                st.cache_data.clear()
                st.balloons()
                st.toast("🎉 ¡Reserva confirmada con éxito!", icon="✅")
                st.success("🎉 ¡Reserva registrada y correo enviado con éxito!")

elif st.session_state.pestana_espacios == "Planilla de Disponibilidad":
    st.markdown("<h4 style='color: #03045E; font-size: 1.15rem; margin-bottom: 10px;'>Ocupación actual de Espacios y Aulas</h4>", unsafe_allow_html=True)
    if not registros_actuales:
        st.info("No hay reservas registradas en este módulo.")
    else:
        df = pd.DataFrame(registros_actuales)
        st.dataframe(df, use_container_width=True, hide_index=True)

elif st.session_state.pestana_espacios == "Cancelar Reserva":
    st.markdown("<h4 style='color: #03045E; font-size: 1.15rem; margin-bottom: 10px;'>Anulación de Turnos</h4>", unsafe_allow_html=True)
    if not registros_actuales:
        st.info("No hay turnos para cancelar.")
    else:
        opciones = {
            r["id"]: f"{r['fecha']} | {r['espacio']} | {r['turno']} (Prof. {r['profesor']})"
            for r in registros_actuales
        }
        reserva_id = st.selectbox("Seleccionar turno a dar de baja:", options=list(opciones.keys()), format_func=lambda x: opciones[x])
        clave = st.text_input("Clave Institucional de Confirmación:", type="password", key="pwd_esp")
        if st.button("Eliminar Reserva", type="primary", use_container_width=True, key="btn_del_esp"):
            if clave == CLAVE_CANCELACION:
                if eliminar_registro(reserva_id):
                    st.cache_data.clear()
                    st.toast("🗑️ Cancelación realizada correctamente.", icon="⚠️")
                    st.success("✅ Cancelación exitosa: La reserva ha sido eliminada de la base de datos.")
            else:
                st.error("🔒 Clave incorrecta.")