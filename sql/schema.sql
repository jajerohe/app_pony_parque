-- Esquema de la base de datos del sistema Pony Parque (Neon / PostgreSQL).
-- Ejecutar una vez en Neon → SQL Editor. Se puede volver a ejecutar sin
-- perder datos.
--
-- Cada módulo nuevo agrega sus tablas al final de este archivo.

-- crypt() y gen_salt() para guardar las contraseñas cifradas (bcrypt).
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- USUARIOS Y PERFILES
-- ============================================================
CREATE TABLE IF NOT EXISTS public."PERFILES" (
    "PERFIL"      text PRIMARY KEY,
    "DESCRIPCION" text
);

INSERT INTO public."PERFILES" ("PERFIL", "DESCRIPCION") VALUES
    ('Administrador', 'Acceso completo, incluida la administración de usuarios.'),
    ('Operador', 'Acceso a los módulos de operación.')
ON CONFLICT ("PERFIL") DO NOTHING;

-- Se ingresa con el correo y la contraseña. CLAVE guarda solo el hash bcrypt
-- de la contraseña, nunca la contraseña en texto plano.
CREATE TABLE IF NOT EXISTS public."USUARIOS" (
    "USUARIO"           text PRIMARY KEY,
    "NOMBRE"            text NOT NULL,
    "CORREO"            text NOT NULL,
    "CLAVE"             text NOT NULL,
    "PERFIL"            text NOT NULL REFERENCES public."PERFILES" ("PERFIL"),
    "ACTIVO"            boolean NOT NULL DEFAULT true,
    "FECHA_CREACION"    timestamptz NOT NULL DEFAULT now(),
    "USUARIO_ACTUALIZA" text,
    "FECHA_ACTUALIZA"   timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS "USUARIOS_CORREO" ON public."USUARIOS" (lower("CORREO"));

-- ============================================================
-- PRIMER USUARIO (administrador)
-- Cambie el nombre, el correo y la contraseña, y ejecute solo esta parte.
-- Los demás usuarios se crean desde la aplicación, en Usuarios.
--
-- INSERT INTO public."USUARIOS" ("USUARIO", "NOMBRE", "CORREO", "CLAVE", "PERFIL")
-- VALUES ('ADMIN', 'Nombre Apellido', 'correo@dominio.com',
--         crypt('contraseña segura', gen_salt('bf')), 'Administrador');
-- ============================================================

-- ============================================================
-- TAQUILLAS
-- ============================================================
CREATE TABLE IF NOT EXISTS public."TAQUILLAS" (
    "ID_TAQUILLA"       integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    "NOMBRE"            text NOT NULL,
    "UBICACION"         text,
    "ACTIVO"            boolean NOT NULL DEFAULT true,
    "FECHA_CREACION"    timestamptz NOT NULL DEFAULT now(),
    "USUARIO_ACTUALIZA" text,
    "FECHA_ACTUALIZA"   timestamptz NOT NULL DEFAULT now()
);

-- ============================================================
-- MANILLAS (conceptos que se venden en taquilla)
-- ============================================================
CREATE TABLE IF NOT EXISTS public."MANILLAS" (
    "ID_MANILLA"        integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    "NOMBRE"            text NOT NULL,
    "DESCRIPCION"       text,
    "ACTIVO"            boolean NOT NULL DEFAULT true,
    "FECHA_CREACION"    timestamptz NOT NULL DEFAULT now(),
    "USUARIO_ACTUALIZA" text,
    "FECHA_ACTUALIZA"   timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS "MANILLAS_NOMBRE" ON public."MANILLAS" (lower("NOMBRE"));

INSERT INTO public."MANILLAS" ("NOMBRE")
SELECT nombre FROM (VALUES
    (1, 'Adulto'), (2, 'Adulto Mayor'), (3, 'Niño'), (4, 'Combo Básico'), (5, 'Combo Infantil'),
    (6, 'Combo Junior'), (7, 'Pasaporte Full Vaquero'), (8, 'Paseo a caballo'), (9, 'Niño Cabrio'),
    (10, 'Tiro al blanco'), (11, 'Paseo en tren'), (12, 'Tirolesa'), (13, 'Cuatrimoto')
) AS m (orden, nombre)
WHERE NOT EXISTS (SELECT 1 FROM public."MANILLAS")
ORDER BY orden;

-- ============================================================
-- MANILLAS QUE VENDE CADA TAQUILLA
-- ============================================================
CREATE TABLE IF NOT EXISTS public."TAQUILLAS_MANILLAS" (
    "ID_TAQUILLA"       integer NOT NULL REFERENCES public."TAQUILLAS" ("ID_TAQUILLA") ON DELETE CASCADE,
    "ID_MANILLA"        integer NOT NULL REFERENCES public."MANILLAS" ("ID_MANILLA"),
    "USUARIO_ACTUALIZA" text,
    "FECHA_ACTUALIZA"   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY ("ID_TAQUILLA", "ID_MANILLA")
);
