import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "m4-tatica-secret")
    SQLALCHEMY_DATABASE_URI = "postgresql://neondb_owner:npg_qXEJL5vYs7Zz@ep-young-cake-ad2mlkly-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
