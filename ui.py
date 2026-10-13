"""Funciones de interfaz compartidas por los módulos de la aplicación."""

import html

import streamlit as st


def seccion(titulo, descripcion=None):
    """Subtítulo de sección."""
    contenido = f'<div class="pp-section-title">{titulo}</div>'
    if descripcion:
        contenido += f'<div class="pp-section-caption">{descripcion}</div>'
    st.markdown(contenido, unsafe_allow_html=True)


def ficha(campos, columnas=3):
    """Tarjeta con datos en cuadrícula (etiqueta pequeña + valor)."""
    celdas = "".join(
        f'<div><div class="pp-ficha-label">{etiqueta}</div>'
        f'<div class="pp-ficha-valor">{"—" if valor in (None, "") else html.escape(str(valor))}</div></div>'
        for etiqueta, valor in campos
    )
    st.markdown(
        f'<div class="pp-ficha" style="grid-template-columns:repeat({columnas},minmax(0,1fr))">{celdas}</div>',
        unsafe_allow_html=True
    )


def mostrar_mensaje(clave):
    """Muestra el mensaje que dejó la acción anterior antes de st.rerun()."""
    if clave in st.session_state:
        tipo, mensaje = st.session_state.pop(clave)
        getattr(st, tipo)(mensaje)
