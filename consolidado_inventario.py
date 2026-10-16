"""Consolidado diario del inventario: una planilla por taquilla, de solo lectura.

Muestra para la fecha elegida, por taquilla, el inventario INICIAL, el FINAL
(del cierre de taquillas) y las VENDIDAS (inicial - final), y el total del día
por concepto.
"""

from datetime import timedelta
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd
import psycopg
import streamlit as st

from database import Database
from usuarios import seccion


ZONA_HORARIA = ZoneInfo("America/Bogota")


@st.cache_data(ttl=60, show_spinner=False)
def obtener_consolidado(fecha):
    """Una fila por taquilla activa y manilla (asignada y activa, o con inventario en la fecha)."""
    db = Database()
    try:
        db.conectar()
        db.execute(
            '''SELECT t."ID_TAQUILLA", t."NOMBRE", t."UBICACION",
                      m."ID_MANILLA",
                      m."NOMBRE" || CASE WHEN m."ACTIVO" THEN '' ELSE ' (inactiva)' END,
                      i."CANTIDAD", i."USUARIO_ACTUALIZA", i."FECHA_ACTUALIZA",
                      i."CANTIDAD" - f."CANTIDAD", f."CANTIDAD"
               FROM public."TAQUILLAS" t
               CROSS JOIN public."MANILLAS" m
               LEFT JOIN public."TAQUILLAS_MANILLAS" a
                      ON a."ID_TAQUILLA" = t."ID_TAQUILLA" AND a."ID_MANILLA" = m."ID_MANILLA"
               LEFT JOIN public."INVENTARIO_INICIAL" i
                      ON i."ID_TAQUILLA" = t."ID_TAQUILLA" AND i."ID_MANILLA" = m."ID_MANILLA"
                     AND i."FECHA" = %(f)s
               LEFT JOIN public."INVENTARIO_FINAL" f
                      ON f."ID_TAQUILLA" = t."ID_TAQUILLA" AND f."ID_MANILLA" = m."ID_MANILLA"
                     AND f."FECHA" = %(f)s
               WHERE t."ACTIVO"
                 AND ((a."ID_MANILLA" IS NOT NULL AND m."ACTIVO") OR i."CANTIDAD" IS NOT NULL)
               ORDER BY t."ID_TAQUILLA", m."ID_MANILLA"''',
            {"f": fecha}
        )
        datos = pd.DataFrame(db.fetchall(), columns=[
            "ID_TAQUILLA", "TAQUILLA", "UBICACION", "ID_MANILLA", "CONCEPTO",
            "INICIAL", "USUARIO", "ACTUALIZADO", "VENDIDAS", "FINAL",
        ])
        # FINAL viene del cierre de la taquilla; VENDIDAS = INICIAL - FINAL.
        return datos
    finally:
        db.cerrar()


@st.cache_data(ttl=60, show_spinner=False)
def obtener_taquillas_activas():
    db = Database()
    try:
        db.conectar()
        db.execute('SELECT "ID_TAQUILLA", "NOMBRE" FROM public."TAQUILLAS" WHERE "ACTIVO" ORDER BY "ID_TAQUILLA"')
        return pd.DataFrame(db.fetchall(), columns=["ID_TAQUILLA", "TAQUILLA"])
    finally:
        db.cerrar()


def _numero(valor):
    return "" if valor is None or pd.isna(valor) else f"{int(valor):,}".replace(",", ".")


def _planilla_html(nombre, ubicacion, filas, inicializada, actualizado):
    """Planilla de una taquilla con el mismo orden de columnas del formato en papel."""
    cuerpo = "".join(
        f'<tr><td class="pp-inv-num pp-inv-vend">{_numero(f["VENDIDAS"]) or 0}</td>'
        f'<td class="pp-inv-concepto">{escape(f["CONCEPTO"])}</td>'
        f'<td class="pp-inv-num pp-inv-cant">{_numero(f["INICIAL"])}</td>'
        f'<td class="pp-inv-num pp-inv-cant">{_numero(f["FINAL"])}</td></tr>'
        for _, f in filas.iterrows()
    ) or '<tr><td colspan="4" class="pp-inv-vacio">Sin manillas asignadas</td></tr>'
    total = filas["INICIAL"].fillna(0).sum()
    vendidas = filas["VENDIDAS"].fillna(0).sum()
    final = filas["FINAL"].fillna(0).sum()
    estado = (
        f'<span class="pp-inv-badge pp-inv-ok">Inicializada</span>' if inicializada
        else '<span class="pp-inv-badge pp-inv-pendiente">Pendiente</span>'
    )
    pie = f'<div class="pp-inv-pie">{escape(actualizado)}</div>' if actualizado else ""
    sub = f'<div class="pp-inv-ubic">{escape(ubicacion)}</div>' if ubicacion else ""
    return f'''<div class="pp-inv-card">
<div class="pp-inv-titulo"><div><div>{escape(nombre)}</div>{sub}</div>{estado}</div>
<table class="pp-inv-tabla">
<thead><tr><th>VENDIDAS</th><th>CONCEPTO</th><th>INICIAL</th><th>FINAL</th></tr></thead>
<tbody>{cuerpo}</tbody>
<tfoot><tr><td class="pp-inv-num">{_numero(vendidas) or 0}</td><td class="pp-inv-total-label">TOTAL MANILLAS</td>
<td class="pp-inv-num">{_numero(total) if inicializada else ""}</td>
<td class="pp-inv-num">{_numero(final) if inicializada else ""}</td></tr></tfoot>
</table>{pie}</div>'''


ESTILO = """<style>
.pp-inv-card{background:#fff;border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-bottom:16px;box-shadow:0 2px 8px rgba(107,52,22,.06)}
.pp-inv-titulo{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:10px 14px;background:linear-gradient(90deg,var(--dark),var(--dark2));color:#fff;font-weight:800;font-size:15px;text-transform:uppercase;letter-spacing:.4px}
.pp-inv-ubic{font-size:10px;font-weight:600;text-transform:none;letter-spacing:0;opacity:.8}
.pp-inv-badge{font-size:10px;font-weight:800;padding:3px 9px;border-radius:999px;text-transform:uppercase;white-space:nowrap}
.pp-inv-ok{background:#e6f2d4;color:#3f6212}.pp-inv-pendiente{background:#fff3df;color:#9a5b12}
.pp-inv-tabla{width:100%;border-collapse:collapse;font-size:13px;color:var(--text)}
.pp-inv-tabla th{background:#fff3df;color:var(--dark);font-size:10px;font-weight:800;padding:7px 8px;border-bottom:1px solid var(--border);text-align:center}
.pp-inv-tabla td{padding:6px 8px;border-bottom:1px dotted var(--border)}
.pp-inv-tabla th:nth-child(1),.pp-inv-tabla td:nth-child(1){width:17%}
.pp-inv-tabla th:nth-child(3),.pp-inv-tabla td:nth-child(3),.pp-inv-tabla th:nth-child(4),.pp-inv-tabla td:nth-child(4){width:17%}
.pp-inv-num{text-align:center;font-variant-numeric:tabular-nums}
.pp-inv-cant{background:#faf6ef;font-weight:600}
.pp-inv-pend{color:#b9a796}
.pp-inv-vend{font-weight:800}
.pp-inv-pend:empty::after{content:"—"}
.pp-inv-tabla tfoot td{border-top:2px solid var(--dark);border-bottom:none;font-weight:800;padding:8px}
.pp-inv-total-label{text-align:right}
.pp-inv-vacio{text-align:center;color:var(--muted);padding:14px!important}
.pp-inv-pie{font-size:10px;color:var(--muted);padding:6px 12px 8px;text-align:right}
</style>"""


def mostrar_consolidado_inventario(hoy):

    if "cons_fecha" not in st.session_state:
        st.session_state["cons_fecha"] = hoy

    def mover(dias):
        st.session_state["cons_fecha"] += timedelta(days=dias)

    with st.container(horizontal=True, vertical_alignment="bottom", gap="small"):
        st.date_input("📅 Fecha", format="DD/MM/YYYY", key="cons_fecha", width=220)
        st.button("", icon=":material/chevron_left:", key="btn_neutral_cons_ant",
                  help="Día anterior", on_click=mover, args=(-1,))
        st.button("", icon=":material/chevron_right:", key="btn_neutral_cons_sig",
                  help="Día siguiente", on_click=mover, args=(1,))
        st.button("Hoy", key="cons_hoy", on_click=lambda: st.session_state.update(cons_fecha=hoy))
    fecha = st.session_state["cons_fecha"]

    try:
        datos = obtener_consolidado(fecha)
        taquillas = obtener_taquillas_activas()
    except psycopg.errors.UndefinedTable:
        st.error("❌ Falta crear las tablas: ejecute `sql/schema.sql` en Neon → SQL Editor.")
        return

    if taquillas.empty:
        st.info("No hay taquillas activas. Cree una en el módulo **Taquillas**.")
        return

    inicializadas = set(datos.loc[datos["INICIAL"].notna(), "ID_TAQUILLA"])
    total_inicial = int(datos["INICIAL"].fillna(0).sum())

    with st.container(horizontal=True, gap="medium"):
        st.metric("Taquillas inicializadas", f"{len(inicializadas)} de {len(taquillas)}", border=True)
        st.metric("Total manillas inicial", _numero(total_inicial) or "0", border=True)
        st.metric("Vendidas", _numero(datos["VENDIDAS"].fillna(0).sum()) or "0", border=True)
        st.metric("Final", _numero(datos["FINAL"].fillna(0).sum()) or "0", border=True,
                  help="Inventario final registrado al cerrar las taquillas.")

    st.markdown(ESTILO, unsafe_allow_html=True)
    seccion(f"🎟️ Planillas del {fecha.strftime('%d/%m/%Y')}",
            "Solo lectura. El inicial se carga en Operación → Inicializar taquillas por día y el final en Operación → Cerrar taquillas por día (VENDIDAS = INICIAL - FINAL).")

    columnas = st.columns(2, gap="medium")
    for n, (_, taq) in enumerate(taquillas.iterrows()):
        filas = datos[datos["ID_TAQUILLA"] == taq["ID_TAQUILLA"]]
        cargadas = filas[filas["ACTUALIZADO"].notna()]
        actualizado = ""
        if not cargadas.empty:
            ultima = cargadas.sort_values("ACTUALIZADO").iloc[-1]
            actualizado = f"Cargado por {ultima['USUARIO'] or '—'} · {pd.Timestamp(ultima['ACTUALIZADO']).tz_convert(ZONA_HORARIA).strftime('%d/%m/%Y %H:%M')}"
        ubicacion = filas["UBICACION"].iloc[0] if not filas.empty else ""
        with columnas[n % 2]:
            st.markdown(_planilla_html(taq["TAQUILLA"], ubicacion, filas,
                                       taq["ID_TAQUILLA"] in inicializadas, actualizado),
                        unsafe_allow_html=True)

    # Total del día por concepto, con una columna por taquilla.
    cargado = datos[datos["INICIAL"].notna()]
    if cargado.empty:
        st.info("Ninguna taquilla tiene inventario inicial cargado en esta fecha.")
        return
    with st.container(border=True):
        seccion("📊 Total del día por concepto", "Inventario inicial de todas las taquillas sumado por manilla.")
        orden = cargado.drop_duplicates("ID_MANILLA").sort_values("ID_MANILLA")["CONCEPTO"]
        pivote = (cargado.pivot_table(index="CONCEPTO", columns="TAQUILLA", values="INICIAL",
                                      aggfunc="sum").reindex(orden))
        pivote = pivote[[t for t in taquillas["TAQUILLA"] if t in pivote.columns]]  # orden por ID
        pivote.columns = [c.upper() for c in pivote.columns]
        pivote["TOTAL"] = pivote.sum(axis=1)
        pivote.loc["TOTAL MANILLAS"] = pivote.sum()
        st.dataframe(
            pivote.reset_index(), hide_index=True, width="stretch", placeholder="—",
            height=38 + 35 * len(pivote),
            column_config={c: st.column_config.NumberColumn(c, format="%d") for c in pivote.columns},
        )
