# Pony Parque · Sistema de gestión

Sistema del **Pony Parque (Hotel Mesa de los Santos)** en Streamlit, con la base de datos en Neon (PostgreSQL) y el código en GitHub. Se construye por módulos, a medida que el cliente define sus necesidades.

## Módulos

| Menú | Quién lo ve | Qué incluye |
|---|---|---|
| **Inicio** | Todos | Bienvenida y accesos a los módulos. |
| **Mi cuenta** | Todos | Cambiar la propia contraseña. |
| **Taquillas** | Administrador | Igual que Usuarios: buscar, seleccionar y crear, editar, activar o desactivar y eliminar taquillas (el ID se genera solo; nombre y ubicación). |
| **Manillas** | Administrador | Igual que Taquillas, con nombre y descripción. Viene con los 13 conceptos del parque (Adulto, Adulto Mayor, Niño, combos, atracciones). |
| **Usuarios** | Administrador | Igual que en PODEX: buscar, seleccionar un usuario en la tabla y usar los botones para crear (con correo de bienvenida opcional), editar, cambiar la contraseña, activar o desactivar y eliminar. |

## Estructura

| Archivo | Contenido |
|---|---|
| `app.py` | Inicio de sesión, menú, estilos, encabezado y navegación |
| `inicio.py` | Página de inicio |
| `catalogo.py` | Pantalla genérica de catálogos (crear, editar, activar/desactivar, eliminar) |
| `taquillas.py`, `manillas.py` | Configuración de los catálogos Taquillas y Manillas |
| `usuarios.py` | Módulos Usuarios y Mi cuenta, con sus consultas |
| `correo.py` | Correo de bienvenida a los usuarios nuevos |
| `auth.py` | Inicio de sesión contra la tabla `USUARIOS` |
| `database.py` | Conexión a PostgreSQL |
| `sql/schema.sql` | Tablas de la base de datos |
| `assets/` | Logo e ícono |

Para agregar un módulo: sus tablas van al final de `sql/schema.sql`, su pantalla y sus consultas en un archivo propio, y la opción en el menú y en `TITULOS_PAGINA` de `app.py`.

## Puesta en marcha

1. En Neon → **SQL Editor**, ejecute `sql/schema.sql`.
2. Cree el primer administrador con el `INSERT` que está al final de `schema.sql` (cambie nombre, correo y contraseña). Los demás usuarios se crean desde la aplicación.
3. Configure los secretos.

Las contraseñas se guardan cifradas con bcrypt (`pgcrypto`), nunca en texto plano.

## Secretos (`.streamlit/secrets.toml` o Settings → Secrets en Streamlit Cloud)

Los datos salen de Neon → **Connect** (con *Connection pooling* apagado):

```toml
[database]
host = "ep-xxxx.us-east-2.aws.neon.tech"
port = 5432
database = "neondb"
user = "neondb_owner"
password = "..."
sslmode = "require"
```

Opcional, para enviar el correo de bienvenida al crear un usuario:

```toml
[email]
smtp_host = "smtp.gmail.com"
smtp_port = 587
usuario = "notificaciones@dominio.com"
password = "..."
remitente = "Pony Parque <notificaciones@dominio.com>"
app_url = "https://ponyparque.streamlit.app"
```

## Ejecución local

```bash
pip install -r requirements.txt
streamlit run app.py
```
