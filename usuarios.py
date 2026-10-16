"""
Módulo de creación y administración de usuarios (solo Administrador) y
página Mi cuenta (cualquier usuario).

Cada usuario vive en public."USUARIOS": usuario, nombre, correo, perfil,
estado y la contraseña cifrada con bcrypt (pgcrypto). No se usa ningún
servicio externo de autenticación.
"""

import re
from html import escape

import pandas as pd
import psycopg
import streamlit as st

from correo import configuracion_correo, enviar_correo_bienvenida
from database import Database

LONGITUD_MINIMA_CONTRASENA = 8
PATRON_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PATRON_USUARIO = re.compile(r"^[A-Z0-9_.-]{3,30}$")


# ============================================================
# CONSULTAS
# ============================================================
@st.cache_data(ttl=60, show_spinner=False)
def obtener_perfiles():
    db = Database()
    try:
        db.conectar()
        db.execute('SELECT "PERFIL" FROM public."PERFILES" ORDER BY "PERFIL"')
        return [fila[0] for fila in db.fetchall()]
    finally:
        db.cerrar()


@st.cache_data(ttl=60, show_spinner=False)
def obtener_descripcion_perfil(perfil):
    """Descripción del perfil en la tabla PERFILES (None si no tiene)."""
    db = Database()
    try:
        db.conectar()
        db.execute('SELECT "DESCRIPCION" FROM public."PERFILES" WHERE "PERFIL" = %s', (perfil,))
        fila = db.fetchone()
        return fila[0] if fila and fila[0] else None
    except Exception:
        return None
    finally:
        db.cerrar()


@st.cache_data(ttl=60, show_spinner=False)
def obtener_usuarios():
    db = Database()
    try:
        db.conectar()
        db.execute('''
            SELECT "USUARIO", "NOMBRE", "CORREO", "PERFIL", "ACTIVO"
            FROM public."USUARIOS"
            ORDER BY "USUARIO"
        ''')
        return pd.DataFrame(db.fetchall(), columns=["USUARIO", "NOMBRE", "CORREO", "PERFIL", "ACTIVO"])
    finally:
        db.cerrar()


def ejecutar(sql, parametros):
    """Ejecuta una escritura en su propia transacción. Devuelve las filas afectadas."""
    db = Database()
    try:
        db.conectar()
        db.execute(sql, parametros)
        filas = db.cursor.rowcount
        db.commit()
        return filas
    except Exception:
        db.rollback()
        raise
    finally:
        db.cerrar()


# ============================================================
# VALIDACIONES
# ============================================================
def validar_contrasena(contrasena, confirmacion):
    if len(contrasena or "") < LONGITUD_MINIMA_CONTRASENA:
        return f"La contraseña debe tener al menos {LONGITUD_MINIMA_CONTRASENA} caracteres."
    if contrasena != confirmacion:
        return "La contraseña y su confirmación no coinciden."
    return None


def validar_datos(nombre, correo, perfil):
    if not nombre:
        return "Debe ingresar el nombre."
    if not PATRON_CORREO.match(correo or ""):
        return "Debe ingresar un correo electrónico válido."
    if not perfil:
        return "Debe seleccionar el perfil."
    return None


def encabezado_ventana(titulo):
    """Encabezado de las ventanas con el mismo estilo del encabezado de página."""
    st.markdown(
        f'''<div class="pp-topbar pp-dialog-header"><div>
        <div class="pp-top-title">{titulo}</div>
        <div class="pp-top-subtitle">Ponycash · Pony Parque · Hotel Mesa de los Santos</div>
        </div></div>''',
        unsafe_allow_html=True
    )


def ficha(campos, columnas=3):
    """Tarjeta con datos en cuadrícula (etiqueta pequeña + valor)."""
    celdas = "".join(
        f'<div><div class="pp-ficha-label">{etiqueta}</div>'
        f'<div class="pp-ficha-valor">{"—" if valor is None or (isinstance(valor, float) and pd.isna(valor)) or valor == "" else escape(str(valor))}</div></div>'
        for etiqueta, valor in campos
    )
    st.markdown(
        f'<div class="pp-ficha" style="grid-template-columns:repeat({columnas},minmax(0,1fr))">{celdas}</div>',
        unsafe_allow_html=True
    )


def seccion(titulo, descripcion=None):
    """Subtítulo de sección dentro de una ventana."""
    html = f'<div class="pp-section-title pp-dialog-section">{titulo}</div>'
    if descripcion:
        html += f'<div class="pp-section-caption">{descripcion}</div>'
    st.markdown(html, unsafe_allow_html=True)


def notificar(mensaje, tipo="success"):
    """Guarda un mensaje para mostrarlo después del st.rerun() y descarta los
    datos en caché para que la tabla refleje el cambio."""
    st.cache_data.clear()
    st.session_state["mensaje_usuarios"] = (tipo, mensaje)
    st.rerun()


# ============================================================
# VENTANAS (OVERLAY)
# ============================================================
@st.dialog(" ", width="large")
def ventana_crear_usuario(perfiles):

    encabezado_ventana("Nuevo Usuario")

    with st.form("form_crear_usuario"):
        c1, c2 = st.columns(2)
        with c1:
            usuario = st.text_input(
                "Usuario",
                max_chars=30,
                placeholder="Ej: JPEREZ",
                help="Letras, números, punto, guion o guion bajo. Se guarda en MAYÚSCULAS."
            )
        with c2:
            nombre = st.text_input("Nombre completo")

        c3, c4 = st.columns(2)
        with c3:
            correo = st.text_input("Correo electrónico", placeholder="usuario@dominio.com")
        with c4:
            perfil = st.selectbox(
                "Perfil",
                perfiles,
                index=perfiles.index("Operador") if "Operador" in perfiles else 0
            )

        c5, c6 = st.columns(2)
        with c5:
            contrasena = st.text_input("Contraseña temporal", type="password")
        with c6:
            confirmacion = st.text_input("Confirmar contraseña", type="password")

        correo_configurado = configuracion_correo() is not None
        enviar_bienvenida = st.checkbox(
            "Enviar correo de bienvenida con los datos de acceso",
            value=correo_configurado,
            disabled=not correo_configurado,
            help=(
                "Se envía al correo registrado: dirección de acceso, usuario, perfil, "
                "contraseña temporal y procedimiento de ingreso."
                if correo_configurado else
                "Configure la sección [email] en los secretos de la aplicación para habilitar el envío."
            )
        )

        with st.container(key="acciones_dlg_crear", horizontal=True,
                          horizontal_alignment="right", gap="small"):
            crear = st.form_submit_button("", icon=":material/person_add:", key="btn_ok_crear", help="Crear usuario")

    if not crear:
        return

    usuario = (usuario or "").strip().upper()
    nombre = (nombre or "").strip()
    correo = (correo or "").strip().lower()

    if not PATRON_USUARIO.match(usuario):
        st.error("❌ El usuario debe tener entre 3 y 30 caracteres: letras, números, punto, guion o guion bajo.")
        return
    error = validar_datos(nombre, correo, perfil) or validar_contrasena(contrasena, confirmacion)
    if error:
        st.error(f"❌ {error}")
        return

    try:
        ejecutar(
            '''INSERT INTO public."USUARIOS" ("USUARIO","NOMBRE","CORREO","CLAVE","PERFIL")
               VALUES (%s,%s,%s,crypt(%s, gen_salt('bf')),%s)''',
            (usuario, nombre, correo, contrasena, perfil)
        )
    except psycopg.errors.UniqueViolation:
        st.error(f"❌ Ya existe un usuario con el código {usuario} o con el correo {correo}.")
        return
    except Exception as e:
        st.error(f"❌ No fue posible crear el usuario: {e}")
        return

    if not enviar_bienvenida:
        notificar(f"✅ Usuario {usuario} creado correctamente.")

    # El usuario ya quedó creado; un fallo en el correo solo genera un aviso.
    try:
        with st.spinner("Enviando correo de bienvenida..."):
            enviar_correo_bienvenida(
                nombre=nombre,
                usuario=usuario,
                correo=correo,
                perfil=perfil,
                contrasena=contrasena,
                descripcion_perfil=obtener_descripcion_perfil(perfil),
            )
    except Exception as e:
        notificar(
            f"✅ Usuario {usuario} creado correctamente, pero no fue posible enviar "
            f"el correo de bienvenida a {correo}: {e}",
            tipo="warning"
        )

    notificar(f"✅ Usuario {usuario} creado correctamente. Se envió el correo de bienvenida a {correo}.")


@st.dialog(" ", width="large")
def ventana_editar_usuario(fila, perfiles, usuario_actual):

    encabezado_ventana("Editar Usuario")

    es_mismo_usuario = fila["USUARIO"] == usuario_actual

    ficha([("Usuario", fila["USUARIO"]), ("Perfil", fila["PERFIL"]),
           ("Estado", "Activo" if fila["ACTIVO"] else "Inactivo")])

    with st.form(f"form_editar_{fila['USUARIO']}"):
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre completo", value=fila["NOMBRE"] or "")
        with c2:
            correo = st.text_input("Correo electrónico", value=fila["CORREO"] or "")

        perfil = st.selectbox(
            "Perfil",
            perfiles,
            index=perfiles.index(fila["PERFIL"]) if fila["PERFIL"] in perfiles else 0,
            disabled=es_mismo_usuario,
            help="No puede cambiar su propio perfil." if es_mismo_usuario else None
        )

        with st.container(key="acciones_dlg_editar", horizontal=True,
                          horizontal_alignment="right", gap="small"):
            guardar = st.form_submit_button("", icon=":material/save:", key="btn_info_editar", help="Guardar cambios")

    if not guardar:
        return

    nombre = (nombre or "").strip()
    correo = (correo or "").strip().lower()
    if es_mismo_usuario:
        perfil = fila["PERFIL"]

    error = validar_datos(nombre, correo, perfil)
    if error:
        st.error(f"❌ {error}")
        return

    try:
        ejecutar(
            '''UPDATE public."USUARIOS"
               SET "NOMBRE" = %s, "CORREO" = %s, "PERFIL" = %s, "FECHA_ACTUALIZA" = now()
               WHERE "USUARIO" = %s''',
            (nombre, correo, perfil, fila["USUARIO"])
        )
    except psycopg.errors.UniqueViolation:
        st.error(f"❌ Ya existe otro usuario con el correo {correo}.")
        return
    except Exception as e:
        st.error(f"❌ No fue posible guardar los cambios: {e}")
        return

    if es_mismo_usuario:
        st.session_state["nombre_actual"] = nombre
        st.session_state["email_actual"] = correo

    notificar(f"✅ Usuario {fila['USUARIO']} actualizado correctamente.")


@st.dialog(" ", width="large")
def ventana_contrasena(fila):

    encabezado_ventana("Cambiar Contraseña")

    ficha([("Usuario", fila["USUARIO"]), ("Nombre", fila["NOMBRE"]), ("Correo", fila["CORREO"])])

    with st.form(f"form_contrasena_{fila['USUARIO']}"):
        c1, c2 = st.columns(2)
        with c1:
            contrasena = st.text_input("Nueva contraseña", type="password")
        with c2:
            confirmacion = st.text_input("Confirmar contraseña", type="password")
        with st.container(key="acciones_dlg_clave", horizontal=True,
                          horizontal_alignment="right", gap="small"):
            cambiar = st.form_submit_button("", icon=":material/key:", key="btn_neutral_clave", help="Cambiar contraseña")

    if not cambiar:
        return

    error = validar_contrasena(contrasena, confirmacion)
    if error:
        st.error(f"❌ {error}")
        return

    try:
        ejecutar(
            '''UPDATE public."USUARIOS"
               SET "CLAVE" = crypt(%s, gen_salt('bf')), "FECHA_ACTUALIZA" = now()
               WHERE "USUARIO" = %s''',
            (contrasena, fila["USUARIO"])
        )
    except Exception as e:
        st.error(f"❌ No fue posible cambiar la contraseña: {e}")
        return

    notificar(f"✅ Contraseña de {fila['USUARIO']} actualizada correctamente.")


@st.dialog(" ", width="large")
def ventana_estado(fila):

    encabezado_ventana("Cambiar Estado del Usuario")

    activar = not fila["ACTIVO"]
    accion = "activar" if activar else "desactivar"

    ficha([("Usuario", fila["USUARIO"]), ("Nombre", fila["NOMBRE"]), ("Correo", fila["CORREO"])])
    seccion(
        f"¿Está seguro que desea {accion} este usuario?",
        None if activar else "Un usuario desactivado no puede iniciar sesión. Sus datos se conservan."
    )

    with st.form(f"form_estado_{fila['USUARIO']}"):
        with st.container(key="acciones_dlg_estado", horizontal=True,
                          horizontal_alignment="right", gap="small"):
            cancelar = st.form_submit_button("", icon=":material/close:", key="btn_cancel_estado", help="Cancelar")
            confirmar = st.form_submit_button("", icon=":material/check:", key="btn_warn_estado", help=f"Sí, {accion}")

    if cancelar:
        st.rerun()
    if not confirmar:
        return

    try:
        ejecutar(
            'UPDATE public."USUARIOS" SET "ACTIVO" = %s, "FECHA_ACTUALIZA" = now() WHERE "USUARIO" = %s',
            (activar, fila["USUARIO"])
        )
    except Exception as e:
        st.error(f"❌ No fue posible {accion} el usuario: {e}")
        return

    estado = "activado" if activar else "desactivado"
    notificar(f"✅ Usuario {fila['USUARIO']} {estado} correctamente.")


@st.dialog(" ", width="large")
def ventana_eliminar(fila):

    encabezado_ventana("Eliminar Usuario")

    ficha([("Usuario", fila["USUARIO"]), ("Nombre", fila["NOMBRE"]), ("Correo", fila["CORREO"])])
    seccion(
        "¿Está seguro que desea eliminar este usuario?",
        "Se elimina el usuario y su acceso al sistema. Esta acción no se puede deshacer."
    )

    with st.form(f"form_eliminar_{fila['USUARIO']}"):
        with st.container(key="acciones_dlg_eliminar", horizontal=True,
                          horizontal_alignment="right", gap="small"):
            cancelar = st.form_submit_button("", icon=":material/close:", key="btn_cancel_eliminar", help="Cancelar")
            confirmar = st.form_submit_button("", icon=":material/delete:", key="btn_danger_eliminar", help="Sí, eliminar")

    if cancelar:
        st.rerun()
    if not confirmar:
        return

    try:
        ejecutar('DELETE FROM public."USUARIOS" WHERE "USUARIO" = %s', (fila["USUARIO"],))
    except Exception as e:
        st.error(f"❌ No fue posible eliminar el usuario: {e}")
        return

    notificar(f"✅ Usuario {fila['USUARIO']} eliminado correctamente.")


# ============================================================
# PÁGINA PRINCIPAL DEL MÓDULO
# ============================================================
def mostrar_modulo_usuarios(usuario_actual):

    mensaje = st.session_state.pop("mensaje_usuarios", None)
    if mensaje:
        tipo, texto = mensaje
        (st.warning if tipo == "warning" else st.success)(texto)

    try:
        perfiles = obtener_perfiles()
        usuarios = obtener_usuarios()
    except Exception as e:
        st.error("❌ No fue posible consultar los usuarios.")
        st.exception(e)
        return

    texto = st.text_input(
        "🔎 Buscar usuario",
        placeholder="Digite usuario, nombre, correo o perfil..."
    )

    if texto:
        texto_busqueda = texto.lower()
        mascara = usuarios.apply(
            lambda f: texto_busqueda in " ".join(
                str(v) for v in [f["USUARIO"], f["NOMBRE"], f["PERFIL"], f["CORREO"]]
            ).lower(),
            axis=1
        )
        usuarios = usuarios[mascara]

    usuarios = usuarios.reset_index(drop=True)

    # Fila seleccionada en la cuadrícula (se dibuja más abajo).
    seleccion = st.session_state.get("tabla_usuarios")
    filas = seleccion.selection.rows if seleccion else []
    fila = (
        usuarios.iloc[filas[0]]
        if filas and filas[0] < len(usuarios)
        else None
    )

    es_mismo_usuario = fila is not None and fila["USUARIO"] == usuario_actual
    activo = bool(fila["ACTIVO"]) if fila is not None else None

    c_sel, c_acciones = st.columns([3, 1.4], vertical_alignment="center")

    with c_sel:
        if fila is not None:
            st.markdown(f"**Usuario seleccionado:** {fila['USUARIO']} · {escape(fila['NOMBRE'])}")
        else:
            st.caption("☝️ Seleccione un usuario en la tabla para administrarlo.")

    with c_acciones:
        with st.container(key="acciones_usuarios", horizontal=True,
                          horizontal_alignment="right", gap="small"):
            if st.button("", icon=":material/person_add:", key="btn_usr_nuevo", help="Nuevo usuario"):
                ventana_crear_usuario(perfiles)

            if st.button("", icon=":material/edit:", key="btn_usr_editar",
                         disabled=fila is None, help="Editar usuario"):
                ventana_editar_usuario(fila, perfiles, usuario_actual)

            if st.button("", icon=":material/key:", key="btn_usr_clave",
                         disabled=fila is None, help="Cambiar contraseña"):
                ventana_contrasena(fila)

            if st.button("", icon=":material/person_off:" if activo is not False else ":material/person_check:",
                         key="btn_usr_estado",
                         disabled=fila is None or es_mismo_usuario,
                         help="Activar usuario" if activo is False else "Desactivar usuario"):
                ventana_estado(fila)

            if st.button("", icon=":material/delete:", key="btn_usr_eliminar",
                         disabled=fila is None or es_mismo_usuario,
                         help="Eliminar usuario"):
                ventana_eliminar(fila)

    if usuarios.empty:
        st.info("ℹ️ No existen usuarios que coincidan con el criterio de búsqueda.")
        return

    tabla = pd.DataFrame({
        "USUARIO": usuarios["USUARIO"],
        "NOMBRE": usuarios["NOMBRE"],
        "PERFIL": usuarios["PERFIL"],
        "CORREO": usuarios["CORREO"],
        "ESTADO": usuarios["ACTIVO"].map(lambda v: "🟢 Activo" if v else "🔴 Inactivo"),
    })

    st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)

    st.dataframe(
        tabla,
        key="tabla_usuarios",
        on_select="rerun",
        selection_mode="single-row",
        hide_index=True,
        width="stretch",
        height=min(38 + 35 * len(tabla), 640),
        column_config={
            "USUARIO": st.column_config.TextColumn("USUARIO", width="small"),
            "NOMBRE": st.column_config.TextColumn("NOMBRE", width="medium"),
            "PERFIL": st.column_config.TextColumn("PERFIL", width="small"),
            "CORREO": st.column_config.TextColumn("CORREO", width="medium"),
            "ESTADO": st.column_config.TextColumn("ESTADO", width="small"),
        },
    )


# ============================================================
# MI CUENTA (cualquier usuario)
# ============================================================
def mostrar_mi_cuenta(usuario_actual):
    if "mensaje_mi_cuenta" in st.session_state:
        st.success(st.session_state.pop("mensaje_mi_cuenta"))

    with st.container(border=True):
        st.markdown(
            '<div class="pp-section-title">🔑 Cambiar mi contraseña</div>'
            f'<div class="pp-section-caption">Mínimo {LONGITUD_MINIMA_CONTRASENA} caracteres.</div>',
            unsafe_allow_html=True
        )
        with st.form("form_mi_clave", clear_on_submit=True):
            actual = st.text_input("Contraseña actual", type="password")
            c1, c2 = st.columns(2)
            with c1:
                nueva = st.text_input("Nueva contraseña", type="password")
            with c2:
                confirmacion = st.text_input("Confirmar nueva contraseña", type="password")
            with st.container(key="acciones_mi_clave", horizontal=True,
                              horizontal_alignment="right", gap="small"):
                cambiar = st.form_submit_button("", icon=":material/key:", key="btn_ok_mi_clave",
                                                help="Cambiar contraseña")

    if not cambiar:
        return

    error = validar_contrasena(nueva, confirmacion)
    if error:
        st.error(f"❌ {error}")
        return

    try:
        cambiada = ejecutar(
            '''UPDATE public."USUARIOS"
               SET "CLAVE" = crypt(%s, gen_salt('bf')), "FECHA_ACTUALIZA" = now()
               WHERE "USUARIO" = %s AND "CLAVE" = crypt(%s, "CLAVE")''',
            (nueva, usuario_actual, actual)
        ) == 1
    except Exception as e:
        st.error(f"❌ No fue posible cambiar la contraseña: {e}")
        return

    if not cambiada:
        st.error("❌ La contraseña actual no es correcta.")
        return

    st.session_state["mensaje_mi_cuenta"] = "✅ Su contraseña fue cambiada correctamente."
    st.rerun()
