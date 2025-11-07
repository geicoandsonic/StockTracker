import os
import secrets

class Config:
    # SQLite database by default
    SQLALCHEMY_DATABASE_URI = 'sqlite:///stock_tracker.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Add a secret key for session security and flash messages
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(16)