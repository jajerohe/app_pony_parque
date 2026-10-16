"""Distribuir ventas por día.

Las manillas vendidas en el día salen del cierre de taquillas: por cada manilla,
la suma de INICIAL - FINAL de todas las taquillas cerradas. Ese total se reparte
entre las tarifas de la manilla: se digitan los convenios, descuentos,
cortesías..., y la tarifa plena se calcula sola (VENDIDAS menos lo demás). Lo
guardado alimenta el Balance y el inventario general.
"""

import unicodedata
from html import escape

import pandas as pd
import psycopg
import streamlit as st

from database import Database
from usuarios import seccion

NOMBRE_CERRAR = "Cerrar taquillas por día"


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
def obtener_vendidas_dia(fecha):
    """Por manilla: vendidas del día según el cierre de las taquillas (INICIAL - FINAL)."""
    datos = _consultar(
        '''SELECT m."ID_MANILLA", m."NOMBRE", SUM(i."CANTIDAD" - f."CANTIDAD")
           FROM public."INVENTARIO_INICIAL" i
           JOIN public."MANILLAS" m ON m."ID_MANILLA" = i."ID_MANILLA"
           JOIN public."INVENTARIO_FINAL" f
             ON f."FECHA" = i."FECHA" AND f."ID_TAQUILLA" = i."ID_TAQUILLA" AND f."ID_MANILLA" = i."ID_MANILLA"
           WHERE i."FECHA" = %s
           GROUP BY m."ID_MANILLA", m."NOMBRE"
           ORDER BY m."ID_MANILLA"''',
        (fecha,), ("ID_MANILLA", "MANILLA", "VENDIDAS"),
    )
    datos["VENDIDAS"] = datos["VENDIDAS"].astype(int)
    return datos


@st.cache_data(ttl=60, show_spinner=False)
def obtener_taquillas_sin_cerrar(fecha):
    """Taquillas inicializadas en la fecha a las que les falta el final de alguna manilla."""
    return _consultar(
        '''SELECT DISTINCT t."ID_TAQUILLA", t."NOMBRE"
           FROM public."INVENTARIO_INICIAL" i
           JOIN public."TAQUILLAS" t ON t."ID_TAQUILLA" = i."ID_TAQUILLA"
           LEFT JOIN public."INVENTARIO_FINAL" f
                  ON f."FECHA" = i."FECHA" AND f."ID_TAQUILLA" = i."ID_TAQUILLA" AND f."ID_MANILLA" = i."ID_MANILLA"
           WHERE i."FECHA" = %s AND f."CANTIDAD" IS NULL
           ORDER BY 1''',
        (fecha,), ("ID", "NOMBRE"),
    )


@st.cache_data(ttl=60, show_spinner=False)
def obtener_planilla(fecha):
    """Tarifas activas y vigentes de las manillas que se movieron en el día, más
    las que ya tengan ventas guardadas, con la cantidad guardada."""
    datos = _consultar(
        '''SELECT r."ID_TARIFA", c."ID_CATEGORIA", c."NOMBRE", m."ID_MANILLA", m."NOMBRE", p."NOMBRE",
                  COALESCE(v."VALOR_UNITARIO", r."VALOR"), v."CANTIDAD"
           FROM public."TARIFAS" r
           JOIN public."CATEGORIAS" c ON c."ID_CATEGORIA" = r."ID_CATEGORIA"
           JOIN public."MANILLAS" m ON m."ID_MANILLA" = r."ID_MANILLA"
           JOIN public."TIPOS_TARIFA" p ON p."ID_TIPO" = r."ID_TIPO"
           LEFT JOIN public."VENTAS" v ON v."ID_TARIFA" = r."ID_TARIFA" AND v."FECHA" = %(f)s
           WHERE (r."ACTIVO" AND %(f)s BETWEEN r."DESDE" AND r."HASTA"
                  AND r."ID_MANILLA" IN (SELECT "ID_MANILLA" FROM public."INVENTARIO_INICIAL"
                                         WHERE "FECHA" = %(f)s))
              OR v."CANTIDAD" IS NOT NULL
           ORDER BY c."ID_CATEGORIA", m."ID_MANILLA", r."VALOR" DESC, p."ID_TIPO"''',
        {"f": fecha},
        ("ID_TARIFA", "ID_CATEGORIA", "CATEGORIA", "ID_MANILLA", "MANILLA", "TIPO", "VALOR", "CANTIDAD"),
    )
    datos["VALOR"] = datos["VALOR"].astype(float)
    datos["CANTIDAD"] = pd.to_numeric(datos["CANTIDAD"]).astype("Int64")
    return datos


def _es_plena(tipo):
    texto = unicodedata.normalize("NFKD", str(tipo)).encode("ascii", "ignore").decode().strip().lower()
    return texto.startswith("plen")


def _tarifa_plena(tarifas):
    """Índice de la tarifa plena de una manilla (si no tiene, la de mayor valor)."""
    plenas = tarifas[tarifas["TIPO"].map(_es_plena)]
    candidatas = plenas if not plenas.empty else tarifas
    return candidatas.sort_values(["ID_CATEGORIA", "VALOR"], ascending=[True, False]).index[0]


def _marcar_plenas(planilla, vendidas):
    """Columna PLENA: True en la tarifa plena de cada manilla vendida (una por
    manilla). Su cantidad no se digita: se calcula con _calcular."""
    planilla = planilla.copy()
    planilla["PLENA"] = False
    for id_manilla in vendidas["ID_MANILLA"]:
        tarifas = planilla[planilla["ID_MANILLA"] == id_manilla]
        if not tarifas.empty:
            planilla.loc[_tarifa_plena(tarifas), "PLENA"] = True
    return planilla


def _calcular(planilla, vendidas):
    """CANT de la tarifa plena = VENDIDAS de la manilla - lo distribuido en sus
    otras tarifas, y TOTAL = CANT x VALOR en todas las filas."""
    planilla = planilla.copy()
    planilla["CANT"] = pd.to_numeric(planilla["CANT"]).astype("Int64")
    por_manilla = dict(zip(vendidas["ID_MANILLA"], vendidas["VENDIDAS"]))
    otras = planilla[~planilla["PLENA"]].groupby("ID_MANILLA")["CANT"].sum()
    for i in planilla.index[planilla["PLENA"]]:
        id_manilla = planilla.at[i, "ID_MANILLA"]
        planilla.at[i, "CANT"] = int(por_manilla.get(id_manilla, 0)) - int(otras.get(id_manilla, 0))
    planilla["TOTAL"] = planilla["CANT"].fillna(0).astype(float) * planilla["VALOR"]
    return planilla


def pesos(valor):
    """25000 -> '$ 25.000'"""
    if valor is None or pd.isna(valor):
        return "—"
    signo = "-" if valor < 0 else ""
    return f"{signo}$ {abs(valor):,.0f}".replace(",", ".")


# Tabla para digitar: una fila por tarifa, con el campo CANT solo en las que no son la plena.
ESTILO_GRILLA = """<style>
.st-key-ven_grilla{background:#fff;border:1px solid var(--border);border-radius:10px;overflow:hidden}
.st-key-ven_grilla [class*="st-key-ven_fila_"]{border-bottom:1px solid #e6d9c6!important;padding:3px 10px!important;min-height:38px;justify-content:center}
.st-key-ven_grilla [class*="st-key-ven_fila_"]:last-child{border-bottom:none}
.st-key-ven_fila_titulos{background:#faf6ef;border-bottom:1px solid var(--border);padding:0 10px;min-height:36px;justify-content:center}
.st-key-ven_fila_titulos p{font-size:11px!important;color:var(--muted)!important;letter-spacing:.3px}
.st-key-ven_grilla p{font-size:13px;margin:0!important;line-height:1.3}
.st-key-ven_grilla [data-testid="stColumn"]:nth-child(n+4) p{text-align:right}
.st-key-ven_grilla [data-testid="stNumberInputContainer"]{height:30px!important;min-height:30px!important}
.st-key-ven_grilla [data-testid="stNumberInput"] input{padding:2px 8px;text-align:right;font-size:13px}
.st-key-ven_grilla [data-testid="stNumberInputStepUp"],.st-key-ven_grilla [data-testid="stNumberInputStepDown"]{display:none}
.st-key-ven_grilla [data-testid="stColumn"]{display:flex;flex-direction:column;justify-content:center}
.st-key-ven_grilla [data-testid="stColumn"] [data-testid="stElementContainer"],.st-key-ven_grilla [data-testid="stMarkdown"]{height:auto!important}
.st-key-ven_grilla [data-testid="stNumberInputField"]{height:30px!important;line-height:30px;padding:0 8px!important}
.st-key-ven_grilla [class*="st-key-ven_plena_"] p{font-weight:800;background:#f4ece0;border-radius:6px;padding:0 8px;line-height:30px}
</style>"""


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
    return (f'<div class="pp-caja"><div class="pp-caja-titulo">{escape(titulo)}</div><table>'
            '<thead><tr><th colspan="3">Descripción tarifa</th><th>Cant</th><th>Valor</th><th>Valor total</th></tr></thead>'
            f'<tbody>{"".join(filas)}</tbody></table></div>')



# ============================================================
# GUARDAR
# ============================================================
def _guardar_ventas(fecha, editada, usuario_actual):
    """Reemplaza las ventas del día por la distribución digitada."""
    db = Database()
    try:
        db.conectar()
        db.execute('DELETE FROM public."VENTAS" WHERE "FECHA"=%s', (fecha,))
        for _, f in editada.iterrows():
            cantidad = 0 if pd.isna(f["CANT"]) else int(f["CANT"])
            if cantidad > 0:
                db.execute(
                    '''INSERT INTO public."VENTAS" ("FECHA","ID_TARIFA","ID_MANILLA","CANTIDAD",
                                                  "VALOR_UNITARIO","USUARIO_ACTUALIZA")
                       VALUES (%s,%s,%s,%s,%s,%s)''',
                    (fecha, int(f["ID_TARIFA"]), int(f["ID_MANILLA"]), cantidad, float(f["VALOR"]),
                     usuario_actual),
                )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.cerrar()


def _resumen(vendidas, calculada):
    """Por manilla: vendidas (cierre), lo distribuido en otras tarifas y lo que
    queda en la plena."""
    filas = []
    for id_manilla, manilla, total in zip(vendidas["ID_MANILLA"], vendidas["MANILLA"], vendidas["VENDIDAS"]):
        tarifas = calculada[calculada["ID_MANILLA"] == id_manilla]
        otras = int(tarifas.loc[~tarifas["PLENA"], "CANT"].fillna(0).sum())
        plena = tarifas.loc[tarifas["PLENA"], "CANT"]
        filas.append({"MANILLA": manilla, "VENDIDAS": int(total), "OTRAS TARIFAS": otras,
                      "PLENA": int(plena.iloc[0]) if not plena.empty else None})
    return pd.DataFrame(filas, columns=["MANILLA", "VENDIDAS", "OTRAS TARIFAS", "PLENA"])


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

    # El operador solo distribuye el día de hoy; el administrador puede corregir otras fechas.
    fecha = st.date_input("📅 Fecha", value=hoy, format="DD/MM/YYYY", disabled=not es_administrador,
                          key="ven_fecha", width=220)

    try:
        vendidas = obtener_vendidas_dia(fecha)
        sin_cerrar = obtener_taquillas_sin_cerrar(fecha)
        planilla = obtener_planilla(fecha)
    except psycopg.errors.UndefinedTable:
        st.error("❌ Falta crear las tablas: ejecute `sql/schema.sql` en Neon → SQL Editor.")
        return

    if not sin_cerrar.empty:
        st.warning(f"⚠️ Taquillas sin cerrar el {fecha:%d/%m/%Y}: {', '.join(sin_cerrar['NOMBRE'])}. "
                   f"Sus ventas no se suman hasta cerrarlas en Operación → {NOMBRE_CERRAR}.")
    total_vendidas = int(vendidas["VENDIDAS"].sum())
    if planilla["CANTIDAD"].isna().all() and total_vendidas == 0:
        st.info(f"No hay manillas vendidas el {fecha:%d/%m/%Y}. Las vendidas salen de Operación → "
                f"{NOMBRE_CERRAR} (INICIAL - FINAL de cada taquilla).")
        return

    con_tarifa = set(planilla["ID_MANILLA"])
    sin_tarifa = [m for i, m, v in zip(vendidas["ID_MANILLA"], vendidas["MANILLA"], vendidas["VENDIDAS"])
                  if v and i not in con_tarifa]
    if sin_tarifa:
        st.warning("⚠️ Estas manillas tienen vendidas pero no tienen tarifa vigente en la fecha, así que no "
                   "se pueden distribuir: " + ", ".join(sin_tarifa) + ". Créela en Administración → Tarifas.")

    # Una fila por tarifa: las que se digitan tienen un campo numérico y la plena
    # 🔒 es solo texto (se calcula). Cada campo guarda su valor en la sesión; al
    # cambiarlo se revisa que la manilla no quede con más de lo vendido.
    planilla = _marcar_plenas(planilla, vendidas)
    version = st.session_state.get("version_ventas", 0)
    prefijo = f"ven_{fecha}_{version}"
    previos = st.session_state.setdefault(f"previos_{prefijo}", {})
    por_manilla = dict(zip(vendidas["ID_MANILLA"], vendidas["VENDIDAS"]))
    claves = {i: f"{prefijo}_{int(t)}" for i, t in zip(planilla.index, planilla["ID_TARIFA"])}
    for i in planilla.index:
        if not planilla.at[i, "PLENA"] and claves[i] not in previos:
            guardada = planilla.at[i, "CANTIDAD"]
            previos[claves[i]] = None if pd.isna(guardada) else int(guardada)

    def al_cambiar(i):
        clave = claves[i]
        id_manilla = planilla.at[i, "ID_MANILLA"]
        otras = sum(int(st.session_state.get(claves[j], previos.get(claves[j])) or 0)
                    for j in planilla.index[(planilla["ID_MANILLA"] == id_manilla) & ~planilla["PLENA"]])
        vendidas_manilla = int(por_manilla.get(id_manilla, 0))
        if otras > vendidas_manilla:
            resto = otras - int(st.session_state[clave] or 0)
            st.session_state[clave] = previos[clave]
            st.session_state["aviso_ventas"] = (
                f"❌ No se aceptó el valor: {planilla.at[i, 'MANILLA']} · {planilla.at[i, 'TIPO']}: vendió "
                f"{vendidas_manilla} y ya hay {resto} en otras tarifas, así que caben máximo "
                f"{max(vendidas_manilla - resto, 0)}.")
        else:
            previos[clave] = st.session_state[clave]

    digitado = planilla.copy()
    digitado["CANT"] = pd.array([None if p else st.session_state.get(claves[i], previos[claves[i]])
                                 for i, p in zip(planilla.index, planilla["PLENA"])], dtype="Int64")
    calculada = _calcular(digitado, vendidas)

    aviso = st.session_state.pop("aviso_ventas", None)
    if aviso:
        st.error(aviso)
    seccion("✍️ Distribuir manillas vendidas",
            "Digite cuánto se vendió en cada tarifa (convenios, descuentos, cortesías...). La tarifa plena 🔒 "
            "se calcula sola: VENDIDAS de la manilla menos lo distribuido en sus otras tarifas.")
    st.markdown(ESTILO_GRILLA, unsafe_allow_html=True)
    izquierda, derecha = st.columns([1.45, 1], gap="large")
    anchos = [1, 1.5, 1.3, 0.8, 1, 1.1]
    with izquierda, st.container(key="ven_grilla", gap=None):
        with st.container(key="ven_fila_titulos"):
            for col, titulo in zip(st.columns(anchos, gap="small"),
                                   ["CATEGORÍA", "MANILLA", "TIPO", "CANT", "VALOR", "VALOR TOTAL"]):
                col.markdown(titulo)
        for n, i in enumerate(planilla.index):
            f = calculada.loc[i]
            with st.container(key=f"ven_fila_{n}"):
                c = st.columns(anchos, gap="small", vertical_alignment="center")
                c[0].markdown(escape(f["CATEGORIA"]))
                c[1].markdown(escape(f["MANILLA"]))
                if f["PLENA"]:
                    c[2].markdown(f"{escape(f['TIPO'])} 🔒")
                    with c[3], st.container(key=f"ven_plena_{n}"):
                        st.markdown(f"{int(f['CANT'])}", help="Se calcula sola: VENDIDAS - otras tarifas.")
                else:
                    c[2].markdown(escape(f["TIPO"]))
                    c[3].number_input("CANT", value=previos[claves[i]], min_value=0, step=1, key=claves[i],
                                      label_visibility="collapsed", placeholder="", on_change=al_cambiar,
                                      args=(i,))
                c[4].markdown(pesos(f["VALOR"]))
                c[5].markdown(pesos(f["TOTAL"]) if f["TOTAL"] else "\\-")

    cantidades = calculada["CANT"].fillna(0).astype(int)
    total_ventas = float(calculada["TOTAL"].sum())
    resumen = _resumen(vendidas, calculada)
    with derecha:
        with st.container(horizontal=True, gap="small"):
            st.metric("Manillas vendidas", total_vendidas, border=True,
                      help=f"Suma de INICIAL - FINAL de las taquillas cerradas ({NOMBRE_CERRAR}).")
            st.metric("Total ventas", pesos(total_ventas), border=True)
        seccion("🎫 Vendidas por manilla", "PLENA = VENDIDAS - OTRAS TARIFAS; no puede quedar negativa.")
        st.dataframe(
            resumen.style.map(lambda v: "color:#b42318;font-weight:700" if pd.notna(v) and v < 0 else "",
                              subset=["PLENA"]),
            hide_index=True, width="stretch", height=38 + 35 * len(resumen),
        )
        with st.container(key="acciones_ventas", horizontal=True, horizontal_alignment="right"):
            guardar = st.button("", icon=":material/save:", key="btn_ok_ventas", help="Guardar distribución")

    # El estilo va en su propio bloque: los bloques que traen <style> se ocultan.
    st.markdown(ESTILO, unsafe_allow_html=True)
    st.markdown(cuadro_caja_html(calculada.assign(CANTIDAD=cantidades), "Caja general del día"),
                unsafe_allow_html=True)

    if not guardar:
        return
    excedidas = [f"{f['MANILLA']}: vendidas {f['VENDIDAS']}, en otras tarifas {f['OTRAS TARIFAS']}"
                 for _, f in resumen.iterrows() if pd.notna(f["PLENA"]) and f["PLENA"] < 0]
    if excedidas:
        derecha.error("❌ Lo distribuido en las otras tarifas no puede superar lo vendido de la manilla:\n\n- "
                 + "\n- ".join(excedidas))
        return
    try:
        _guardar_ventas(fecha, calculada, usuario_actual)
    except Exception as e:
        derecha.error(f"❌ No fue posible guardar la distribución: {e}")
        return
    st.session_state["version_ventas"] = version + 1
    _notificar(f"✅ Distribución del {fecha:%d/%m/%Y} guardada: {int(cantidades.sum())} manillas por "
               f"{pesos(total_ventas)}.")
