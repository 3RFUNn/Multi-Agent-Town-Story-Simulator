# app.py

import os
from flask import Flask, send_from_directory
from flask_socketio import SocketIO, emit

# Initialize the Flask application
app = Flask(__name__)
# IMPORTANT: Use a strong, unique secret key in a real application!
app.config['SECRET_KEY'] = 'a_new_secret_key_for_the_refactor'
socketio = SocketIO(app, cors_allowed_origins="*")

# Define the directory where your HTML, CSS, and JS files are located
STATIC_FOLDER = os.path.join(os.path.dirname(__file__), 'static')

# --- Data (This is now just for reference for the map dimensions) ---
# The canonical data now lives in simulation/config.py
MAP_LAYOUT = [
    ['G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
    ['G', 'O', 'O', 'O', 'O', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'L', 'L', 'L', 'L', 'L', 'P', 'P', 'P', 'P', 'P', 'P', 'G'],
    ['G', 'O', 'O', 'O', 'O', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'P', 'L', 'L', 'L', 'L', 'L', 'P', 'G', 'G', 'G', 'G', 'P', 'G'],
    ['G', 'O', 'O', 'O', 'O', 'P', 'G', 'B', 'B', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'P', 'L', 'L', 'L', 'L', 'L', 'P', 'G', 'G', 'G', 'G', 'P', 'G'],
    ['G', 'P', 'P', 'P', 'P', 'P', 'G', 'B', 'B', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'G', 'G', 'G', 'G', 'P', 'G'],
    ['G', 'P', 'G', 'G', 'G', 'G', 'G', 'P', 'P', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'P', 'G'],
    ['G', 'P', 'G', 'C', 'C', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'P', 'G'],
    ['G', 'P', 'G', 'C', 'C', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'P', 'G'],
    ['G', 'P', 'P', 'P', 'P', 'P', 'G', 'F', 'F', 'F', 'F', 'F', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'P', 'G'],
    ['G', 'P', 'G', 'G', 'G', 'G', 'G', 'F', 'F', 'F', 'F', 'F', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'P', 'G'],
    ['G', 'P', 'G', 'K', 'K', 'K', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'G'],
    ['G', 'P', 'G', 'K', 'K', 'K', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
    ['G', 'P', 'G', 'K', 'K', 'K', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
    ['G', 'P', 'G', 'H', 'H', 'H', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
    ['G', 'P', 'G', 'H', 'H', 'H', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
    ['G', 'P', 'G', 'H', 'H', 'H', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
    ['G', 'P', 'P', 'P', 'P', 'P', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
    ['G', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
    ['G', 'P', 'G', 'D', 'D', 'D', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
    ['G', 'P', 'G', 'D', 'D', 'D', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
    ['G', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'G'],
    ['G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G']
]

# --- Flask Routes ---
@app.route('/')
def index():
    """Serves the main index.html file."""
    return send_from_directory(STATIC_FOLDER, 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    """Serves other static files (like CSS and JS)."""
    return send_from_directory(STATIC_FOLDER, filename)


# --- SocketIO Event Handlers ---

@socketio.on('connect')
def handle_connect():
    """Handles a new client connection."""
    print('Client connected to server.')
    emit('log_message', {'message': 'Python backend (app.py) connected!'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handles a client disconnection."""
    print('Client disconnected from server.')

@socketio.on('command_client_ready')
def handle_command_client_ready():
    """
    Receives the readiness signal from command.py and relays it to all
    frontend clients so they can start their simulation loops.
    """
    print("Relaying 'command_client_ready' signal to frontend.")
    emit('command_client_ready', {}, broadcast=True)

@socketio.on('simulation_state_update')
def handle_simulation_state_update(data):
    """
    Receives the full agent state update from command.py and broadcasts
    it to all frontend clients.
    """
    emit('simulation_state_update', data, broadcast=True)

@socketio.on('execute_commands')
def handle_execute_commands(data):
    """
    Receives a list of low-level commands from command.py and broadcasts
    them to all frontend clients for execution.
    """
    emit('execute_commands', data, broadcast=True)


if __name__ == '__main__':
    print(f"Serving files from: {STATIC_FOLDER}")
    print("Open your browser and navigate to http://127.0.0.1:5000/")
    print("Run 'command.py' in a separate terminal to start the simulation.")
    # The 'allow_unsafe_werkzeug' is for development auto-reloading with threads.
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)