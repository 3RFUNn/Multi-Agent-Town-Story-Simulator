# simulation/manager.py

import random
from .entities import Agent
from .config import AGENT_CONFIG, PLACES, ACTIVITY_DATA
from behavior.agent_behaviors import create_agent_bt

def find_path_bfs(start_x, start_y, target_x, target_y, world_layout):
    rows, cols = len(world_layout), len(world_layout[0])
    queue = [((start_x, start_y), [(start_x, start_y)])]
    visited = {(start_x, start_y)}
    directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    def is_traversable(x, y):
        return 0 <= y < rows and 0 <= x < cols and world_layout[y][x] != 'G'
    while queue:
        (current_x, current_y), path = queue.pop(0)
        if current_x == target_x and current_y == target_y: return path
        for dx, dy in directions:
            next_x, next_y = current_x + dx, current_y + dy
            if (next_x, next_y) not in visited and is_traversable(next_x, next_y):
                visited.add((next_x, next_y))
                new_path = list(path); new_path.append((next_x, next_y))
                queue.append(((next_x, next_y), new_path))
    return None

class AgentManager:
    def __init__(self, world_layout):
        self.agents = {}
        self.world_layout = world_layout
        self.world_state = { 'time': (9, 0), 'places': PLACES, 'activity_data': ACTIVITY_DATA }
        self._initialize_agents()

    def _initialize_agents(self):
        for config in AGENT_CONFIG:
            agent = Agent(
                agent_id=config['id'], name=config['name'], icon=config['icon'], color=config['color'],
                home_x=config['home_pos'][0], home_y=config['home_pos'][1],
                personality=config['personality'], schedule=config['schedule']
            )
            # Pass a reference to the full agent dictionary into the world state
            self.world_state['agents'] = self.agents
            agent.behavior_tree = create_agent_bt(agent, self.world_state)
            self.agents[agent.id] = agent
        print(f"Initialized {len(self.agents)} agents.")

    def _update_agent_schedules(self):
        hour, _ = self.world_state['time']
        for agent in self.agents.values():
            # Don't assign a new activity if the agent is busy interacting
            if agent.state == 'interacting':
                continue
            
            agent.current_activity = None
            # Add a sleep schedule for all agents
            if 22 <= hour or hour < 6:
                 agent.current_activity = "sleep_at_home"
            else:
                for (start_hour, end_hour), activity in agent.schedule.items():
                    if start_hour <= hour < end_hour:
                        agent.current_activity = activity
                        break

    def tick(self):
        hour, minute = self.world_state['time']
        minute += 10
        if minute >= 60: minute = 0; hour = (hour + 1) % 24
        self.world_state['time'] = (hour, minute)

        self._update_agent_schedules()
        occupied_positions = { (agent.x, agent.y) for agent in self.agents.values() }
        
        # Create a copy of agents to iterate over, to avoid issues when modifying during iteration
        agents_to_process = list(self.agents.values())

        for agent in agents_to_process:
            agent.update_needs(self.world_state['time'])
            
            # --- State Machine for Agent Actions ---
            if agent.state == 'interacting':
                agent.action_duration -= 1
                if agent.action_duration <= 0:
                    other_agent_id = agent.interacting_with
                    if other_agent_id and other_agent_id in self.agents:
                        self.agents[other_agent_id].state = 'idle'
                        self.agents[other_agent_id].interacting_with = None
                        agent.add_log(f"Finished my conversation with {self.agents[other_agent_id].name}.", self.world_state['time'])
                    agent.state = 'idle'
                    agent.interacting_with = None
                continue # Skip to next agent if interacting

            if agent.state == 'doing_action':
                agent.action_duration -= 1
                if agent.action_duration <= 0:
                    agent.state = 'idle'
                continue

            if agent.state == 'idle':
                agent.behavior_tree.tick(agent, self.world_state)

            if agent.state == 'moving':
                if not agent.path or agent.path_index >= len(agent.path):
                    location_name = agent.destination_name
                    target_pos = None
                    
                    if "home" in location_name:
                        target_pos = (agent.home['x'], agent.home['y'])
                    else:
                        target_location = self.world_state['places'].get(location_name)
                        if target_location:
                            available_spots = [p for p in target_location['coords'] if p not in occupied_positions]
                            if available_spots:
                                target_pos = random.choice(available_spots)
                                occupied_positions.add(target_pos) # Reserve the spot

                    if target_pos:
                        path = find_path_bfs(agent.x, agent.y, target_pos[0], target_pos[1], self.world_layout)
                        agent.path = path; agent.path_index = 0
                        if not path: agent.state = 'idle'; agent.add_log("I can't find a path to my destination.", self.world_state['time'])
                    else:
                        agent.state = 'idle'; agent.add_log(f"I can't go to {location_name}, it's full.", self.world_state['time'])

                if agent.path and agent.path_index < len(agent.path):
                    next_pos = agent.path[agent.path_index]
                    agent.x, agent.y = next_pos
                    agent.path_index += 1
                    if agent.path_index >= len(agent.path):
                        agent.state = 'idle'; agent.path = []

        state_payload = {
            'agents': [agent.to_dict() for agent in self.agents.values()],
            'time': self.world_state['time']
        }
        return [], state_payload
