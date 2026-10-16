"""
Correo de bienvenida a los usuarios nuevos de Ponycash (Pony Parque).

Se usa un servidor SMTP configurado en los secretos de Streamlit:

    [email]
    smtp_host = "smtp.gmail.com"         # o smtp.office365.com, etc.
    smtp_port = 587                      # 587 (STARTTLS) o 465 (SSL)
    usuario = "notificaciones@dominio.com"
    password = "..."
    remitente = "Pony Parque <notificaciones@dominio.com>"   # opcional
    app_url = "https://ponyparque.streamlit.app"             # opcional
"""

import smtplib
import ssl
from datetime import datetime
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, parseaddr
from html import escape
from pathlib import Path

import streamlit as st

from marca import DESCRIPCION_SISTEMA as _DESCRIPCION, NOMBRE_SISTEMA

DESCRIPCION_SISTEMA = f"{_DESCRIPCION} · Pony Parque"
APP_URL_DEFECTO = "https://appponyparque.streamlit.app"
LOGO = Path(__file__).parent / "assets" / "logo_correo_ponycash.png"
CID_LOGO = "logo_ponycash"

# Paleta del logo, la misma de la aplicación.
CAFE_OSCURO = "#4a2412"
CAFE = "#6b3416"
NARANJA = "#f59e1b"
AMARILLO = "#ffc629"
GRIS_TEXTO = "#7a5c48"
FONDO = "#fbf7ef"
BORDE = "#efe2cf"

DESCRIPCION_PERFILES = {
    "ADMINISTRADOR": "Acceso completo, incluida la administración de usuarios.",
    "OPERADOR": "Acceso a los módulos de operación.",
}


def configuracion_correo():
    """Devuelve la sección [email] de los secretos o None si no está configurada."""
    try:
        config = dict(st.secrets["email"])
    except (KeyError, FileNotFoundError):
        return None
    if not all(config.get(c) for c in ("smtp_host", "smtp_port", "usuario", "password")):
        return None
    return config


def _fila(etiqueta, valor):
    return (
        f'<tr><td style="padding:8px 0;border-bottom:1px solid {BORDE};color:{GRIS_TEXTO};'
        f'font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;width:42%;">'
        f'{escape(etiqueta)}</td>'
        f'<td style="padding:8px 0;border-bottom:1px solid {BORDE};color:{CAFE_OSCURO};font-size:14px;">'
        f'{valor}</td></tr>'
    )


def _paso(numero, texto):
    return (
        f'<tr><td style="vertical-align:top;padding:6px 12px 6px 0;">'
        f'<div style="width:26px;height:26px;border-radius:50%;background:{CAFE};color:{AMARILLO};'
        f'font-size:13px;font-weight:700;text-align:center;line-height:26px;">{numero}</div></td>'
        f'<td style="padding:6px 0;color:{CAFE_OSCURO};font-size:14px;line-height:1.5;">{texto}</td></tr>'
    )


def _plantilla(titulo, cuerpo):
    """Estructura del correo: franja de colores, logo, título, cuerpo y pie."""
    anio = datetime.now().year
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:{FONDO};font-family:'Segoe UI',Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{FONDO};padding:24px 12px;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#fff;border-radius:10px;overflow:hidden;border:1px solid {BORDE};">

  <tr><td style="height:6px;background:linear-gradient(90deg,{AMARILLO},{NARANJA},{CAFE});background-color:{NARANJA};font-size:0;line-height:0;">&nbsp;</td></tr>
  <tr><td align="center" style="padding:26px 24px 10px;">
    <img src="cid:{CID_LOGO}" width="220" alt="{NOMBRE_SISTEMA}" style="display:block;border:0;width:220px;height:auto;">
  </td></tr>
  <tr><td align="center" style="padding:0 24px 22px;">
    <div style="color:{CAFE};font-size:22px;font-weight:800;">{titulo}</div>
    <div style="color:{GRIS_TEXTO};font-size:12px;margin-top:4px;">{DESCRIPCION_SISTEMA}</div>
  </td></tr>

{cuerpo}  <tr><td style="background:{CAFE};padding:16px 24px;" align="center">
    <div style="color:{AMARILLO};font-size:13px;font-weight:700;">{NOMBRE_SISTEMA}</div>
    <div style="color:#f3dcc3;font-size:11px;margin-top:2px;">{DESCRIPCION_SISTEMA}</div>
    <div style="color:#d8b998;font-size:10px;margin-top:8px;">Este es un mensaje automático, por favor no responda a este correo. © {anio} {NOMBRE_SISTEMA}</div>
  </td></tr>
  <tr><td style="height:4px;background:{NARANJA};font-size:0;line-height:0;">&nbsp;</td></tr>

</table>
</td></tr></table>
</body></html>"""


def construir_correo_bienvenida(nombre, usuario, correo, perfil, contrasena, app_url, descripcion_perfil=None):
    """Devuelve (asunto, texto_plano, html) del correo de bienvenida."""
    descripcion_perfil = descripcion_perfil or DESCRIPCION_PERFILES.get((perfil or "").upper(), "")
    anio = datetime.now().year

    asunto = f"Bienvenido a {NOMBRE_SISTEMA} · Datos de acceso de su cuenta"

    texto = f"""Hola {nombre},

Se ha creado su cuenta en el sistema de gestión de {NOMBRE_SISTEMA}.

DATOS DE SU CUENTA
- Dirección de acceso: {app_url}
- Nombre: {nombre}
- Usuario: {usuario}
- Correo de acceso: {correo}
- Contraseña temporal: {contrasena}
- Perfil: {perfil}{f" ({descripcion_perfil})" if descripcion_perfil else ""}

PROCEDIMIENTO DE ACCESO
1. Ingrese a {app_url}
2. Escriba su correo de acceso y la contraseña temporal, y pulse "Ingresar".
3. Cambie su contraseña en "Mi cuenta", en el menú lateral.
4. Al terminar, cierre la sesión con el botón circular de la parte superior derecha.

RECOMENDACIONES
- No comparta su usuario ni su contraseña.
- Si no puede ingresar, comuníquese con el administrador del sistema.

{NOMBRE_SISTEMA} · {DESCRIPCION_SISTEMA}
Este es un mensaje automático, por favor no responda a este correo.
© {anio} {NOMBRE_SISTEMA}
"""

    filas = "".join([
        _fila("Dirección de acceso",
              f'<a href="{escape(app_url)}" style="color:{CAFE};font-weight:700;">{escape(app_url)}</a>'),
        _fila("Nombre", escape(nombre)),
        _fila("Usuario", f"<strong>{escape(usuario)}</strong>"),
        _fila("Correo de acceso", escape(correo)),
        _fila("Contraseña temporal",
              f'<span style="font-family:Consolas,monospace;background:{FONDO};padding:3px 8px;'
              f'border-radius:4px;border:1px solid {BORDE};">{escape(contrasena)}</span>'),
        _fila("Perfil",
              f"<strong>{escape(perfil)}</strong>"
              + (f'<br><span style="color:{GRIS_TEXTO};font-size:12px;">{escape(descripcion_perfil)}</span>'
                 if descripcion_perfil else "")),
    ])

    pasos = "".join([
        _paso(1, f'Ingrese a <a href="{escape(app_url)}" style="color:{CAFE};font-weight:700;">'
                 f'{escape(app_url)}</a>.'),
        _paso(2, "Escriba su <strong>correo de acceso</strong> y la <strong>contraseña temporal</strong>, "
                 "y pulse <strong>Ingresar</strong>."),
        _paso(3, "Cambie su contraseña en <strong>Mi cuenta</strong>, en el menú lateral."),
        _paso(4, "Al terminar, cierre la sesión con el botón circular de la parte superior derecha."),
    ])

    cuerpo = f"""  <tr><td style="padding:0 32px;">
    <p style="color:{CAFE_OSCURO};font-size:15px;line-height:1.6;margin:0 0 6px;">Hola <strong>{escape(nombre)}</strong>,</p>
    <p style="color:{CAFE_OSCURO};font-size:14px;line-height:1.6;margin:0 0 18px;">
      Se ha creado su cuenta en el sistema de gestión de <strong>{NOMBRE_SISTEMA}</strong>. A continuación
      encontrará la información necesaria para ingresar.</p>
  </td></tr>

  <tr><td style="padding:0 32px 8px;">
    <div style="border:1px solid #f1d6a8;border-radius:8px;box-shadow:inset 0 3px 0 {NARANJA};padding:16px 18px 8px;">
      <div style="color:{CAFE};font-size:15px;font-weight:800;margin-bottom:6px;">Datos de su cuenta</div>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{filas}</table>
    </div>
  </td></tr>

  <tr><td style="padding:18px 32px 4px;">
    <div style="color:{CAFE};font-size:15px;font-weight:800;margin-bottom:6px;">Procedimiento de acceso</div>
    <table role="presentation" cellpadding="0" cellspacing="0">{pasos}</table>
  </td></tr>

  <tr><td align="center" style="padding:16px 32px 8px;">
    <a href="{escape(app_url)}" style="display:inline-block;background:{CAFE};background:linear-gradient(90deg,{CAFE},#c8681a);
       color:#fff;text-decoration:none;font-size:14px;font-weight:700;padding:12px 34px;border-radius:24px;">Ingresar a {NOMBRE_SISTEMA}</a>
  </td></tr>

  <tr><td style="padding:16px 32px 24px;">
    <div style="background:#fff8e1;border:1px solid {AMARILLO};border-radius:8px;padding:12px 16px;color:#5a4300;font-size:13px;line-height:1.55;">
      <strong>Recomendaciones de seguridad</strong><br>
      • No comparta su usuario ni su contraseña.<br>
      • Si no puede ingresar, comuníquese con el administrador del sistema.
    </div>
  </td></tr>

"""
    return asunto, texto, _plantilla(f"¡Bienvenido a {NOMBRE_SISTEMA}!", cuerpo)


def enviar_correo_bienvenida(nombre, usuario, correo, perfil, contrasena, descripcion_perfil=None):
    """Envía el correo de bienvenida. Lanza una excepción si no es posible."""
    config = configuracion_correo()
    if config is None:
        raise RuntimeError("Falta configurar la sección [email] en los secretos de la aplicación.")

    app_url = config.get("app_url") or APP_URL_DEFECTO
    asunto, texto, html = construir_correo_bienvenida(
        nombre, usuario, correo, perfil, contrasena, app_url, descripcion_perfil
    )

    with _servidor_smtp(config) as servidor:
        servidor.send_message(_armar_mensaje(config, correo, asunto, texto, html))


def _armar_mensaje(config, destinatario, asunto, texto, html):
    """Mensaje MIME con versión de texto, HTML y el logo incrustado."""
    remitente = config.get("remitente") or formataddr((NOMBRE_SISTEMA, config["usuario"]))
    nombre_rem, correo_rem = parseaddr(remitente)

    mensaje = MIMEMultipart("related")
    mensaje["Subject"] = asunto
    mensaje["From"] = formataddr((nombre_rem or NOMBRE_SISTEMA, correo_rem or config["usuario"]))
    mensaje["To"] = destinatario

    alternativa = MIMEMultipart("alternative")
    alternativa.attach(MIMEText(texto, "plain", "utf-8"))
    alternativa.attach(MIMEText(html, "html", "utf-8"))
    mensaje.attach(alternativa)

    if LOGO.exists():
        logo = MIMEImage(LOGO.read_bytes(), _subtype="png")
        logo.add_header("Content-ID", f"<{CID_LOGO}>")
        logo.add_header("Content-Disposition", "inline", filename=LOGO.name)
        mensaje.attach(logo)

    return mensaje


def _servidor_smtp(config):
    """Conexión SMTP autenticada (465 = SSL; otro puerto = STARTTLS)."""
    host = config["smtp_host"]
    puerto = int(config["smtp_port"])
    contexto = ssl.create_default_context()

    if puerto == 465:
        servidor = smtplib.SMTP_SSL(host, puerto, context=contexto, timeout=30)
    else:
        servidor = smtplib.SMTP(host, puerto, timeout=30)
        servidor.starttls(context=contexto)
    servidor.login(config["usuario"], config["password"])
    return servidor
