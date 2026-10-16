"""
Vista previa de los correos antes de enviarlos (igual que en Podex).

Un módulo prepara el correo con programar_envio() y hace st.rerun(); app.py
llama a mostrar_envio_pendiente() en cada página, que abre la ventana con el
correo tal como llegará y los botones para enviarlo o no enviarlo.
"""

from html import escape

import streamlit as st

from correo import enviar_correo, remitente, vista_previa_html
from usuarios import encabezado_ventana

CLAVE = "envio_pendiente"


def programar_envio(titulo, asunto, texto, html, para, aviso_ok="Correo enviado"):
    """Deja el correo listo para la vista previa (se abre en el siguiente rerun)."""
    st.session_state[CLAVE] = {
        "titulo": titulo, "asunto": asunto, "texto": texto, "html": html,
        "para": list(para), "aviso_ok": aviso_ok,
    }


def _chips(correos):
    return " ".join(
        '<span style="display:inline-block;background:#fff3df;border:1px solid #efe2cf;border-radius:99px;'
        f'padding:1px 8px;margin:0 4px 3px 0;font-size:11px">{escape(c)}</span>'
        for c in correos
    ) or "—"


@st.dialog(" ", width="large")
def ventana_envio(datos):
    encabezado_ventana(f"Vista previa · {datos['titulo']}")

    # Misma tarjeta de ficha() de usuarios.py, con HTML en los valores.
    st.markdown(
        '<div class="pp-ficha" style="grid-template-columns:repeat(2,minmax(0,1fr))">'
        + "".join(
            f'<div><div class="pp-ficha-label">{etiqueta}</div><div class="pp-ficha-valor">{valor}</div></div>'
            for etiqueta, valor in [
                ("Asunto", f"<b>{escape(datos['asunto'])}</b>"),
                ("Envía", escape(remitente() or "Sin configurar")),
                ("Para", _chips(datos["para"])),
            ]
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    st.iframe(vista_previa_html(datos["html"]), height=560)

    sin_config = remitente() is None
    if sin_config:
        st.warning("⚠️ Falta configurar la sección [email] en los secretos; no es posible enviar.")

    c_nota, c_acciones = st.columns([3, 1], vertical_alignment="center")
    with c_nota:
        st.caption("El correo no se envía hasta que pulse ✈. Si cierra esta ventana, no se envía.")
    with c_acciones:
        with st.container(key="acciones_dlg_envio", horizontal=True,
                          horizontal_alignment="right", gap="small"):
            no_enviar = st.button("", icon=":material/close:", key="btn_cancel_envio", help="No enviar")
            enviar = st.button("", icon=":material/send:", key="btn_ok_envio", help="Enviar",
                               disabled=sin_config or not datos["para"])

    if no_enviar:
        st.session_state["mensaje_envio"] = ("info", f"ℹ️ {datos['titulo']}: el correo no se envió.")
        st.rerun()
    if not enviar:
        return

    try:
        with st.spinner("Enviando el correo..."):
            enviados = enviar_correo(datos["asunto"], datos["texto"], datos["html"], para=datos["para"])
    except Exception as e:
        st.error(f"❌ No fue posible enviar el correo: {e}")
        return

    st.session_state["mensaje_envio"] = ("success", f"📧 {datos['aviso_ok']} a {enviados} destinatario(s).")
    st.rerun()


def mostrar_envio_pendiente():
    """Muestra el resultado del último envío y abre la vista previa pendiente."""
    mensaje = st.session_state.pop("mensaje_envio", None)
    if mensaje:
        tipo, texto = mensaje
        {"success": st.success, "info": st.info}.get(tipo, st.warning)(texto)

    datos = st.session_state.pop(CLAVE, None)
    if datos:
        ventana_envio(datos)
