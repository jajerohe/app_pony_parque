import base64
import html
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

from auth import iniciar_sesion, cerrar_sesion
from inicio import mostrar_inicio
from usuarios import mostrar_mi_cuenta, mostrar_modulo_usuarios

ZONA_HORARIA = ZoneInfo("America/Bogota")
CARPETA_IMAGENES = Path(__file__).parent / "assets"


@st.cache_data
def logo_base64():
    return base64.b64encode((CARPETA_IMAGENES / "logo.png").read_bytes()).decode()


st.set_page_config(
    page_title="Pony Parque",
    page_icon=str(CARPETA_IMAGENES / "icono.png"),
    layout="wide"
)

# ============================================================
# OCULTAR BARRA SUPERIOR NATIVA DE STREAMLIT
# ============================================================
st.markdown("""
<style>
header[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"] {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    min-height: 0 !important;
}
.block-container {
    padding-top: 0.5rem !important;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# INICIO DE SESIÓN
# ============================================================
def mostrar_login():
    """Muestra el inicio de sesión: marca a la izquierda y acceso a la derecha."""

    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { display: none !important; }
        .block-container, [data-testid="stMainBlockContainer"] {
            padding: 0 !important;
            max-width: 100% !important;
        }
        div[data-testid="stElementContainer"]:has(style) { display: none; }
        [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] { gap: 0; }
        [data-testid="stForm"] [data-testid="stVerticalBlock"] { gap: 1rem; }

        div[data-testid="stHorizontalBlock"]:has(.pp-marca) { gap: 0 !important; min-height: 100vh; }
        div[data-testid="stColumn"]:has(.pp-marca) {
            background:
                radial-gradient(circle at 20% 15%, rgba(255, 255, 255, 0.85), transparent 40%),
                linear-gradient(180deg, #CDEBFA 0%, #E9F6FD 45%, #EEF6DF 75%, #D7EBB4 100%);
            border-right: 4px solid #F59E1B;
        }
        div[data-testid="stColumn"]:has(.pp-marca),
        div[data-testid="stColumn"]:has(.pp-acceso) { min-height: 100vh; }
        div[data-testid="stColumn"]:has(.pp-marca) > div,
        div[data-testid="stColumn"]:has(.pp-acceso) > div {
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        div[data-testid="stColumn"]:has(.pp-marca) > div { padding: 2rem 3.5rem; }
        div[data-testid="stColumn"]:has(.pp-acceso) > div { padding: 2rem 1.5rem; }

        .pp-marca { text-align: center; }
        .pp-marca img { display: block; margin: 0 auto; width: min(340px, 80%); height: auto; filter: drop-shadow(0 14px 22px rgba(74, 36, 18, .25)); }
        .pp-marca p {
            display: inline-block; color: #FFC629; background: #6B3416; font-weight: 800; font-size: 1.05rem;
            letter-spacing: .04em; margin: 1.2rem 0 0; padding: .45rem 1.2rem; border-radius: 6px;
            box-shadow: 0 4px 0 #4A2412;
        }

        .pp-acceso { text-align: center; }
        .pp-acceso h3 { color: #4A2412; font-weight: 700; font-size: 1.75rem !important; margin: 0; padding: 0 0 .3rem; }
        .pp-acceso p { color: #7A5C48; font-size: 1.05rem; margin: 0 0 1.4rem; }

        div[data-testid="stColumn"]:has(.pp-acceso) [data-testid="stForm"] {
            background: #FFFFFF;
            border: 1px solid #F1DFC4;
            border-top: 4px solid #F59E1B;
            border-radius: 14px;
            box-shadow: 0 10px 30px rgba(74, 36, 18, 0.10);
            padding: 1.6rem 1.6rem 1.2rem;
        }
        div[data-testid="stForm"] input:focus {
            border-color: #F59E1B !important;
            box-shadow: 0 0 0 1px #F59E1B !important;
        }
        div[data-testid="stFormSubmitButton"] button {
            background: linear-gradient(90deg, #6B3416 0%, #8E4A1E 55%, #C8681A 100%) !important;
            border: none !important;
            color: #FFFFFF !important;
            border-radius: 8px !important;
            min-height: 44px !important;
            font-weight: 700 !important;
            box-shadow: 0 4px 14px rgba(107, 52, 22, 0.28);
        }
        div[data-testid="stFormSubmitButton"] button:hover { filter: brightness(1.07); }

        .pp-pie { text-align: center; color: #7A5C48; font-size: .83rem; line-height: 1.5; margin-top: 1.8rem; }
        .pp-pie p { margin: 0 0 .8rem; }
        .pp-pie b { color: #4A2412; }
        .pp-pie .firma { font-size: .78rem; letter-spacing: .02em; }

        @media (max-width: 640px) {
            div[data-testid="stHorizontalBlock"]:has(.pp-marca),
            div[data-testid="stColumn"]:has(.pp-marca),
            div[data-testid="stColumn"]:has(.pp-acceso) { min-height: auto; }
            div[data-testid="stColumn"]:has(.pp-marca) > div { padding: 2.5rem 1.5rem 2rem; }
            div[data-testid="stColumn"]:has(.pp-acceso) > div { padding: 2rem 1rem; }
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    marca, acceso = st.columns(2)

    with marca:
        st.markdown(
            """
            <div class="pp-marca">
                <img src="data:image/png;base64,{logo}" alt="Pony Parque - Hotel Mesa de los Santos">
                <p>SISTEMA DE GESTIÓN</p>
            </div>
            """.format(logo=logo_base64()),
            unsafe_allow_html=True
        )

    with acceso:
        st.markdown(
            """
            <div class="pp-acceso">
                <h3>Bienvenido de nuevo</h3>
                <p>Ingresa con tus credenciales para continuar</p>
            </div>
            """,
            unsafe_allow_html=True
        )

        _, centro, _ = st.columns([0.12, 0.76, 0.12])
        with centro:
            with st.form("form_login"):
                email = st.text_input("Correo electrónico", placeholder="usuario@dominio.com")
                password = st.text_input("Contraseña", type="password", placeholder="Ingrese su contraseña")
                ingresar = st.form_submit_button("Ingresar", type="primary", width="stretch")

        st.markdown(
            """
            <div class="pp-pie">
                <p><b>Pony Parque</b> · Sistema de gestión<br>
                Acceso protegido mediante autenticación segura.</p>
                <p class="firma">Powered by <b>JAJEROHE Systems</b></p>
            </div>
            """,
            unsafe_allow_html=True
        )

        if ingresar:
            email = email.strip()

            if not email or not password:
                st.warning("⚠️ Debe ingresar el correo electrónico y la contraseña.")
                return

            try:
                with st.spinner("Validando credenciales..."):
                    usuario = iniciar_sesion(email, password)

                if not usuario:
                    st.error("❌ Correo o contraseña incorrectos.")
                    return

                st.session_state["usuario_actual"] = usuario["USUARIO"]
                st.session_state["perfil_actual"] = usuario["PERFIL"]
                st.session_state["nombre_actual"] = usuario["NOMBRE"]
                st.session_state["email_actual"] = email

                st.rerun()

            except Exception:
                st.error("❌ No fue posible conectarse a la base de datos. Intente de nuevo en un momento.")


# ============================================================
# CONTROL DE ACCESO
# ============================================================

# El botón circular de cerrar sesión del encabezado es un enlace a ?logout=1.
if st.query_params.get("logout"):
    cerrar_sesion()
    for clave in ["usuario_actual", "perfil_actual", "nombre_actual", "email_actual", "pagina_actual"]:
        st.session_state.pop(clave, None)
    st.query_params.clear()

if "usuario_actual" not in st.session_state:
    mostrar_login()
    st.stop()

usuario_actual = st.session_state["usuario_actual"]
perfil_actual = st.session_state.get("perfil_actual", "")
nombre_actual = st.session_state.get("nombre_actual", "")

# Perfil Administrador: acceso completo, incluida la administración de usuarios.
# Perfil Operador: módulos de operación.
es_administrador = str(perfil_actual or "").strip().lower() == "administrador"

PAGINAS_ADMIN = {"usuarios"}
if "pagina_actual" not in st.session_state or (
    st.session_state["pagina_actual"] in PAGINAS_ADMIN and not es_administrador
):
    st.session_state["pagina_actual"] = "inicio"
pagina_actual = st.session_state["pagina_actual"]

# ============================================================
# ESTILO GENERAL DE LA APLICACIÓN
# ============================================================
st.markdown("""
<style>
:root{--dark:#6b3416;--dark2:#8e4a1e;--acento:#f59e1b;--amarillo:#ffc629;--cielo:#5bb8e6;--verde:#6a9a24;--rojo:#c62828;--bg:#fbf7ef;--border:#efe2cf;--text:#4a2412;--muted:#7a5c48}
html,body,[data-testid="stAppViewContainer"]{background:var(--bg)!important}
[data-testid="stAppViewContainer"]>.main{background:var(--bg)!important}
.block-container{padding:1.05rem 1.45rem 2rem!important;max-width:100%!important}
section[data-testid="stSidebar"]{background:#fff!important;border-right:3px solid var(--acento)!important;min-width:235px!important;width:235px!important}
section[data-testid="stSidebar"]>div{padding:.8rem .8rem 1rem!important}
.pp-side-brand{padding:0 7px 12px;border-bottom:1px solid #f3e6d3;margin-bottom:10px;text-align:center}
.pp-side-logo{width:150px;max-width:100%;height:auto;filter:drop-shadow(0 6px 10px rgba(74,36,18,.18))}
.pp-side-title{display:inline-block;color:var(--amarillo);background:var(--dark);font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.6px;margin-top:6px;padding:4px 10px;border-radius:4px}
.pp-menu-section{color:#a0663a;font-size:10px;font-weight:800;text-transform:uppercase;margin:16px 7px 6px;letter-spacing:.6px}
.st-key-pp_menu div[data-testid="stButton"]>button,.st-key-pp_menu_admin div[data-testid="stButton"]>button{justify-content:flex-start!important;height:auto!important;min-height:38px!important;padding:9px!important;margin:0!important;border:none!important;border-radius:7px!important;background:transparent!important;color:#5a3a24!important;font-size:12px!important;font-weight:600!important;box-shadow:none!important}
.st-key-pp_menu div[data-testid="stButton"]>button:hover,.st-key-pp_menu_admin div[data-testid="stButton"]>button:hover{background:#fff3df!important}
.st-key-pp_menu div[data-testid="stButton"]>button[kind="primary"],.st-key-pp_menu_admin div[data-testid="stButton"]>button[kind="primary"]{color:#fff!important;background:linear-gradient(90deg,#6b3416,#8e4a1e)!important;box-shadow:inset 4px 0 0 var(--amarillo),0 3px 10px rgba(107,52,22,.18)!important}
.st-key-pp_menu div[data-testid="stButton"]>button>div,.st-key-pp_menu_admin div[data-testid="stButton"]>button>div{justify-content:flex-start!important;width:100%!important}
.st-key-pp_menu div[data-testid="stButton"]>button p,.st-key-pp_menu_admin div[data-testid="stButton"]>button p{font-size:12px!important;font-weight:600!important;text-align:left!important}
.st-key-pp_menu,.st-key-pp_menu_admin{gap:3px!important}
.pp-topbar{background:#fff;border:1px solid #f1d6a8;border-radius:8px;min-height:64px;padding:9px 16px;display:flex;align-items:center;justify-content:space-between;box-shadow:inset 0 4px 0 var(--acento);margin-bottom:12px}
.pp-top-title{color:var(--dark);font-size:18px;font-weight:800}.pp-top-subtitle{color:var(--muted);font-size:10px;margin-top:2px}.pp-user-pill{background:#fff6e2;border:1px solid #f5d79a;color:var(--dark);border-radius:20px;padding:7px 12px;font-size:10px;font-weight:700}.pp-top-actions{display:flex;align-items:center;gap:10px}.pp-logout{width:36px;height:36px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;background:linear-gradient(160deg,#C3C5C6,#403833);box-shadow:0 2px 6px rgba(64,56,51,.3);transition:transform .15s,box-shadow .15s;text-decoration:none!important}.pp-logout:hover{transform:scale(1.08);box-shadow:0 3px 10px rgba(64,56,51,.4)}
.pp-section-title{color:var(--dark);font-size:15px;font-weight:800;margin:2px 0 5px}.pp-section-caption{color:var(--muted);font-size:11px;margin-bottom:8px}
div[data-testid="stVerticalBlockBorderWrapper"]{border-color:var(--border)!important;border-radius:8px!important;background:#fff!important}
div[data-testid="stTextInput"] input,div[data-testid="stTextArea"] textarea,div[data-baseweb="select"]>div{border-radius:6px!important}
button[kind="primary"]{background:var(--dark)!important;border-color:var(--dark)!important;border-radius:6px!important;font-weight:700!important;color:#fff!important}button[kind="primary"]:hover{background:#4a2412!important;border-color:#4a2412!important}
[data-testid="stMetric"]{background:#fff;border:1px solid var(--border);border-left:4px solid var(--acento);border-radius:7px;padding:9px 11px}[data-testid="stMetricLabel"]{color:var(--muted)!important}[data-testid="stMetricValue"]{color:var(--dark)!important;font-size:1.45rem!important}
div[data-testid="stAlert"]{border-radius:7px!important}
.stTabs [data-baseweb="tab"]{font-weight:700}.stTabs [aria-selected="true"]{color:var(--dark)!important}.stTabs [data-baseweb="tab-highlight"]{background:var(--acento)!important}
.pp-ficha{display:grid;gap:12px 22px;background:#fff;border:1px solid var(--border);border-radius:8px;padding:14px 16px;margin:6px 0;box-shadow:0 2px 7px rgba(74,36,18,.04)}
.pp-ficha-label{color:#a0663a;font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.4px}
.pp-ficha-valor{color:var(--text);font-size:13px;margin-top:3px;line-height:1.35;word-break:break-word;font-weight:600}
.pp-chip{display:inline-block;font-size:12px;font-weight:700;padding:6px 12px;border-radius:99px;background:#e6f4fc;color:#2a7aa8}
.pp-chip.ok{background:#edf5dc;color:#4f7a16}
hr{margin:8px 0!important;border-color:#f1e4d0!important}
@media(max-width:900px){.block-container{padding:.7rem .75rem 1.5rem!important}section[data-testid="stSidebar"]{min-width:200px!important;width:200px!important}.pp-topbar{min-height:58px}}
</style>
""", unsafe_allow_html=True)

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown(
        f'<div class="pp-side-brand"><img class="pp-side-logo" src="data:image/png;base64,{logo_base64()}" alt="Pony Parque">'
        '<div class="pp-side-title">Sistema de gestión</div></div>',
        unsafe_allow_html=True
    )

    def mostrar_menu(clave_menu, opciones_menu):
        with st.container(key=clave_menu):
            for clave_pagina, etiqueta in opciones_menu:
                if st.button(
                    etiqueta,
                    key=f"menu_{clave_pagina}",
                    type="primary" if pagina_actual == clave_pagina else "secondary",
                    width="stretch"
                ):
                    st.session_state["pagina_actual"] = clave_pagina
                    st.rerun()

    # Cada módulo nuevo se agrega a este menú y a TITULOS_PAGINA.
    st.markdown('<div class="pp-menu-section">General</div>', unsafe_allow_html=True)
    mostrar_menu("pp_menu", [
        ("inicio", "🏠  Inicio"),
        ("mi_cuenta", "🔑  Mi cuenta"),
    ])

    if es_administrador:
        st.markdown('<div class="pp-menu-section">Administración</div>', unsafe_allow_html=True)
        mostrar_menu("pp_menu_admin", [("usuarios", "👥  Usuarios")])

# ============================================================
# ENCABEZADO INTERNO
# ============================================================
TITULOS_PAGINA = {
    "inicio": "Inicio",
    "mi_cuenta": "Mi Cuenta",
    "usuarios": "Usuarios",
}

st.markdown(f"""
<div class="pp-topbar"><div><div class="pp-top-title">{TITULOS_PAGINA.get(pagina_actual, 'Inicio')}</div>
<div class="pp-top-subtitle">Pony Parque · Hotel Mesa de los Santos</div></div>
<div class="pp-top-actions"><div class="pp-user-pill">👤 {html.escape(nombre_actual or usuario_actual)} · Usuario: {usuario_actual} · Perfil: {perfil_actual or 'Sin perfil'}</div>
<a class="pp-logout" href="?logout=1" target="_self" title="Cerrar sesión" aria-label="Cerrar sesión"><svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h3a1 1 0 0 1 1 1v3M18 16v3a1 1 0 0 1-1 1h-3"/><path d="M5 4.5 11 3a1 1 0 0 1 1.2 1v16a1 1 0 0 1-1.2 1L5 19.5z" fill="#fff"/><path d="M14.5 12H22M19 9l3 3-3 3"/></svg></a></div></div>
""", unsafe_allow_html=True)

# ============================================================
# PÁGINAS
# ============================================================
hoy = datetime.now(ZONA_HORARIA).date()

try:
    if pagina_actual == "usuarios" and es_administrador:
        mostrar_modulo_usuarios(usuario_actual)
    elif pagina_actual == "mi_cuenta":
        mostrar_mi_cuenta(usuario_actual)
    else:
        mostrar_inicio(nombre_actual, usuario_actual, perfil_actual, hoy)
except Exception as e:
    st.error(f"❌ Ocurrió un error al cargar la página: {e}")
