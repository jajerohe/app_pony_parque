"""Tipos de tarifa (Plena, Convenio, Descuento, Cortesía...). Solo Administrador.
Usa el catálogo genérico de catalogo.py."""

from catalogo import mostrar_catalogo

TIPOS_TARIFA = {
    "clave": "tip",
    "tabla": "TIPOS_TARIFA",
    "id": "ID_TIPO",
    "extra": "DESCRIPCION",
    "singular": "tipo de tarifa",
    "plural": "tipos de tarifa",
    "masculino": True,
    "etiqueta_extra": "Descripción",
    "ejemplo_nombre": "Convenio 1",
    "ejemplo_extra": "Empresas con convenio vigente",
    "icono_nuevo": ":material/sell:",
    "aviso_desactivar": "Un tipo de tarifa desactivado no se podrá usar en tarifas nuevas. Sus datos se conservan.",
}


def mostrar_modulo_tipos_tarifa(usuario_actual):
    mostrar_catalogo(TIPOS_TARIFA, usuario_actual)
