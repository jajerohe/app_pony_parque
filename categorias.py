"""Categorías de tarifa (Entradas, Combo...). Solo Administrador. Usa el catálogo genérico de catalogo.py."""

from catalogo import mostrar_catalogo

CATEGORIAS = {
    "clave": "cat",
    "tabla": "CATEGORIAS",
    "id": "ID_CATEGORIA",
    "extra": "DESCRIPCION",
    "singular": "categoría",
    "plural": "categorías",
    "etiqueta_extra": "Descripción",
    "ejemplo_nombre": "Entradas",
    "ejemplo_extra": "Ingreso al parque por persona",
    "icono_nuevo": ":material/new_label:",
    "aviso_desactivar": "Una categoría desactivada no se podrá usar en tarifas nuevas. Sus datos se conservan.",
}


def mostrar_modulo_categorias(usuario_actual):
    mostrar_catalogo(CATEGORIAS, usuario_actual)
