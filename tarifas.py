"""Tarifas: precio de cada manilla por categoría y tipo (plena, convenio,
descuento, cortesía...), con su vigencia desde/hasta. El precio es el mismo en
todas las taquillas: cada taquilla vende las tarifas de sus manillas asignadas.

Funciona igual que los catálogos: buscar y filtrar, seleccionar una tarifa en la
tabla y usar los botones para crear, editar, activar o desactivar y eliminar.
Además se pueden cargar muchas tarifas de una vez desde Excel, CSV o pegando
las filas copiadas de una hoja de cálculo.
"""

import csv
import io
import re
import unicodedata
from datetime import date

import pandas as pd
import psycopg
import streamlit as st

from catalogo import obtener_asignaciones, obtener_registros
from database import Database
from usuarios import encabezado_ventana, ficha, seccion

COLUMNAS_IMPORTAR = ["CATEGORIA", "MANILLA", "TIPO", "VALOR", "DESDE", "HASTA"]


# ============================================================
# DATOS
# ============================================================
@st.cache_data(ttl=60, show_spinner=False)
def obtener_tarifas():
    db = Database()
    try:
        db.conectar()
        db.execute('''
            SELECT r."ID_TARIFA", r."ID_CATEGORIA", c."NOMBRE", r."ID_MANILLA", m."NOMBRE", r."ID_TIPO", p."NOMBRE",
                   r."VALOR", r."DESDE", r."HASTA", r."ACTIVO"
            FROM public."TARIFAS" r
            JOIN public."CATEGORIAS" c ON c."ID_CATEGORIA" = r."ID_CATEGORIA"
            JOIN public."MANILLAS" m ON m."ID_MANILLA" = r."ID_MANILLA"
            JOIN public."TIPOS_TARIFA" p ON p."ID_TIPO" = r."ID_TIPO"
            ORDER BY c."ID_CATEGORIA", m."ID_MANILLA", r."VALOR" DESC, p."ID_TIPO", r."DESDE"
        ''')
        datos = pd.DataFrame(db.fetchall(), columns=[
            "ID", "ID_CATEGORIA", "CATEGORIA", "ID_MANILLA", "MANILLA",
            "ID_TIPO", "TIPO", "VALOR", "DESDE", "HASTA", "ACTIVO",
        ])
        datos["VALOR"] = datos["VALOR"].astype(float)
        return datos
    finally:
        db.cerrar()


def _ejecutar(sql, parametros):
    db = Database()
    try:
        db.conectar()
        db.execute(sql, parametros)
        filas = db.cursor.rowcount if hasattr(db, "cursor") else None
        db.commit()
        return filas
    except Exception:
        db.rollback()
        raise
    finally:
        db.cerrar()


def _notificar(mensaje, tipo="success"):
    st.cache_data.clear()
    st.session_state["mensaje_tarifas"] = (tipo, mensaje)
    st.rerun()


def _activos(tabla, id_col):
    registros = obtener_registros(tabla, id_col, "NOMBRE")
    return registros[registros["ACTIVO"]]


def _asignadas():
    """IDs de las manillas asignadas a alguna taquilla (las que se pueden vender)."""
    a = obtener_asignaciones("TAQUILLAS_MANILLAS", "ID_TAQUILLA", "MANILLAS", "ID_MANILLA")
    return set(a["ID_OTRO"].astype(int))


def _aviso_sin_taquilla(id_manilla, nombre):
    if id_manilla is not None and int(id_manilla) not in _asignadas():
        st.warning(f"⚠️ Ninguna taquilla tiene asignada la manilla {nombre}: la tarifa no aparecerá en ventas "
                   "hasta que la asigne en Taquillas → Asignar manillas.")


def _pesos(valor):
    """25000 -> '$ 25.000' (se muestran decimales solo si los tiene)."""
    if valor is None or pd.isna(valor):
        return "—"
    texto = f"{valor:,.2f}".rstrip("0").rstrip(".")
    return "$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _vigencia(desde, hasta, hoy):
    if desde > hoy:
        return "⏳ Futura"
    if hasta < hoy:
        return "⚪ Vencida"
    return "🟢 Vigente"


def _fin_de_anio(hoy):
    return date(hoy.year, 12, 31)


def _lista(tabla, id_col, actual=None):
    """{ID: nombre} de los registros activos, más el actual aunque esté inactivo."""
    r = obtener_registros(tabla, id_col, "NOMBRE")
    r = r[r["ACTIVO"] | (r["ID"] == actual)]
    return {int(i): n + ("" if a else " (inactivo)") for i, n, a in zip(r["ID"], r["NOMBRE"], r["ACTIVO"])}


def _validar(categoria, tipo, valor, desde, hasta):
    if categoria is None:
        return "Debe indicar la categoría."
    if tipo is None:
        return "Debe indicar el tipo de tarifa."
    if valor is None or valor < 0:
        return "El valor debe ser mayor o igual a cero."
    if not desde or not hasta:
        return "Debe indicar la vigencia desde y hasta."
    if hasta < desde:
        return "La fecha HASTA no puede ser anterior a la fecha DESDE."
    return None


def _campos_tarifa(prefijo, fila=None, hoy=None):
    """Campos comunes de crear y editar. Devuelve ID categoría, ID tipo, valor, desde, hasta."""
    categorias = _lista("CATEGORIAS", "ID_CATEGORIA", fila["ID_CATEGORIA"] if fila is not None else None)
    tipos = _lista("TIPOS_TARIFA", "ID_TIPO", fila["ID_TIPO"] if fila is not None else None)
    c1, c2 = st.columns(2)
    with c1:
        id_categoria = st.selectbox(
            "Categoría", list(categorias), format_func=lambda i: categorias[i], key=f"{prefijo}_categoria",
            index=list(categorias).index(fila["ID_CATEGORIA"]) if fila is not None else None,
            placeholder="Seleccione...", help="Se administran en Administración → Categorías.",
        )
    with c2:
        id_tipo = st.selectbox(
            "Tipo", list(tipos), format_func=lambda i: tipos[i], key=f"{prefijo}_tipo",
            index=list(tipos).index(fila["ID_TIPO"]) if fila is not None else None,
            placeholder="Seleccione...", help="Se administran en Administración → Tipos de tarifa.",
        )
    c3, c4, c5 = st.columns(3)
    with c3:
        valor = st.number_input("Valor ($)", min_value=0.0, step=500.0, format="%.0f", key=f"{prefijo}_valor",
                                value=float(fila["VALOR"]) if fila is not None else None,
                                placeholder="Ej: 25000")
    with c4:
        desde = st.date_input("Vigente desde", format="DD/MM/YYYY", key=f"{prefijo}_desde",
                              value=fila["DESDE"] if fila is not None else hoy)
    with c5:
        hasta = st.date_input("Vigente hasta", format="DD/MM/YYYY", key=f"{prefijo}_hasta",
                              value=fila["HASTA"] if fila is not None else _fin_de_anio(hoy))
    return id_categoria, id_tipo, valor, desde, hasta


def _choque(tarifas, id_categoria, id_manilla, id_tipo, desde, hasta, excluir=None):
    """ID de una tarifa activa de la misma categoría, manilla y tipo cuyas fechas se
    cruzan con desde/hasta (None si no hay). Así en ventas nunca hay dos precios
    posibles para el mismo tipo en un mismo día."""
    otras = tarifas[
        tarifas["ACTIVO"]
        & (tarifas["ID_CATEGORIA"] == id_categoria) & (tarifas["ID_MANILLA"] == id_manilla)
        & (tarifas["ID_TIPO"] == id_tipo) & (tarifas["ID"] != excluir)
        & (tarifas["DESDE"] <= hasta) & (tarifas["HASTA"] >= desde)
    ]
    return None if otras.empty else int(otras["ID"].iloc[0])


def _error_bd(e, accion):
    if isinstance(e, psycopg.errors.ExclusionViolation):
        st.error("❌ Ya existe una tarifa activa del mismo tipo para esa categoría y manilla en esas fechas. "
                 "Use otro tipo (por ejemplo Convenio 2) o ajuste la vigencia.")
    elif isinstance(e, psycopg.errors.UniqueViolation):
        st.error("❌ Ya existe una tarifa igual (misma categoría, manilla, tipo, valor y vigencia).")
    else:
        st.error(f"❌ No fue posible {accion} la tarifa: {e}")


# ============================================================
# VENTANAS
# ============================================================
INSERTAR = '''INSERT INTO public."TARIFAS"
    ("ID_CATEGORIA","ID_MANILLA","ID_TIPO","VALOR","DESDE","HASTA","USUARIO_ACTUALIZA")
    VALUES (%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT DO NOTHING'''


@st.dialog(" ", width="large")
def ventana_crear(tarifas, usuario_actual, hoy):
    encabezado_ventana("Nueva Tarifa")

    manillas = _activos("MANILLAS", "ID_MANILLA")
    nombres_man = dict(zip(manillas["ID"], manillas["NOMBRE"]))

    id_manilla = st.selectbox("Manilla", list(nombres_man), format_func=lambda i: nombres_man[i],
                              index=None, placeholder="Seleccione la manilla...", key="tar_n_manilla",
                              help="El valor aplica en todas las taquillas que tengan asignada la manilla.")
    _aviso_sin_taquilla(id_manilla, nombres_man.get(id_manilla))
    id_categoria, id_tipo, valor, desde, hasta = _campos_tarifa("tar_n", hoy=hoy)

    with st.container(key="acciones_dlg_crear_tar", horizontal=True, horizontal_alignment="right"):
        crear = st.button("", icon=":material/add_card:", key="btn_ok_crear_tar", help="Crear tarifa")
    if not crear:
        return

    error = ("Debe seleccionar la manilla." if id_manilla is None
             else _validar(id_categoria, id_tipo, valor, desde, hasta))
    if not error:
        choca = _choque(tarifas, id_categoria, id_manilla, id_tipo, desde, hasta)
        if choca:
            error = (f"La tarifa {choca} ya es del mismo tipo para esa categoría y manilla en esas fechas. "
                     "Use otro tipo (por ejemplo Convenio 2) o ajuste la vigencia.")
    if error:
        st.error(f"❌ {error}")
        return

    try:
        creadas = _ejecutar(INSERTAR, (id_categoria, int(id_manilla), id_tipo, valor, desde, hasta, usuario_actual))
    except Exception as e:
        _error_bd(e, "crear")
        return
    if not creadas:
        st.error("❌ Ya existe una tarifa igual (misma categoría, manilla, tipo, valor y vigencia).")
        return
    _notificar(f"✅ Tarifa de {nombres_man[id_manilla]} · {_lista('TIPOS_TARIFA', 'ID_TIPO')[id_tipo]} creada.")


@st.dialog(" ", width="large")
def ventana_editar(fila, tarifas, usuario_actual):
    encabezado_ventana("Editar Tarifa")

    manillas = obtener_registros("MANILLAS", "ID_MANILLA", "NOMBRE")
    # Activas más la que ya tiene la tarifa, aunque esté inactiva.
    manillas = manillas[manillas["ACTIVO"] | (manillas["ID"] == fila["ID_MANILLA"])]
    nombres_man = dict(zip(manillas["ID"], manillas["NOMBRE"]))

    ficha([("ID", fila["ID"]), ("Vigencia", fila["VIGENCIA"]),
           ("Estado", "Activa" if fila["ACTIVO"] else "Inactiva")])

    id_manilla = st.selectbox("Manilla", list(nombres_man), format_func=lambda i: nombres_man[i],
                              index=list(nombres_man).index(fila["ID_MANILLA"]), key="tar_e_manilla")
    _aviso_sin_taquilla(id_manilla, nombres_man.get(id_manilla))
    id_categoria, id_tipo, valor, desde, hasta = _campos_tarifa(f"tar_e_{fila['ID']}", fila=fila)

    with st.container(key="acciones_dlg_editar_tar", horizontal=True, horizontal_alignment="right"):
        guardar = st.button("", icon=":material/save:", key="btn_info_editar_tar", help="Guardar cambios")
    if not guardar:
        return

    error = _validar(id_categoria, id_tipo, valor, desde, hasta)
    if not error and fila["ACTIVO"]:
        choca = _choque(tarifas, id_categoria, id_manilla, id_tipo, desde, hasta, excluir=fila["ID"])
        if choca:
            error = (f"La tarifa {choca} ya es del mismo tipo para esa categoría y manilla en esas fechas. "
                     "Use otro tipo o ajuste la vigencia.")
    if error:
        st.error(f"❌ {error}")
        return
    try:
        _ejecutar(
            '''UPDATE public."TARIFAS"
               SET "ID_CATEGORIA"=%s, "ID_MANILLA"=%s, "ID_TIPO"=%s, "VALOR"=%s,
                   "DESDE"=%s, "HASTA"=%s, "USUARIO_ACTUALIZA"=%s, "FECHA_ACTUALIZA"=now()
               WHERE "ID_TARIFA"=%s''',
            (id_categoria, int(id_manilla), id_tipo, valor, desde, hasta,
             usuario_actual, int(fila["ID"]))
        )
    except Exception as e:
        _error_bd(e, "actualizar")
        return
    _notificar(f"✅ Tarifa {fila['ID']} actualizada correctamente.")


def _ficha_tarifa(fila):
    ficha([("ID", fila["ID"]), ("Categoría", fila["CATEGORIA"]), ("Manilla", fila["MANILLA"]),
           ("Tipo", fila["TIPO"]), ("Valor", _pesos(fila["VALOR"])),
           ("Vigencia", f"{fila['DESDE']:%d/%m/%Y} a {fila['HASTA']:%d/%m/%Y}")])


@st.dialog(" ", width="large")
def ventana_estado(fila, usuario_actual):
    activar = not fila["ACTIVO"]
    accion = "activar" if activar else "desactivar"
    encabezado_ventana("Cambiar Estado de la Tarifa")
    _ficha_tarifa(fila)
    seccion(f"¿Está seguro que desea {accion} esta tarifa?",
            None if activar else "Una tarifa desactivada no se podrá usar en las ventas. Sus datos se conservan.")

    with st.container(key="acciones_dlg_estado_tar", horizontal=True, horizontal_alignment="right", gap="small"):
        cancelar = st.button("", icon=":material/close:", key="btn_cancel_estado_tar", help="Cancelar")
        confirmar = st.button("", icon=":material/check:", key="btn_warn_estado_tar", help=f"Sí, {accion}")
    if cancelar:
        st.rerun()
    if not confirmar:
        return
    try:
        _ejecutar('''UPDATE public."TARIFAS" SET "ACTIVO"=%s, "USUARIO_ACTUALIZA"=%s, "FECHA_ACTUALIZA"=now()
                     WHERE "ID_TARIFA"=%s''', (activar, usuario_actual, int(fila["ID"])))
    except Exception as e:
        _error_bd(e, accion)
        return
    _notificar(f"✅ Tarifa {fila['ID']} {'activada' if activar else 'desactivada'} correctamente.")


@st.dialog(" ", width="large")
def ventana_eliminar(fila):
    encabezado_ventana("Eliminar Tarifa")
    _ficha_tarifa(fila)
    seccion("¿Está seguro que desea eliminar esta tarifa?", "Esta acción no se puede deshacer.")

    with st.container(key="acciones_dlg_eliminar_tar", horizontal=True, horizontal_alignment="right", gap="small"):
        cancelar = st.button("", icon=":material/close:", key="btn_cancel_eliminar_tar", help="Cancelar")
        confirmar = st.button("", icon=":material/delete:", key="btn_danger_eliminar_tar", help="Sí, eliminar")
    if cancelar:
        st.rerun()
    if not confirmar:
        return
    try:
        _ejecutar('DELETE FROM public."TARIFAS" WHERE "ID_TARIFA"=%s', (int(fila["ID"]),))
    except psycopg.errors.ForeignKeyViolation:
        st.error("❌ La tarifa ya tiene movimientos registrados. Desactívela en lugar de eliminarla.")
        return
    except Exception as e:
        _error_bd(e, "eliminar")
        return
    _notificar(f"✅ Tarifa {fila['ID']} eliminada correctamente.")


# ============================================================
# CARGA MASIVA (Excel, CSV o filas pegadas)
# ============================================================
def _normalizar(texto):
    """'COMBO BASICO' y 'Combo Básico' se consideran iguales."""
    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", texto).strip().lower()


def _numero(texto):
    """'$ 25,000.00', '25.000', '25000' -> 25000.0"""
    if isinstance(texto, (int, float)) and not pd.isna(texto):
        return float(texto)
    t = re.sub(r"[^\d,.\-]", "", str(texto or ""))
    if not t:
        return None
    if "," in t and "." in t:
        decimal = "," if t.rfind(",") > t.rfind(".") else "."
        miles = "." if decimal == "," else ","
        t = t.replace(miles, "").replace(decimal, ".")
    elif "," in t or "." in t:
        sep = "," if "," in t else "."
        partes = t.split(sep)
        # Con grupos de 3 dígitos es separador de miles (25,000 · 1.250.000); si no, decimal.
        t = t.replace(sep, "") if all(len(p) == 3 for p in partes[1:]) else t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def _fecha(valor):
    if isinstance(valor, (pd.Timestamp, date)):
        return pd.Timestamp(valor).date()
    f = pd.to_datetime(str(valor or "").strip(), dayfirst=True, errors="coerce")
    return None if pd.isna(f) else f.date()


def _leer_tabla(archivo, texto):
    """DataFrame con las columnas de la hoja tal cual vienen (sin el título TARIFAS)."""
    if archivo is not None:
        if archivo.name.lower().endswith((".xlsx", ".xls")):
            crudo = pd.read_excel(archivo, header=None, dtype=object)
        else:
            contenido = archivo.getvalue().decode("utf-8-sig", errors="replace")
            separador = max([";", "\t", ","], key=contenido.count)
            filas = [f for f in csv.reader(io.StringIO(contenido), delimiter=separador) if any(c.strip() for c in f)]
            ancho = max(len(f) for f in filas)
            crudo = pd.DataFrame([f + [None] * (ancho - len(f)) for f in filas], dtype=object)
    else:
        # Filas copiadas de Excel: separadas por tabulador; el título puede tener menos columnas.
        filas = [linea.split("\t") for linea in texto.splitlines() if linea.strip()]
        ancho = max(len(f) for f in filas)
        crudo = pd.DataFrame([f + [None] * (ancho - len(f)) for f in filas], dtype=object)

    # La fila de encabezados es la que contiene CATEGORIA (puede haber un título encima).
    for i, fila in crudo.iterrows():
        if any(_normalizar(v) == "categoria" for v in fila):
            datos = crudo.iloc[i + 1:].copy()
            datos.columns = [_normalizar(v).upper() for v in fila]
            datos = datos.rename(columns={"MANILLAS": "MANILLA"})
            return datos.dropna(how="all")
    raise ValueError("No se encontró la fila de encabezados (CATEGORIA, MANILLAS, TIPO, VALOR, DESDE, HASTA).")


def _preparar_importacion(datos):
    faltan = [c for c in COLUMNAS_IMPORTAR if c not in datos.columns]
    if faltan:
        raise ValueError(f"Faltan las columnas: {', '.join(faltan)}.")

    manillas = _activos("MANILLAS", "ID_MANILLA")
    por_nombre_man = {_normalizar(n): i for i, n in zip(manillas["ID"], manillas["NOMBRE"])}
    categorias = {_normalizar(n): i for i, n in _lista("CATEGORIAS", "ID_CATEGORIA").items()}
    tipos = {_normalizar(n): i for i, n in _lista("TIPOS_TARIFA", "ID_TIPO").items()}
    existentes = obtener_tarifas()
    nuevas = []  # filas válidas del archivo, para detectar repetidas dentro del mismo archivo

    filas = []
    for _, f in datos.iterrows():
        cat = str(f["CATEGORIA"] or "").strip()
        tipo = str(f["TIPO"] or "").strip()
        valor, desde, hasta = _numero(f["VALOR"]), _fecha(f["DESDE"]), _fecha(f["HASTA"])
        id_man = por_nombre_man.get(_normalizar(f["MANILLA"]))
        problemas = []
        if id_man is None:
            problemas.append("manilla no existe o está inactiva")
        id_cat, id_tipo = categorias.get(_normalizar(cat)), tipos.get(_normalizar(tipo))
        if id_cat is None:
            problemas.append(f"la categoría «{cat}» no existe")
        if id_tipo is None:
            problemas.append(f"el tipo «{tipo}» no existe")
        error = _validar(id_cat, id_tipo, valor, desde, hasta) if id_cat and id_tipo else None
        if error:
            problemas.append(error.rstrip(".").lower())
        if not problemas:
            choca = _choque(existentes, id_cat, id_man, id_tipo, desde, hasta)
            if choca:
                problemas.append(f"ya existe la tarifa {choca} de este tipo en esas fechas")
            elif (id_cat, id_man, id_tipo, valor, desde, hasta) in nuevas:
                # Hojas antiguas traen la misma tarifa una vez por taquilla: se carga una sola.
                problemas.append("igual a otra fila del archivo (se carga una sola vez)")
            elif any(n[:3] == (id_cat, id_man, id_tipo) and n[4] <= hasta and n[5] >= desde for n in nuevas):
                problemas.append(f"el tipo «{tipo}» está repetido en el archivo para esta categoría y "
                                 "manilla en las mismas fechas con otro valor (¿debería ser otro tipo, como Convenio 2?)")
            else:
                nuevas.append((id_cat, id_man, id_tipo, valor, desde, hasta))
        filas.append({
            "CATEGORIA": cat, "ID_CATEGORIA": id_cat,
            "MANILLA": str(f["MANILLA"] or "").strip(), "ID_MANILLA": id_man,
            "TIPO": tipo, "ID_TIPO": id_tipo,
            "VALOR": valor, "DESDE": desde, "HASTA": hasta,
            "OBSERVACION": "; ".join(problemas) or "✅ Lista para cargar",
            "OK": not problemas,
        })
    return pd.DataFrame(filas)


@st.dialog(" ", width="large")
def ventana_importar(usuario_actual):
    encabezado_ventana("Cargar Tarifas")
    seccion("Desde una hoja de cálculo",
            "Use las columnas CATEGORIA, MANILLAS, TIPO, VALOR, DESDE y HASTA (el valor aplica en "
            "todas las taquillas; si la hoja trae una columna TAQUILLA se ignora). Los nombres de "
            "manillas, categorías y tipos deben coincidir con los del sistema (no importan "
            "mayúsculas ni tildes).")

    archivo = st.file_uploader("Archivo Excel o CSV", type=["xlsx", "csv"], key="tar_archivo")
    texto = st.text_area("…o pegue aquí las filas copiadas de Excel (con los encabezados)",
                         height=120, key="tar_pegado")

    if archivo is None and not texto.strip():
        return

    try:
        preparadas = _preparar_importacion(_leer_tabla(archivo, texto))
    except Exception as e:
        st.error(f"❌ No fue posible leer las tarifas: {e}")
        return

    preparadas = preparadas.sort_values("OK", kind="stable").reset_index(drop=True)  # problemas primero
    validas = preparadas[preparadas["OK"]]
    st.markdown(f"**{len(validas)} de {len(preparadas)} filas listas para cargar.**")
    vista = preparadas.drop(columns=["ID_CATEGORIA", "ID_MANILLA", "ID_TIPO", "OK"]).copy()
    vista["VALOR"] = vista["VALOR"].map(_pesos)
    st.dataframe(vista, hide_index=True, width="stretch", height=min(38 + 35 * len(vista), 360),
                 column_config={"DESDE": st.column_config.DateColumn(format="DD/MM/YYYY"),
                                "HASTA": st.column_config.DateColumn(format="DD/MM/YYYY")})

    with st.container(key="acciones_dlg_importar_tar", horizontal=True, horizontal_alignment="right"):
        cargar = st.button("", icon=":material/upload:", key="btn_ok_importar_tar",
                           disabled=validas.empty, help="Cargar las filas listas")
    if not cargar:
        return

    db = Database()
    creadas = 0
    try:
        db.conectar()
        for _, f in validas.iterrows():
            db.execute(INSERTAR, (int(f["ID_CATEGORIA"]), int(f["ID_MANILLA"]), int(f["ID_TIPO"]),
                                  float(f["VALOR"]), f["DESDE"], f["HASTA"], usuario_actual))
            creadas += db.cursor.rowcount
        db.commit()
    except Exception as e:
        db.rollback()
        _error_bd(e, "cargar")
        return
    finally:
        db.cerrar()

    repetidas = len(validas) - creadas
    omitidas = len(preparadas) - len(validas)
    _notificar(
        f"✅ {creadas} tarifas cargadas."
        + (f" {repetidas} ya existían y no se duplicaron." if repetidas else "")
        + (f" {omitidas} filas con problemas no se cargaron." if omitidas else "")
    )


# ============================================================
# PÁGINA
# ============================================================
def mostrar_modulo_tarifas(usuario_actual, hoy):

    mensaje = st.session_state.pop("mensaje_tarifas", None)
    if mensaje:
        getattr(st, mensaje[0])(mensaje[1])

    try:
        tarifas = obtener_tarifas()
    except psycopg.errors.UndefinedTable:
        st.error("❌ Falta crear la tabla de tarifas: ejecute `sql/schema.sql` en Neon → SQL Editor.")
        return

    tarifas["VIGENCIA"] = [_vigencia(d, h, hoy) for d, h in zip(tarifas["DESDE"], tarifas["HASTA"])]

    # Filtros
    f1, f2, f3 = st.columns([1.3, 1.3, 1])
    with f1:
        f_man = st.multiselect("🎫 Manilla", list(dict.fromkeys(tarifas["MANILLA"])), placeholder="Todas")
    with f2:
        f_cat = st.multiselect("🏷️ Categoría", sorted(tarifas["CATEGORIA"].unique()), placeholder="Todas")
    with f3:
        f_vig = st.selectbox("📅 Vigencia", ["Todas", "🟢 Vigente", "⏳ Futura", "⚪ Vencida"])

    vista = tarifas
    if f_man:
        vista = vista[vista["MANILLA"].isin(f_man)]
    if f_cat:
        vista = vista[vista["CATEGORIA"].isin(f_cat)]
    if f_vig != "Todas":
        vista = vista[vista["VIGENCIA"] == f_vig]
    vista = vista.reset_index(drop=True)

    seleccion = st.session_state.get("tabla_tar")
    filas = seleccion.selection.rows if seleccion else []
    fila = vista.iloc[filas[0]] if filas and filas[0] < len(vista) else None
    activo = bool(fila["ACTIVO"]) if fila is not None else None

    c_sel, c_acciones = st.columns([3, 1.6], vertical_alignment="center")
    with c_sel:
        if fila is not None:
            st.markdown(f"**Tarifa seleccionada:** {fila['ID']} · {fila['CATEGORIA']} · {fila['MANILLA']} · "
                        f"{fila['TIPO']} · {_pesos(fila['VALOR'])}")
        else:
            st.caption("☝️ Seleccione una tarifa en la tabla para administrarla.")

    with c_acciones:
        with st.container(key="acciones_tar", horizontal=True, horizontal_alignment="right", gap="small"):
            if st.button("", icon=":material/add_card:", key="btn_tar_nuevo", help="Nueva tarifa"):
                ventana_crear(tarifas, usuario_actual, hoy)
            if st.button("", icon=":material/upload_file:", key="btn_tar_importar",
                         help="Cargar tarifas desde Excel"):
                ventana_importar(usuario_actual)
            if st.button("", icon=":material/edit:", key="btn_tar_editar", disabled=fila is None,
                         help="Editar tarifa"):
                ventana_editar(fila, tarifas, usuario_actual)
            if st.button("", icon=":material/toggle_off:" if activo is not False else ":material/toggle_on:",
                         key="btn_tar_estado", disabled=fila is None,
                         help="Activar tarifa" if activo is False else "Desactivar tarifa"):
                ventana_estado(fila, usuario_actual)
            if st.button("", icon=":material/delete:", key="btn_tar_eliminar", disabled=fila is None,
                         help="Eliminar tarifa"):
                ventana_eliminar(fila)

    if vista.empty:
        st.info("ℹ️ No hay tarifas registradas. Créelas con ➕ o cárguelas desde Excel."
                if tarifas.empty else "ℹ️ No hay tarifas que coincidan con los filtros.")
        return

    tabla = pd.DataFrame({
        "ID": vista["ID"],
        "CATEGORÍA": vista["CATEGORIA"],
        "MANILLA": vista["MANILLA"],
        "TIPO": vista["TIPO"],
        "VALOR": vista["VALOR"].map(_pesos),
        "DESDE": vista["DESDE"],
        "HASTA": vista["HASTA"],
        "VIGENCIA": vista["VIGENCIA"],
        "ESTADO": vista["ACTIVO"].map(lambda v: "🟢 Activa" if v else "🔴 Inactiva"),
    })

    st.caption(f"{len(vista)} tarifa(s)")
    st.dataframe(
        tabla, key="tabla_tar", on_select="rerun", selection_mode="single-row",
        hide_index=True, width="stretch", height=min(38 + 35 * len(tabla), 640),
        column_config={
            "ID": st.column_config.NumberColumn("ID", width="small", format="%d"),
            "VALOR": st.column_config.TextColumn("VALOR", alignment="right"),
            "DESDE": st.column_config.DateColumn("DESDE", format="DD/MM/YYYY"),
            "HASTA": st.column_config.DateColumn("HASTA", format="DD/MM/YYYY"),
        },
    )
