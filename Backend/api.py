import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from datetime import datetime, timedelta
import logging
import asyncio
from time import sleep
from functools import wraps
from typing import Tuple, Dict, Any, Optional
from contextlib import asynccontextmanager
from flask import Flask, request, jsonify, current_app, session, abort, make_response
from flask_cors import CORS
from flask_login import login_user, logout_user, login_required, current_user, LoginManager, UserMixin
from google.cloud.firestore_v1.base_query import FieldFilter
import zmq
import zmq.asyncio
import bcrypt
import re
from httpcodes import *
from Agents import AgentManager, Agent
from .app import *
from dotenv import load_dotenv
from Logger import LoggerManager
import threading
import time
import secrets
import inspect
import requests


# Collection name constants
COMPANY_DATA = 'CompanyData'
CONSULTANTS = 'Consultants'
USERS = 'Users'
TENDERS = 'Tenders'


# Initialize logger
logger = LoggerManager.get_logger(
    name='api',
    log_to_console=True,
    level=logging.INFO
)


class ZMQClientPool:
    def __init__(self, max_connections: int = 10, server_url: str = "tcp://localhost:5001"):
        self.max_connections = max_connections
        self.server_url = server_url
        self.pool = None
        self.context = None
        self._initialize_pool()

    def _initialize_pool(self):
        """Initialize the connection pool with ZMQ sockets"""
        self.context = zmq.asyncio.Context()
        self.pool = asyncio.Queue(maxsize=self.max_connections)
        
        for _ in range(self.max_connections):
            socket = self.context.socket(zmq.REQ)
            socket.connect(self.server_url)
            self.pool.put_nowait(socket)

    @asynccontextmanager
    async def get_connection(self):
        """Get a connection from the pool with automatic reconnection"""
        if self.pool is None or self.context is None:
            self._initialize_pool()
            
        socket = await self.pool.get()
        try:
            if not socket.closed:
                yield socket
            else:
                new_socket = self.context.socket(zmq.REQ)
                new_socket.connect(self.server_url)
                yield new_socket
        finally:
            if not socket.closed:
                await self.pool.put(socket)

    async def close(self):
        """Close all connections in the pool"""
        if self.pool is not None:
            while not self.pool.empty():
                socket = await self.pool.get()
                if not socket.closed:
                    socket.close()
        if self.context is not None:
            self.context.term()
        self.pool = None
        self.context = None


load_dotenv()
app = CreateApp()


CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:3000"],
        "methods": ["GET", "POST", "PUT", "DELETE"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})


context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.connect("tcp://localhost:5001")

_connection_pool_initialized = False

@app.before_request
def initialize_connection_pool():
    """Initialize the ZMQ connection pool when the first request is made"""
    global _connection_pool_initialized
    if not _connection_pool_initialized:
        app.connection_pool = ZMQClientPool()
        _connection_pool_initialized = True


@app.teardown_appcontext
async def cleanup(exception=None):
    """Cleanup resources when the application context is torn down"""
    if hasattr(current_app, 'connection_pool'):
        await current_app.connection_pool.close()


@app.login_manager.unauthorized_handler
def unauthorized():
    return jsonify({"message": "You must be logged in to access this resource."}), 401
# ------------------------------------------------------------------------------------------------------------- #
# --------------------------------------------- Request Functions --------------------------------------------- #
async def ServerRequest(command: str = None, params: dict = None) -> Tuple[Dict[str, Any], int]:
    try:
        command_obj = {
            'command': command,
            'params': params if params is not None else {}
        }
        
        logger.debug(f"Sending server request: {command}", extra={'command': command, 'params': params})
        
        async with current_app.connection_pool.get_connection() as socket:
            await socket.send_json(command_obj)
            backend_response = await socket.recv_json()
        
        logger.debug(f"Received server response: {backend_response}", extra={'response': backend_response})
        return jsonify(backend_response["data"]), backend_response.get("status_code", 200)
    except Exception as e:
        logger.error(f"Server request failed: {str(e)}", extra={'error': str(e), 'command': command})
        # If we get an event loop error, reinitialize the pool
        if "bound to a different event loop" in str(e):
            current_app.connection_pool._initialize_pool()
        return jsonify({"error": str(e)}), 500


async def DatabaseRequest(collection_name: str = None, data: dict = None, doc_id: str = None) -> Tuple[Dict[str, Any], int]:
    try:
        method_to_command = {
            'POST': 'create',
            'GET': 'read',
            'PUT': 'update',
            'DELETE': 'delete'
        }
        command = method_to_command.get(request.method)
        params = {
            'collection_name': collection_name,
            'document_data': data,
            'document_id': doc_id
        }
        return await ServerRequest(command, params)
    except Exception as e:
        logger.error(f"Database request failed: {str(e)}", extra={'error': str(e)})
        return jsonify({"error": str(e)}), 500


def ValidateModel(model_class):
    def decorator(func):
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                if request.method == 'GET':
                    return await func(*args, **kwargs)
                data = request.get_json()
                try:
                    model_instance = model_class(**data)
                    request.validated_data = model_instance.to_dict()
                except TypeError as e:
                    return http_400(f"Validation Error: {str(e)}")
                except ValueError as e:
                    return http_422(f"Data Error: {str(e)}")
                return await func(*args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                if request.method == 'GET':
                    return func(*args, **kwargs)
                data = request.get_json()
                try:
                    model_instance = model_class(**data)
                    request.validated_data = model_instance.to_dict()
                except TypeError as e:
                    return http_400(f"Validation Error: {str(e)}")
                except ValueError as e:
                    return http_422(f"Data Error: {str(e)}")
                return func(*args, **kwargs)
            return sync_wrapper
    return decorator


def ValidatePassword(password: str) -> bool:
    # Minimum 8 characters, at least one uppercase, one lowercase, one digit, one special character
    pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&#^()[\]{}<>.,;:|~`_+=-]).{8,}$'
    return bool(re.match(pattern, password))


def RoleRequired(*roles: str):
    """Decorator to require a user to have a specific role (or one of several roles), or be an Agent/AgentManager object."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Allow if current_user is Agent or AgentManager instance
            if (
                not hasattr(current_user, 'role') or
                (
                    current_user.role not in roles and
                    not isinstance(current_user, Agent) and
                    not isinstance(current_user, AgentManager)
                )
            ):
                return http_403(f"You do not have the required role: {roles} or Agent/AgentManager access")
            return await func(*args, **kwargs)
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            if (
                not hasattr(current_user, 'role') or
                (
                    current_user.role not in roles and
                    not isinstance(current_user, Agent) and
                    not isinstance(current_user, AgentManager)
                )
            ):
                return http_403(f"You do not have the required role: {roles} or Agent/AgentManager access")
            return func(*args, **kwargs)
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    return decorator

def BlockAgents(func):
    """Decorator to block access for Agent and AgentManager objects."""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        if isinstance(current_user, Agent) or isinstance(current_user, AgentManager):
            return http_403("Agent and AgentManager processes are not allowed to access this endpoint.")
        return await func(*args, **kwargs)
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        if isinstance(current_user, Agent) or isinstance(current_user, AgentManager):
            return http_403("Agent and AgentManager processes are not allowed to access this endpoint.")
        return func(*args, **kwargs)
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper
# ------------------------------------------------------------------------------------------------------------- #
# ---------------------------------------------- Route Functions ---------------------------------------------- #
@app.route('/api/status/server', methods=['GET'])
@login_required
async def ServerStatus() -> Tuple[Dict[str, Any], int]:
    return await ServerRequest('status')


@app.route('/api/status/api', methods=['GET'])
@login_required
async def ApiStatus() -> Tuple[Dict[str, Any], int]:
    return http_200('API is Online!')


@app.route('/api/user/register', methods=['POST'])
@BlockAgents
async def Register() -> Tuple[Dict[str, Any], int]:
    data = request.get_json()
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    role = data.get("role", "User")

    # Basic validation
    if not username or not email or not password:
        return http_400("Username, email, and password are required.")
    
    if not ValidatePassword(password):
        return http_400("Password must be at least 8 characters and include uppercase, lowercase, number, and symbol.")

    # Check if user already exists
    users_ref = current_app.db.collection(USERS)
    existing_users = list(users_ref.where(filter=FieldFilter('username', '==', username)).limit(1).stream())
    if existing_users:
        return http_409("Username already exists.")

    # Hash the password
    hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    # Generate a secure validation code
    validation_code = secrets.token_urlsafe(16)

    # Store user in Firestore with validated=False and validation_code
    user_data = {
        "username": username,
        "email": email,
        "password": hashed_pw,
        "validated": False,
        "validation_code": validation_code,
        "role": role
    }
    user_ref = users_ref.add(user_data)
    logger.info(f"User registered: {username}", extra={'user_id': user_ref[1].id})
    return jsonify({"message": "User registered successfully. Please validate your account.", "validation_code": validation_code}), 201


@app.route('/api/user/login', methods=['POST'])
@BlockAgents
async def Login() -> Tuple[Dict[str, Any], int]:
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return http_401("Username and password required.")

    # Use the User class's authenticate method
    user_obj = app.User.authenticate(username, password)
    if not user_obj:
        return http_401("Invalid credentials.")

    if not user_obj.validated:
        return http_401("Account not validated. Please validate your account.")

    login_user(user_obj)
    logger.info(f"User logged in: {username}", extra={'user_id': user_obj.id})
    return jsonify({"message": "Login successful"}), 200


@app.route('/api/user/logout', methods=['POST'])
@BlockAgents
@login_required
async def Logout() -> Tuple[Dict[str, Any], int]:
    logout_user()
    return jsonify({"message": "Successfully logged out"}), 200


@app.route('/api/user/profile', methods=['GET'])
@BlockAgents
@login_required
async def GetProfile():
    try:
        current_user_id = current_user.get_id()
        logger.info(f"Getting profile for user: {current_user_id}", extra={'user_id': current_user_id})
        return await DatabaseRequest(collection_name=USERS, data=None, doc_id=current_user_id)
    except Exception as e:
        logger.error(f"Get profile failed: {str(e)}", extra={'error': str(e)})
        return jsonify({"error": str(e)}), 500


@app.route('/api/user/update', methods=['PUT'])
@BlockAgents
@login_required
@ValidateModel(UserProfile)
async def UpdateProfile():
    try:
        current_user_id = current_user.get_id()
        data = request.validated_data

        if 'password' in data:
            data['password'] = bcrypt.hashpw(data['password'].encode(), bcrypt.gensalt()).decode()
        
        logger.info(f"Updating profile for user: {current_user_id}", extra={'user_id': current_user_id})
        return await DatabaseRequest(collection_name=USERS, data=data, doc_id=current_user_id)
    except Exception as e:
        logger.error(f"Update profile failed: {str(e)}", extra={'error': str(e)})
        return jsonify({"error": str(e)}), 500


@app.route('/api/user/delete', methods=['DELETE'])
@BlockAgents
@login_required
async def DeleteUser() -> Tuple[Dict[str, Any], int]:
    current_user_id = current_user.get_id()
    logger.info(f"Deleting user: {current_user_id}", extra={'user_id': current_user_id})
    return await DatabaseRequest(collection_name=USERS, data=None, doc_id=current_user_id)


@app.route('/api/user/delete_other', methods=['POST'])
@BlockAgents
@login_required
@RoleRequired('Admin')
async def DeleteOtherUser() -> Tuple[Dict[str, Any], int]:
    data = request.get_json()
    user_id = data.get("user_id")
    logger.info(f"Deleting user: {user_id}", extra={'user_id': user_id})
    return await DatabaseRequest(collection_name=USERS, data=None, doc_id=user_id)


@app.route('/api/user/validate', methods=['POST'])
@BlockAgents
async def ValidateUser() -> Tuple[Dict[str, Any], int]:
    data = request.get_json()
    email = data.get("email")
    code = data.get("validation_code")

    if not code or not email:
        return http_400("Invalid input: Email and validation code are required.")

    users_ref = current_app.db.collection(USERS)
    query = users_ref.where(filter=FieldFilter('email', '==', email)).limit(1)
    user_docs = list(query.stream())
    if not user_docs:
        return http_404("User not found.")
    user_doc = user_docs[0]
    user_data = user_doc.to_dict()
    if user_data.get("validated", False):
        return http_400("User already validated.")
    if user_data.get("validation_code") != code:
        return http_401("Invalid validation code.")
    # Set validated to True and remove validation_code
    user_doc.reference.update({"validated": True, "validation_code": firestore.DELETE_FIELD})
    logger.info(f"User validated: {user_doc.id}", extra={'user_id': user_doc.id})
    return jsonify({"msg": "User validated successfully."}), 200


@app.route('/api/user/get_role', methods=['GET'])
@login_required
async def GetRoles():
    return jsonify({"role": current_user.role}), 200


# ------------------------------------------------------------------------------------------------------------- #
# --------------------------------------------- Agent Management ---------------------------------------------- #
@app.route('/api/agents', methods=['POST', 'GET', 'DELETE'])
@login_required
@RoleRequired('Admin')
async def AgentManagement():
    try:
        if request.method == 'POST':
            # JSON example
            """
            {
                agent_type: "WebCrawler"
            }
            """
            return await ServerRequest(command='start_agent', params=request.get_json())

        elif request.method == 'GET':
            return await ServerRequest(command='get_agents')

        elif request.method == 'DELETE':
            # JSON example
            """
            {
                "agent_id": 1
            }
            """
            agent_id = request.get_json().get('agent_id')
            if not agent_id:
                return http_400("Missing agent_id parameter")
            
            return await ServerRequest(command='stop_agent', params={'agent_id': int(agent_id)})
    except Exception as e:
        logger.error(f"Agent management failed: {str(e)}", extra={'error': str(e)})
        return jsonify({"error": str(e)}), 500
# ------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------- Update Application --------------------------------------------- #
def GetLatestRelease():
    url = None
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data['tag_name'], data["assets"]
    return None, None


@app.route('/api/update_app', methods=['GET'])
def GetUpdate():
    # Create update directory in instance folder
    update_dir = os.path.join(app.instance_path, 'updates')
    os.makedirs(update_dir, exist_ok=True)
    
    # Version file path in update directory
    version_path = os.path.join(update_dir, 'version.txt')
    
    # Create version file if it doesn't exist
    if not os.path.exists(version_path):
        with open(version_path, 'w') as file:
            file.write('0.0.0')  # Initial version
    
    with open(version_path, 'r') as file:
        current_version = file.read().strip()
    
    latest_version, assets = GetLatestRelease()
    
    if latest_version and latest_version != current_version and len(assets) >= 1:
        # Find the main.py file in assets
        main_asset = next((asset for asset in assets if asset['name'] == 'main.py'), None)
        
        if not main_asset:
            return http_404("main.py not found in release assets")
        
        try:
            # Download main.py
            download_url = main_asset['browser_download_url']
            file_path = os.path.join(update_dir, 'main.py')
            
            # Stream download to handle large files
            with requests.get(download_url, stream=True) as response:
                response.raise_for_status()
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:  # Filter out keep-alive chunks
                            f.write(chunk)
            
            # Update version after successful download
            with open(version_path, 'w') as file:
                file.write(latest_version)
            
            return http_200({
                "status": "success",
                "version": latest_version,
                "downloaded_file": "main.py",
                "update_path": update_dir
            })
        except Exception as e:
            logger.error(f"Failed to download main.py: {str(e)}", extra={'error': str(e)})
            return http_500(f"Failed to download main.py: {str(e)}")
            
    return http_404("Update not found.")
# ------------------------------------------------------------------------------------------------------------- #
# -------------------------------------------- App Config & Startup -------------------------------- #
if __name__ == '__main__':
    import hypercorn.asyncio
    import hypercorn.config
    
    config = hypercorn.config.Config()
    config.bind = ["0.0.0.0:5000"]
    config.use_reloader = True

    asyncio.run(hypercorn.asyncio.serve(app, config))