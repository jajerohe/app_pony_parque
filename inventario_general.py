"""Inventario general de manillas del parque.

Se registran los ingresos de manillas (compras, recepciones o ajustes; un ajuste
negativo resta). Las ventas de todas las taquillas se descuentan solas, así que:
    EXISTENCIAS = INGRESOS − VENDIDAS
"""

import pandas as pd
import psycopg
import streamlit as st

from catalogo import obtener_registros
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
def obtener_existencias(hasta):
    """Por manilla: ingresos, vendidas y existencias acumuladas hasta la fecha."""
    datos = _consultar(
        '''SELECT m."ID_MANILLA", m."NOMBRE", m."ACTIVO",
                  COALESCE((SELECT SUM(g."CANTIDAD") FROM public."INVENTARIO_GENERAL" g
                            WHERE g."ID_MANILLA" = m."ID_MANILLA" AND g."FECHA" <= %(h)s), 0),
                  COALESCE((SELECT SUM(v."CANTIDAD") FROM public."VENTAS" v
                            WHERE v."ID_MANILLA" = m."ID_MANILLA" AND v."FECHA" <= %(h)s), 0),
                  COALESCE((SELECT SUM(i."CANTIDAD") FROM public."INVENTARIO_INICIAL" i
                            WHERE i."ID_MANILLA" = m."ID_MANILLA" AND i."FECHA" = %(h)s), 0)
           FROM public."MANILLAS" m
           ORDER BY m."ID_MANILLA"''',
        {"h": hasta}, ("ID_MANILLA", "MANILLA", "ACTIVO", "INGRESOS", "VENDIDAS", "EN_TAQUILLAS"),
    )
    for c in ["INGRESOS", "VENDIDAS", "EN_TAQUILLAS"]:
        datos[c] = datos[c].astype(int)
    datos["EXISTENCIAS"] = datos["INGRESOS"] - datos["VENDIDAS"]
    return datos


@st.cache_data(ttl=60, show_spinner=False)
def obtener_movimientos():
    return _consultar(
        '''SELECT g."ID_MOVIMIENTO", g."FECHA", m."NOMBRE", g."CANTIDAD", g."OBSERVACION", g."USUARIO_ACTUALIZA"
           FROM public."INVENTARIO_GENERAL" g JOIN public."MANILLAS" m ON m."ID_MANILLA" = g."ID_MANILLA"
           ORDER BY g."FECHA" DESC, g."ID_MOVIMIENTO" DESC''',
        columnas=("ID", "FECHA", "MANILLA", "CANTIDAD", "OBSERVACION", "USUARIO"),
    )


def _ejecutar(sql, parametros):
    db = Database()
    try:
        db.conectar()
        db.execute(sql, parametros)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.cerrar()


def _notificar(mensaje, tipo="success"):
    st.cache_data.clear()
    st.session_state["mensaje_inv_general"] = (tipo, mensaje)
    st.rerun()


def mostrar_inventario_general(usuario_actual, hoy):

    mensaje = st.session_state.pop("mensaje_inv_general", None)
    if mensaje:
        getattr(st, mensaje[0])(mensaje[1])

    fecha = st.date_input("📅 Existencias al", value=hoy, format="DD/MM/YYYY", key="invg_fecha", width=220)
    try:
        existencias = obtener_existencias(fecha)
        movimientos = obtener_movimientos()
    except psycopg.errors.UndefinedTable:
        st.error("❌ Falta crear la tabla de inventario general: ejecute `sql/schema.sql` en Neon → SQL Editor.")
        return

    with st.container(horizontal=True, gap="medium"):
        st.metric("Ingresos acumulados", f"{existencias['INGRESOS'].sum():,}".replace(",", "."), border=True)
        st.metric("Vendidas acumuladas", f"{existencias['VENDIDAS'].sum():,}".replace(",", "."), border=True)
        st.metric("Existencias", f"{existencias['EXISTENCIAS'].sum():,}".replace(",", "."), border=True)
        negativas = int((existencias["EXISTENCIAS"] < 0).sum())
        st.metric("Manillas en negativo", negativas, border=True,
                  help="Manillas con más ventas que ingresos registrados. Registre su ingreso.")

    with st.container(border=True):
        seccion(f"📦 Existencias por manilla al {fecha:%d/%m/%Y}",
                "EXISTENCIAS = INGRESOS − VENDIDAS (todas las taquillas). "
                "EN TAQUILLAS es el inventario inicial cargado ese día.")
        tabla = existencias[existencias["ACTIVO"] | (existencias["INGRESOS"] != 0) | (existencias["VENDIDAS"] != 0)]
        tabla = tabla[["MANILLA", "INGRESOS", "VENDIDAS", "EXISTENCIAS", "EN_TAQUILLAS"]].copy()
        tabla["ESTADO"] = tabla["EXISTENCIAS"].map(lambda e: "🔴 Revisar" if e < 0 else ("⚪ Agotada" if e == 0 else "🟢 OK"))
        st.dataframe(tabla, hide_index=True, width="stretch", height=38 + 35 * len(tabla),
                     column_config={"EN_TAQUILLAS": st.column_config.NumberColumn("EN TAQUILLAS")})

    with st.container(border=True):
        seccion("➕ Registrar ingreso o ajuste",
                "Ingreso de manillas al parque (compra, recepción). Para un ajuste que resta, use cantidad negativa.")
        manillas = obtener_registros("MANILLAS", "ID_MANILLA", "NOMBRE")
        manillas = manillas[manillas["ACTIVO"]]
        nombres = dict(zip(manillas["ID"], manillas["NOMBRE"]))
        with st.form("form_ingreso_general", clear_on_submit=True):
            c1, c2, c3 = st.columns([1, 1.6, 1])
            with c1:
                f_mov = st.date_input("Fecha", value=hoy, format="DD/MM/YYYY")
            with c2:
                id_manilla = st.selectbox("Manilla", list(nombres), format_func=lambda i: nombres[i],
                                          index=None, placeholder="Seleccione...")
            with c3:
                cantidad = st.number_input("Cantidad", step=1, value=None, placeholder="Ej: 500")
            observacion = st.text_input("Observación (opcional)", placeholder="Ej: Compra factura 1234")
            with st.container(key="acciones_ingreso", horizontal=True, horizontal_alignment="right"):
                registrar = st.form_submit_button("", icon=":material/add:", key="btn_ok_ingreso",
                                                  help="Registrar movimiento")
        if registrar:
            if id_manilla is None or not cantidad:
                st.error("❌ Seleccione la manilla y una cantidad distinta de cero.")
            else:
                try:
                    _ejecutar('''INSERT INTO public."INVENTARIO_GENERAL"
                                 ("FECHA","ID_MANILLA","CANTIDAD","OBSERVACION","USUARIO_ACTUALIZA")
                                 VALUES (%s,%s,%s,%s,%s)''',
                              (f_mov, int(id_manilla), int(cantidad), (observacion or "").strip() or None,
                               usuario_actual))
                except Exception as e:
                    st.error(f"❌ No fue posible registrar el movimiento: {e}")
                else:
                    _notificar(f"✅ Movimiento registrado: {int(cantidad):+d} {nombres[id_manilla]}.")

    with st.container(border=True):
        seccion("🧾 Movimientos registrados", "Seleccione uno para eliminarlo si quedó mal registrado.")
        if movimientos.empty:
            st.info("Aún no hay ingresos registrados.")
            return
        st.dataframe(movimientos, key="tabla_movimientos", on_select="rerun", selection_mode="single-row",
                     hide_index=True, width="stretch", height=min(38 + 35 * len(movimientos), 420),
                     column_config={"FECHA": st.column_config.DateColumn(format="DD/MM/YYYY")})
        sel = st.session_state.get("tabla_movimientos")
        filas = sel.selection.rows if sel else []
        if filas:
            mov = movimientos.iloc[filas[0]]
            if st.button(f"Eliminar movimiento {mov['ID']} ({mov['CANTIDAD']:+d} {mov['MANILLA']})",
                         icon=":material/delete:", key="btn_eliminar_movimiento"):
                _ejecutar('DELETE FROM public."INVENTARIO_GENERAL" WHERE "ID_MOVIMIENTO"=%s', (int(mov["ID"]),))
                _notificar(f"✅ Movimiento {mov['ID']} eliminado.")
