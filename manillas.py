"""Módulo de manillas (solo Administrador). Usa el catálogo genérico de catalogo.py."""

from catalogo import mostrar_catalogo

MANILLAS = {
    "clave": "man",
    "tabla": "MANILLAS",
    "id": "ID_MANILLA",
    "extra": "DESCRIPCION",
    "singular": "manilla",
    "plural": "manillas",
    "etiqueta_extra": "Descripción",
    "ejemplo_nombre": "Combo Básico",
    "ejemplo_extra": "Entrada + taller de arte + cabrio",
    "icono_nuevo": ":material/add_circle:",
    "aviso_desactivar": "Una manilla desactivada no se podrá vender. Sus datos se conservan.",
}


def mostrar_modulo_manillas(usuario_actual):
    mostrar_catalogo(MANILLAS, usuario_actual)
