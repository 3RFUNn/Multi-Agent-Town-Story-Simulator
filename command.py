import socketio
import time
import random
import requests # Used for initial state sync if needed, not for commands

# --- Configuration ---
# URL for the Flask-SocketIO server
FLASK_SERVER_URL = 'http://127.0.0.1:5000'

# --- Map and Places Data (must be consistent with app.py and script.js) ---
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
    ['G', 'P', 'G', 'P', 'P', 'P', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
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
    'houses_south_west_1': {'type': 'Houses', 'name': 'South West Houses 1', 'coords': [[3,14],[4,14],[5,14],[3,15],[4,15],[5,15]]},
    'houses_south_west_2': {'type': 'Houses', 'name': 'South West Houses 2', 'coords': [[1,12],[2,12],[1,13],[2,13]]},
    'houses_north_east_1': {'type': 'Houses', 'name': 'North East Houses 1', 'coords': [[24,1],[25,1],[26,1],[27,1],[28,1]]},
    'houses_north_east_2': {'type': 'Houses', 'name': 'North East Houses 2', 'coords': [[24,14],[25,14],[26,14],[27,14],[28,14]]},
    'houses_central_1': {'type': 'Houses', 'name': 'Central Houses 1', 'coords': [[14,5],[15,5],[16,5],[14,6],[15,6],[16,6]]},
    'college_dorm_main': {'type': 'College Dorm', 'name': 'Main College Dorm', 'coords': [[3,18],[4,18],[5,18],[3,19],[4,19],[5,19]]},
}

# Initial agent data (must be consistent with script.js and app.py)
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

# --- SocketIO Client for command.py ---
sio = socketio.Client()

# Local dictionary to keep track of agent states received from frontend
# This is crucial for command.py to know which agents are 'idle'
agent_current_states = {agent['id']: {'x': agent['x'], 'y': agent['y'], 'state': 'idle'} for agent in AGENTS_INITIAL_STATE}

@sio.event
def connect():
    print('command.py connected to Flask server!')

@sio.event
def connect_error(data):
    print("command.py connection failed:", data)

@sio.event
def disconnect():
    print('command.py disconnected from Flask server.')

@sio.event
def log_message(data):
    # Receive log messages from app.py (which might originate from frontend)
    print(f"[App Log] {data['message']}") # Uncomment if you want to see app.py's logs here too

@sio.event
def update_agent_state_in_command(data):
    agent_id = data['agentId']
    state = data['state']
    x = data['x']
    y = data['y']
    if agent_id in agent_current_states:
        agent_current_states[agent_id]['state'] = state
        agent_current_states[agent_id]['x'] = x
        agent_current_states[agent_id]['y'] = y
        print(f"command.py: Updated state for {agent_id} to {state} at ({x},{y})")
    else:
        # Handle newly added agents
        agent_current_states[agent_id] = {'x': x, 'y': y, 'state': state}
        print(f"command.py: Added new agent {agent_id} with state {state} at ({x},{y})")


def send_agent_command(agent_id, start_pos, target_pos, destination_name):
    path = find_path_python(start_pos['x'], start_pos['y'], target_pos['x'], target_pos['y'])
    if path:
        try:
            sio.emit('command_agent_from_python', {
                'agentId': agent_id,
                'targetX': target_pos['x'],
                'targetY': target_pos['y'],
                'destinationName': destination_name,
                'path': path # Send the calculated path
            })
            print(f"command.py: Commanded agent {agent_id} to go to {destination_name}")
            return True
        except Exception as e:
            print(f"command.py: Error sending command for {agent_id}: {e}")
            return False
    else:
        print(f"command.py: No path found for {agent_id} from {start_pos} to {target_pos}")
        return False

# --- Main Command Logic Loop ---
def main():
    try:
        sio.connect(FLASK_SERVER_URL)
        print(f"command.py: Attempting to connect to {FLASK_SERVER_URL}")
    except Exception as e:
        print(f"command.py: Could not connect to Flask server at {FLASK_SERVER_URL}: {e}")
        print("Please ensure app.py is running in a separate terminal.")
        return

    command_check_interval = 1 # seconds between checking for idle agents

    while True:
        sio.sleep(command_check_interval) # Sleep to allow SocketIO to process events and for agents to update state

        # Get list of currently idle agents based on received updates
        idle_agents_ids = [agent_id for agent_id, state in agent_current_states.items() if state['state'] == 'idle']
        
        if idle_agents_ids:
            agent_id = random.choice(idle_agents_ids)
            agent_pos = {'x': agent_current_states[agent_id]['x'], 'y': agent_current_states[agent_id]['y']}

            # Pick a random place as a destination
            place_ids = list(PLACES.keys())
            random_place_id = random.choice(place_ids)
            target_place_coords = PLACES[random_place_id]['coords']

            target_cell = None
            random.shuffle(target_place_coords) # Shuffle to try different cells
            for coord in target_place_coords:
                x, y = coord
                # command.py cannot know if a cell is occupied by *another* agent in real-time
                # The frontend's moveAgentStep will handle this collision by making the agent wait.
                if is_traversable(x, y):
                    target_cell = {'x': x, 'y': y}
                    break
            
            if target_cell:
                # Send command and optimistically update state
                if send_agent_command(agent_id, agent_pos, target_cell, PLACES[random_place_id]['name']):
                    agent_current_states[agent_id]['state'] = 'moving' # Optimistic update
                    # The actual position will be updated by frontend's agent_state_update when it moves
                else:
                    print(f"command.py: Failed to command {agent_id}, retrying next tick.")
            else:
                print(f"command.py: No valid traversable destination cell found for {agent_id} in {PLACES[random_place_id]['name']}")
        else:
            print("command.py: No idle agents to command. All agents are either moving or doing actions.")

if __name__ == '__main__':
    # Ensure python-socketio is installed: pip install python-socketio
    main()
