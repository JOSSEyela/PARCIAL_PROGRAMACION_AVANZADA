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
MYSQL_PASSWORD, MYSQL_DATABASE, MONGO_URI, MONGO_DATABASE, SECRET_KEY,
SESSION_LIFETIME_HOURS, FILE_ENCRYPTION_KEY, MAX_UPLOAD_MB, LIMITE_IMAGEN_MYSQL_MB,
LIMITE_IMAGEN_DISCO_MB, LIMITE_DESCARGA_URL_MB, TIMEOUT_DESCARGA_URL_SEGUNDOS,
COMPRESION_CALIDAD y COMPRESION_LADO_MAXIMO.
Sin variables se mantienen los valores locales de la plantilla.

- `SECRET_KEY`: firma la cookie de sesión (login incluido). Si no se define,
  se genera una clave temporal en cada arranque y **todas las sesiones activas
  se invalidan al reiniciar el servidor** (queda registrado un warning en el
  log). En cualquier entorno persistente, fija un valor secreto y estable.
- `SESSION_LIFETIME_HOURS`: duración de la sesión antes de expirar (por
  defecto 8 horas).
- `FILE_ENCRYPTION_KEY`: clave simétrica (Fernet) para cifrar los archivos
  guardados en `/images`. Si no se define, se genera una temporal y **las
  imágenes cifradas en este proceso quedan ilegibles al reiniciar el
  servidor** (warning en el log). Generar una fija con:
  ```powershell
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
  y guardarla en `.env` como `FILE_ENCRYPTION_KEY=...`. Si se pierde o cambia,
  las imágenes ya guardadas en disco no se pueden recuperar.
- `MAX_UPLOAD_MB`: techo del cuerpo del formulario (por defecto 15 MB); las
  imágenes no viajan en el POST (se descargan aparte), esto solo cubre los
  campos de texto.
- `LIMITE_IMAGEN_MYSQL_MB` / `LIMITE_IMAGEN_DISCO_MB`: umbrales de la
  bifurcación de almacenamiento (por defecto 1 y 3 MB).
- `LIMITE_DESCARGA_URL_MB` / `TIMEOUT_DESCARGA_URL_SEGUNDOS`: techo de tamaño
  (por defecto 15 MB) y de tiempo (por defecto 10 s) al descargar la imagen
  de la URL que se ingresa en el formulario.
- `COMPRESION_CALIDAD` / `COMPRESION_LADO_MAXIMO`: calidad JPEG (por defecto
  75) y lado máximo en píxeles (por defecto 1920) al recomprimir imágenes
  mayores al umbral de disco.

## Acceso (login)

Antes de ver o modificar productos hace falta una cuenta:

1. Ejecutar `dbs/agregar_usuarios.sql` una sola vez (crea la tabla `usuario`;
   no toca las tablas existentes).
2. Ir a `/registro`, crear un usuario (usuario 3-80 caracteres, contraseña
   mínimo 8) — la contraseña se guarda con hash (`werkzeug.security`,
   `pbkdf2:sha256`), nunca en texto plano.
3. Iniciar sesión en `/login`.

La sesión es la cookie firmada nativa de Flask (sin JWT ni almacén de
sesiones aparte): el servidor firma `session['user']` con `SECRET_KEY` y la
valida en cada request; no hay forma de falsificarla sin conocer esa clave.
Todas las rutas de productos (`/`, `/productos`, `/imagenes_productos`,
`/productos/guardar`, `/productos/eliminar`) exigen sesión activa y
redirigen a `/login` si falta. `/logout` (botón "Cerrar sesión" en la
tabla) limpia la sesión.

## Bases existentes

No ejecutar `dbs/mercancia.sql` sobre datos existentes: el script original elimina
el esquema. Para conservar datos y habilitar centavos, ejecutar solamente
`dbs/actualizar_precio.sql`. Este ajuste ya se aplicó a la base local durante la implementación.
Para el módulo de acceso, ejecutar además `dbs/agregar_usuarios.sql` (ver sección "Acceso").
Para el pipeline de imágenes, ejecutar además `dbs/agregar_imagenes.sql` (ver sección
"Imágenes: almacenamiento híbrido y cifrado").

## Imágenes: almacenamiento híbrido y cifrado

La imagen se ingresa **por URL** (campo "URL de la imagen") — no hay subida de
archivo local. Al guardar, el propio servidor descarga esa URL y decide dónde
guardar el contenido según su tamaño real:

| Tamaño | Destino | Referencia en Mongo |
|---|---|---|
| ≤ 1 MB | Binario tal cual en MySQL (`producto_imagen_blob.imagen`, `MEDIUMBLOB`) | `almacenamiento = "mysql_blob"` |
| > 1 MB y ≤ 3 MB | Archivo en `/images/<uuid>.<ext>` | `ruta_imagen` (p. ej. `/images/3f2a...jpg`) |
| > 3 MB | Comprimido (Pillow, recodificado a JPEG) y guardado en `/images/images-compress/<uuid>.jpg` | `ruta_imagen_comprimida` |

Los archivos guardados en `/images` (y `/images/images-compress`) se cifran en
disco con Fernet (`FILE_ENCRYPTION_KEY`) — nunca se escribe una copia sin
cifrar, aunque el nombre conserve la extensión original (p. ej. `.jpg`) para
legibilidad; el contenido del archivo es el ciphertext, no la imagen en claro.
El binario en MySQL no pasa por este cifrado de archivo (queda protegido por
el acceso a la base).

**Descarga desde la URL** (`imagen_almacenamiento._descargar_url`): antes de
guardar nada se valida que el esquema sea `http`/`https`, se resuelve el
dominio y se rechaza si apunta a una IP privada/loopback/link-local
(mitigación básica de SSRF: evita que la URL apunte a `localhost` o a la red
interna del servidor), no se siguen redirecciones, se limita el tamaño de la
descarga (`LIMITE_DESCARGA_URL_MB`) y el tiempo de espera
(`TIMEOUT_DESCARGA_URL_SEGUNDOS`), y se valida con Pillow que el contenido
sea realmente una imagen antes de aceptarla.

**Servido protegido**: `GET /imagenes/<clave>` exige sesión activa, localiza el
documento, descifra en memoria (si aplica) y transmite el archivo con
`Cache-Control: private, no-store` (no se cachea en proxies compartidos). Si
la sesión no está activa, ese endpoint nunca entrega bytes de la imagen.

**Frontend**: en la tabla, las imágenes en MySQL o en disco (sin comprimir) se
muestran como `<img>` normal apuntando a ese endpoint. Cuando la imagen es la
versión comprimida (>3 MB), se muestra un botón "Ver imagen" en vez de
cargarla automáticamente. La columna "Tamaño" muestra el tamaño según dónde
vive la imagen —el binario de MySQL, o el tamaño en disco (con su ruta
`/images/...` debajo), o —cuando se comprimió— **tanto el tamaño original
como el comprimido**, uno junto al otro.

Si al editar dejas la misma URL de antes, no se vuelve a descargar (se
conserva la referencia ya procesada). Si cambias la URL, o si la imagen
anterior vivía en un backend distinto al nuevo (p. ej. de MySQL a disco), la
referencia vieja se limpia: el `DELETE` en MySQL viaja en la misma
transacción del producto (se revierte con el rollback); el borrado de
archivos en disco, al ser irreversible, solo ocurre después de confirmado el
commit. Si borras el campo URL, se suelta la imagen asociada.

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

## Verificar la conexión a MongoDB

Sin arrancar la app entera:

```powershell
python -c "from src.config.mongo_connection import get_mongo_connection; print(get_mongo_connection().command('ping'))"
```

Si imprime `{'ok': 1.0}`, la conexión funciona con el `MONGO_URI`/`MONGO_DATABASE`
que tengas en el entorno (o los valores por defecto: `mongodb://localhost:27017/`,
base `mercancia`). Si lanza una excepción (timeout, `ServerSelectionTimeoutError`,
error de autenticación), ahí está el problema — revisa que el servicio de Mongo
esté corriendo y que la URI sea correcta. También puedes confirmarlo dentro de
la propia app: si `/productos` carga la tabla sin el aviso rojo "No se pudieron
consultar las bases de datos", Mongo respondió correctamente (esa ruta ya
consulta Mongo en cada carga).

## Verificar

```powershell
python pruebas_crud.py
```

La prueba usa ambas bases reales, crea productos con un nombre temporal único y los
limpia al terminar. Comprueba crear, leer, editar, eliminar, validación, CSRF, documentos
originados en Mongo y recuperación ante fallos simulados de Mongo y del commit SQL.
Los errores simulados se imprimen intencionalmente en el registro del servidor.
Bootstrap necesita acceso al CDN para cargar sus estilos y modales.
