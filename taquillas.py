"""
Módulo de taquillas (solo Administrador): crear, editar, activar o
desactivar y eliminar las taquillas del parque. Funciona igual que Usuarios.
"""

from html import escape

import pandas as pd
import psycopg
import streamlit as st

from usuarios import ejecutar, encabezado_ventana, ficha, seccion
from database import Database


# ============================================================
# CONSULTAS
# ============================================================
@st.cache_data(ttl=60, show_spinner=False)
def obtener_taquillas():
    db = Database()
    try:
        db.conectar()
        db.execute('''
            SELECT "ID_TAQUILLA", "NOMBRE", "UBICACION", "ACTIVO"
            FROM public."TAQUILLAS"
            ORDER BY "ID_TAQUILLA"
        ''')
        return pd.DataFrame(db.fetchall(), columns=["ID_TAQUILLA", "NOMBRE", "UBICACION", "ACTIVO"])
    finally:
        db.cerrar()


def notificar(mensaje, tipo="success"):
    """Guarda un mensaje para mostrarlo después del st.rerun() y descarta los
    datos en caché para que la tabla refleje el cambio."""
    st.cache_data.clear()
    st.session_state["mensaje_taquillas"] = (tipo, mensaje)
    st.rerun()


# ============================================================
# VENTANAS (OVERLAY)
# ============================================================
@st.dialog(" ", width="large")
def ventana_crear_taquilla(usuario_actual):

    encabezado_ventana("Nueva Taquilla")

    with st.form("form_crear_taquilla"):
        nombre = st.text_input("Nombre", placeholder="Ej: Taquilla principal",
                               help="El ID de la taquilla lo genera el sistema al crearla.")
        ubicacion = st.text_input("Ubicación (opcional)", placeholder="Ej: Entrada del parque")

        with st.container(key="acciones_dlg_crear_taq", horizontal=True,
                          horizontal_alignment="right", gap="small"):
            crear = st.form_submit_button("", icon=":material/add_business:", key="btn_ok_crear_taq",
                                          help="Crear taquilla")

    if not crear:
        return

    nombre = (nombre or "").strip()
    ubicacion = (ubicacion or "").strip() or None

    if not nombre:
        st.error("❌ Debe ingresar el nombre.")
        return

    db = Database()
    try:
        db.conectar()
        db.execute(
            '''INSERT INTO public."TAQUILLAS" ("NOMBRE","UBICACION","USUARIO_ACTUALIZA")
               VALUES (%s,%s,%s)
               RETURNING "ID_TAQUILLA"''',
            (nombre, ubicacion, usuario_actual)
        )
        id_taquilla = db.fetchone()[0]
        db.commit()
    except Exception as e:
        db.rollback()
        st.error(f"❌ No fue posible crear la taquilla: {e}")
        return
    finally:
        db.cerrar()

    notificar(f"✅ Taquilla {id_taquilla} · {nombre} creada correctamente.")


@st.dialog(" ", width="large")
def ventana_editar_taquilla(fila, usuario_actual):

    encabezado_ventana("Editar Taquilla")

    ficha([("ID", fila["ID_TAQUILLA"]), ("Nombre", fila["NOMBRE"]),
           ("Estado", "Activa" if fila["ACTIVO"] else "Inactiva")])

    with st.form(f"form_editar_taq_{fila['ID_TAQUILLA']}"):
        nombre = st.text_input("Nombre", value=fila["NOMBRE"] or "")
        ubicacion = st.text_input("Ubicación (opcional)", value=fila["UBICACION"] or "")

        with st.container(key="acciones_dlg_editar_taq", horizontal=True,
                          horizontal_alignment="right", gap="small"):
            guardar = st.form_submit_button("", icon=":material/save:", key="btn_info_editar_taq",
                                            help="Guardar cambios")

    if not guardar:
        return

    nombre = (nombre or "").strip()
    ubicacion = (ubicacion or "").strip() or None
    if not nombre:
        st.error("❌ Debe ingresar el nombre.")
        return

    try:
        ejecutar(
            '''UPDATE public."TAQUILLAS"
               SET "NOMBRE" = %s, "UBICACION" = %s, "USUARIO_ACTUALIZA" = %s, "FECHA_ACTUALIZA" = now()
               WHERE "ID_TAQUILLA" = %s''',
            (nombre, ubicacion, usuario_actual, fila["ID_TAQUILLA"])
        )
    except Exception as e:
        st.error(f"❌ No fue posible guardar los cambios: {e}")
        return

    notificar(f"✅ Taquilla {fila['ID_TAQUILLA']} actualizada correctamente.")


@st.dialog(" ", width="large")
def ventana_estado_taquilla(fila, usuario_actual):

    encabezado_ventana("Cambiar Estado de la Taquilla")

    activar = not fila["ACTIVO"]
    accion = "activar" if activar else "desactivar"

    ficha([("ID", fila["ID_TAQUILLA"]), ("Nombre", fila["NOMBRE"]), ("Ubicación", fila["UBICACION"])])
    seccion(
        f"¿Está seguro que desea {accion} esta taquilla?",
        None if activar else "Una taquilla desactivada no se podrá usar en la operación. Sus datos se conservan."
    )

    with st.form(f"form_estado_taq_{fila['ID_TAQUILLA']}"):
        with st.container(key="acciones_dlg_estado_taq", horizontal=True,
                          horizontal_alignment="right", gap="small"):
            cancelar = st.form_submit_button("", icon=":material/close:", key="btn_cancel_estado_taq", help="Cancelar")
            confirmar = st.form_submit_button("", icon=":material/check:", key="btn_warn_estado_taq",
                                              help=f"Sí, {accion}")

    if cancelar:
        st.rerun()
    if not confirmar:
        return

    try:
        ejecutar(
            '''UPDATE public."TAQUILLAS"
               SET "ACTIVO" = %s, "USUARIO_ACTUALIZA" = %s, "FECHA_ACTUALIZA" = now()
               WHERE "ID_TAQUILLA" = %s''',
            (activar, usuario_actual, fila["ID_TAQUILLA"])
        )
    except Exception as e:
        st.error(f"❌ No fue posible {accion} la taquilla: {e}")
        return

    estado = "activada" if activar else "desactivada"
    notificar(f"✅ Taquilla {fila['ID_TAQUILLA']} {estado} correctamente.")


@st.dialog(" ", width="large")
def ventana_eliminar_taquilla(fila):

    encabezado_ventana("Eliminar Taquilla")

    ficha([("ID", fila["ID_TAQUILLA"]), ("Nombre", fila["NOMBRE"]), ("Ubicación", fila["UBICACION"])])
    seccion(
        "¿Está seguro que desea eliminar esta taquilla?",
        "Esta acción no se puede deshacer. Si solo quiere dejar de usarla, desactívela."
    )

    with st.form(f"form_eliminar_taq_{fila['ID_TAQUILLA']}"):
        with st.container(key="acciones_dlg_eliminar_taq", horizontal=True,
                          horizontal_alignment="right", gap="small"):
            cancelar = st.form_submit_button("", icon=":material/close:", key="btn_cancel_eliminar_taq", help="Cancelar")
            confirmar = st.form_submit_button("", icon=":material/delete:", key="btn_danger_eliminar_taq",
                                              help="Sí, eliminar")

    if cancelar:
        st.rerun()
    if not confirmar:
        return

    try:
        ejecutar('DELETE FROM public."TAQUILLAS" WHERE "ID_TAQUILLA" = %s', (fila["ID_TAQUILLA"],))
    except psycopg.errors.ForeignKeyViolation:
        st.error("❌ La taquilla ya tiene movimientos registrados y no se puede eliminar. Puede desactivarla.")
        return
    except Exception as e:
        st.error(f"❌ No fue posible eliminar la taquilla: {e}")
        return

    notificar(f"✅ Taquilla {fila['ID_TAQUILLA']} eliminada correctamente.")


# ============================================================
# PÁGINA PRINCIPAL DEL MÓDULO
# ============================================================
def mostrar_modulo_taquillas(usuario_actual):

    mensaje = st.session_state.pop("mensaje_taquillas", None)
    if mensaje:
        tipo, texto = mensaje
        (st.warning if tipo == "warning" else st.success)(texto)

    try:
        taquillas = obtener_taquillas()
    except psycopg.errors.UndefinedTable:
        st.error("❌ Falta crear la tabla de taquillas: ejecute `sql/schema.sql` en Neon → SQL Editor.")
        return
    except Exception as e:
        st.error("❌ No fue posible consultar las taquillas.")
        st.exception(e)
        return

    texto = st.text_input(
        "🔎 Buscar taquilla",
        placeholder="Digite ID, nombre o ubicación..."
    )

    if texto and not taquillas.empty:
        texto_busqueda = texto.lower()
        mascara = taquillas.apply(
            lambda f: texto_busqueda in " ".join(
                str(v) for v in [f["ID_TAQUILLA"], f["NOMBRE"], f["UBICACION"] or ""]
            ).lower(),
            axis=1
        )
        taquillas = taquillas[mascara]

    taquillas = taquillas.reset_index(drop=True)

    # Fila seleccionada en la cuadrícula (se dibuja más abajo).
    seleccion = st.session_state.get("tabla_taquillas")
    filas = seleccion.selection.rows if seleccion else []
    fila = (
        taquillas.iloc[filas[0]]
        if filas and filas[0] < len(taquillas)
        else None
    )
    activo = bool(fila["ACTIVO"]) if fila is not None else None

    c_sel, c_acciones = st.columns([3, 1.4], vertical_alignment="center")

    with c_sel:
        if fila is not None:
            st.markdown(f"**Taquilla seleccionada:** {fila['ID_TAQUILLA']} · {escape(fila['NOMBRE'])}")
        else:
            st.caption("☝️ Seleccione una taquilla en la tabla para administrarla.")

    with c_acciones:
        with st.container(key="acciones_taquillas", horizontal=True,
                          horizontal_alignment="right", gap="small"):
            if st.button("", icon=":material/add_business:", key="btn_taq_nuevo", help="Nueva taquilla"):
                ventana_crear_taquilla(usuario_actual)

            if st.button("", icon=":material/edit:", key="btn_taq_editar",
                         disabled=fila is None, help="Editar taquilla"):
                ventana_editar_taquilla(fila, usuario_actual)

            if st.button("", icon=":material/toggle_off:" if activo is not False else ":material/toggle_on:",
                         key="btn_taq_estado",
                         disabled=fila is None,
                         help="Activar taquilla" if activo is False else "Desactivar taquilla"):
                ventana_estado_taquilla(fila, usuario_actual)

            if st.button("", icon=":material/delete:", key="btn_taq_eliminar",
                         disabled=fila is None, help="Eliminar taquilla"):
                ventana_eliminar_taquilla(fila)

    if taquillas.empty:
        st.info("ℹ️ No hay taquillas registradas." if not texto
                else "ℹ️ No existen taquillas que coincidan con el criterio de búsqueda.")
        return

    tabla = pd.DataFrame({
        "ID": taquillas["ID_TAQUILLA"],
        "NOMBRE": taquillas["NOMBRE"],
        "UBICACIÓN": taquillas["UBICACION"].fillna("—"),
        "ESTADO": taquillas["ACTIVO"].map(lambda v: "🟢 Activa" if v else "🔴 Inactiva"),
    })

    st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)

    st.dataframe(
        tabla,
        key="tabla_taquillas",
        on_select="rerun",
        selection_mode="single-row",
        hide_index=True,
        width="stretch",
        height=min(38 + 35 * len(tabla), 640),
        column_config={
            "ID": st.column_config.NumberColumn("ID", width="small", format="%d"),
            "NOMBRE": st.column_config.TextColumn("NOMBRE", width="medium"),
            "UBICACIÓN": st.column_config.TextColumn("UBICACIÓN", width="medium"),
            "ESTADO": st.column_config.TextColumn("ESTADO", width="small"),
        },
    )
