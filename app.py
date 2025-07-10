import os
from flask import Flask, send_from_directory, jsonify
from flask_socketio import SocketIO, emit
import random

# Initialize the Flask application
app = Flask(__name__)
# Configure SocketIO
app.config['SECRET_KEY'] = 'your_secret_key_here' # IMPORTANT: Change this to a strong, unique secret key!
socketio = SocketIO(app, cors_allowed_origins="*") # Allow all origins for development, adjust for production

# Define the directory where your HTML, CSS, and JS files are located
STATIC_FOLDER = os.path.join(os.path.dirname(__file__), 'static')

# Ensure the static directory exists (useful for initial setup)
if not os.path.exists(STATIC_FOLDER):
    os.makedirs(STATIC_FOLDER)

# --- Map and Places Data (duplicated from frontend for pathfinding in Python) ---
# This data MUST be consistent across app.py, command.py, and script.js
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
    ['G', 'P', 'G', 'H', 'H', 'H', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'], # Changed P to H for (3,13) to (5,13)
    ['G', 'P', 'G', 'H', 'H', 'H', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
    ['G', 'P', 'G', 'H', 'H', 'H', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
    ['G', 'P', 'P', 'P', 'P', 'P', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
    ['G', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
    ['G', 'P', 'G', 'D', 'D', 'D', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
    ['G', 'P', 'G', 'D', 'D', 'D', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
    ['G', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'G'],
    ['G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G']
]

MAP_ROWS = len(MAP_LAYOUT)
MAP_COLS = len(MAP_LAYOUT[0])

PLACES = {
    'co_living_space': {'type': 'Co-Living Space', 'name': 'Co-Living Space', 'coords': [[1,1],[2,1],[3,1],[4,1],[1,2],[2,2],[3,2],[4,2],[1,3],[2,3],[3,3],[4,3]]},
    'bar_hobbs': {'type': 'Bar', 'name': 'Hobbs Bar', 'coords': [[7,3],[8,3],[7,4],[8,4]]},
    'cafe_hobbs': {'type': 'Cafe', 'name': 'Hobbs Cafe', 'coords': [[3,6],[4,6],[3,7],[4,7]]},
    'supply_store_harvey': {'type': 'Supply Store', 'name': 'Harvey Oak Supply Store', 'coords': [[6,1],[7,1],[6,2],[7,2]]},
    'college_oak_hill': {'type': 'College', 'name': 'Oak Hill College', 'coords': [[18,1],[19,1],[20,1],[21,1],[22,1],[18,2],[19,2],[20,2],[21,2],[22,2],[18,3],[19,3],[20,3],[21,3],[22,3]]},
    'grocery_pharmacy_willow': {'type': 'Grocery & Pharmacy', 'name': 'Willow Market and Pharmacy', 'coords': [[7,8],[8,8],[9,8],[10,8],[11,8],[7,9],[8,9],[9,9],[10,9],[11,9]]},
    'johnson_park': {'type': 'Park', 'name': 'Johnson Park', 'coords': [[3,10],[4,10],[5,10],[3,11],[4,11],[5,11],[3,12],[4,12],[5,12]]},
    'main_house': {'type': 'House', 'name': 'Main House Area', 'coords': [[3,13],[4,13],[5,13],[3,14],[4,14],[5,14],[3,15],[4,15],[5,15]]}, # Consolidated house area
    'college_dorm_main': {'type': 'College Dorm', 'name': 'Main College Dorm', 'coords': [[3,18],[4,18],[5,18],[3,19],[4,19],[5,19]]},
}

# Initial agent data (must be consistent with script.js and command.py)
AGENTS_INITIAL_STATE = [
    {'id': 'emily', 'name': 'Emily Carter', 'x': 3, 'y': 14, 'icon': 'EC', 'color': '#FF69B4', 'currentAction': 'At home', 'home': {'x': 3, 'y': 14}, 'destination': None, 'path': [], 'pathIndex': 0, 'isMoving': False, 'state': 'idle', 'actionEndTime': 0},
    {'id': 'sophia', 'name': 'Sophia Reyes', 'x': 3, 'y': 6, 'icon': 'SR', 'color': '#8A2BE2', 'currentAction': 'At home', 'home': {'x': 3, 'y': 6}, 'destination': None, 'path': [], 'pathIndex': 0, 'isMoving': False, 'state': 'idle', 'actionEndTime': 0},
    {'id': 'mia', 'name': 'Mia Bennett', 'x': 24, 'y': 14, 'icon': 'MB', 'color': '#DAA520', 'currentAction': 'At home', 'home': {'x': 24, 'y': 14}, 'destination': None, 'path': [], 'pathIndex': 0, 'isMoving': False, 'state': 'idle', 'actionEndTime': 0},
    {'id': 'ryan', 'name': 'Ryan Cooper', 'x': 24, 'y': 1, 'icon': 'RC', 'color': '#00CED1', 'currentAction': 'At home', 'home': {'x': 24, 'y': 1}, 'destination': None, 'path': [], 'pathIndex': 0, 'isMoving': False, 'state': 'idle', 'actionEndTime': 0},
    {'id': 'daniel', 'name': 'Daniel Park', 'x': 3, 'y': 18, 'icon': 'DP', 'color': '#FF4500', 'currentAction': 'At home', 'home': {'x': 3, 'y': 18}, 'destination': None, 'path': [], 'pathIndex': 0, 'isMoving': False, 'state': 'idle', 'actionEndTime': 0},
    {'id': 'lucas', 'name': 'Lucas Brooks', 'x': 18, 'y': 1, 'icon': 'LB', 'color': '#32CD32', 'currentAction': 'At home', 'home': {'x': 18, 'y': 1}, 'destination': None, 'path': [], 'pathIndex': 0, 'isMoving': False, 'state': 'idle', 'actionEndTime': 0}
]

# --- Python Pathfinding (BFS) ---
def is_valid(x, y):
    return 0 <= x < MAP_COLS and 0 <= y < MAP_ROWS

def is_traversable(x, y):
    if not is_valid(x, y):
        return False
    cell_type = MAP_LAYOUT[y][x]
    return cell_type in ['P', 'G', 'H', 'C', 'K', 'S', 'L', 'F', 'D', 'B', 'O']

def find_path_python(start_x, start_y, target_x, target_y):
    if not is_traversable(start_x, start_y) or not is_traversable(target_x, target_y):
        return []
    if start_x == target_x and start_y == target_y:
        return [[target_x, target_y]]

    queue = []
    visited = set()
    parent_map = {}

    queue.append((start_x, start_y))
    visited.add((start_x, start_y))
    parent_map[(start_x, start_y)] = None

    directions = [
        (0, 1), (0, -1), (1, 0), (-1, 0)
    ]

    while queue:
        current_x, current_y = queue.pop(0)

        if current_x == target_x and current_y == target_y:
            path = []
            curr = (target_x, target_y)
            while curr is not None:
                path.insert(0, list(curr))
                curr = parent_map.get(curr)
            return path

        for dx, dy in directions:
            next_x, next_y = current_x + dx, current_y + dy
            next_coord = (next_x, next_y)

            if is_valid(next_x, next_y) and is_traversable(next_x, next_y) and next_coord not in visited:
                visited.add(next_coord)
                parent_map[next_coord] = (current_x, current_y)
                queue.append(next_coord)
    return []

# --- Flask Routes ---
@app.route('/')
def index():
    return send_from_directory(STATIC_FOLDER, 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(STATIC_FOLDER, filename)

# SocketIO event to receive commands from command.py and emit to frontend
@socketio.on('command_agent_from_python')
def handle_command_agent(data):
    agent_id = data['agentId']
    target_x = data['targetX']
    target_y = data['targetY']
    destination_name = data['destinationName']
    path = data['path'] # Path is now sent directly from command.py

    print(f"App.py received command for {agent_id}: to {destination_name} via path {path}")
    
    # Emit to all connected frontend clients
    emit('set_agent_path', {
        'agentId': agent_id,
        'path': path,
        'destinationName': destination_name
    }, broadcast=True)
    print(f"App.py relayed command for {agent_id} to frontend.")

# SocketIO event to receive agent state updates from frontend and relay to command.py
@socketio.on('agent_state_update')
def handle_agent_state_update(data):
    agent_id = data['agentId']
    state = data['state']
    x = data['x']
    y = data['y']
    
    print(f"App.py received state update for {agent_id}: {state} at ({x},{y})")
    # Relay this state update to command.py
    emit('update_agent_state_in_command', {'agentId': agent_id, 'state': state, 'x': x, 'y': y}, broadcast=True, include_self=False)


# --- SocketIO Event Handlers ---
@socketio.on('connect')
def test_connect():
    print('Client connected')
    emit('log_message', {'message': 'Python backend (app.py) connected!'})

@socketio.on('disconnect')
def test_disconnect():
    print('Client disconnected')

# New: SocketIO event to receive readiness signal from command.py and relay to frontend
@socketio.on('command_client_ready')
def handle_command_client_ready():
    print("App.py received 'command_client_ready' signal from command.py. Relaying to frontend.")
    emit('command_client_ready', {}, broadcast=True, include_self=False)

if __name__ == '__main__':
    print(f"Serving files from: {STATIC_FOLDER}")
    print("Open your browser and navigate to http://127.0.0.1:5000/")
    print("Run 'command.py' in a separate terminal to send agent commands.")
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True) # allow_unsafe_werkzeug for reloader with threads