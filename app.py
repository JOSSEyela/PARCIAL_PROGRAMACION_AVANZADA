import os
from flask import Flask
from src.controllers.controller import productos_c

app = Flask(__name__, template_folder='src/templates')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY') or os.urandom(32)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024
app.register_blueprint(productos_c)

if __name__ == '__main__':
  app.run(debug=True)
