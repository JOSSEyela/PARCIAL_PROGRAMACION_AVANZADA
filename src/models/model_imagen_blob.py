from src.config.mysql_connection import get_mysql_connection


class ImagenBlob:


  def guardar(connection, idproducto, imagen, mime, tamano_bytes):
    with connection.cursor() as cursor:
      cursor.execute(
        'INSERT INTO producto_imagen_blob (idproducto, imagen, mime, tamano_bytes) VALUES (%s, %s, %s, %s) '
        'ON DUPLICATE KEY UPDATE imagen=VALUES(imagen), mime=VALUES(mime), tamano_bytes=VALUES(tamano_bytes)',
        (idproducto, imagen, mime, tamano_bytes))


  def eliminar(connection, idproducto):
    with connection.cursor() as cursor:
      cursor.execute('DELETE FROM producto_imagen_blob WHERE idproducto=%s', (idproducto,))


  def leer(idproducto):
    connection = get_mysql_connection()
    try:
      with connection.cursor(dictionary=True) as cursor:
        cursor.execute('SELECT imagen, mime, tamano_bytes FROM producto_imagen_blob WHERE idproducto=%s', (idproducto,))
        return cursor.fetchone()
    finally:
      connection.close()


  def leer_tamanos():
    """{idproducto: {'mime': ..., 'tamano_bytes': ...}} para todas las filas,
    usado para mostrar el tamaño en la tabla sin traer el binario completo."""
    connection = get_mysql_connection()
    try:
      with connection.cursor(dictionary=True) as cursor:
        cursor.execute('SELECT idproducto, mime, tamano_bytes FROM producto_imagen_blob')
        return {fila['idproducto']: fila for fila in cursor.fetchall()}
    finally:
      connection.close()
