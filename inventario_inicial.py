"""Inventario inicial: cuántas manillas recibe cada taquilla al abrir el día.

Por cada fecha y taquilla se carga la cantidad inicial de las manillas que tiene
asignadas. Los cálculos de vendidas y final se harán en los módulos de ventas e
inventario.
"""

import pandas as pd
import psycopg
import streamlit as st

from database import Database
from usuarios import seccion


def _consultar(sql, parametros=(), columnas=()):
    db = Database()
    try:
        db.conectar()
        db.execute(sql, parametros)
        return pd.DataFrame(db.fetchall(), columns=list(columnas))
    finally:
        db.cerrar()


@st.cache_data(ttl=60, show_spinner=False)
def obtener_taquillas_activas():
    return _consultar(
        'SELECT "ID_TAQUILLA", "NOMBRE" FROM public."TAQUILLAS" WHERE "ACTIVO" ORDER BY "ID_TAQUILLA"',
        columnas=("ID", "NOMBRE"),
    )


@st.cache_data(ttl=60, show_spinner=False)
def obtener_resumen(fecha):
    """Total cargado por taquilla en la fecha (las que no aparecen están pendientes)."""
    return _consultar(
        '''SELECT "ID_TAQUILLA", SUM("CANTIDAD"), MAX("USUARIO_ACTUALIZA")
           FROM public."INVENTARIO_INICIAL" WHERE "FECHA" = %s GROUP BY "ID_TAQUILLA"''',
        (fecha,), ("ID", "TOTAL", "USUARIO"),
    )


@st.cache_data(ttl=60, show_spinner=False)
def obtener_planilla(fecha, id_taquilla):
    """Manillas de la taquilla con su cantidad inicial de la fecha.

    Incluye las manillas activas asignadas y, para no perder lo ya cargado, las
    que tengan cantidad en esa fecha aunque ya no estén asignadas o activas."""
    return _consultar(
        '''SELECT m."ID_MANILLA",
                  m."NOMBRE" || CASE WHEN m."ACTIVO" THEN '' ELSE ' (inactiva)' END,
                  i."CANTIDAD"
           FROM public."MANILLAS" m
           LEFT JOIN public."TAQUILLAS_MANILLAS" a
                  ON a."ID_MANILLA" = m."ID_MANILLA" AND a."ID_TAQUILLA" = %(t)s
           LEFT JOIN public."INVENTARIO_INICIAL" i
                  ON i."ID_MANILLA" = m."ID_MANILLA" AND i."ID_TAQUILLA" = %(t)s AND i."FECHA" = %(f)s
           WHERE (a."ID_MANILLA" IS NOT NULL AND m."ACTIVO") OR i."CANTIDAD" IS NOT NULL
           ORDER BY m."ID_MANILLA"''',
        {"t": id_taquilla, "f": fecha}, ("ID", "CONCEPTO", "INICIAL"),
    )


def _guardar(fecha, id_taquilla, planilla, usuario_actual):
    db = Database()
    try:
        db.conectar()
        for _, fila in planilla.iterrows():
            if pd.isna(fila["INICIAL"]):
                db.execute(
                    'DELETE FROM public."INVENTARIO_INICIAL" WHERE "FECHA"=%s AND "ID_TAQUILLA"=%s AND "ID_MANILLA"=%s',
                    (fecha, id_taquilla, int(fila["ID"])),
                )
            else:
                db.execute(
                    '''INSERT INTO public."INVENTARIO_INICIAL"
                           ("FECHA","ID_TAQUILLA","ID_MANILLA","CANTIDAD","USUARIO_ACTUALIZA")
                       VALUES (%s,%s,%s,%s,%s)
                       ON CONFLICT ("FECHA","ID_TAQUILLA","ID_MANILLA") DO UPDATE
                       SET "CANTIDAD" = EXCLUDED."CANTIDAD",
                           "USUARIO_ACTUALIZA" = EXCLUDED."USUARIO_ACTUALIZA",
                           "FECHA_ACTUALIZA" = now()''',
                    (fecha, id_taquilla, int(fila["ID"]), int(fila["INICIAL"]), usuario_actual),
                )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.cerrar()


def mostrar_modulo_inventario_inicial(usuario_actual, es_administrador, hoy):

    mensaje = st.session_state.pop("mensaje_inventario", None)
    if mensaje:
        getattr(st, mensaje[0])(mensaje[1])

    try:
        taquillas = obtener_taquillas_activas()
    except psycopg.errors.UndefinedTable:
        st.error("❌ Falta crear las tablas: ejecute `sql/schema.sql` en Neon → SQL Editor.")
        return

    if taquillas.empty:
        st.info("No hay taquillas activas. Cree una en el módulo **Taquillas**.")
        return

    col_fecha, col_taquilla = st.columns([1, 2])
    with col_fecha:
        # El operador solo carga el día de hoy; el administrador puede corregir otras fechas.
        fecha = st.date_input("📅 Fecha", value=hoy, format="DD/MM/YYYY",
                              disabled=not es_administrador, key="inv_fecha")
    nombres = dict(zip(taquillas["ID"], taquillas["NOMBRE"]))
    with col_taquilla:
        id_taquilla = st.selectbox("🎟️ Taquilla", list(nombres), format_func=lambda i: f"{i} · {nombres[i]}",
                                   key="inv_taquilla")

    try:
        resumen = obtener_resumen(fecha)
        planilla = obtener_planilla(fecha, id_taquilla)
    except psycopg.errors.UndefinedTable:
        st.error("❌ Falta crear la tabla de inventario inicial: ejecute `sql/schema.sql` en Neon → SQL Editor.")
        return

    # Estado de todas las taquillas en la fecha, con el total de manillas guardado.
    totales = dict(zip(resumen["ID"], resumen["TOTAL"]))
    estado = pd.DataFrame({
        "TAQUILLA": [f"{i} · {n}" for i, n in nombres.items()],
        "ESTADO": ["🟢 Inicializada" if i in totales else "⚪ Pendiente" for i in nombres],
        "TOTAL MANILLAS": [int(totales[i]) if i in totales else None for i in nombres],
    })
    with st.container(border=True):
        seccion(f"📋 Taquillas del {fecha.strftime('%d/%m/%Y')}")
        st.dataframe(estado, hide_index=True, width="stretch", placeholder="—",
                     column_config={"TOTAL MANILLAS": st.column_config.NumberColumn(format="%d")})

    with st.container(border=True):
        seccion(f"🎫 Inventario inicial · {nombres[id_taquilla]}",
                "Digite la cantidad inicial de cada manilla y guarde. Deje en blanco las que no recibe hoy.")

        if planilla.empty:
            st.info("Esta taquilla no tiene manillas asignadas. Asígnelas en **Taquillas** → Asignar manillas.")
            return

        # En un formulario para que digitar seguido no recargue la página en cada celda.
        with st.form(f"form_inventario_{fecha}_{id_taquilla}", border=False):
            editada = st.data_editor(
                planilla,
                hide_index=True,
                width="stretch",
                height=38 + 35 * len(planilla),
                placeholder="",
                column_order=["CONCEPTO", "INICIAL"],
                disabled=["CONCEPTO"],
                column_config={
                    "CONCEPTO": st.column_config.TextColumn("CONCEPTO", width="large"),
                    "INICIAL": st.column_config.NumberColumn("INICIAL", min_value=0, step=1, format="%d"),
                },
                key=f"editor_inventario_{fecha}_{id_taquilla}",
            )
            with st.container(key="acciones_inventario", horizontal=True, horizontal_alignment="right"):
                guardar = st.form_submit_button("", icon=":material/save:", key="btn_ok_inventario",
                                                help="Guardar inventario inicial")

    if guardar:
        try:
            _guardar(fecha, id_taquilla, editada, usuario_actual)
        except Exception as e:
            st.error(f"❌ No fue posible guardar el inventario: {e}")
            return
        st.cache_data.clear()
        total = int(editada["INICIAL"].fillna(0).sum())
        st.session_state["mensaje_inventario"] = (
            "success", f"✅ Inventario inicial de {nombres[id_taquilla]} guardado: {total} manillas."
        )
        st.rerun()
