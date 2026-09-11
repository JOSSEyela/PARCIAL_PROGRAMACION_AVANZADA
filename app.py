import os
from datetime import timedelta
from flask import Flask
from src.controllers.controller import productos_c
from src.controllers.auth_controller import auth_c

app = Flask(__name__, template_folder='src/templates')

secret_key = os.getenv('SECRET_KEY')
if not secret_key:
  # Sin SECRET_KEY fija, las sesiones (login incluido) se invalidan en cada
  # reinicio del proceso. Sirve para desarrollo; en producción define la
  # variable de entorno con un valor fijo y secreto.
  secret_key = os.urandom(32)
  app.logger.warning('SECRET_KEY no está definida: se generó una clave temporal, las sesiones no sobrevivirán a un reinicio.')
app.config['SECRET_KEY'] = secret_key

# Techo global de subida (evita payloads abusivos); la bifurcación real
# 1MB/3MB/comprimido se decide después, por el tamaño real del archivo.
app.config['MAX_CONTENT_LENGTH'] = int(float(os.getenv('MAX_UPLOAD_MB', '15')) * 1024 * 1024)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=float(os.getenv('SESSION_LIFETIME_HOURS', '8')))

app.register_blueprint(productos_c)
app.register_blueprint(auth_c)

if __name__ == '__main__':
  app.run(debug=True)
