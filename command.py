# command.py

import socketio
import time
from simulation.manager import AgentManager
# *** FIX: Import both MAP_LAYOUT and PLACES from our central loader in app.py ***
from app import MAP_LAYOUT, PLACES

# --- Configuration ---
FLASK_SERVER_URL = 'http://127.0.0.1:5000'

# --- SocketIO Client Setup ---
sio = socketio.Client()

simulation_paused = False

@sio.event
def connect():
    print('Connected to Flask server as command client.')
    sio.emit('command_client_ready')

@sio.event
def connect_error(data):
    print("Connection failed:", data)

@sio.event
def disconnect():
    print('Disconnected from Flask server.')

@sio.on('pause_simulation')
def on_pause_simulation(data):
    global simulation_paused
    print("--- SIMULATION PAUSED ---")
    simulation_paused = True

@sio.on('resume_simulation')
def on_resume_simulation(data):
    global simulation_paused
    print("--- SIMULATION RESUMED ---")
    simulation_paused = False

# --- Main Simulation Logic ---
def run_simulation():
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
    # *** FIX: Pass the imported PLACES data into the AgentManager constructor. ***
    manager = AgentManager(world_layout=MAP_LAYOUT, places_data=PLACES)
    print("Agent Manager initialized. Starting simulation loop.")

    # *** FIX: Set the simulation tick interval to 0.4 seconds for faster movement. ***
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
    try:
        sio.connect(FLASK_SERVER_URL)
        run_simulation()
    except socketio.exceptions.ConnectionError as e:
        print(f"Could not connect to Flask server at {FLASK_SERVER_URL}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == '__main__':
    main()