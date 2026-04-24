import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "bonsai-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "bonsai.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    CLOUDINARY_CLOUD_NAME = "daytrfyrg"
    CLOUDINARY_API_KEY = "784438178628159"
    CLOUDINARY_API_SECRET = "DHKWrW5-kS_ItxG1TibCZNEnGgM"
