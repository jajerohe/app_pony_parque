"""
Lectura y escritura en PostgreSQL (Neon).

Cada módulo nuevo agrega aquí sus consultas, en una sección propia.
"""

import streamlit as st

from database import Database

# Tiempo máximo (segundos) que se reutilizan los datos consultados entre
# interacciones. Cualquier cambio guardado limpia la caché de inmediato.
TTL_CACHE = 60


def _ejecutar(sql, parametros):
    """Ejecuta una escritura en su propia transacción y limpia la caché."""
    db = Database()
    try:
        db.conectar()
        db.execute(sql, parametros)
        filas = db.cursor.rowcount
        db.commit()
        return filas
    except Exception:
        db.rollback()
        raise
    finally:
        db.cerrar()
        st.cache_data.clear()


# ============================================================
# USUARIOS
# ============================================================
@st.cache_data(ttl=TTL_CACHE, show_spinner=False)
def obtener_perfiles():
    db = Database()
    try:
        db.conectar()
        db.execute('SELECT "PERFIL" FROM public."PERFILES" ORDER BY "PERFIL"')
        return [fila[0] for fila in db.fetchall()]
    finally:
        db.cerrar()


@st.cache_data(ttl=TTL_CACHE, show_spinner=False)
def obtener_usuarios():
    db = Database()
    try:
        db.conectar()
        db.execute(
            """
            SELECT "USUARIO", "NOMBRE", "CORREO", "PERFIL", "ACTIVO", "FECHA_CREACION"
            FROM public."USUARIOS"
            ORDER BY "ACTIVO" DESC, "NOMBRE"
            """
        )
        columnas = ["USUARIO", "NOMBRE", "CORREO", "PERFIL", "ACTIVO", "FECHA_CREACION"]
        return [dict(zip(columnas, fila)) for fila in db.fetchall()]
    finally:
        db.cerrar()


def crear_usuario(usuario, nombre, correo, clave, perfil, usuario_crea):
    _ejecutar(
        """
        INSERT INTO public."USUARIOS" ("USUARIO", "NOMBRE", "CORREO", "CLAVE", "PERFIL", "USUARIO_ACTUALIZA")
        VALUES (%s, %s, %s, crypt(%s, gen_salt('bf')), %s, %s)
        """,
        (usuario, nombre, correo, clave, perfil, usuario_crea)
    )


def actualizar_usuario(usuario, nombre, correo, perfil, activo, usuario_actualiza):
    _ejecutar(
        """
        UPDATE public."USUARIOS"
        SET "NOMBRE" = %s, "CORREO" = %s, "PERFIL" = %s, "ACTIVO" = %s,
            "USUARIO_ACTUALIZA" = %s, "FECHA_ACTUALIZA" = now()
        WHERE "USUARIO" = %s
        """,
        (nombre, correo, perfil, activo, usuario_actualiza, usuario)
    )


def cambiar_clave(usuario, clave_nueva, usuario_actualiza):
    _ejecutar(
        """
        UPDATE public."USUARIOS"
        SET "CLAVE" = crypt(%s, gen_salt('bf')), "USUARIO_ACTUALIZA" = %s, "FECHA_ACTUALIZA" = now()
        WHERE "USUARIO" = %s
        """,
        (clave_nueva, usuario_actualiza, usuario)
    )


def cambiar_mi_clave(usuario, clave_actual, clave_nueva):
    """Cambia la contraseña solo si la actual es correcta. Devuelve True si cambió."""
    return _ejecutar(
        """
        UPDATE public."USUARIOS"
        SET "CLAVE" = crypt(%s, gen_salt('bf')), "USUARIO_ACTUALIZA" = %s, "FECHA_ACTUALIZA" = now()
        WHERE "USUARIO" = %s AND "CLAVE" = crypt(%s, "CLAVE")
        """,
        (clave_nueva, usuario, usuario, clave_actual)
    ) == 1
