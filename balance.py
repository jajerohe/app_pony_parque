"""Balance de ventas por día o por mes: totales y
detalle por categoría, manilla y tipo de tarifa (lo guardado en Distribuir
ventas por día)."""

import calendar
from datetime import date

import pandas as pd
import psycopg
import streamlit as st

from database import Database
from usuarios import seccion
from ventas import ESTILO, cuadro_caja_html, pesos

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
         "Septiembre", "Octubre", "Noviembre", "Diciembre"]


def _consultar(sql, parametros=(), columnas=()):
    db = Database()
    try:
        db.conectar()
        db.execute(sql, parametros)
        return pd.DataFrame(db.fetchall(), columns=list(columnas))
    finally:
        db.cerrar()


@st.cache_data(ttl=60, show_spinner=False)
def obtener_ventas(desde, hasta):
    datos = _consultar(
        '''SELECT v."FECHA", c."ID_CATEGORIA", c."NOMBRE",
                  m."ID_MANILLA", m."NOMBRE", p."NOMBRE", v."VALOR_UNITARIO", v."CANTIDAD"
           FROM public."VENTAS" v
           JOIN public."TARIFAS" r ON r."ID_TARIFA" = v."ID_TARIFA"
           JOIN public."CATEGORIAS" c ON c."ID_CATEGORIA" = r."ID_CATEGORIA"
           JOIN public."MANILLAS" m ON m."ID_MANILLA" = v."ID_MANILLA"
           JOIN public."TIPOS_TARIFA" p ON p."ID_TIPO" = r."ID_TIPO"
           WHERE v."FECHA" BETWEEN %s AND %s
           ORDER BY v."FECHA", c."ID_CATEGORIA", m."ID_MANILLA", v."VALOR_UNITARIO" DESC''',
        (desde, hasta),
        ("FECHA", "ID_CATEGORIA", "CATEGORIA", "ID_MANILLA", "MANILLA",
         "TIPO", "VALOR", "CANTIDAD"),
    )
    datos["VALOR"] = datos["VALOR"].astype(float)
    datos["TOTAL"] = datos["VALOR"] * datos["CANTIDAD"]
    return datos


def _tabla_pesos(df, columnas_pesos, columnas_num=()):
    config = {c: st.column_config.TextColumn(c, alignment="right") for c in columnas_pesos}
    config.update({c: st.column_config.NumberColumn(c, format="%d") for c in columnas_num})
    vista = df.copy()
    for c in columnas_pesos:
        vista[c] = vista[c].map(pesos)
    st.dataframe(vista, hide_index=True, width="stretch", height=38 + 35 * len(vista), column_config=config)


def mostrar_balance(hoy):

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        periodo = st.segmented_control("Periodo", ["Día", "Mes"], default="Día", key="bal_periodo")
    if periodo == "Mes":
        with c2:
            mes = st.selectbox("Mes", range(1, 13), index=hoy.month - 1, format_func=lambda m: MESES[m - 1],
                               key="bal_mes")
        with c3:
            anio = st.number_input("Año", min_value=2024, max_value=2100, value=hoy.year, step=1, key="bal_anio")
        desde = date(int(anio), mes, 1)
        hasta = date(int(anio), mes, calendar.monthrange(int(anio), mes)[1])
        titulo = f"{MESES[mes - 1]} {int(anio)}"
    else:
        with c2:
            desde = hasta = st.date_input("Fecha", value=hoy, format="DD/MM/YYYY", key="bal_fecha")
        titulo = f"{desde:%d/%m/%Y}"

    try:
        ventas = obtener_ventas(desde, hasta)
    except psycopg.errors.UndefinedTable:
        st.error("❌ Falta crear las tablas de ventas: ejecute `sql/schema.sql` en Neon → SQL Editor.")
        return

    total = float(ventas["TOTAL"].sum())
    dias = ventas["FECHA"].nunique()

    with st.container(horizontal=True, gap="medium"):
        st.metric(f"Ventas · {titulo}", pesos(total), border=True)
        st.metric("Manillas vendidas", f"{int(ventas['CANTIDAD'].sum()):,}".replace(",", "."), border=True)
        if periodo == "Mes":
            st.metric("Promedio por día", pesos(total / dias) if dias else "—", border=True,
                      help="Total vendido dividido entre los días con ventas.")

    if ventas.empty:
        st.info(f"No hay ventas registradas en {titulo}.")
        return

    if periodo == "Mes":
        with st.container(border=True):
            seccion("📈 Ventas por día", "Total vendido cada día del mes, por categoría.")
            diario = ventas.pivot_table(index="FECHA", columns="CATEGORIA", values="TOTAL", aggfunc="sum").fillna(0)
            diario.index = pd.to_datetime(diario.index)
            st.bar_chart(diario, stack=True, y_label="$", x_label="Día")
            tabla_diaria = diario.copy()
            tabla_diaria["TOTAL"] = tabla_diaria.sum(axis=1)
            tabla_diaria.index = tabla_diaria.index.strftime("%d/%m/%Y")
            _tabla_pesos(tabla_diaria.reset_index().rename(columns={"index": "FECHA"}),
                         list(tabla_diaria.columns))

    izquierda, derecha = st.columns(2, gap="large")
    with izquierda:
        with st.container(border=True):
            seccion("🏷️ Por categoría")
            por_cat = (ventas.groupby(["ID_CATEGORIA", "CATEGORIA"])
                       .agg(MANILLAS=("CANTIDAD", "sum"), VENTAS=("TOTAL", "sum")).reset_index()
                       .drop(columns="ID_CATEGORIA"))
            por_cat["PARTICIPACIÓN"] = (por_cat["VENTAS"] / total * 100).round(1).astype(str) + " %"
            _tabla_pesos(por_cat, ["VENTAS"], ["MANILLAS"])
        with st.container(border=True):
            seccion("🎫 Por manilla y tipo")
            detalle = (ventas.groupby(["ID_CATEGORIA", "ID_MANILLA", "MANILLA", "TIPO", "VALOR"], sort=True)
                       .agg(CANT=("CANTIDAD", "sum"), TOTAL=("TOTAL", "sum")).reset_index()
                       .sort_values(["ID_CATEGORIA", "ID_MANILLA", "VALOR"], ascending=[True, True, False])
                       [["MANILLA", "TIPO", "VALOR", "CANT", "TOTAL"]])
            _tabla_pesos(detalle, ["VALOR", "TOTAL"], ["CANT"])
    with derecha:
        # El mismo cuadro de caja del periodo.
        cuadro = (ventas.groupby(["ID_CATEGORIA", "CATEGORIA", "ID_MANILLA", "MANILLA", "TIPO", "VALOR"], sort=False)
                  ["CANTIDAD"].sum().reset_index()
                  .sort_values(["ID_CATEGORIA", "ID_MANILLA", "VALOR"], ascending=[True, True, False]))
        st.markdown(ESTILO, unsafe_allow_html=True)
        st.markdown(cuadro_caja_html(cuadro, f"Caja general · {titulo}"), unsafe_allow_html=True)

    st.download_button(
        "Descargar detalle (CSV)", icon=":material/download:",
        data=ventas.drop(columns=["ID_CATEGORIA", "ID_MANILLA"]).to_csv(index=False).encode("utf-8-sig"),
        file_name=f"ventas_{desde:%Y%m%d}_{hasta:%Y%m%d}.csv", mime="text/csv", key="bal_descargar",
    )
