"""
Módulo de usuarios: el administrador crea usuarios, les asigna perfil, los
activa o desactiva y les cambia la contraseña. Cualquier usuario puede cambiar
su propia contraseña en Mi cuenta.
"""

import re

import pandas as pd
import psycopg
import streamlit as st

from datos import (actualizar_usuario, cambiar_clave, cambiar_mi_clave, crear_usuario, obtener_perfiles,
                   obtener_usuarios)
from ui import mostrar_mensaje, seccion

LARGO_MINIMO_CLAVE = 8
PATRON_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PATRON_USUARIO = re.compile(r"^[A-Z0-9_.-]{3,30}$")


def _error_clave(clave, confirmacion):
    if len(clave) < LARGO_MINIMO_CLAVE:
        return f"La contraseña debe tener al menos {LARGO_MINIMO_CLAVE} caracteres."
    if clave != confirmacion:
        return "Las contraseñas no coinciden."
    return None


def _error_datos(nombre, correo):
    if not nombre.strip():
        return "Escriba el nombre."
    if not PATRON_CORREO.match(correo.strip()):
        return "Escriba un correo válido."
    return None


def _guardar(accion, mensaje_ok):
    try:
        accion()
        st.session_state["mensaje_usuarios"] = ("success", mensaje_ok)
        st.rerun()
    except psycopg.errors.UniqueViolation:
        st.error("❌ Ya existe un usuario con ese código o ese correo.")
    except Exception as e:
        st.error(f"❌ No fue posible guardar: {e}")


def mostrar_modulo_usuarios(usuario_actual):
    mostrar_mensaje("mensaje_usuarios")

    usuarios = obtener_usuarios()
    perfiles = obtener_perfiles()

    with st.container(border=True):
        seccion("👥 Usuarios del sistema", f"{sum(u['ACTIVO'] for u in usuarios)} activos de {len(usuarios)}.")
        st.dataframe(
            pd.DataFrame([
                {
                    "Usuario": u["USUARIO"], "Nombre": u["NOMBRE"], "Correo": u["CORREO"],
                    "Perfil": u["PERFIL"], "Estado": "Activo" if u["ACTIVO"] else "Inactivo",
                    "Creado": u["FECHA_CREACION"].strftime("%d/%m/%Y") if u["FECHA_CREACION"] else "",
                }
                for u in usuarios
            ]),
            hide_index=True,
            width="stretch",
        )

    nuevo, editar = st.tabs(["➕ Nuevo usuario", "✏️ Editar usuario"])

    with nuevo:
        with st.form("form_nuevo_usuario", clear_on_submit=False):
            c1, c2 = st.columns(2)
            codigo = c1.text_input("Usuario", placeholder="Ej. CAJERO1", help="Letras, números, punto o guion.")
            nombre = c2.text_input("Nombre completo")
            correo = c1.text_input("Correo electrónico", help="Con este correo ingresa al sistema.")
            perfil = c2.selectbox("Perfil", perfiles)
            clave = c1.text_input("Contraseña", type="password")
            confirmacion = c2.text_input("Confirmar contraseña", type="password")
            if st.form_submit_button("💾 Crear usuario", type="primary"):
                codigo = codigo.strip().upper()
                error = (
                    None if PATRON_USUARIO.match(codigo)
                    else "El usuario debe tener entre 3 y 30 letras, números, punto o guion, sin espacios."
                ) or _error_datos(nombre, correo) or _error_clave(clave, confirmacion)
                if error:
                    st.error(f"❌ {error}")
                else:
                    _guardar(
                        lambda: crear_usuario(codigo, nombre.strip(), correo.strip(), clave, perfil, usuario_actual),
                        f"✅ Usuario {codigo} creado. Ya puede ingresar con {correo.strip()}.",
                    )

    with editar:
        if not usuarios:
            st.info("No hay usuarios para editar.")
            return
        opciones = {f"{u['NOMBRE']} ({u['USUARIO']})": u for u in usuarios}
        elegido = opciones[st.selectbox("Usuario a editar", list(opciones))]
        es_yo = elegido["USUARIO"] == usuario_actual

        with st.form(f"form_editar_{elegido['USUARIO']}"):
            c1, c2 = st.columns(2)
            nombre = c1.text_input("Nombre completo", value=elegido["NOMBRE"])
            correo = c2.text_input("Correo electrónico", value=elegido["CORREO"])
            perfil = c1.selectbox(
                "Perfil", perfiles,
                index=perfiles.index(elegido["PERFIL"]) if elegido["PERFIL"] in perfiles else 0,
                disabled=es_yo, help="No puede cambiar su propio perfil." if es_yo else None,
            )
            activo = c2.toggle(
                "Activo", value=elegido["ACTIVO"], disabled=es_yo,
                help="No puede desactivarse a sí mismo." if es_yo else "Un usuario inactivo no puede ingresar.",
            )
            if st.form_submit_button("💾 Guardar cambios", type="primary"):
                error = _error_datos(nombre, correo)
                if error:
                    st.error(f"❌ {error}")
                else:
                    _guardar(
                        lambda: actualizar_usuario(
                            elegido["USUARIO"], nombre.strip(), correo.strip(),
                            elegido["PERFIL"] if es_yo else perfil, True if es_yo else activo, usuario_actual,
                        ),
                        f"✅ Usuario {elegido['USUARIO']} actualizado.",
                    )

        with st.form(f"form_clave_{elegido['USUARIO']}", clear_on_submit=True):
            seccion("🔑 Asignar nueva contraseña", "Úselo cuando el usuario olvide su contraseña.")
            c1, c2 = st.columns(2)
            clave = c1.text_input("Nueva contraseña", type="password")
            confirmacion = c2.text_input("Confirmar contraseña", type="password")
            if st.form_submit_button("🔑 Cambiar contraseña"):
                error = _error_clave(clave, confirmacion)
                if error:
                    st.error(f"❌ {error}")
                else:
                    _guardar(
                        lambda: cambiar_clave(elegido["USUARIO"], clave, usuario_actual),
                        f"✅ Contraseña de {elegido['USUARIO']} cambiada.",
                    )


def mostrar_mi_cuenta(usuario_actual):
    mostrar_mensaje("mensaje_mi_cuenta")
    with st.container(border=True):
        seccion("🔑 Cambiar mi contraseña", f"Mínimo {LARGO_MINIMO_CLAVE} caracteres.")
        with st.form("form_mi_clave", clear_on_submit=True):
            actual = st.text_input("Contraseña actual", type="password")
            c1, c2 = st.columns(2)
            nueva = c1.text_input("Nueva contraseña", type="password")
            confirmacion = c2.text_input("Confirmar nueva contraseña", type="password")
            if st.form_submit_button("💾 Cambiar contraseña", type="primary"):
                error = _error_clave(nueva, confirmacion)
                if error:
                    st.error(f"❌ {error}")
                    return
                try:
                    if cambiar_mi_clave(usuario_actual, actual, nueva):
                        st.session_state["mensaje_mi_cuenta"] = ("success", "✅ Su contraseña fue cambiada.")
                        st.rerun()
                    else:
                        st.error("❌ La contraseña actual no es correcta.")
                except Exception as e:
                    st.error(f"❌ No fue posible cambiar la contraseña: {e}")
