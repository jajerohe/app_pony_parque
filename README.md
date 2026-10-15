# Pony Parque · Sistema de gestión

Sistema del **Pony Parque (Hotel Mesa de los Santos)** en Streamlit, con la base de datos en Neon (PostgreSQL) y el código en GitHub. Se construye por módulos, a medida que el cliente define sus necesidades.

## Módulos

| Menú | Quién lo ve | Qué incluye |
|---|---|---|
| **Inicio** | Todos | Bienvenida y accesos a los módulos. |
| **Mi cuenta** | Todos | Cambiar la propia contraseña. |
| **Ventas del día** | Todos | Por fecha y taquilla, cantidad vendida de cada tarifa vigente, con el cuadro «Caja general taquilla del día» (categoría, manilla, tipo, cant, valor, total y subtotales). No deja vender más que el inventario inicial. Pestaña **Inventario del día**: inicial, vendidas y final. |
| **Consolidado inventario** | Todos | Solo lectura. Por día, una planilla por taquilla (VENDIDAS, CONCEPTO, INICIAL, FINAL), indicadores del día y el total por concepto de todas las taquillas. Vendidas y Final se llenarán con los módulos de ventas e inventario. |
| **Inventario inicial** | Todos | Por fecha y taquilla, cargar la cantidad inicial de cada manilla asignada. Muestra qué taquillas ya están inicializadas y su total. El operador solo carga el día de hoy; el administrador puede corregir otras fechas. |
| **Taquillas** | Administrador | Igual que Usuarios: buscar, seleccionar y crear, editar, activar o desactivar y eliminar taquillas (el ID se genera solo; nombre y ubicación). Con el botón **Asignar manillas** se marcan las manillas que vende cada taquilla. |
| **Manillas** | Administrador | Igual que Taquillas, con nombre y descripción. Viene con los 13 conceptos del parque (Adulto, Adulto Mayor, Niño, combos, atracciones). |
| **Balance** | Administrador | Por día o por mes: ventas, manillas y taquillas con ventas; detalle por taquilla, categoría, manilla y tipo; ventas por día del mes y el cuadro de caja general sumado. Descarga en CSV. |
| **Inventario general** | Administrador | Ingresos de manillas al parque (compras o ajustes). EXISTENCIAS = INGRESOS − VENDIDAS de todas las taquillas, a cualquier fecha. |
| **Tarifas** | Administrador | Valor de cada manilla por categoría y tipo, con vigencia desde/hasta. El valor es el mismo en todas las taquillas: cada taquilla vende las tarifas de las manillas que tiene asignadas. Filtros por manilla, categoría y vigencia. Se pueden cargar muchas desde Excel, CSV o pegando las filas copiadas. |
| **Categorías** | Administrador | Nombres de las categorías de tarifa (Entradas, Combo, Atracciones). Igual que Manillas. |
| **Tipos de tarifa** | Administrador | Nombres de los tipos de tarifa (Plena, Convenio 1, Descuento 50%, Cortesía...). Igual que Manillas. |
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
