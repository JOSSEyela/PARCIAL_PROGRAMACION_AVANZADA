from src.config.mysql_connection import get_mysql_connection


class Producto:

  
  def leer_productos():
    connection = get_mysql_connection()
    try:
      with connection.cursor(dictionary=True) as cursor:
        cursor.execute('SELECT * FROM producto ORDER BY idproducto')
        return cursor.fetchall()
    finally:
      connection.close()

  
  def insertar_producto(connection, datos):
    with connection.cursor() as cursor:
      cursor.execute('INSERT INTO producto (producto, marca, precio) VALUES (%s, %s, %s)',
                     (datos['producto'], datos['marca'], datos['precio']))
      return cursor.lastrowid

  
  def actualizar_producto(connection, identificador, datos):
    with connection.cursor() as cursor:
      cursor.execute('SELECT idproducto FROM producto WHERE idproducto=%s FOR UPDATE', (identificador,))
      if cursor.fetchone() is None:
        raise ValueError('El producto ya no existe. Recarga la tabla.')
      cursor.execute('UPDATE producto SET producto=%s, marca=%s, precio=%s WHERE idproducto=%s',
                     (datos['producto'], datos['marca'], datos['precio'], identificador))

  
  def eliminar_producto(connection, identificador):
    with connection.cursor() as cursor:
      cursor.execute('DELETE FROM producto WHERE idproducto=%s', (identificador,))
      if cursor.rowcount != 1:
        raise ValueError('El producto ya no existe. Recarga la tabla.')
