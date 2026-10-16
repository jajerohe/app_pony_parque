"""Nombre y descripción del sistema.

Se toman de las variables de entorno NOMBRE_SISTEMA y DESCRIPCION_SISTEMA. En
Streamlit Cloud se definen en Settings → Secrets como claves de primer nivel
(NOMBRE_SISTEMA = "..."), que Streamlit también publica como variables de
entorno. Si no están definidas se usan los valores por defecto de abajo.
"""

import json
import os

NOMBRE_DEFECTO = "Ponycash"
DESCRIPCION_DEFECTO = "Caja diaria · Terceros · Inventario de manillas"


def _leer(variable, defecto):
    valor = os.environ.get(variable)
    if not valor:
        try:
            import streamlit as st
            valor = st.secrets.get(variable)
        except Exception:
            valor = None
    return str(valor).strip() if valor and str(valor).strip() else defecto


NOMBRE_SISTEMA = _leer("NOMBRE_SISTEMA", NOMBRE_DEFECTO)
DESCRIPCION_SISTEMA = _leer("DESCRIPCION_SISTEMA", DESCRIPCION_DEFECTO)


def negrilla(texto):
    """Letras Unicode en negrilla: la pestaña del navegador no admite formato."""
    resultado = ""
    for c in texto:
        if "A" <= c <= "Z":
            resultado += chr(0x1D5D4 + ord(c) - ord("A"))
        elif "a" <= c <= "z":
            resultado += chr(0x1D5EE + ord(c) - ord("a"))
        elif "0" <= c <= "9":
            resultado += chr(0x1D7EC + ord(c) - ord("0"))
        else:
            resultado += c
    return resultado


TITULO_PESTANA = f"{negrilla(NOMBRE_SISTEMA)} - {DESCRIPCION_SISTEMA}"


def fijar_titulo_pestana():
    """Deja en la pestaña solo TITULO_PESTANA: Streamlit Cloud le agrega « · Streamlit»."""
    import streamlit as st
    st.html(f"""
<script>
(() => {{
    const titulo = {json.dumps(TITULO_PESTANA)};
    const fijar = () => {{ if (document.title !== titulo) document.title = titulo; }};
    fijar();
    if (window.titulo_sistema) return;
    window.titulo_sistema = new MutationObserver(fijar);
    window.titulo_sistema.observe(document.querySelector("title") || document.head,
                                  {{ childList: true, characterData: true, subtree: true }});
}})();
</script>
""", unsafe_allow_javascript=True)
