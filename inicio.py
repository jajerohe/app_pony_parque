"""Página de inicio. Aquí se van agregando accesos a los módulos nuevos."""

import html

import streamlit as st

from usuarios import ficha, seccion


def mostrar_inicio(nombre_actual, usuario_actual, perfil_actual, hoy):
    seccion(f"👋 Hola, {html.escape(nombre_actual or usuario_actual)}",
            "Bienvenido al sistema de gestión del Pony Parque.")
    ficha([
        ("Usuario", usuario_actual),
        ("Perfil", perfil_actual),
        ("Fecha", hoy.strftime("%d/%m/%Y")),
    ])

    with st.container(border=True):
        seccion("🧩 Módulos", "Los módulos del sistema se irán agregando aquí a medida que se construyan.")
        st.info("Por ahora están disponibles **Mi cuenta** y, para el administrador, **Usuarios**.")
