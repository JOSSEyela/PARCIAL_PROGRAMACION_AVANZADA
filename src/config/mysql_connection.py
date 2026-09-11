import os

import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def get_mysql_connection():
  return mysql.connector.connect(
    host=os.getenv('MYSQL_HOST', 'localhost'),
    port=int(os.getenv('MYSQL_PORT', '3306')),
    user=os.getenv('MYSQL_USER', 'root'),
    password=os.getenv('MYSQL_PASSWORD', '123456'),
    database=os.getenv('MYSQL_DATABASE', 'mercancia'),
    charset='utf8mb4',
    connection_timeout=5,
  )
