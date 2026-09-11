from decimal import Decimal, InvalidOperation
from io import BytesIO
from secrets import token_hex, compare_digest
from urllib.parse import urlparse
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, send_file, abort
from src.models.model_productos import Producto
from src.models.model_imagenes import ImagenProducto
from src.models.model_imagen_blob import ImagenBlob
from src.config.mysql_connection import get_mysql_connection
from src.controllers.auth_controller import login_required
from src.services import imagen_almacenamiento

productos_c = Blueprint('productos_c', __name__, template_folder='../templates')


def _info_tamano(imagen, idproducto, tamanos_blob):
  """Tamaños (y, si aplica, ruta en disco) a mostrar en la tabla: el binario
  en MySQL (<=1MB) no tiene ruta de archivo; lo guardado en disco sí."""
  imagen = imagen or {}
  almacenamiento = imagen.get('almacenamiento')
  tamano_mysql = tamano_original = tamano_comprimido = None
  if almacenamiento == 'mysql_blob' and idproducto is not None:
    fila_blob = tamanos_blob.get(idproducto)
    tamano_mysql = fila_blob['tamano_bytes'] if fila_blob else None
  elif almacenamiento in ('disco', 'disco_comprimido'):
    tamano_original = imagen.get('tamano_original_bytes')
    if almacenamiento == 'disco_comprimido':
      tamano_comprimido = imagen.get('tamano_comprimido_bytes')
  return dict(
    almacenamiento=almacenamiento,
    tamano_mysql_legible=imagen_almacenamiento.formatear_tamano(tamano_mysql),
    tamano_original_legible=imagen_almacenamiento.formatear_tamano(tamano_original),
    tamano_comprimido_legible=imagen_almacenamiento.formatear_tamano(tamano_comprimido),
    ruta_imagen=imagen.get('ruta_imagen'),
    ruta_imagen_comprimida=imagen.get('ruta_imagen_comprimida'),
  )


def unir_productos():
  productos = Producto.leer_productos()
  imagenes = ImagenProducto.leer_imagenes()
  tamanos_blob = ImagenBlob.leer_tamanos()
  usados = set()
  filas = []
  for producto in productos:
    coincidencias = [i for i in imagenes if i.get('idproducto') == producto['idproducto']]
    if not coincidencias:
      # Compatibilidad con los documentos originales, sin idproducto.
      candidatos = [i for i in imagenes if not i.get('idproducto') and
                    i.get('producto', '').strip().casefold() == producto['producto'].strip().casefold()]
      nombres = [p for p in productos if p['producto'].strip().casefold() == producto['producto'].strip().casefold()]
      if len(candidatos) == 1 and len(nombres) == 1:
        coincidencias = candidatos
    if len(coincidencias) > 1:
      raise ValueError('Hay documentos duplicados para un mismo idproducto. Corrige la relación antes de continuar.')
    imagen = coincidencias[0] if coincidencias else None
    if imagen:
      usados.add(imagen['_id'])
    filas.append(dict(producto, clave='sql-' + str(producto['idproducto']),
                      descripcion=(imagen or {}).get('descripcion', ''), url=(imagen or {}).get('url', ''),
                      documento=imagen, origen='MySQL + MongoDB' if imagen else 'Solo MySQL',
                      **_info_tamano(imagen, producto['idproducto'], tamanos_blob)))
  for imagen in imagenes:
    if imagen['_id'] not in usados:
      filas.append(dict(idproducto=None, clave='mongo-' + str(imagen['_id']), producto=imagen.get('producto', ''),
                        marca=imagen.get('marca', ''), precio=imagen.get('precio', ''),
                        descripcion=imagen.get('descripcion', ''), url=imagen.get('url', ''),
                        documento=imagen, origen='Solo MongoDB',
                        **_info_tamano(imagen, imagen.get('idproducto'), tamanos_blob)))
  return filas


@productos_c.route('/')
@productos_c.route('/productos')
@login_required
def obtener_productos():
  session.setdefault('csrf_token', token_hex(32))
  try:
    data = unir_productos()
    return render_template('productos.html', data=data)
  except Exception:
    current_app.logger.exception('No se pudieron consultar las bases de datos')
    flash('No se pudo cargar la tabla. Revisa las conexiones y la relación de los datos.', 'danger')
    return render_template('productos.html', data=[], error_carga=True), 503


@productos_c.route('/imagenes_productos')
@login_required
def obtener_imagenes():
  return obtener_productos()


def validar_datos(formulario):
  datos = {campo: formulario.get(campo, '').strip() for campo in ('producto', 'marca', 'precio', 'descripcion', 'url')}
  if not datos['producto'] or not datos['marca']:
    raise ValueError('Producto y marca son obligatorios.')
  if any(len(datos[campo]) > limite for campo, limite in [('producto', 200), ('marca', 200), ('descripcion', 2000), ('url', 2000)]):
    raise ValueError('Uno de los campos supera la longitud permitida.')
  try:
    precio = Decimal(datos['precio'])
    if not precio.is_finite() or precio < 0 or precio > Decimal('9999999999.99') or precio != precio.quantize(Decimal('0.01')):
      raise ValueError()
  except (InvalidOperation, ValueError):
    raise ValueError('El precio debe ser un número positivo o cero, con máximo dos decimales. No se permite texto.')
  datos['precio'] = precio
  if datos['url'] and (urlparse(datos['url']).scheme not in ('http', 'https') or not urlparse(datos['url']).netloc):
    raise ValueError('La URL de la imagen debe comenzar con http:// o https:// y tener un dominio.')
  return datos


_CAMPOS_IMAGEN = ('almacenamiento', 'ruta_imagen', 'ruta_imagen_comprimida',
                  'mime_original', 'tamano_original_bytes', 'tamano_comprimido_bytes')


def sincronizar(accion, fila, datos=None):
  connection = get_mysql_connection()
  anterior = fila.get('documento') if fila else None
  nuevo_id = None
  mongo_cambiado = False
  campos_imagen_nuevos = None
  documento = None
  try:
    connection.start_transaction()
    identificador = fila.get('idproducto') if fila else None
    if accion == 'eliminar':
      if identificador is not None:
        Producto.eliminar_producto(connection, identificador)
      if anterior:
        ImagenProducto.eliminar_imagen(anterior['_id'])
        imagen_almacenamiento.eliminar_blob_transaccional(connection, identificador, anterior)
        mongo_cambiado = True
    else:
      if identificador is None:
        identificador = Producto.insertar_producto(connection, datos)
      else:
        Producto.actualizar_producto(connection, identificador, datos)
      documento = dict(datos, idproducto=identificador, precio=str(datos['precio']))
      url_anterior = (anterior or {}).get('url', '')
      if datos['url'] and datos['url'] != url_anterior:
        # URL nueva o distinta a la guardada: se descarga y se bifurca por tamaño.
        campos_imagen_nuevos = imagen_almacenamiento.guardar_desde_url(connection, identificador, datos['url'])
        documento.update(campos_imagen_nuevos)
        # Si la imagen anterior vivía en MySQL y la nueva usa otro backend,
        # el blob viejo queda huérfano: se borra dentro de la misma
        # transacción (se revierte solo con el rollback de SQL).
        if anterior and anterior.get('almacenamiento') == 'mysql_blob' and campos_imagen_nuevos['almacenamiento'] != 'mysql_blob':
          imagen_almacenamiento.eliminar_blob_transaccional(connection, identificador, anterior)
      elif datos['url'] and anterior:
        # Misma URL de antes: se conserva la referencia ya procesada, sin
        # volver a descargar/cifrar en cada edición.
        for campo in _CAMPOS_IMAGEN:
          if campo in anterior:
            documento[campo] = anterior[campo]
      elif not datos['url'] and anterior and anterior.get('almacenamiento') == 'mysql_blob':
        # Se quitó la URL: también hay que soltar el blob de MySQL.
        imagen_almacenamiento.eliminar_blob_transaccional(connection, identificador, anterior)
      if anterior:
        ImagenProducto.actualizar_imagen(anterior['_id'], documento)
      else:
        nuevo_id = ImagenProducto.insertar_imagen(documento)
      mongo_cambiado = True
    connection.commit()
    # Ya confirmado el commit: recién ahora es seguro borrar archivos en
    # disco (irreversible). Antes del commit solo se tocó lo transaccional.
    if accion == 'eliminar' and anterior:
      imagen_almacenamiento.borrar_archivos_fisicos(anterior)
    elif anterior and documento and (anterior.get('ruta_imagen') != documento.get('ruta_imagen') or
                                      anterior.get('ruta_imagen_comprimida') != documento.get('ruta_imagen_comprimida')):
      imagen_almacenamiento.borrar_archivos_fisicos(anterior)
  except Exception:
    try:
      connection.rollback()
    finally:
      if campos_imagen_nuevos:
        # El archivo (si se llegó a escribir en disco) queda huérfano porque
        # la transacción no se confirmó: se borra como compensación.
        imagen_almacenamiento.deshacer_subida(campos_imagen_nuevos)
      if mongo_cambiado:
        try:
          if anterior:
            ImagenProducto.restaurar_imagen(anterior)
          elif nuevo_id is not None:
            ImagenProducto.eliminar_imagen(nuevo_id)
        except Exception:
          current_app.logger.exception('Fallo al compensar MongoDB; se requiere revisar ambas bases')
          raise RuntimeError('No se pudo recuperar la sincronización. Revisa ambas bases antes de reintentar.')
    raise
  finally:
    connection.close()


@productos_c.route('/productos/guardar', methods=['POST'])
@login_required
def guardar_producto():
  return modificar_producto('guardar')


@productos_c.route('/productos/eliminar', methods=['POST'])
@login_required
def eliminar_producto():
  return modificar_producto('eliminar')


def modificar_producto(accion):
  if not compare_digest(session.get('csrf_token', ''), request.form.get('csrf_token', '')) or not session.get('csrf_token'):
    flash('El formulario expiró. Recarga la página e inténtalo nuevamente.', 'danger')
    return redirect(url_for('productos_c.obtener_productos'))
  try:
    datos = validar_datos(request.form) if accion == 'guardar' else None
    clave = request.form.get('clave', '')
    fila = None
    if clave:
      fila = next((fila for fila in unir_productos() if fila['clave'] == clave), None)
      if fila is None:
        raise ValueError('El registro ya no existe. Recarga la tabla.')
    elif accion == 'eliminar':
      raise ValueError('Selecciona la fila que quieres eliminar.')
    sincronizar(accion, fila, datos)
    flash('Registro eliminado con éxito en ambas bases de datos.' if accion == 'eliminar' else
          'Registro guardado con éxito en MySQL y MongoDB.', 'success')
  except ValueError as error:
    flash(str(error), 'warning')
  except Exception:
    current_app.logger.exception('No se pudo completar la operación sincronizada')
    flash('No se pudo completar la operación en ambas bases. Revisa las conexiones y los registros del servidor antes de reintentar.', 'danger')
  return redirect(url_for('productos_c.obtener_productos'))


@productos_c.route('/imagenes/<clave>')
@login_required
def servir_imagen(clave):
  fila = next((fila for fila in unir_productos() if fila['clave'] == clave), None)
  documento = fila.get('documento') if fila else None
  if not documento or not documento.get('almacenamiento'):
    abort(404)
  try:
    contenido, mime = imagen_almacenamiento.leer_bytes(fila.get('idproducto'), documento)
  except ValueError as error:
    current_app.logger.exception('No se pudo servir la imagen de %s', clave)
    abort(404, str(error))
  respuesta = send_file(BytesIO(contenido), mimetype=mime)
  # Contenido autenticado: nunca en cachés compartidos/proxies.
  respuesta.headers['Cache-Control'] = 'private, no-store'
  return respuesta
