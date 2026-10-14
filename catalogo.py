"""
Catálogos sencillos del sistema (Taquillas, Manillas, ...): crear, editar,
activar o desactivar y eliminar registros con ID automático, nombre y un
campo de texto opcional. Funcionan igual que Usuarios.

Cada catálogo se describe con un diccionario de configuración (ver
taquillas.py y manillas.py). Los nombres de tabla y columnas salen de esa
configuración, nunca de lo que escribe el usuario.
"""

from html import escape

import pandas as pd
import psycopg
import streamlit as st

from database import Database
from usuarios import encabezado_ventana, ficha, seccion

# Claves de la configuración:
#   clave        prefijo de las keys de Streamlit ("taq", "man")
#   tabla        tabla en PostgreSQL ("TAQUILLAS")
#   id           columna del ID automático ("ID_TAQUILLA")
#   extra        columna del campo opcional ("UBICACION")
#   singular     "taquilla" · plural "taquillas"
#   etiqueta_extra, ejemplo_nombre, ejemplo_extra, icono_nuevo, aviso_desactivar
#   asignacion   (opcional) relación con otro catálogo, por ejemplo las manillas
#                que vende cada taquilla:
#                  tabla        tabla de la relación ("TAQUILLAS_MANILLAS")
#                  tabla_otro   catálogo asignado ("MANILLAS")
#                  id_otro      columna del ID del catálogo asignado ("ID_MANILLA")
#                  titulo       "Manillas" · singular "manilla" · icono del botón


@st.cache_data(ttl=60, show_spinner=False)
def obtener_registros(tabla, id_col, extra_col):
    db = Database()
    try:
        db.conectar()
        db.execute(f'''
            SELECT "{id_col}", "NOMBRE", "{extra_col}", "ACTIVO"
            FROM public."{tabla}"
            ORDER BY "{id_col}"
        ''')
        return pd.DataFrame(db.fetchall(), columns=["ID", "NOMBRE", "EXTRA", "ACTIVO"])
    finally:
        db.cerrar()


@st.cache_data(ttl=60, show_spinner=False)
def obtener_asignaciones(tabla_rel, id_col, tabla_otro, id_otro):
    """Pares (ID del registro, ID asignado, nombre asignado, activo) de la relación."""
    db = Database()
    try:
        db.conectar()
        db.execute(f'''
            SELECT r."{id_col}", o."{id_otro}", o."NOMBRE", o."ACTIVO"
            FROM public."{tabla_rel}" r
            JOIN public."{tabla_otro}" o ON o."{id_otro}" = r."{id_otro}"
            ORDER BY o."{id_otro}"
        ''')
        return pd.DataFrame(db.fetchall(), columns=["ID", "ID_OTRO", "NOMBRE", "ACTIVO"])
    finally:
        db.cerrar()


def _ejecutar(sql, parametros, devolver=False):
    db = Database()
    try:
        db.conectar()
        db.execute(sql, parametros)
        resultado = db.fetchone()[0] if devolver else None
        db.commit()
        return resultado
    except Exception:
        db.rollback()
        raise
    finally:
        db.cerrar()


def _notificar(cfg, mensaje, tipo="success"):
    """Guarda un mensaje para mostrarlo después del st.rerun() y descarta los
    datos en caché para que la tabla refleje el cambio."""
    st.cache_data.clear()
    st.session_state[f"mensaje_{cfg['clave']}"] = (tipo, mensaje)
    st.rerun()


ANCHO_ASIGNACION = 560  # píxeles de la columna de asignaciones


def _lineas_etiquetas(nombres):
    """Líneas que ocupan las etiquetas en la columna de asignaciones, para dar
    a las filas la altura justa y que no se corte ninguna."""
    lineas, usado = 1, 0
    for n in nombres:
        ancho = 6.5 * len(n) + 28
        if usado and usado + ancho > ANCHO_ASIGNACION - 16:
            lineas, usado = lineas + 1, 0
        usado += ancho
    return lineas


_GENERO = {
    "a": ("a", "o"), "una": ("una", "un"), "la": ("la", "el"), "del": ("de la", "del"),
    "esta": ("esta", "este"), "Nueva": ("Nueva", "Nuevo"),
}


def _g(cfg, palabra):
    """Concordancia: «Nueva categoría» pero «Nuevo tipo» (cfg["masculino"] = True)."""
    return _GENERO[palabra][1 if cfg.get("masculino") else 0]


def _titulo(texto):
    return texto[:1].upper() + texto[1:]


# ============================================================
# VENTANAS (OVERLAY)
# ============================================================
@st.dialog(" ", width="large")
def ventana_crear(cfg, usuario_actual):

    k, singular = cfg["clave"], cfg["singular"]
    encabezado_ventana(f"{_g(cfg, 'Nueva')} {_titulo(singular)}")

    with st.form(f"form_crear_{k}"):
        nombre = st.text_input("Nombre", placeholder=f"Ej: {cfg['ejemplo_nombre']}",
                               help=f"El ID {_g(cfg, 'del')} {singular} lo genera el sistema al crearla.")
        extra = st.text_input(f"{cfg['etiqueta_extra']} (opcional)", placeholder=f"Ej: {cfg['ejemplo_extra']}")

        with st.container(key=f"acciones_dlg_crear_{k}", horizontal=True,
                          horizontal_alignment="right", gap="small"):
            crear = st.form_submit_button("", icon=cfg["icono_nuevo"], key=f"btn_ok_crear_{k}",
                                          help=f"Crear {singular}")

    if not crear:
        return

    nombre = (nombre or "").strip()
    extra = (extra or "").strip() or None
    if not nombre:
        st.error("❌ Debe ingresar el nombre.")
        return

    try:
        nuevo_id = _ejecutar(
            f'''INSERT INTO public."{cfg['tabla']}" ("NOMBRE","{cfg['extra']}","USUARIO_ACTUALIZA")
                VALUES (%s,%s,%s)
                RETURNING "{cfg['id']}"''',
            (nombre, extra, usuario_actual),
            devolver=True
        )
    except psycopg.errors.UniqueViolation:
        st.error(f"❌ Ya existe {_g(cfg, 'una')} {singular} con el nombre {nombre}.")
        return
    except Exception as e:
        st.error(f"❌ No fue posible crear {_g(cfg, 'la')} {singular}: {e}")
        return

    _notificar(cfg, f"✅ {_titulo(singular)} {nuevo_id} · {nombre} cread{_g(cfg, 'a')} correctamente.")


@st.dialog(" ", width="large")
def ventana_editar(cfg, fila, usuario_actual):

    k, singular = cfg["clave"], cfg["singular"]
    encabezado_ventana(f"Editar {_titulo(singular)}")

    ficha([("ID", fila["ID"]), ("Nombre", fila["NOMBRE"]),
           ("Estado", ("Activ" if fila["ACTIVO"] else "Inactiv") + _g(cfg, "a"))])

    with st.form(f"form_editar_{k}_{fila['ID']}"):
        nombre = st.text_input("Nombre", value=fila["NOMBRE"] or "")
        extra = st.text_input(f"{cfg['etiqueta_extra']} (opcional)", value=fila["EXTRA"] or "")

        with st.container(key=f"acciones_dlg_editar_{k}", horizontal=True,
                          horizontal_alignment="right", gap="small"):
            guardar = st.form_submit_button("", icon=":material/save:", key=f"btn_info_editar_{k}",
                                            help="Guardar cambios")

    if not guardar:
        return

    nombre = (nombre or "").strip()
    extra = (extra or "").strip() or None
    if not nombre:
        st.error("❌ Debe ingresar el nombre.")
        return

    try:
        _ejecutar(
            f'''UPDATE public."{cfg['tabla']}"
                SET "NOMBRE" = %s, "{cfg['extra']}" = %s, "USUARIO_ACTUALIZA" = %s, "FECHA_ACTUALIZA" = now()
                WHERE "{cfg['id']}" = %s''',
            (nombre, extra, usuario_actual, int(fila["ID"]))
        )
    except psycopg.errors.UniqueViolation:
        st.error(f"❌ Ya existe otra {singular} con el nombre {nombre}.")
        return
    except Exception as e:
        st.error(f"❌ No fue posible guardar los cambios: {e}")
        return

    _notificar(cfg, f"✅ {_titulo(singular)} {fila['ID']} actualizad{_g(cfg, 'a')} correctamente.")


@st.dialog(" ", width="large")
def ventana_estado(cfg, fila, usuario_actual):

    k, singular = cfg["clave"], cfg["singular"]
    encabezado_ventana(f"Cambiar Estado {_g(cfg, 'del')} {_titulo(singular)}")

    activar = not fila["ACTIVO"]
    accion = "activar" if activar else "desactivar"

    ficha([("ID", fila["ID"]), ("Nombre", fila["NOMBRE"]), (cfg["etiqueta_extra"], fila["EXTRA"])])
    seccion(
        f"¿Está seguro que desea {accion} {_g(cfg, 'esta')} {singular}?",
        None if activar else cfg["aviso_desactivar"]
    )

    with st.form(f"form_estado_{k}_{fila['ID']}"):
        with st.container(key=f"acciones_dlg_estado_{k}", horizontal=True,
                          horizontal_alignment="right", gap="small"):
            cancelar = st.form_submit_button("", icon=":material/close:", key=f"btn_cancel_estado_{k}", help="Cancelar")
            confirmar = st.form_submit_button("", icon=":material/check:", key=f"btn_warn_estado_{k}",
                                              help=f"Sí, {accion}")

    if cancelar:
        st.rerun()
    if not confirmar:
        return

    try:
        _ejecutar(
            f'''UPDATE public."{cfg['tabla']}"
                SET "ACTIVO" = %s, "USUARIO_ACTUALIZA" = %s, "FECHA_ACTUALIZA" = now()
                WHERE "{cfg['id']}" = %s''',
            (activar, usuario_actual, int(fila["ID"]))
        )
    except Exception as e:
        st.error(f"❌ No fue posible {accion} {_g(cfg, 'la')} {singular}: {e}")
        return

    estado = ("activad" if activar else "desactivad") + _g(cfg, "a")
    _notificar(cfg, f"✅ {_titulo(singular)} {fila['ID']} {estado} correctamente.")


@st.dialog(" ", width="large")
def ventana_eliminar(cfg, fila):

    k, singular = cfg["clave"], cfg["singular"]
    encabezado_ventana(f"Eliminar {_titulo(singular)}")

    ficha([("ID", fila["ID"]), ("Nombre", fila["NOMBRE"]), (cfg["etiqueta_extra"], fila["EXTRA"])])
    seccion(
        f"¿Está seguro que desea eliminar {_g(cfg, 'esta')} {singular}?",
        "Esta acción no se puede deshacer. Si solo quiere dejar de usarla, desactívela."
    )

    with st.form(f"form_eliminar_{k}_{fila['ID']}"):
        with st.container(key=f"acciones_dlg_eliminar_{k}", horizontal=True,
                          horizontal_alignment="right", gap="small"):
            cancelar = st.form_submit_button("", icon=":material/close:", key=f"btn_cancel_eliminar_{k}", help="Cancelar")
            confirmar = st.form_submit_button("", icon=":material/delete:", key=f"btn_danger_eliminar_{k}",
                                              help="Sí, eliminar")

    if cancelar:
        st.rerun()
    if not confirmar:
        return

    try:
        _ejecutar(f'DELETE FROM public."{cfg["tabla"]}" WHERE "{cfg["id"]}" = %s', (int(fila["ID"]),))
    except psycopg.errors.ForeignKeyViolation:
        st.error(f"❌ {_titulo(_g(cfg, 'la'))} {singular} ya tiene movimientos registrados y no se puede eliminar. "
                 f"Puede desactivarl{_g(cfg, 'a')}.")
        return
    except Exception as e:
        st.error(f"❌ No fue posible eliminar {_g(cfg, 'la')} {singular}: {e}")
        return

    _notificar(cfg, f"✅ {_titulo(singular)} {fila['ID']} eliminad{_g(cfg, 'a')} correctamente.")


@st.dialog(" ", width="large")
def ventana_asignar(cfg, fila, asignados, usuario_actual):

    k, singular, asig = cfg["clave"], cfg["singular"], cfg["asignacion"]
    encabezado_ventana(f"Asignar {asig['titulo']}")

    ficha([("ID", fila["ID"]), ("Nombre", fila["NOMBRE"]),
           ("Estado", ("Activ" if fila["ACTIVO"] else "Inactiv") + _g(cfg, "a"))])

    otros = obtener_registros(asig["tabla_otro"], asig["id_otro"], "NOMBRE")
    actuales = set(asignados["ID_OTRO"])
    # Se ofrecen los activos y, para no perderlos al guardar, los ya asignados aunque estén inactivos.
    opciones = otros[otros["ACTIVO"] | otros["ID"].isin(actuales)]
    nombres = {
        int(o["ID"]): o["NOMBRE"] + ("" if o["ACTIVO"] else " (inactiva)")
        for _, o in opciones.iterrows()
    }

    with st.form(f"form_asignar_{k}_{fila['ID']}"):
        elegidos = st.multiselect(
            f"{asig['titulo']} de {_g(cfg, 'esta')} {singular}",
            list(nombres),
            default=[i for i in nombres if i in actuales],
            format_func=lambda i: nombres[i],
            placeholder=f"Seleccione las {asig['titulo'].lower()}...",
        )
        with st.container(key=f"acciones_dlg_asignar_{k}", horizontal=True,
                          horizontal_alignment="right", gap="small"):
            guardar = st.form_submit_button("", icon=":material/save:", key=f"btn_ok_asignar_{k}",
                                            help="Guardar asignación")

    if not guardar:
        return

    db = Database()
    try:
        db.conectar()
        db.execute(f'DELETE FROM public."{asig["tabla"]}" WHERE "{cfg["id"]}" = %s', (int(fila["ID"]),))
        for id_otro in elegidos:
            db.execute(
                f'INSERT INTO public."{asig["tabla"]}" ("{cfg["id"]}","{asig["id_otro"]}","USUARIO_ACTUALIZA") '
                'VALUES (%s,%s,%s)',
                (int(fila["ID"]), int(id_otro), usuario_actual)
            )
        db.commit()
    except Exception as e:
        db.rollback()
        st.error(f"❌ No fue posible guardar la asignación: {e}")
        return
    finally:
        db.cerrar()

    _notificar(cfg, f"✅ {_titulo(singular)} {fila['ID']}: {len(elegidos)} {asig['titulo'].lower()} asignadas.")


# ============================================================
# PÁGINA PRINCIPAL DEL CATÁLOGO
# ============================================================
def mostrar_catalogo(cfg, usuario_actual):

    k, singular, plural = cfg["clave"], cfg["singular"], cfg["plural"]
    etiqueta_extra = cfg["etiqueta_extra"]

    mensaje = st.session_state.pop(f"mensaje_{k}", None)
    if mensaje:
        tipo, texto = mensaje
        (st.warning if tipo == "warning" else st.success)(texto)

    asig = cfg.get("asignacion")
    try:
        registros = obtener_registros(cfg["tabla"], cfg["id"], cfg["extra"])
        asignaciones = (
            obtener_asignaciones(asig["tabla"], cfg["id"], asig["tabla_otro"], asig["id_otro"])
            if asig else None
        )
    except psycopg.errors.UndefinedTable:
        st.error(f"❌ Falta crear la tabla de {plural}: ejecute `sql/schema.sql` en Neon → SQL Editor.")
        return
    except Exception as e:
        st.error(f"❌ No fue posible consultar las {plural}.")
        st.exception(e)
        return

    texto = st.text_input(
        f"🔎 Buscar {singular}",
        placeholder=f"Digite ID, nombre o {etiqueta_extra.lower()}..."
    )

    if texto and not registros.empty:
        texto_busqueda = texto.lower()
        mascara = registros.apply(
            lambda f: texto_busqueda in " ".join(
                str(v) for v in [f["ID"], f["NOMBRE"], f["EXTRA"] or ""]
            ).lower(),
            axis=1
        )
        registros = registros[mascara]

    registros = registros.reset_index(drop=True)

    # Fila seleccionada en la cuadrícula (se dibuja más abajo).
    seleccion = st.session_state.get(f"tabla_{k}")
    filas = seleccion.selection.rows if seleccion else []
    fila = (
        registros.iloc[filas[0]]
        if filas and filas[0] < len(registros)
        else None
    )
    activo = bool(fila["ACTIVO"]) if fila is not None else None

    c_sel, c_acciones = st.columns([3, 1.4], vertical_alignment="center")

    with c_sel:
        if fila is not None:
            st.markdown(f"**{_titulo(singular)} seleccionad{_g(cfg, 'a')}:** {fila['ID']} · {escape(fila['NOMBRE'])}")
        else:
            st.caption(f"☝️ Seleccione {_g(cfg, 'una')} {singular} en la tabla para administrarla.")

    with c_acciones:
        with st.container(key=f"acciones_{k}", horizontal=True,
                          horizontal_alignment="right", gap="small"):
            if st.button("", icon=cfg["icono_nuevo"], key=f"btn_{k}_nuevo", help=f"{_g(cfg, 'Nueva')} {singular}"):
                ventana_crear(cfg, usuario_actual)

            if st.button("", icon=":material/edit:", key=f"btn_{k}_editar",
                         disabled=fila is None, help=f"Editar {singular}"):
                ventana_editar(cfg, fila, usuario_actual)

            if st.button("", icon=":material/toggle_off:" if activo is not False else ":material/toggle_on:",
                         key=f"btn_{k}_estado",
                         disabled=fila is None,
                         help=f"Activar {singular}" if activo is False else f"Desactivar {singular}"):
                ventana_estado(cfg, fila, usuario_actual)

            if asig and st.button("", icon=asig["icono"], key=f"btn_{k}_asignar",
                                  disabled=fila is None, help=f"Asignar {asig['titulo'].lower()}"):
                ventana_asignar(cfg, fila, asignaciones[asignaciones["ID"] == fila["ID"]], usuario_actual)

            if st.button("", icon=":material/delete:", key=f"btn_{k}_eliminar",
                         disabled=fila is None, help=f"Eliminar {singular}"):
                ventana_eliminar(cfg, fila)

    if registros.empty:
        st.info(f"ℹ️ No hay {plural} registrad{_g(cfg, 'a')}s." if not texto
                else f"ℹ️ No existen {plural} que coincidan con el criterio de búsqueda.")
        return

    columna_extra = etiqueta_extra.upper()
    tabla = pd.DataFrame({
        "ID": registros["ID"],
        "NOMBRE": registros["NOMBRE"],
        columna_extra: registros["EXTRA"].fillna("—"),
        "ESTADO": registros["ACTIVO"].map(lambda v: ("🟢 Activ" if v else "🔴 Inactiv") + _g(cfg, "a")),
    })

    alto_fila = 35
    columnas = {
        "ID": st.column_config.NumberColumn("ID", width="small", format="%d"),
        "NOMBRE": st.column_config.TextColumn("NOMBRE", width="medium"),
        columna_extra: st.column_config.TextColumn(columna_extra, width="medium"),
    }
    if asig:
        columna_asig = asig["titulo"].upper()
        # Cada manilla se muestra como una etiqueta separada, sin cortar el texto.
        por_registro = {
            id_: [n + ("" if a else " (inactiva)") for n, a in zip(grupo["NOMBRE"], grupo["ACTIVO"])]
            for id_, grupo in asignaciones.groupby("ID")
        }
        listas = registros["ID"].map(lambda i: por_registro.get(i, []))
        tabla.insert(3, columna_asig, listas)
        columnas[columna_asig] = st.column_config.ListColumn(columna_asig, width=ANCHO_ASIGNACION)
        alto_fila = max(35, 12 + 28 * max((_lineas_etiquetas(l) for l in listas), default=1))
    columnas["ESTADO"] = st.column_config.TextColumn("ESTADO", width="small")

    st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)

    st.dataframe(
        tabla,
        key=f"tabla_{k}",
        on_select="rerun",
        selection_mode="single-row",
        hide_index=True,
        width="stretch",
        row_height=alto_fila,
        height=min(38 + alto_fila * len(tabla), 640),
        column_config=columnas,
    )
