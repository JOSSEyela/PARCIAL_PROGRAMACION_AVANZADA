import io
import ipaddress
import os
import socket
import urllib.error
import urllib.request
import uuid
from urllib.parse import urlparse
from PIL import Image, UnidentifiedImageError
from src.utils.cifrado import cifrar, descifrar
from src.utils.compresion import comprimir_imagen
from src.models.model_imagen_blob import ImagenBlob

# Rutas relativas a la raíz del proyecto (no al directorio de trabajo actual),
# así funciona igual sin importar desde dónde se ejecute `python app.py`.
RAIZ_PROYECTO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CARPETA_IMGS = 'images'
CARPETA_COMPRIMIDAS = f'{CARPETA_IMGS}/images-compress'  # con "/" explícito: es una ruta de referencia (se guarda en Mongo), no una de sistema de archivos

LIMITE_MYSQL_BYTES = int(float(os.getenv('LIMITE_IMAGEN_MYSQL_MB', '1')) * 1024 * 1024)
LIMITE_DISCO_BYTES = int(float(os.getenv('LIMITE_IMAGEN_DISCO_MB', '3')) * 1024 * 1024)
LIMITE_DESCARGA_BYTES = int(float(os.getenv('LIMITE_DESCARGA_URL_MB', '15')) * 1024 * 1024)
TIMEOUT_DESCARGA_SEGUNDOS = float(os.getenv('TIMEOUT_DESCARGA_URL_SEGUNDOS', '10'))

_EXTENSION_POR_MIME = {
  'image/jpeg': '.jpg', 'image/jpg': '.jpg', 'image/png': '.png',
  'image/webp': '.webp', 'image/gif': '.gif', 'image/bmp': '.bmp',
}


def _extension(mime):
  return _EXTENSION_POR_MIME.get((mime or '').lower(), '.jpg')


class _SinRedirecciones(urllib.request.HTTPRedirectHandler):
  """Bloquea redirecciones: si se siguieran, una URL con apariencia pública
  podría reenviar a una dirección interna y burlar la validación de red."""
  def redirect_request(self, *args, **kwargs):
    raise ValueError('La URL respondió con una redirección; no se sigue por seguridad.')


_opener = urllib.request.build_opener(_SinRedirecciones)


def _validar_url_publica(url):
  partes = urlparse(url)
  if partes.scheme not in ('http', 'https') or not partes.hostname:
    raise ValueError('La URL debe ser http:// o https:// con un dominio válido.')
  try:
    infos = socket.getaddrinfo(partes.hostname, None)
  except socket.gaierror:
    raise ValueError('No se pudo resolver el dominio de la imagen.')
  for info in infos:
    ip = ipaddress.ip_address(info[4][0])
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
      raise ValueError('La URL de la imagen apunta a una red no permitida.')


def _descargar_url(url):
  """Descarga el contenido de una URL de imagen con límites de tamaño/tiempo
  y bloqueando redes privadas (mitigación básica de SSRF)."""
  _validar_url_publica(url)
  peticion = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
  try:
    with _opener.open(peticion, timeout=TIMEOUT_DESCARGA_SEGUNDOS) as respuesta:
      contenido = respuesta.read(LIMITE_DESCARGA_BYTES + 1)
      mime = (respuesta.headers.get_content_type() or '').lower()
  except urllib.error.URLError as error:
    raise ValueError(f'No se pudo descargar la imagen: {error}')
  if len(contenido) > LIMITE_DESCARGA_BYTES:
    raise ValueError(f'La imagen supera el límite de descarga ({LIMITE_DESCARGA_BYTES // (1024 * 1024)} MB).')
  # Se valida con Pillow que sea una imagen real (no confiar solo en el
  # Content-Type que reporte el servidor remoto).
  try:
    formato = Image.open(io.BytesIO(contenido)).format
  except (UnidentifiedImageError, OSError):
    raise ValueError('La URL no apunta a un archivo de imagen válido.')
  if not mime.startswith('image/'):
    mime = Image.MIME.get(formato, 'application/octet-stream')
  return contenido, mime


def _ruta_absoluta(ruta_relativa):
  # Las rutas se guardan con "/" inicial (p. ej. "/images/prueba.jpg"); se
  # normalizan antes de unirlas a la raíz del proyecto.
  return os.path.join(RAIZ_PROYECTO, ruta_relativa.lstrip('/\\'))


def _escribir_cifrado(ruta_relativa, contenido):
  ruta = _ruta_absoluta(ruta_relativa)
  os.makedirs(os.path.dirname(ruta), exist_ok=True)
  with open(ruta, 'wb') as archivo:
    archivo.write(cifrar(contenido))


def _borrar_archivo(ruta_relativa):
  if not ruta_relativa:
    return
  try:
    os.remove(_ruta_absoluta(ruta_relativa))
  except FileNotFoundError:
    pass


def _bifurcar_y_guardar(connection, idproducto, contenido, mime):
  """Bifurca el almacenamiento según el tamaño real del contenido ya
  descargado. `connection`: conexión MySQL abierta en la misma transacción
  del producto (necesaria solo para el caso <=1MB). Devuelve los campos a
  fusionar en el documento Mongo."""
  tamano = len(contenido)
  campos = dict(almacenamiento=None, ruta_imagen=None, ruta_imagen_comprimida=None,
                mime_original=mime, tamano_original_bytes=tamano, tamano_comprimido_bytes=None)

  if tamano <= LIMITE_MYSQL_BYTES:
    ImagenBlob.guardar(connection, idproducto, contenido, mime, tamano)
    campos['almacenamiento'] = 'mysql_blob'
    return campos

  if tamano <= LIMITE_DISCO_BYTES:
    ruta = f'/{CARPETA_IMGS}/{uuid.uuid4().hex}{_extension(mime)}'
    _escribir_cifrado(ruta, contenido)
    campos['almacenamiento'] = 'disco'
    campos['ruta_imagen'] = ruta
    return campos

  comprimido, mime_comprimido = comprimir_imagen(contenido, mime)
  ruta = f'/{CARPETA_COMPRIMIDAS}/{uuid.uuid4().hex}{_extension(mime_comprimido)}'
  _escribir_cifrado(ruta, comprimido)
  campos['almacenamiento'] = 'disco_comprimido'
  campos['ruta_imagen_comprimida'] = ruta
  campos['mime_original'] = mime_comprimido
  campos['tamano_comprimido_bytes'] = len(comprimido)
  return campos


def guardar_desde_url(connection, idproducto, url):
  """Descarga la imagen de `url` (con las validaciones de `_descargar_url`)
  y la bifurca según su tamaño real."""
  contenido, mime = _descargar_url(url)
  return _bifurcar_y_guardar(connection, idproducto, contenido, mime)


def eliminar_blob_transaccional(connection, idproducto, documento):
  """Parte reversible de la limpieza: el DELETE en MySQL vive en la misma
  transacción del producto y se revierte solo con el rollback de SQL."""
  if documento and documento.get('almacenamiento') == 'mysql_blob' and idproducto is not None:
    ImagenBlob.eliminar(connection, idproducto)


def borrar_archivos_fisicos(documento):
  """Parte NO reversible de la limpieza (borrado en disco). Llamar solo
  después de confirmar el commit de la transacción, nunca antes."""
  if not documento:
    return
  _borrar_archivo(documento.get('ruta_imagen'))
  _borrar_archivo(documento.get('ruta_imagen_comprimida'))


def deshacer_subida(campos):
  """Compensación si falla la escritura en Mongo/MySQL después de haber
  guardado el archivo en disco (no aplica a mysql_blob: esa escritura vive
  en la misma transacción SQL y se revierte con el rollback)."""
  if not campos:
    return
  _borrar_archivo(campos.get('ruta_imagen'))
  _borrar_archivo(campos.get('ruta_imagen_comprimida'))


def leer_bytes(idproducto, documento):
  """Devuelve (bytes_listos_para_servir, mime) para el endpoint protegido de
  descarga, descifrando en memoria sin persistir el resultado en disco."""
  almacenamiento = documento.get('almacenamiento')
  if almacenamiento == 'mysql_blob':
    fila = ImagenBlob.leer(idproducto)
    if not fila:
      raise ValueError('La imagen ya no existe en MySQL.')
    return fila['imagen'], fila['mime']
  ruta = documento.get('ruta_imagen_comprimida') if almacenamiento == 'disco_comprimido' else documento.get('ruta_imagen')
  if not ruta:
    raise ValueError('La imagen ya no existe en disco.')
  with open(_ruta_absoluta(ruta), 'rb') as archivo:
    cifrado = archivo.read()
  return descifrar(cifrado), documento.get('mime_original') or 'application/octet-stream'


def formatear_tamano(tamano_bytes):
  if tamano_bytes is None:
    return None
  if tamano_bytes < 1024 * 1024:
    return f'{tamano_bytes / 1024:.1f} KB'
  return f'{tamano_bytes / (1024 * 1024):.2f} MB'
