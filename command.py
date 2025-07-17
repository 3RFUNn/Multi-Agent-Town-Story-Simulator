# command.py

import socketio
import time
from simulation.manager import AgentManager
from app import MAP_LAYOUT

# --- Configuration ---
FLASK_SERVER_URL = 'http://127.0.0.1:5000'

# --- SocketIO Client Setup ---
sio = socketio.Client()

# *** FIX: Add a global flag to control the simulation loop ***
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

# *** FIX: Add event handlers to receive pause/resume signals ***
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
    print("Initializing Agent Manager...")
    manager = AgentManager(world_layout=MAP_LAYOUT)
    print("Agent Manager initialized. Starting simulation loop.")

    simulation_tick_interval = 1.0

    while True:
        try:
            # *** FIX: The entire tick logic is now conditional on the pause flag ***
            if not simulation_paused:
                commands, state_payload = manager.tick()
                if state_payload:
                    sio.emit('simulation_state_update', state_payload)

            # The loop still sleeps to avoid busy-waiting
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
