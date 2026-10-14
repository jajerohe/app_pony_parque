"""Módulo de taquillas (solo Administrador). Usa el catálogo genérico de catalogo.py."""

from catalogo import mostrar_catalogo

TAQUILLAS = {
    "clave": "taq",
    "tabla": "TAQUILLAS",
    "id": "ID_TAQUILLA",
    "extra": "UBICACION",
    "singular": "taquilla",
    "plural": "taquillas",
    "etiqueta_extra": "Ubicación",
    "ejemplo_nombre": "Taquilla principal",
    "ejemplo_extra": "Entrada del parque",
    "icono_nuevo": ":material/add_business:",
    "aviso_desactivar": "Una taquilla desactivada no se podrá usar en la operación. Sus datos se conservan.",
    # Manillas que vende cada taquilla.
    "asignacion": {
        "tabla": "TAQUILLAS_MANILLAS",
        "tabla_otro": "MANILLAS",
        "id_otro": "ID_MANILLA",
        "titulo": "Manillas",
        "icono": ":material/confirmation_number:",
    },
}


def mostrar_modulo_taquillas(usuario_actual):
    mostrar_catalogo(TAQUILLAS, usuario_actual)
