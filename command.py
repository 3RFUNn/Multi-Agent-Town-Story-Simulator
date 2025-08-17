# command.py
# Command client for simulation control and agent management.
# Connects to Flask server, manages simulation state, and relays updates via SocketIO.

import socketio
import time
from simulation.manager import AgentManager
from app import MAP_LAYOUT, PLACES

FLASK_SERVER_URL = 'http://127.0.0.1:5000'

# --- SocketIO Client Setup ---
sio = socketio.Client()
simulation_paused = False

@sio.event
def connect():
    """Handles connection to the Flask server."""
    print('Connected to Flask server as command client.')
    sio.emit('command_client_ready')

@sio.event
def connect_error(data):
    """Handles connection errors."""
    print("Connection failed:", data)

@sio.event
def disconnect():
    """Handles disconnection from the Flask server."""
    print('Disconnected from Flask server.')

@sio.on('pause_simulation')
def on_pause_simulation(data):
    """Pauses the simulation when triggered by the server."""
    global simulation_paused
    print("--- SIMULATION PAUSED ---")
    simulation_paused = True

@sio.on('resume_simulation')
def on_resume_simulation(data):
    """Resumes the simulation when triggered by the server."""
    global simulation_paused
    print("--- SIMULATION RESUMED ---")
    simulation_paused = False

# --- Main Simulation Logic ---
def run_simulation():
    """Initializes and runs the agent simulation loop."""
    from simulation.llm_handler import LLMHandler
    print("Checking LLM API connectivity...")
    llm = LLMHandler()
    ok, msg = llm.check_llm_api()
    if ok:
        print(f"LLM API is working: {msg}")
    else:
        print(f"LLM API check failed: {msg}")
        print("Simulation will not start. Please check your API key and network.")
        return

    print("Initializing Agent Manager...")
    manager = AgentManager(world_layout=MAP_LAYOUT, places_data=PLACES)
    print("Agent Manager initialized. Starting simulation loop.")

    simulation_tick_interval = 0.4

    while True:
        try:
            if not simulation_paused:
                commands, state_payload = manager.tick()
                if state_payload:
                    sio.emit('simulation_state_update', state_payload)
            time.sleep(simulation_tick_interval)
        except KeyboardInterrupt:
            print("Simulation stopped by user.")
            break
        except Exception as e:
            print(f"An error occurred in the simulation loop: {e}")
            break
    sio.disconnect()

def main():
    """Entry point for the command client."""
    try:
        sio.connect(FLASK_SERVER_URL)
        run_simulation()
    except socketio.exceptions.ConnectionError as e:
        print(f"Could not connect to Flask server at {FLASK_SERVER_URL}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == '__main__':
    main()