# simulation/manager.py

import random
from .entities import Agent
from .config import AGENT_CONFIG, PLACES, ACTIVITY_LOCATIONS
from behavior.agent_behaviors import create_agent_bt

# (The find_path_bfs function remains the same as before)
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
        self.world_state = { 'time': (9, 0), 'places': PLACES, 'activity_locations': ACTIVITY_LOCATIONS }
        self._initialize_agents()

    def _initialize_agents(self):
        for config in AGENT_CONFIG:
            agent = Agent(
                agent_id=config['id'], name=config['name'], icon=config['icon'], color=config['color'],
                home_x=config['home_pos'][0], home_y=config['home_pos'][1],
                personality=config['personality'], schedule=config['schedule']
            )
            agent.behavior_tree = create_agent_bt(agent, self.world_state)
            self.agents[agent.id] = agent
        print(f"Initialized {len(self.agents)} agents.")

    def tick(self):
        """The main simulation loop tick."""
        occupied_positions = { (agent.x, agent.y) for agent in self.agents.values() }

        for agent in self.agents.values():
            if agent.state == 'doing_action':
                agent.action_duration -= 1
                if agent.action_duration <= 0:
                    agent.state = 'idle'
                continue

            if agent.state == 'idle':
                agent.behavior_tree.tick(agent, self.world_state)

            if agent.state == 'moving':
                # *** FIX: Collision Avoidance and Target Selection Logic ***
                if not agent.path or agent.path_index >= len(agent.path):
                    location_name = agent.destination_name
                    target_location = self.world_state['places'].get(location_name)
                    
                    if target_location:
                        available_spots = [
                            pos for pos in target_location['coords'] 
                            if pos not in occupied_positions
                        ]
                        
                        if available_spots:
                            target_pos = random.choice(available_spots)
                            path = find_path_bfs(agent.x, agent.y, target_pos[0], target_pos[1], self.world_layout)
                            agent.path = path
                            agent.path_index = 0
                            if not path: agent.state = 'idle' # No path found
                        else:
                            agent.state = 'idle' # Location is full
                            agent.current_action = f"Waiting for space at {location_name}"
                    else:
                        agent.state = 'idle' # Invalid location

                if agent.path and agent.path_index < len(agent.path):
                    next_pos = agent.path[agent.path_index]
                    agent.x, agent.y = next_pos
                    agent.path_index += 1
                    if agent.path_index >= len(agent.path):
                        agent.state = 'idle'
                        agent.path = []

        agent_states = [agent.to_dict() for agent in self.agents.values()]
        return [], agent_states
