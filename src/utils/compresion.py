import os
from io import BytesIO
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

# Configurables por variable de entorno: calidad de recodificación JPEG y el
# lado máximo (en píxeles) al que se reduce la imagen antes de cifrarla.
CALIDAD_COMPRESION = int(os.getenv('COMPRESION_CALIDAD', '75'))
LADO_MAXIMO = int(os.getenv('COMPRESION_LADO_MAXIMO', '1920'))


def comprimir_imagen(contenido: bytes, mime_original: str) -> tuple[bytes, str]:
  """Recomprime una imagen a JPEG, reduciendo calidad y resolución.
  Devuelve (bytes_comprimidos, mime_resultante). Si Pillow no logra
  decodificarla (formato no soportado), devuelve el contenido original sin
  comprimir en vez de fallar la subida."""
  try:
    imagen = Image.open(BytesIO(contenido))
    imagen.load()
  except Exception:
    return contenido, mime_original
  if imagen.mode not in ('RGB', 'L'):
    imagen = imagen.convert('RGB')
  imagen.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
  salida = BytesIO()
  imagen.save(salida, format='JPEG', quality=CALIDAD_COMPRESION, optimize=True)
  return salida.getvalue(), 'image/jpeg'
