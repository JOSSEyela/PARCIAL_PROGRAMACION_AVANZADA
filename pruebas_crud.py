"""Prueba de integración: crea datos temporales y los limpia al terminar.
Ejecutar: python pruebas_crud.py (requiere ambas bases disponibles).
"""
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch
from app import app
from src.config.mysql_connection import get_mysql_connection
from src.config.mongo_connection import get_mongo_connection
from src.controllers.controller import unir_productos
from src.models.model_imagenes import ImagenProducto


def probar():
  nombre = '__prueba_crud_' + uuid4().hex
  mongo = get_mongo_connection().producto
  client = app.test_client()
  datos = dict(producto=nombre, marca='Prueba', precio='19.95', descripcion='Temporal', url='')
  try:
    assert client.get('/productos').status_code == 200
    assert client.get('/imagenes_productos').status_code == 200
    with client.session_transaction() as sesion:
      datos['csrf_token'] = sesion['csrf_token']
    assert client.post('/productos/guardar', data={**datos, 'csrf_token': ''}).status_code == 302
    assert mongo.count_documents({'producto': nombre}) == 0
    for invalido in ('texto', '-1', 'NaN', 'Infinity', '1.234', '10000000000'):
      client.post('/productos/guardar', data={**datos, 'precio': invalido})
      assert mongo.count_documents({'producto': nombre}) == 0
    client.post('/productos/guardar', data=datos)
    fila = next(p for p in unir_productos() if p['producto'] == nombre)
    assert fila['precio'] == Decimal('19.95') and fila['origen'] == 'MySQL + MongoDB'
    assert mongo.find_one({'producto': nombre})['idproducto'] == fila['idproducto']
    datos['clave'] = fila['clave']
    datos['precio'] = '27.50'
    client.post('/productos/guardar', data=datos)
    assert next(p for p in unir_productos() if p['producto'] == nombre)['precio'] == Decimal('27.50')
    assert mongo.find_one({'producto': nombre})['precio'] == '27.50'
    # El error de Mongo revierte la modificación SQL.
    with patch.object(ImagenProducto, 'actualizar_imagen', side_effect=RuntimeError('Fallo simulado')):
      client.post('/productos/guardar', data={**datos, 'precio': '99.00'})
    assert next(p for p in unir_productos() if p['producto'] == nombre)['precio'] == Decimal('27.50')
    # Un commit SQL fallido después de escribir Mongo restaura el documento anterior.
    connection = get_mysql_connection()
    class CommitFallido:
      def __getattr__(self, atributo): return getattr(connection, atributo)
      def commit(self): raise RuntimeError('Fallo de commit simulado')
    with patch('src.controllers.controller.get_mysql_connection', return_value=CommitFallido()):
      client.post('/productos/guardar', data={**datos, 'precio': '88.00'})
    assert mongo.find_one({'producto': nombre})['precio'] == '27.50'
    assert next(p for p in unir_productos() if p['producto'] == nombre)['precio'] == Decimal('27.50')
    client.post('/productos/eliminar', data=datos)
    assert not any(p['producto'] == nombre for p in unir_productos())
    # Un documento originado en Mongo se completa en MySQL al guardar.
    identificador = mongo.insert_one({'producto': nombre, 'descripcion': 'Solo Mongo', 'url': ''}).inserted_id
    datos['clave'] = 'mongo-' + str(identificador)
    client.post('/productos/guardar', data=datos)
    assert next(p for p in unir_productos() if p['producto'] == nombre)['origen'] == 'MySQL + MongoDB'
    # La misma acción de eliminación funciona desde la clave del documento.
    # Después de vincular, la tabla utiliza la clave SQL común.
    datos['clave'] = next(p for p in unir_productos() if p['producto'] == nombre)['clave']
    client.post('/productos/eliminar', data=datos)
    assert mongo.count_documents({'producto': nombre}) == 0
    identificador = mongo.insert_one({'producto': nombre, 'url': ''}).inserted_id
    client.post('/productos/eliminar', data={**datos, 'clave': 'mongo-' + str(identificador)})
    assert not any(p['producto'] == nombre for p in unir_productos())
    print('OK: vistas, CSRF, validaciones, crear, editar, eliminar, origen Mongo, rollback y compensación.')
  finally:
    mongo.delete_many({'producto': nombre})
    connection = get_mysql_connection()
    try:
      with connection.cursor() as cursor:
        cursor.execute('DELETE FROM producto WHERE producto=%s', (nombre,))
      connection.commit()
    finally:
      connection.close()


if __name__ == '__main__':
  probar()
