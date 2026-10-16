"""Cerrar taquillas por día: cuántas manillas le quedan a cada taquilla al cerrar.

Por cada fecha y taquilla se toma el inventario INICIAL registrado en
Inicializar taquillas por día (no se puede modificar aquí), se digita el FINAL
de cada manilla y las VENDIDAS se calculan como INICIAL - FINAL.
"""

import pandas as pd
import psycopg
import streamlit as st

from database import Database
from inventario_inicial import obtener_taquillas_activas
from usuarios import seccion

NOMBRE_INICIALIZAR = "Inicializar taquillas por día"


def _consultar(sql, parametros=(), columnas=()):
    db = Database()
    try:
        db.conectar()
        db.execute(sql, parametros)
        return pd.DataFrame(db.fetchall(), columns=list(columnas))
    finally:
        db.cerrar()


@st.cache_data(ttl=60, show_spinner=False)
def obtener_resumen(fecha):
    """Totales INICIAL y FINAL por taquilla en la fecha."""
    return _consultar(
        '''SELECT COALESCE(i."ID_TAQUILLA", f."ID_TAQUILLA"), SUM(i."CANTIDAD"), SUM(f."CANTIDAD"),
                  COUNT(i."CANTIDAD"), COUNT(f."CANTIDAD")
           FROM public."INVENTARIO_INICIAL" i
           FULL JOIN public."INVENTARIO_FINAL" f
                  ON f."FECHA" = i."FECHA" AND f."ID_TAQUILLA" = i."ID_TAQUILLA" AND f."ID_MANILLA" = i."ID_MANILLA"
           WHERE COALESCE(i."FECHA", f."FECHA") = %s
           GROUP BY 1''',
        (fecha,), ("ID", "INICIAL", "FINAL", "N_INICIAL", "N_FINAL"),
    )


@st.cache_data(ttl=60, show_spinner=False)
def obtener_planilla(fecha, id_taquilla):
    """Manillas con inventario inicial de la taquilla en la fecha, con su final."""
    datos = _consultar(
        '''SELECT m."ID_MANILLA", m."NOMBRE", i."CANTIDAD", f."CANTIDAD"
           FROM public."INVENTARIO_INICIAL" i
           JOIN public."MANILLAS" m ON m."ID_MANILLA" = i."ID_MANILLA"
           LEFT JOIN public."INVENTARIO_FINAL" f
                  ON f."FECHA" = i."FECHA" AND f."ID_TAQUILLA" = i."ID_TAQUILLA" AND f."ID_MANILLA" = i."ID_MANILLA"
           WHERE i."FECHA" = %(f)s AND i."ID_TAQUILLA" = %(t)s
           ORDER BY m."ID_MANILLA"''',
        {"t": id_taquilla, "f": fecha}, ("ID", "CONCEPTO", "INICIAL", "FINAL"),
    )
    datos["INICIAL"] = datos["INICIAL"].astype(int)
    datos["FINAL"] = pd.to_numeric(datos["FINAL"]).astype("Int64")
    return datos


def _guardar(fecha, id_taquilla, planilla, usuario_actual):
    db = Database()
    try:
        db.conectar()
        for _, fila in planilla.iterrows():
            if pd.isna(fila["FINAL"]):
                db.execute(
                    'DELETE FROM public."INVENTARIO_FINAL" WHERE "FECHA"=%s AND "ID_TAQUILLA"=%s AND "ID_MANILLA"=%s',
                    (fecha, id_taquilla, int(fila["ID"])),
                )
            else:
                db.execute(
                    '''INSERT INTO public."INVENTARIO_FINAL"
                           ("FECHA","ID_TAQUILLA","ID_MANILLA","CANTIDAD","USUARIO_ACTUALIZA")
                       VALUES (%s,%s,%s,%s,%s)
                       ON CONFLICT ("FECHA","ID_TAQUILLA","ID_MANILLA") DO UPDATE
                       SET "CANTIDAD" = EXCLUDED."CANTIDAD",
                           "USUARIO_ACTUALIZA" = EXCLUDED."USUARIO_ACTUALIZA",
                           "FECHA_ACTUALIZA" = now()''',
                    (fecha, id_taquilla, int(fila["ID"]), int(fila["FINAL"]), usuario_actual),
                )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.cerrar()


def _estado(fila):
    if not fila["N_INICIAL"]:
        return "⚪ Sin inicializar"
    if fila["N_FINAL"] >= fila["N_INICIAL"]:
        return "🔴 Cerrada"
    return "🟡 Cierre parcial" if fila["N_FINAL"] else "🟢 Abierta"


def mostrar_modulo_cierre_taquillas(usuario_actual, es_administrador, hoy):

    mensaje = st.session_state.pop("mensaje_cierre", None)
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
        # El operador solo cierra el día de hoy; el administrador puede corregir otras fechas.
        fecha = st.date_input("📅 Fecha", value=hoy, format="DD/MM/YYYY",
                              disabled=not es_administrador, key="cierre_fecha")
    nombres = dict(zip(taquillas["ID"], taquillas["NOMBRE"]))
    with col_taquilla:
        id_taquilla = st.selectbox("🎟️ Taquilla", list(nombres), format_func=lambda i: f"{i} · {nombres[i]}",
                                   key="cierre_taquilla")

    try:
        resumen = obtener_resumen(fecha)
        planilla = obtener_planilla(fecha, id_taquilla)
    except psycopg.errors.UndefinedTable:
        st.error("❌ Falta crear la tabla de inventario final: ejecute `sql/schema.sql` en Neon → SQL Editor.")
        return

    # Estado de todas las taquillas en la fecha.
    por_taquilla = resumen.set_index("ID")
    filas = []
    for i, n in nombres.items():
        r = por_taquilla.loc[i] if i in por_taquilla.index else {"N_INICIAL": 0, "N_FINAL": 0}
        inicial = int(r["INICIAL"]) if r["N_INICIAL"] else None
        final = int(r["FINAL"]) if r["N_FINAL"] else None
        filas.append({"TAQUILLA": f"{i} · {n}", "ESTADO": _estado(r), "INICIAL": inicial, "FINAL": final,
                      "VENDIDAS": inicial - final if inicial is not None and final is not None else None})
    with st.container(border=True):
        seccion(f"📋 Taquillas del {fecha.strftime('%d/%m/%Y')}")
        st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch", placeholder="—",
                     column_config={c: st.column_config.NumberColumn(format="%d")
                                    for c in ("INICIAL", "FINAL", "VENDIDAS")})

    with st.container(border=True):
        seccion(f"🎫 Inventario final · {nombres[id_taquilla]}",
                "Digite la cantidad final de cada manilla y guarde. El inicial viene de "
                f"{NOMBRE_INICIALIZAR} y no se puede modificar aquí; VENDIDAS = INICIAL - FINAL.")

        if planilla.empty:
            st.info(f"{nombres[id_taquilla]} no tiene inventario inicial el {fecha:%d/%m/%Y}. "
                    f"Regístrelo primero en Operación → {NOMBRE_INICIALIZAR}.")
            return

        # VENDIDAS se recalcula con lo que se va digitando (aún sin guardar).
        # La versión cambia al guardar para que la tabla arranque sin cambios pendientes.
        clave = f"editor_cierre_{fecha}_{id_taquilla}_{st.session_state.get('version_cierre', 0)}"
        digitado = planilla.copy()
        for fila, cambios in (st.session_state.get(clave) or {}).get("edited_rows", {}).items():
            if "FINAL" in cambios:
                digitado.loc[int(fila), "FINAL"] = cambios["FINAL"]
        planilla["VENDIDAS"] = (digitado["INICIAL"] - pd.to_numeric(digitado["FINAL"])).astype("Int64")

        editada = st.data_editor(
            planilla,
            hide_index=True,
            width="stretch",
            height=38 + 35 * len(planilla),
            placeholder="",
            column_order=["CONCEPTO", "INICIAL", "FINAL", "VENDIDAS"],
            disabled=["CONCEPTO", "INICIAL", "VENDIDAS"],
            column_config={
                "CONCEPTO": st.column_config.TextColumn("CONCEPTO", width="large"),
                "INICIAL": st.column_config.NumberColumn("INICIAL", format="%d",
                                                         help=f"Registrado en {NOMBRE_INICIALIZAR}."),
                "FINAL": st.column_config.NumberColumn("FINAL", min_value=0, step=1, format="%d"),
                "VENDIDAS": st.column_config.NumberColumn("VENDIDAS", format="%d", help="INICIAL - FINAL"),
            },
            key=clave,
        )
        with st.container(key="acciones_cierre", horizontal=True, horizontal_alignment="right"):
            guardar = st.button("", icon=":material/save:", key="btn_ok_cierre", help="Guardar inventario final")

    if not guardar:
        return

    excedidas = [f"{f['CONCEPTO']}: final {int(f['FINAL'])} y el inicial es {f['INICIAL']}"
                 for _, f in editada.iterrows() if pd.notna(f["FINAL"]) and f["FINAL"] > f["INICIAL"]]
    if excedidas:
        st.error("❌ El final no puede ser mayor que el inicial:\n\n- " + "\n- ".join(excedidas))
        return
    try:
        _guardar(fecha, id_taquilla, editada, usuario_actual)
    except Exception as e:
        st.error(f"❌ No fue posible guardar el inventario final: {e}")
        return
    st.cache_data.clear()
    st.session_state["version_cierre"] = st.session_state.get("version_cierre", 0) + 1
    final = editada["FINAL"].dropna()
    vendidas = int((editada.loc[final.index, "INICIAL"] - final).sum())
    st.session_state["mensaje_cierre"] = (
        "success", f"✅ Inventario final de {nombres[id_taquilla]} guardado: {int(final.sum())} manillas "
                   f"finales, {vendidas} vendidas."
    )
    st.rerun()
