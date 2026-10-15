"""Ventas del día por taquilla.

El operador registra cuántas manillas vendió de cada tarifa (como el cuadro
«Caja general taquilla del día»). El valor sale de la tarifa vigente y queda
guardado con la venta. Con eso:
  * el inventario del día se descuenta solo (FINAL = INICIAL - VENDIDAS),
  * el inventario general se descuenta solo (existencias = ingresos - vendidas).
"""

from html import escape

import pandas as pd
import psycopg
import streamlit as st

from database import Database
from usuarios import seccion

# ============================================================
# DATOS
# ============================================================
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
    return _consultar('SELECT "ID_TAQUILLA", "NOMBRE" FROM public."TAQUILLAS" WHERE "ACTIVO" ORDER BY 1',
                      columnas=("ID", "NOMBRE"))


@st.cache_data(ttl=60, show_spinner=False)
def obtener_planilla_ventas(fecha, id_taquilla):
    """Tarifas activas y vigentes en la fecha de las manillas asignadas a la
    taquilla (el precio es el mismo en todas), más las que ya tengan ventas de
    la taquilla ese día, con la cantidad vendida."""
    datos = _consultar(
        '''SELECT r."ID_TARIFA", c."ID_CATEGORIA", c."NOMBRE", m."ID_MANILLA", m."NOMBRE", p."NOMBRE",
                  COALESCE(v."VALOR_UNITARIO", r."VALOR"), v."CANTIDAD"
           FROM public."TARIFAS" r
           JOIN public."CATEGORIAS" c ON c."ID_CATEGORIA" = r."ID_CATEGORIA"
           JOIN public."MANILLAS" m ON m."ID_MANILLA" = r."ID_MANILLA"
           JOIN public."TIPOS_TARIFA" p ON p."ID_TIPO" = r."ID_TIPO"
           LEFT JOIN public."VENTAS" v
                  ON v."ID_TARIFA" = r."ID_TARIFA" AND v."FECHA" = %(f)s AND v."ID_TAQUILLA" = %(t)s
           WHERE (r."ACTIVO" AND %(f)s BETWEEN r."DESDE" AND r."HASTA"
                  AND EXISTS (SELECT 1 FROM public."TAQUILLAS_MANILLAS" a
                              WHERE a."ID_TAQUILLA" = %(t)s AND a."ID_MANILLA" = r."ID_MANILLA"))
              OR v."CANTIDAD" IS NOT NULL
           ORDER BY c."ID_CATEGORIA", m."ID_MANILLA", r."VALOR" DESC, p."ID_TIPO"''',
        {"f": fecha, "t": id_taquilla},
        ("ID_TARIFA", "ID_CATEGORIA", "CATEGORIA", "ID_MANILLA", "MANILLA", "TIPO", "VALOR", "CANTIDAD"),
    )
    datos["VALOR"] = datos["VALOR"].astype(float)
    return datos


@st.cache_data(ttl=60, show_spinner=False)
def obtener_inventario_dia(fecha, id_taquilla):
    """INICIAL, VENDIDAS y FINAL por manilla de la taquilla en la fecha."""
    datos = _consultar(
        '''SELECT m."ID_MANILLA", m."NOMBRE", i."CANTIDAD",
                  COALESCE((SELECT SUM(v."CANTIDAD") FROM public."VENTAS" v
                            WHERE v."FECHA" = %(f)s AND v."ID_TAQUILLA" = %(t)s
                              AND v."ID_MANILLA" = m."ID_MANILLA"), 0)
           FROM public."MANILLAS" m
           LEFT JOIN public."INVENTARIO_INICIAL" i
                  ON i."ID_MANILLA" = m."ID_MANILLA" AND i."FECHA" = %(f)s AND i."ID_TAQUILLA" = %(t)s
           WHERE i."CANTIDAD" IS NOT NULL
              OR EXISTS (SELECT 1 FROM public."VENTAS" v WHERE v."FECHA" = %(f)s
                         AND v."ID_TAQUILLA" = %(t)s AND v."ID_MANILLA" = m."ID_MANILLA")
           ORDER BY m."ID_MANILLA"''',
        {"f": fecha, "t": id_taquilla}, ("ID_MANILLA", "MANILLA", "INICIAL", "VENDIDAS"),
    )
    datos["VENDIDAS"] = datos["VENDIDAS"].astype(int)
    datos["FINAL"] = datos["INICIAL"].fillna(0).astype(int) - datos["VENDIDAS"]
    return datos


def pesos(valor):
    """25000 -> '$ 25.000'"""
    if valor is None or pd.isna(valor):
        return "—"
    signo = "-" if valor < 0 else ""
    return f"{signo}$ {abs(valor):,.0f}".replace(",", ".")


# ============================================================
# CUADRO «CAJA GENERAL TAQUILLA DEL DÍA»
# ============================================================
ESTILO = """<style>
.pp-caja{background:#fff;border:1px solid var(--border);border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(107,52,22,.06)}
.pp-caja-titulo{background:linear-gradient(90deg,var(--dark),var(--dark2));color:#fff;font-weight:800;font-size:16px;text-align:center;padding:10px;letter-spacing:.5px;text-transform:uppercase}
.pp-caja table{width:100%;border-collapse:collapse;font-size:13px;color:var(--text)}
.pp-caja th{background:#fff3df;color:var(--dark);font-size:10px;font-weight:800;padding:7px 8px;text-transform:uppercase;border-bottom:1px solid var(--border)}
.pp-caja td{padding:5px 8px;border-bottom:1px dotted var(--border)}
.pp-caja .cat{writing-mode:vertical-rl;transform:rotate(180deg);background:var(--dark);color:#fff;font-weight:800;text-align:center;width:34px;letter-spacing:1px;text-transform:uppercase;font-size:13px}
.pp-caja .man{writing-mode:vertical-rl;transform:rotate(180deg);background:#fff3df;color:var(--dark);font-weight:800;text-align:center;width:28px;font-size:10px;text-transform:uppercase;border-right:1px solid var(--border)}
.pp-caja .num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.pp-caja .cant{text-align:center;font-weight:800;background:#faf6ef;width:56px}
.pp-caja .val{color:var(--muted)}
.pp-caja .tot{font-weight:800}
.pp-caja .sub td{background:#fff3df;font-weight:800;border-top:2px solid var(--dark)}
.pp-caja .gran td{background:var(--dark);color:#fff;font-weight:800;font-size:15px}
.pp-caja .cero{color:#c9b8a6;font-weight:400}
.pp-caja .gran td.cant{background:transparent!important;color:#fff!important}
</style>"""


def cuadro_caja_html(planilla, titulo="Caja general taquilla del día"):
    """Mismo orden del formato en papel: categoría > manilla > tipo, con subtotales."""
    filas = []
    for _, cat in planilla.groupby("ID_CATEGORIA", sort=False):
        n_cat = len(cat)
        primera_cat = True
        for _, man in cat.groupby("ID_MANILLA", sort=False):
            primera_man = True
            for _, f in man.iterrows():
                cant = 0 if pd.isna(f["CANTIDAD"]) else int(f["CANTIDAD"])
                celdas = ""
                if primera_cat:
                    celdas += f'<td class="cat" rowspan="{n_cat + 1}">{escape(f["CATEGORIA"])}</td>'
                    primera_cat = False
                if primera_man:
                    celdas += f'<td class="man" rowspan="{len(man)}">{escape(f["MANILLA"])}</td>'
                    primera_man = False
                celdas += (
                    f'<td>{escape(f["TIPO"])}</td>'
                    f'<td class="cant{"" if cant else " cero"}">{cant if cant else ""}</td>'
                    f'<td class="num val">{pesos(f["VALOR"])}</td>'
                    f'<td class="num tot{"" if cant else " cero"}">{pesos(cant * f["VALOR"]) if cant else "-"}</td>'
                )
                filas.append(f"<tr>{celdas}</tr>")
        cant_cat = int(cat["CANTIDAD"].fillna(0).sum())
        total_cat = float((cat["CANTIDAD"].fillna(0) * cat["VALOR"]).sum())
        filas.append(f'<tr class="sub"><td colspan="2"></td><td class="cant">{cant_cat}</td>'
                     f'<td class="num">Subtotal</td><td class="num">{pesos(total_cat)}</td></tr>')

    cant_total = int(planilla["CANTIDAD"].fillna(0).sum())
    total = float((planilla["CANTIDAD"].fillna(0) * planilla["VALOR"]).sum())
    filas.append(f'<tr class="gran"><td colspan="3">TOTAL DEL DÍA</td><td class="cant">'
                 f'{cant_total}</td><td></td><td class="num">{pesos(total)}</td></tr>')
    return (f'{ESTILO}<div class="pp-caja"><div class="pp-caja-titulo">{escape(titulo)}</div><table>'
            '<thead><tr><th colspan="3">Descripción tarifa</th><th>Cant</th><th>Valor</th><th>Valor total</th></tr></thead>'
            f'<tbody>{"".join(filas)}</tbody></table></div>')


# ============================================================
# GUARDAR
# ============================================================
def _guardar_ventas(fecha, id_taquilla, editada, usuario_actual):
    db = Database()
    try:
        db.conectar()
        for _, f in editada.iterrows():
            cantidad = 0 if pd.isna(f["CANT"]) else int(f["CANT"])
            if cantidad <= 0:
                db.execute('DELETE FROM public."VENTAS" WHERE "FECHA"=%s AND "ID_TAQUILLA"=%s AND "ID_TARIFA"=%s',
                           (fecha, id_taquilla, int(f["ID_TARIFA"])))
            else:
                db.execute(
                    '''INSERT INTO public."VENTAS" ("FECHA","ID_TAQUILLA","ID_TARIFA","ID_MANILLA","CANTIDAD",
                                                  "VALOR_UNITARIO","USUARIO_ACTUALIZA")
                       VALUES (%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT ("FECHA","ID_TAQUILLA","ID_TARIFA") DO UPDATE
                       SET "CANTIDAD"=EXCLUDED."CANTIDAD", "USUARIO_ACTUALIZA"=EXCLUDED."USUARIO_ACTUALIZA",
                           "FECHA_ACTUALIZA"=now()''',
                    (fecha, id_taquilla, int(f["ID_TARIFA"]), int(f["ID_MANILLA"]), cantidad,
                     float(f["VALOR"]), usuario_actual),
                )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.cerrar()


def _notificar(mensaje, tipo="success"):
    st.cache_data.clear()
    # Dos «$» en un mensaje se interpretan como fórmula matemática; se escapan.
    st.session_state["mensaje_ventas"] = (tipo, mensaje.replace("$", "\\$"))
    st.rerun()


# ============================================================
# PÁGINA
# ============================================================
def mostrar_modulo_ventas(usuario_actual, es_administrador, hoy):

    mensaje = st.session_state.pop("mensaje_ventas", None)
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

    c1, c2 = st.columns([1, 2])
    with c1:
        # El operador solo registra el día de hoy; el administrador puede corregir otras fechas.
        fecha = st.date_input("📅 Fecha", value=hoy, format="DD/MM/YYYY", disabled=not es_administrador,
                              key="ven_fecha")
    nombres = dict(zip(taquillas["ID"], taquillas["NOMBRE"]))
    with c2:
        id_taquilla = st.selectbox("🎟️ Taquilla", list(nombres), format_func=lambda i: f"{i} · {nombres[i]}",
                                   key="ven_taquilla")

    try:
        planilla = obtener_planilla_ventas(fecha, id_taquilla)
        inventario = obtener_inventario_dia(fecha, id_taquilla)
    except psycopg.errors.UndefinedTable:
        st.error("❌ Falta crear las tablas de ventas: ejecute `sql/schema.sql` en Neon → SQL Editor.")
        return

    total_ventas = float((planilla["CANTIDAD"].fillna(0) * planilla["VALOR"]).sum())
    manillas_vendidas = int(planilla["CANTIDAD"].fillna(0).sum())

    with st.container(horizontal=True, gap="medium"):
        st.metric("Manillas vendidas", manillas_vendidas, border=True)
        st.metric("Total ventas", pesos(total_ventas), border=True)
        st.metric("Manillas disponibles", int(inventario["FINAL"].sum()) if not inventario.empty else 0,
                  border=True, help="Inventario final del día: inicial menos vendidas.")

    if inventario["INICIAL"].isna().all():
        st.warning(f"⚠️ {nombres[id_taquilla]} no tiene inventario inicial el {fecha:%d/%m/%Y}. "
                   "Cárguelo primero en Operación → Inventario inicial.")
        return
    if planilla.empty:
        st.info("Esta taquilla no tiene tarifas vigentes en la fecha. Revise que tenga manillas asignadas "
                "(Taquillas → Asignar manillas) y que esas manillas tengan tarifa en Administración → Tarifas.")
        return

    tab_ventas, tab_inv = st.tabs(["🧾 Ventas del día", "📦 Inventario del día"])

    # ---------------- Ventas ----------------
    with tab_ventas:
        izquierda, derecha = st.columns([1.15, 1], gap="large")
        with izquierda:
            seccion("✍️ Registrar cantidades", "Digite cuántas manillas vendió de cada tarifa y guarde.")
            editor = planilla.assign(CANT=planilla["CANTIDAD"], VALOR_TXT=planilla["VALOR"].map(pesos))
            with st.form(f"form_ventas_{fecha}_{id_taquilla}", border=False):
                editada = st.data_editor(
                    editor, hide_index=True, width="stretch",
                    height=38 + 35 * len(editor), placeholder="",
                    column_order=["CATEGORIA", "MANILLA", "TIPO", "VALOR_TXT", "CANT"],
                    column_config={
                        "CATEGORIA": st.column_config.TextColumn("CATEGORÍA", disabled=True),
                        "MANILLA": st.column_config.TextColumn("MANILLA", disabled=True),
                        "TIPO": st.column_config.TextColumn("TIPO", disabled=True),
                        "VALOR_TXT": st.column_config.TextColumn("VALOR", disabled=True, alignment="right"),
                        "CANT": st.column_config.NumberColumn("CANT", min_value=0, step=1, format="%d"),
                    },
                    key=f"editor_ventas_{fecha}_{id_taquilla}",
                )
                with st.container(key="acciones_ventas", horizontal=True, horizontal_alignment="right"):
                    guardar = st.form_submit_button("", icon=":material/save:", key="btn_ok_ventas",
                                                    help="Guardar ventas")
        with derecha:
            st.markdown(cuadro_caja_html(planilla), unsafe_allow_html=True)

        if guardar:
            # Lo vendido de cada manilla no puede superar su inventario inicial.
            vendidas = editada.assign(C=editada["CANT"].fillna(0)).groupby(["ID_MANILLA", "MANILLA"])["C"].sum()
            iniciales = dict(zip(inventario["ID_MANILLA"], inventario["INICIAL"].fillna(0)))
            excedidas = [f"{m}: vendió {int(c)} y el inicial es {int(iniciales.get(i, 0))}"
                         for (i, m), c in vendidas.items() if c > iniciales.get(i, 0)]
            if excedidas:
                st.error("❌ No hay suficientes manillas en el inventario inicial:\n\n- " + "\n- ".join(excedidas))
            else:
                try:
                    _guardar_ventas(fecha, id_taquilla, editada, usuario_actual)
                except Exception as e:
                    st.error(f"❌ No fue posible guardar las ventas: {e}")
                else:
                    total = float((editada["CANT"].fillna(0) * editada["VALOR"]).sum())
                    _notificar(f"✅ Ventas de {nombres[id_taquilla]} guardadas: "
                               f"{int(editada['CANT'].fillna(0).sum())} manillas por {pesos(total)}.")

    # ---------------- Inventario ----------------
    with tab_inv:
        seccion("📦 Inventario del día", "FINAL = INICIAL − VENDIDAS. Se actualiza al guardar las ventas.")
        tabla = inventario[["MANILLA", "INICIAL", "VENDIDAS", "FINAL"]].copy()
        tabla.loc[len(tabla)] = ["TOTAL", tabla["INICIAL"].fillna(0).sum(), tabla["VENDIDAS"].sum(),
                                 tabla["FINAL"].sum()]
        st.dataframe(tabla, hide_index=True, width="stretch", height=38 + 35 * len(tabla), placeholder="—",
                     column_config={c: st.column_config.NumberColumn(c, format="%d")
                                    for c in ["INICIAL", "VENDIDAS", "FINAL"]})
