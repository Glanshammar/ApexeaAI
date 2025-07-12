import os
import sys
from pathlib import Path
import json
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.insert(0, root_dir)
sys.path.insert(0, current_dir)

from flask import Flask, jsonify
from flask_login import LoginManager, UserMixin
from typing import Optional, TYPE_CHECKING
import secrets
from datetime import datetime, timedelta
from flask import session
import time
from datetime import timedelta
from Backend.database import Database
from flask import current_app

"""
Configuration loading order for CreateApp:
1. If a config object is passed, use it (highest precedence)
2. If a config.yaml file exists in the project root, load and apply its values (except SECRET_KEY)
3. Set default values for any missing config keys

Supported config file formats: YAML (config.yaml)

This module also sets up Flask-Login and provides a User class for session management.

Example config.yaml:
  PERMANENT_SESSION_LIFETIME: 900  # in seconds (15 minutes)
  SESSION_COOKIE_SECURE: true
  SESSION_COOKIE_SAMESITE: "Strict"
  SESSION_COOKIE_HTTPONLY: true

Note: SECRET_KEY must NOT be set in config.yaml. It will always be randomly generated at runtime.
"""

def CreateApp(config=None):
    app = Flask(__name__)

    if config:
        app.config.from_object(config)
    else:
        # Only support YAML config
        root = Path(__file__).parent.parent
        config_yaml = root / 'config.yaml'
        loaded_config = {}
        if config_yaml.exists() and HAS_YAML:
            with config_yaml.open() as f:
                loaded_config = yaml.safe_load(f)
            # Ignore SECRET_KEY if present in config
            if 'SECRET_KEY' in loaded_config:
                print("WARNING: SECRET_KEY found in config.yaml but will be ignored. A random key will be generated at runtime.")
                loaded_config.pop('SECRET_KEY')
        if loaded_config:
            app.config.update(loaded_config)
    
    # Set defaults for any missing config keys
    app.config["SECRET_KEY"] = secrets.token_hex(32) # Always generate a random SECRET_KEY at runtime
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=15)
    app.config["SESSION_REFRESH_EACH_REQUEST"] = True
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SECURE", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Strict")

    # Initialize database
    cred_path = f'{os.path.dirname(os.path.dirname(__file__))}/firebase.json'
    app.config['db'] = Database(db_type='firestore', config=cred_path)

    # --- Flask-Login Setup ---
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'Login'  # type: ignore

    USERS = 'Users'

    class User(UserMixin):
        def __init__(
            self,
            user_id: str,
            username: str,
            email: str,
            validated: bool = False,
            role: str = 'User'
        ):
            self.id = user_id
            self.username = username
            self.email = email
            self.validated = validated
            self.role = role

        def get_id(self) -> str:
            return str(self.id)

        @classmethod
        def get(cls, user_id: str) -> Optional["User"]:           
            data = current_app.config['db'].get_by_id(USERS, user_id)
            if data:
                return cls(
                    user_id=user_id,
                    username=data.get('username'),
                    email=data.get('email'),
                    validated=data.get('validated', False),
                    role=data.get('role', 'User')
                )
            return None

        @classmethod
        def authenticate(cls, username: str, password: str) -> Optional["User"]:
            result = current_app.config['db'].authenticate_user(USERS, username, password)
            
            if result:
                user_id, user_data = result
                return cls(
                    user_id=user_id,
                    username=user_data.get('username'),
                    email=user_data.get('email'),
                    validated=user_data.get('validated', False),
                    role=user_data.get('role', 'User')
                )
            return None

    @login_manager.user_loader
    def load_user(user_id):
        return User.get(user_id)

    # Attach User class to app for import elsewhere
    app.config['User'] = User

    @app.before_request
    def enforce_absolute_session_timeout():
        now = int(time.time())
        if "session_start" not in session:
            session["session_start"] = now
        elif now - session["session_start"] > 12 * 3600:  # 12 hours
            session.clear()
            return jsonify({"message": "Session expired (absolute timeout). Please log in again."}), 401
        
    return app