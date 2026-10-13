from database import Database


def iniciar_sesion(email: str, password: str):
    """Valida el correo y la contraseña contra la tabla USUARIOS.

    La contraseña se compara en PostgreSQL con crypt() (pgcrypto), así que el
    hash bcrypt nunca sale de la base. Devuelve el usuario o None.
    """
    db = Database()
    try:
        db.conectar()
        db.execute(
            """
            SELECT "USUARIO", "PERFIL", "NOMBRE"
            FROM public."USUARIOS"
            WHERE lower("CORREO") = lower(%s)
              AND "ACTIVO"
              AND "CLAVE" = crypt(%s, "CLAVE")
            LIMIT 1
            """,
            (email, password)
        )
        registro = db.fetchone()
        if not registro:
            return None
        return {"USUARIO": registro[0], "PERFIL": registro[1], "NOMBRE": registro[2]}
    finally:
        db.cerrar()


def cerrar_sesion():
    # La sesión de la aplicación vive en st.session_state; no hay una sesión
    # remota que revocar.
    pass
