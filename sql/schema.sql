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

-- ============================================================
-- INVENTARIO INICIAL DE MANILLAS POR TAQUILLA Y FECHA
-- ============================================================
CREATE TABLE IF NOT EXISTS public."INVENTARIO_INICIAL" (
    "FECHA"             date    NOT NULL,
    "ID_TAQUILLA"       integer NOT NULL REFERENCES public."TAQUILLAS" ("ID_TAQUILLA"),
    "ID_MANILLA"        integer NOT NULL REFERENCES public."MANILLAS" ("ID_MANILLA"),
    "CANTIDAD"          integer NOT NULL CHECK ("CANTIDAD" >= 0),
    "USUARIO_ACTUALIZA" text,
    "FECHA_ACTUALIZA"   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY ("FECHA", "ID_TAQUILLA", "ID_MANILLA")
);

-- ============================================================
-- CATEGORÍAS Y TIPOS DE TARIFA
-- ============================================================
CREATE TABLE IF NOT EXISTS public."CATEGORIAS" (
    "ID_CATEGORIA"      integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    "NOMBRE"            text        NOT NULL,
    "DESCRIPCION"       text,
    "ACTIVO"            boolean     NOT NULL DEFAULT true,
    "FECHA_CREACION"    timestamptz NOT NULL DEFAULT now(),
    "USUARIO_ACTUALIZA" text,
    "FECHA_ACTUALIZA"   timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS "CATEGORIAS_NOMBRE" ON public."CATEGORIAS" (lower("NOMBRE"));
INSERT INTO public."CATEGORIAS" ("NOMBRE")
SELECT n FROM unnest(ARRAY['Entradas','Combo','Atracciones']) AS n
WHERE NOT EXISTS (SELECT 1 FROM public."CATEGORIAS");

CREATE TABLE IF NOT EXISTS public."TIPOS_TARIFA" (
    "ID_TIPO"           integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    "NOMBRE"            text        NOT NULL,
    "DESCRIPCION"       text,
    "ACTIVO"            boolean     NOT NULL DEFAULT true,
    "FECHA_CREACION"    timestamptz NOT NULL DEFAULT now(),
    "USUARIO_ACTUALIZA" text,
    "FECHA_ACTUALIZA"   timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS "TIPOS_TARIFA_NOMBRE" ON public."TIPOS_TARIFA" (lower("NOMBRE"));
INSERT INTO public."TIPOS_TARIFA" ("NOMBRE")
SELECT n FROM unnest(ARRAY['Plena','Pleno','Convenio 1','Convenio 2','Descuento 50%','Cortesía']) AS n
WHERE NOT EXISTS (SELECT 1 FROM public."TIPOS_TARIFA");

-- ============================================================
-- TARIFAS POR TAQUILLA, MANILLA Y TIPO, CON VIGENCIA
-- ============================================================
CREATE TABLE IF NOT EXISTS public."TARIFAS" (
    "ID_TARIFA"         integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    "ID_CATEGORIA"      integer       NOT NULL REFERENCES public."CATEGORIAS" ("ID_CATEGORIA"),
    "ID_TAQUILLA"       integer       NOT NULL REFERENCES public."TAQUILLAS" ("ID_TAQUILLA"),
    "ID_MANILLA"        integer       NOT NULL REFERENCES public."MANILLAS" ("ID_MANILLA"),
    "ID_TIPO"           integer       NOT NULL REFERENCES public."TIPOS_TARIFA" ("ID_TIPO"),
    "VALOR"             numeric(12,2) NOT NULL CHECK ("VALOR" >= 0),
    "DESDE"             date          NOT NULL,
    "HASTA"             date          NOT NULL,
    "ACTIVO"            boolean       NOT NULL DEFAULT true,
    "FECHA_CREACION"    timestamptz   NOT NULL DEFAULT now(),
    "USUARIO_ACTUALIZA" text,
    "FECHA_ACTUALIZA"   timestamptz   NOT NULL DEFAULT now(),
    CHECK ("HASTA" >= "DESDE")
);
-- Una tarifa activa por taquilla, manilla y tipo en cada día: así en ventas
-- nunca hay dos precios posibles para el mismo tipo.
CREATE EXTENSION IF NOT EXISTS btree_gist;
-- Incluye la categoría: «Adulto · Plena» puede existir en Entradas y en Pase anual.
ALTER TABLE public."TARIFAS" DROP CONSTRAINT IF EXISTS "TARIFAS_SIN_CRUCE";
ALTER TABLE public."TARIFAS" ADD CONSTRAINT "TARIFAS_SIN_CRUCE" EXCLUDE USING gist (
    "ID_CATEGORIA" WITH =, "ID_TAQUILLA" WITH =, "ID_MANILLA" WITH =, "ID_TIPO" WITH =,
    daterange("DESDE", "HASTA", '[]') WITH &&
) WHERE ("ACTIVO");
-- Evita cargar dos veces exactamente la misma tarifa.
DROP INDEX IF EXISTS public."TARIFAS_UNICA";
CREATE UNIQUE INDEX "TARIFAS_UNICA"
    ON public."TARIFAS" ("ID_CATEGORIA", "ID_TAQUILLA", "ID_MANILLA", "ID_TIPO", "VALOR", "DESDE", "HASTA");

-- ============================================================
-- VENTAS DEL DÍA: cantidad vendida por taquilla y tarifa
-- (el valor unitario se guarda para que un cambio de tarifa no altere lo vendido)
-- ============================================================
CREATE TABLE IF NOT EXISTS public."VENTAS" (
    "FECHA"             date          NOT NULL,
    "ID_TAQUILLA"       integer       NOT NULL REFERENCES public."TAQUILLAS" ("ID_TAQUILLA"),
    "ID_TARIFA"         integer       NOT NULL REFERENCES public."TARIFAS" ("ID_TARIFA"),
    "ID_MANILLA"        integer       NOT NULL REFERENCES public."MANILLAS" ("ID_MANILLA"),
    "CANTIDAD"          integer       NOT NULL CHECK ("CANTIDAD" > 0),
    "VALOR_UNITARIO"    numeric(12,2) NOT NULL CHECK ("VALOR_UNITARIO" >= 0),
    "USUARIO_ACTUALIZA" text,
    "FECHA_ACTUALIZA"   timestamptz   NOT NULL DEFAULT now(),
    PRIMARY KEY ("FECHA", "ID_TAQUILLA", "ID_TARIFA")
);
CREATE INDEX IF NOT EXISTS "VENTAS_MANILLA" ON public."VENTAS" ("FECHA", "ID_TAQUILLA", "ID_MANILLA");

-- ============================================================
-- LIQUIDACIÓN (CIERRE DE CAJA) POR TAQUILLA Y FECHA
-- ============================================================
CREATE TABLE IF NOT EXISTS public."LIQUIDACIONES" (
    "FECHA"             date          NOT NULL,
    "ID_TAQUILLA"       integer       NOT NULL REFERENCES public."TAQUILLAS" ("ID_TAQUILLA"),
    "EFECTIVO"          numeric(12,2) NOT NULL DEFAULT 0 CHECK ("EFECTIVO" >= 0),
    "TARJETA"           numeric(12,2) NOT NULL DEFAULT 0 CHECK ("TARJETA" >= 0),
    "TRANSFERENCIA"     numeric(12,2) NOT NULL DEFAULT 0 CHECK ("TRANSFERENCIA" >= 0),
    "OTROS"             numeric(12,2) NOT NULL DEFAULT 0 CHECK ("OTROS" >= 0),
    "TOTAL_VENTAS"      numeric(12,2) NOT NULL DEFAULT 0,
    "OBSERVACION"       text,
    "CERRADA"           boolean       NOT NULL DEFAULT false,
    "USUARIO_ACTUALIZA" text,
    "FECHA_ACTUALIZA"   timestamptz   NOT NULL DEFAULT now(),
    PRIMARY KEY ("FECHA", "ID_TAQUILLA")
);

-- ============================================================
-- INVENTARIO GENERAL: ingresos de manillas al parque (compras, ajustes).
-- Las existencias = ingresos - vendidas (las ventas se descuentan solas).
-- ============================================================
CREATE TABLE IF NOT EXISTS public."INVENTARIO_GENERAL" (
    "ID_MOVIMIENTO"     integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    "FECHA"             date        NOT NULL,
    "ID_MANILLA"        integer     NOT NULL REFERENCES public."MANILLAS" ("ID_MANILLA"),
    "CANTIDAD"          integer     NOT NULL CHECK ("CANTIDAD" <> 0),
    "OBSERVACION"       text,
    "USUARIO_ACTUALIZA" text,
    "FECHA_ACTUALIZA"   timestamptz NOT NULL DEFAULT now()
);
