import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
USERNAME = os.environ.get("USERNAME", "admin")
PASSWORD = os.environ.get("PASSWORD", "password")
USERNAME2 = os.environ.get("USERNAME2", "")
PASSWORD2 = os.environ.get("PASSWORD2", "")
PORT = int(os.environ.get("PORT", 8080))
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PHOTOS_DIR = os.path.join(DATA_DIR, "photos")
THUMBNAILS_DIR = os.path.join(DATA_DIR, "thumbnails")
VIDEOS_DIR = os.path.join(DATA_DIR, "videos")
DISPLAY_DIR = os.path.join(DATA_DIR, "display")
DB_PATH = os.path.join(DATA_DIR, "photobook.db")
