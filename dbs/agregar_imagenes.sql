-- Migración incremental: NO recrea el esquema. Ejecutar una sola vez.
-- Guarda el binario de las imágenes <= 1 MB (las mayores viven cifradas en
-- disco, con su ruta y tamaño referenciados desde MongoDB).
USE mercancia;

CREATE TABLE IF NOT EXISTS producto_imagen_blob (
  idproducto   INT PRIMARY KEY,
  imagen       MEDIUMBLOB NOT NULL,
  mime         VARCHAR(100) NOT NULL,
  tamano_bytes INT NOT NULL,
  creado_en    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (idproducto) REFERENCES producto(idproducto) ON DELETE CASCADE
);
