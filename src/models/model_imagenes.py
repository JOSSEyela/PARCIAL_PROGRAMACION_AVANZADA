from src.config.mongo_connection import get_mongo_connection


class ImagenProducto:

  
  def leer_imagenes():
    return list(get_mongo_connection().producto.find({}))

  
  def insertar_imagen(datos):
    return get_mongo_connection().producto.insert_one(datos).inserted_id

  
  def actualizar_imagen(identificador, datos):
    result = get_mongo_connection().producto.update_one({'_id': identificador}, {'$set': datos})
    if result.matched_count != 1:
      raise ValueError('El documento ya no existe. Recarga la tabla.')

  
  def eliminar_imagen(identificador):
    result = get_mongo_connection().producto.delete_one({'_id': identificador})
    if result.deleted_count != 1:
      raise ValueError('El documento ya no existe. Recarga la tabla.')

  
  def restaurar_imagen(documento):
    get_mongo_connection().producto.replace_one({'_id': documento['_id']}, documento, upsert=True)
