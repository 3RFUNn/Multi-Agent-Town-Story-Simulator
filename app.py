# app.py

import os
import json # Import the json library
from flask import Flask, send_from_directory
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_new_secret_key_for_the_refactor'
socketio = SocketIO(app, cors_allowed_origins="*")

STATIC_FOLDER = os.path.join(os.path.dirname(__file__), 'static')

# *** Load all map data from the JSON file into global variables ***
MAP_DATA_PATH = os.path.join(STATIC_FOLDER, 'map_data.json')
with open(MAP_DATA_PATH, 'r') as f:
    MAP_DATA = json.load(f)

MAP_LAYOUT = MAP_DATA['layout']
PLACES = MAP_DATA['places']

# FIX: Convert coordinate lists to tuples to make them hashable
for place_data in PLACES.values():
    place_data['coords'] = [tuple(coord) for coord in place_data['coords']]


@app.route('/')
def index():
    return send_from_directory(STATIC_FOLDER, 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    # This will now also serve our new map_data.json file
    return send_from_directory(STATIC_FOLDER, filename)

# Add this function to emit daily stories
def emit_daily_story(story_data):
    # story_data: {'day': day_name, 'text': story}
    emit('new_daily_story', story_data, broadcast=True)

# --- SocketIO Event Handlers ---
@socketio.on('connect')
def handle_connect():
    print('Client connected to server.')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected from server.')

@socketio.on('command_client_ready')
def handle_command_client_ready():
    emit('command_client_ready', {}, broadcast=True)

@socketio.on('simulation_state_update')
def handle_simulation_state_update(data):
    # Add the day of the week to the data sent to the client
    emit('simulation_state_update', data, broadcast=True)

@socketio.on('pause_simulation')
def handle_pause_simulation(data):
    emit('pause_simulation', data, broadcast=True)

@socketio.on('resume_simulation')
def handle_resume_simulation(data):
    emit('resume_simulation', data, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)