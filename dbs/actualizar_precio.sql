-- Ejecutar una sola vez sobre una base existente. No elimina registros.
USE mercancia;
ALTER TABLE producto MODIFY precio DECIMAL(12,2);
