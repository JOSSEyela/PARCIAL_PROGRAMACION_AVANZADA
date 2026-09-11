# Proyecto 4 — CRUD MySQL y MongoDB

Se conserva la estructura MVC: `src/controllers/controller.py` coordina las acciones;
`Producto` consulta MySQL e `ImagenProducto` consulta MongoDB. Las funciones
`obtener_productos`, `obtener_imagenes`, `leer_productos` y `leer_imagenes` se conservan.

## Ejecutar

Con Python instalado:

```powershell
python -m venv env
env\Scripts\Activate
pip install -r requirements.txt
python app.py
```

Abrir http://127.0.0.1:5000/productos. `/imagenes_productos` muestra el mismo CRUD.
El entorno `env` incluido apuntaba a un Python 3.12 que no está disponible en este equipo;
si sigue fallando, recrearlo con la instalación local de Python.

Las conexiones admiten variables de entorno: MYSQL_HOST, MYSQL_PORT, MYSQL_USER,
MYSQL_PASSWORD, MYSQL_DATABASE, MONGO_URI, MONGO_DATABASE y SECRET_KEY.
Sin variables se mantienen los valores locales de la plantilla.

## Bases existentes

No ejecutar `dbs/mercancia.sql` sobre datos existentes: el script original elimina
el esquema. Para conservar datos y habilitar centavos, ejecutar solamente
`dbs/actualizar_precio.sql`. Este ajuste ya se aplicó a la base local durante la implementación.

La tabla combina todas las filas y documentos. `idproducto` vincula ambas bases.
Los documentos originales sin ID se relacionan por nombre, sin distinguir mayúsculas,
solo cuando la coincidencia es única. Al guardar, el documento recibe su ID y los
campos del producto. Un registro que solo exista en una base aparece como pendiente;
al editarlo y guardarlo se crea su contraparte. No se inventan marcas ni precios.

## Comportamiento

- Agregar y editar guarda producto, marca y precio en MySQL; MongoDB almacena
  también descripción, URL e idproducto. El precio de Mongo se conserva como texto
  decimal exacto para evitar errores de coma flotante.
- Eliminar, después de confirmar en el modal, borra ambos registros vinculados.
- Bootstrap presenta acciones, validaciones y avisos de éxito o error.
- Las consultas SQL usan parámetros y los formularios incluyen protección CSRF.
- MySQL usa transacción; ante un error se revierte SQL y se intenta restaurar Mongo
  si ya se había modificado. No existe una transacción distribuida entre estos motores:
  una caída del proceso, una respuesta de red incierta o escrituras concurrentes externas
  pueden requerir reconciliación manual. Los fallos quedan registrados en el servidor.

La sincronización se realiza mediante este CRUD. Borrar o editar directamente con
Workbench, Compass o una consola no ejecuta el controlador y no se replica automáticamente.

## Verificar

```powershell
python pruebas_crud.py
```

La prueba usa ambas bases reales, crea productos con un nombre temporal único y los
limpia al terminar. Comprueba crear, leer, editar, eliminar, validación, CSRF, documentos
originados en Mongo y recuperación ante fallos simulados de Mongo y del commit SQL.
Los errores simulados se imprimen intencionalmente en el registro del servidor.
Bootstrap necesita acceso al CDN para cargar sus estilos y modales.
