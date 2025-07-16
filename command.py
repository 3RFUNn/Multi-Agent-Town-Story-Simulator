# command.py

import socketio
import time
from simulation.manager import AgentManager
from app import MAP_LAYOUT # Import MAP_LAYOUT from app.py to avoid duplication

# --- Configuration ---
FLASK_SERVER_URL = 'http://127.0.0.1:5000'

# --- SocketIO Client Setup ---
sio = socketio.Client()

@sio.event
def connect():
    print('Connected to Flask server as command client.')
    # Signal readiness to the main app, so it can start the frontend simulation
    sio.emit('command_client_ready')

@sio.event
def connect_error(data):
    print("Connection failed:", data)

@sio.event
def disconnect():
    print('Disconnected from Flask server.')

# --- Main Simulation Logic ---
def run_simulation():
    """Initializes the manager and runs the main simulation loop."""
    print("Initializing Agent Manager...")
    # The manager now holds all the agents and the world layout
    manager = AgentManager(world_layout=MAP_LAYOUT)
    print("Agent Manager initialized. Starting simulation loop.")

    simulation_tick_interval = 1.0 # seconds per simulation tick

    while True:
        try:
            # 1. Run one tick of the simulation engine
            commands, agent_states = manager.tick()

            # 2. Send the updated agent states to the frontend
            if agent_states:
                sio.emit('simulation_state_update', {'agents': agent_states})

            # 3. Send any generated low-level commands to the frontend
            # (Currently this is just 'move', but could include 'interact', etc.)
            if commands:
                sio.emit('execute_commands', {'commands': commands})

            # Wait for the next tick
            time.sleep(simulation_tick_interval)

        except KeyboardInterrupt:
            print("Simulation stopped by user.")
            break
        except Exception as e:
            print(f"An error occurred in the simulation loop: {e}")
            break

    sio.disconnect()

def main():
    try:
        sio.connect(FLASK_SERVER_URL)
        run_simulation()
    except socketio.exceptions.ConnectionError as e:
        print(f"Could not connect to Flask server at {FLASK_SERVER_URL}: {e}")
        print("Please ensure app.py is running.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == '__main__':
    main()