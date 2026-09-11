import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
client = MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017/'), serverSelectionTimeoutMS=5000)


def get_mongo_connection():
  return client[os.getenv('MONGO_DATABASE', 'mercancia')]
