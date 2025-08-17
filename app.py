# app.py
# Main Flask application for simulation backend and SocketIO server.
# Serves static files, handles real-time events, and loads map data.

import os
import json
from flask import Flask, send_from_directory
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_new_secret_key_for_the_refactor'
socketio = SocketIO(app, cors_allowed_origins="*")

STATIC_FOLDER = os.path.join(os.path.dirname(__file__), 'static')

# --- Map Data Loading ---
MAP_DATA_PATH = os.path.join(STATIC_FOLDER, 'map_data.json')
with open(MAP_DATA_PATH, 'r') as f:
    MAP_DATA = json.load(f)

MAP_LAYOUT = MAP_DATA['layout']
PLACES = MAP_DATA['places']

# Convert coordinate lists to tuples for hashability
for place_data in PLACES.values():
    place_data['coords'] = [tuple(coord) for coord in place_data['coords']]

@app.route('/')
def index():
    """Serves the main index.html page."""
    return send_from_directory(STATIC_FOLDER, 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    """Serves static files from the static directory."""
    return send_from_directory(STATIC_FOLDER, filename)

# --- SocketIO Event Handlers ---
def emit_daily_story(story_data):
    """Emits a new daily story to all connected clients."""
    socketio.emit('new_daily_story', story_data)

@socketio.on('connect')
def handle_connect():
    """Handles new client connections."""
    print('Client connected to server.')

@socketio.on('disconnect')
def handle_disconnect():
    """Handles client disconnections."""
    print('Client disconnected from server.')

@socketio.on('command_client_ready')
def handle_command_client_ready():
    """Broadcasts when the command client is ready."""
    emit('command_client_ready', {}, broadcast=True)

@socketio.on('simulation_state_update')
def handle_simulation_state_update(data):
    """Broadcasts simulation state updates to all clients."""
    emit('simulation_state_update', data, broadcast=True)

@socketio.on('pause_simulation')
def handle_pause_simulation(data):
    """Broadcasts simulation pause events."""
    emit('pause_simulation', data, broadcast=True)

@socketio.on('resume_simulation')
def handle_resume_simulation(data):
    """Broadcasts simulation resume events."""
    emit('resume_simulation', data, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)