# simulation/manager.py

import random
from .entities import Agent
# *** FIX: No longer imports PLACES from config ***
from .config import AGENT_CONFIG, ACTIVITY_DATA 
from behavior.agent_behaviors import create_agent_bt

def find_path_bfs(start_x, start_y, target_x, target_y, world_layout, occupied_positions):
    rows, cols = len(world_layout), len(world_layout[0])
    queue = [((start_x, start_y), [(start_x, start_y)])]
    visited = {(start_x, start_y)}
    directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    
    def is_traversable(x, y):
        if not (0 <= y < rows and 0 <= x < cols and world_layout[y][x] != 'G'):
            return False
        if (x, y) == (target_x, target_y):
            return True
        if (x, y) in occupied_positions:
            return False
        return True

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
    # *** FIX: The constructor now accepts places data. ***
    def __init__(self, world_layout, places_data):
        self.agents = {}
        self.world_layout = world_layout
        self.world_state = { 
            'time': (9, 0), 
            'places': places_data, # Use the provided places data
            'activity_data': ACTIVITY_DATA 
        }
        self._initialize_agents()

    def _initialize_agents(self):
        for config in AGENT_CONFIG:
            agent = Agent(
                agent_id=config['id'], name=config['name'], icon=config['icon'], color=config['color'],
                home_x=config['home_pos'][0], home_y=config['home_pos'][1],
                personality=config['personality'], schedule=config['schedule']
            )
            self.world_state['agents'] = self.agents
            agent.behavior_tree = create_agent_bt(agent, self.world_state)
            self.agents[agent.id] = agent
        print(f"Initialized {len(self.agents)} agents.")

    def _update_agent_schedules(self):
        hour, _ = self.world_state['time']
        for agent in self.agents.values():
            if agent.state in ['interacting', 'moving']: continue
            
            current_schedule_activity = None
            if 22 <= hour or hour < 7:
                current_schedule_activity = "sleep_at_home"
            else:
                for (start_hour, end_hour), activity in agent.schedule.items():
                    if start_hour <= hour < end_hour:
                        current_schedule_activity = activity
                        break
            agent.current_activity = current_schedule_activity

    def _find_adjacent_spot(self, target_x, target_y, occupied_positions):
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]
        random.shuffle(directions)
        for dx, dy in directions:
            adj_x, adj_y = target_x + dx, target_y + dy
            if (adj_x, adj_y) not in occupied_positions:
                return (adj_x, adj_y)
        return None

    def tick(self):
        hour, minute = self.world_state['time']
        # *** FIX: Decrease time increment to match faster tick rate. ***
        minute += 2 
        if minute >= 60:
            minute %= 60
            hour = (hour + 1) % 24
        self.world_state['time'] = (hour, int(minute))

        self._update_agent_schedules()
        
        agents_to_process = list(self.agents.values())
        random.shuffle(agents_to_process)

        for agent in agents_to_process:
            agent.update_needs(self.world_state['time'])
            
            if agent.state in ['doing_action', 'interacting']:
                agent.action_duration -= 1
                
                if agent.state == 'doing_action' and "work" in (agent.current_activity or ""):
                    agent.money += 0.5 
                
                if agent.action_duration <= 0:
                    if agent.state == 'interacting' and agent.interacting_with:
                        other_agent = self.agents.get(agent.interacting_with)
                        if other_agent:
                            other_agent.state = 'idle'
                            other_agent.interacting_with = None
                        agent.add_log(f"Finished my conversation.", self.world_state['time'])
                    agent.state = 'idle'
                    agent.interacting_with = None
                continue

            if agent.state == 'idle':
                agent.behavior_tree.tick(agent, self.world_state)

            if agent.state == 'moving':
                occupied_positions = { (a.x, a.y) for a in self.agents.values() if a.id != agent.id }
                
                if not agent.path or agent.path_index >= len(agent.path):
                    agent.path = None
                    location_name = agent.destination_name
                    target_pos = None
                    
                    if location_name and location_name.startswith("agent_"):
                        target_agent_id = location_name.split("_")[1]
                        target_agent = self.agents.get(target_agent_id)
                        if target_agent:
                            target_pos = self._find_adjacent_spot(target_agent.x, target_agent.y, occupied_positions)
                    elif location_name and "home" in location_name:
                        target_pos = (agent.home['x'], agent.home['y'])
                    elif location_name:
                        target_location = self.world_state['places'].get(location_name)
                        if target_location:
                            available_spots = [p for p in target_location['coords'] if p not in occupied_positions]
                            if available_spots:
                                target_pos = random.choice(available_spots)
                    
                    if target_pos:
                        path = find_path_bfs(agent.x, agent.y, target_pos[0], target_pos[1], self.world_layout, occupied_positions)
                        agent.path = path
                        agent.path_index = 0
                        if not path:
                            agent.state = 'idle'
                            agent.add_log("I can't find a path to my destination.", self.world_state['time'])
                            if agent.interacting_with:
                                agent.interacting_with = None
                    else:
                        agent.state = 'idle'
                        if location_name:
                             agent.add_log(f"I can't go to {location_name}, there's no space.", self.world_state['time'])
                             if agent.interacting_with:
                                 agent.interacting_with = None

                if agent.path and agent.path_index < len(agent.path):
                    next_pos = agent.path[agent.path_index]
                    agent.x, agent.y = next_pos
                    agent.path_index += 1
                    if agent.path_index >= len(agent.path):
                        agent.path = []
                        
                        if agent.interacting_with:
                            other_agent = self.agents.get(agent.interacting_with)
                            if other_agent and other_agent.state == 'idle':
                                agent.state = 'interacting'
                                other_agent.state = 'interacting'
                                other_agent.interacting_with = agent.id
                                
                                agent.current_goal = f"Chatting with {other_agent.name}"
                                other_agent.current_goal = f"Chatting with {agent.name}"
                                other_agent.add_log(f"{agent.name} is coming over to talk to me.", self.world_state['time'])
                                
                                interaction_duration = random.randint(5, 12)
                                agent.action_duration = interaction_duration
                                other_agent.action_duration = interaction_duration
                            else:
                                agent.state = 'idle'
                                agent.add_log("They seemed busy, so I decided not to interrupt.", self.world_state['time'])
                                agent.interacting_with = None
                        else:
                            agent.state = 'idle'
                        
        state_payload = {
            'agents': [agent.to_dict() for agent in self.agents.values()],
            'time': self.world_state['time']
        }
        return [], state_payload