import os
from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv

load_dotenv()

_clave = os.getenv('FILE_ENCRYPTION_KEY')
_clave_generada = False
if not _clave:
  # Sin clave fija, se genera una temporal: los archivos que se cifren en este
  # proceso quedarán ilegibles en cuanto el servidor se reinicie (la clave se
  # pierde). Sirve para desarrollo; en cualquier entorno persistente hay que
  # definir FILE_ENCRYPTION_KEY con un valor fijo y secreto (ver README).
  _clave = Fernet.generate_key().decode()
  _clave_generada = True

_fernet = Fernet(_clave.encode() if isinstance(_clave, str) else _clave)


def clave_generada_temporalmente():
  return _clave_generada


def cifrar(datos: bytes) -> bytes:
  return _fernet.encrypt(datos)


def descifrar(datos: bytes) -> bytes:
  try:
    return _fernet.decrypt(datos)
  except InvalidToken:
    raise ValueError('No se pudo descifrar el archivo: la clave no coincide o el archivo está corrupto.')
