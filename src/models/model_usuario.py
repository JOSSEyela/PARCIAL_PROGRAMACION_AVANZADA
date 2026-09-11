from werkzeug.security import generate_password_hash, check_password_hash
from src.config.mysql_connection import get_mysql_connection


class Usuario:


  def crear_usuario(user, password):
    connection = get_mysql_connection()
    try:
      with connection.cursor() as cursor:
        cursor.execute('SELECT user FROM usuario WHERE user=%s', (user,))
        if cursor.fetchone() is not None:
          raise ValueError('Ese usuario ya existe.')
        cursor.execute('INSERT INTO usuario (user, password) VALUES (%s, %s)',
                       (user, generate_password_hash(password)))
      connection.commit()
    finally:
      connection.close()


  def verificar_credenciales(user, password):
    connection = get_mysql_connection()
    try:
      with connection.cursor(dictionary=True) as cursor:
        cursor.execute('SELECT password FROM usuario WHERE user=%s', (user,))
        fila = cursor.fetchone()
    finally:
      connection.close()
    return fila is not None and check_password_hash(fila['password'], password)
