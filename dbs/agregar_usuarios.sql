-- Migración incremental: NO recrea el esquema (a diferencia de mercancia.sql).
-- Ejecutar una sola vez sobre la base ya existente para habilitar el módulo de acceso.
USE mercancia;

CREATE TABLE IF NOT EXISTS usuario (
  user      VARCHAR(80)  PRIMARY KEY,
  password  VARCHAR(255) NOT NULL,
  creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
