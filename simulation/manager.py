# simulation/manager.py

import random
from .entities import Agent
from .config import AGENT_CONFIG, ACTIVITY_DATA, SCHEDULE_TEMPLATES
from behavior.agent_behaviors import create_agent_bt
from simulation.narrative.narrative_system import NarrativeSystem
from simulation.llm_handler import LLMHandler
from app import emit_daily_story

def find_path_bfs(start_x, start_y, target_x, target_y, world_layout, occupied_positions):
    """Finds the shortest path from start to target using Breadth-First Search (BFS)."""
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
        if current_x == target_x and current_y == target_y:
            return path
        for dx, dy in directions:
            next_x, next_y = current_x + dx, current_y + dy
            if (next_x, next_y) not in visited and is_traversable(next_x, next_y):
                visited.add((next_x, next_y))
                new_path = list(path)
                new_path.append((next_x, next_y))
                queue.append(((next_x, next_y), new_path))
    return None

class AgentManager:
    def __init__(self, world_layout, places_data):
        self.agents = {}
        self.world_layout = world_layout
        self.days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        self.world_state = { 
            'time': (8, 0),  # Start at 8 AM
            'day_index': 0,
            'day_of_week': self.days[0],
            'places': places_data,
            'activity_data': ACTIVITY_DATA 
        }
        self.llm_handler = LLMHandler()
        self.narrative_system = NarrativeSystem(self.llm_handler)
        self.daily_stories = []
        self._initialize_agents()

    def _initialize_agents(self):
        for config in AGENT_CONFIG:
            agent = Agent(
                agent_id=config['id'], name=config['name'], icon=config['icon'], color=config['color'],
                home_pos=config['home_pos'],
                personality=config['personality'],
                schedule_template=SCHEDULE_TEMPLATES[config['schedule_template']],
                work_location=config.get('work_location')
            )
            self.agents[agent.id] = agent
        
        self.world_state['agents'] = self.agents
        for agent in self.agents.values():
            agent.behavior_tree = create_agent_bt(agent, self.world_state)
        print(f"Initialized {len(self.agents)} agents.")

    def _update_agent_schedules(self):
        hour, minute = self.world_state['time']
        day_of_week = self.world_state['day_of_week']
        schedule_type = 'weekdays' if day_of_week not in ['Saturday', 'Sunday'] else 'weekends'

        for agent in self.agents.values():
            # If agent's activity is over (e.g., socializing after 22:00), force idle and allow schedule update
            if agent.current_activity == "socialize_at_park":
                hour, _ = self.world_state['time']
                if hour >= 22:
                    agent.state = 'idle'
                    agent.current_activity = None
            if agent.state in ['interacting', 'moving']:
                continue

            current_schedule = agent.schedule_template.get(schedule_type, {})
            activity_found = False
            
            # Sleep schedule - different agents have different sleep patterns
            if self._is_sleep_time(agent, hour):
                agent.current_activity = "sleep_at_home"
                activity_found = True
            else:
                # Check scheduled activities
                for (start_hour, end_hour), activity in current_schedule.items():
                    if start_hour <= hour < end_hour:
                        agent.current_activity = activity
                        activity_found = True
                        break
            
            if not activity_found:
                agent.current_activity = None

    def _is_sleep_time(self, agent, hour):
        """Determine if it's sleep time based on agent personality"""
        if 'lazy' in agent.personality_names:
            # Lazy agents sleep more (10 PM to 10 AM)
            return hour >= 22 or hour < 10
        elif 'workaholic' in agent.personality_names:
            # Workaholics sleep less (1 AM to 6 AM)
            return hour >= 1 and hour < 6
        elif 'fitness_enthusiast' in agent.personality_names:
            # Fitness enthusiasts have early bedtime (10 PM to 6 AM)
            return hour >= 22 or hour < 6
        else:
            # Normal sleep schedule (11 PM to 8 AM)
            return hour >= 23 or hour < 8

    def _find_adjacent_spot(self, target_x, target_y, occupied_positions):
        directions = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)]
        random.shuffle(directions)
        for dx, dy in directions:
            adj_x, adj_y = target_x + dx, target_y + dy
            if (adj_x, adj_y) not in occupied_positions:
                return (adj_x, adj_y)
        return None

    def _get_agent_home_target(self, agent, occupied_positions):
        """Get a target position in the agent's home area"""
        home_x, home_y = agent.home['x'], agent.home['y']
        
        # Map agent home positions to the correct place
        if home_x <= 5 and home_y <= 5:  # North houses
            home_coords = self.world_state['places']['north_houses']['coords']
        elif home_x <= 5 and 13 <= home_y <= 17:  # Central houses  
            home_coords = self.world_state['places']['central_houses']['coords']
        elif home_x <= 5 and home_y >= 18:  # South houses
            home_coords = self.world_state['places']['south_houses']['coords']
        elif home_x >= 18 and home_y <= 5:  # Student accommodation
            home_coords = self.world_state['places']['student_accommodation']['coords']
        else:
            # Fallback to exact position
            home_coords = [(home_x, home_y)]
        
        # Find an available spot in the home area
        available_spots = [pos for pos in home_coords if pos not in occupied_positions]
        if available_spots:
            return random.choice(available_spots)
        else:
            # If all spots occupied, return the original home position
            return (home_x, home_y)

    def tick(self):
        hour, minute = self.world_state['time']
        day_index = self.world_state['day_index']
        
        minute += 2 # BUG FIX: Slow down time progression
        day_rolled_over = False
        if minute >= 60:
            minute %= 60
            hour += 1
            if hour >= 24:
                hour %= 24
                day_index = (day_index + 1) % 7
                agent_list = list(self.agents.values())
                random.shuffle(agent_list)
                for agent in agent_list: # Reset BTs at the start of a new day
                    agent.behavior_tree.reset()
                print(f"A new day has dawned! It is now {self.days[day_index]}.")
                day_rolled_over = True
                self._pending_narrative_day = self.days[day_index]
                self._pending_narrative = True

        self.world_state['time'] = (hour, int(minute))
        self.world_state['day_index'] = day_index
        self.world_state['day_of_week'] = self.days[day_index]

        self._update_agent_schedules()
        
        agents_to_process = list(self.agents.values())
        random.shuffle(agents_to_process)

        # Keep track of all spots that are occupied or are the destination of an agent.
        # This prevents agents from selecting the same destination cell in the same tick.
        claimed_spots = set((a.x, a.y) for a in self.agents.values())
        claimed_spots.update(a.path[-1] for a in self.agents.values() if a.path and len(a.path) > 0)

        for agent in agents_to_process:
            agent.update_needs(self.world_state['time'])
            
            if agent.state in ['doing_action', 'interacting']:
                agent.action_duration -= 1
                
                # BUG FIX: Only earn money if at the correct work location and doing work activities
                is_working = ("work" in (agent.current_activity or "") or 
                             "shift" in (agent.current_activity or "") or
                             "classes" in (agent.current_activity or ""))
                
                if agent.state == 'doing_action' and is_working:
                    work_location_data = self.world_state['places'].get(agent.work_location, {})
                    if work_location_data and (agent.x, agent.y) in work_location_data.get('coords', []):
                        # Different earning rates based on job type
                        if "shift" in (agent.current_activity or ""):
                            agent.money += 0.8  # Cafe workers earn more per hour
                        elif "classes" in (agent.current_activity or ""):
                            agent.money += 0.3  # Students earn less (part-time)
                        else:
                            agent.money += 0.5  # Office workers standard rate
                
                if agent.action_duration <= 0:
                    if agent.state == 'interacting' and agent.interacting_with:
                        other_agent = self.agents.get(agent.interacting_with)
                        if other_agent:
                            other_agent.state = 'idle'
                            other_agent.interacting_with = None
                            other_agent.behavior_tree.reset()
                        agent.add_log(f"Finished my conversation.", self.world_state['time'], self.world_state['day_of_week'])
                    agent.state = 'idle'
                    agent.interacting_with = None
                    agent.behavior_tree.reset()
                continue

            if agent.state == 'idle':
                agent.behavior_tree.tick(agent, self.world_state)

            if agent.state == 'moving':
                # For pathfinding traversal, we only care about the current positions of other agents.
                occupied_for_pathing = { (a.x, a.y) for a in self.agents.values() if a.id != agent.id }
                
                if not agent.path or agent.path_index >= len(agent.path):
                    agent.path = None
                    location_name = agent.destination_name
                    target_pos = None
                    
                    if location_name and location_name.startswith("agent_"):
                        target_agent_id = location_name.split("_")[1]
                        target_agent = self.agents.get(target_agent_id)
                        if target_agent:
                            # Find an adjacent spot that isn't currently claimed
                            target_pos = self._find_adjacent_spot(target_agent.x, target_agent.y, claimed_spots)
                    elif location_name and "home" in location_name:
                        # Find a home spot that isn't currently claimed
                        target_pos = self._get_agent_home_target(agent, claimed_spots)
                    elif location_name:
                        target_location = self.world_state['places'].get(location_name)
                        if target_location and target_location.get('coords'):
                            # Find a spot in the location that isn't currently claimed
                            available_spots = [p for p in target_location['coords'] if p not in claimed_spots]
                            if available_spots:
                                target_pos = random.choice(available_spots)
                    
                    if target_pos:
                        # Claim this spot for the rest of the tick so no other agent takes it.
                        claimed_spots.add(target_pos)
                        path = find_path_bfs(agent.x, agent.y, target_pos[0], target_pos[1], self.world_layout, occupied_for_pathing)
                        agent.path = path
                        agent.path_index = 0
                        if not path:
                            agent.add_log(f"I can't find a path to {location_name}.", self.world_state['time'], self.world_state['day_of_week'])
                            agent.state = 'idle'
                            agent.behavior_tree.reset()
                            # Release the claim if pathfinding fails
                            claimed_spots.remove(target_pos)
                    else:
                        agent.state = 'idle'
                        if location_name:
                            agent.add_log(f"I can't go to {location_name}, there's no space.", self.world_state['time'], self.world_state['day_of_week'])

                if agent.path and agent.path_index < len(agent.path):
                    next_pos = agent.path[agent.path_index]
                    
                    current_occupants = { (a.x, a.y) for a in self.agents.values() if a.id != agent.id }
                    if next_pos in current_occupants:
                        agent.add_log(f"My path to {agent.destination_name} is blocked, finding a new spot.", self.world_state['time'], self.world_state['day_of_week'])
                        
                        # --- REPLANNING LOGIC ---
                        location_name = agent.destination_name
                        target_pos = None
                        
                        # Find a new spot in the same destination location
                        if location_name and "home" in location_name:
                            target_pos = self._get_agent_home_target(agent, claimed_spots)
                        elif location_name:
                            target_location = self.world_state['places'].get(location_name)
                            if target_location and target_location.get('coords'):
                                available_spots = [p for p in target_location['coords'] if p not in claimed_spots]
                                if available_spots:
                                    target_pos = random.choice(available_spots)

                        if target_pos:
                            claimed_spots.add(target_pos)
                            occupied_for_pathing = { (a.x, a.y) for a in self.agents.values() if a.id != agent.id }
                            path = find_path_bfs(agent.x, agent.y, target_pos[0], target_pos[1], self.world_layout, occupied_for_pathing)
                            
                            if path:
                                agent.path = path
                                agent.path_index = 0
                                # Move immediately to the first step of the new path if possible
                                if agent.path and agent.path_index < len(agent.path):
                                    new_next_pos = agent.path[agent.path_index]
                                    if new_next_pos not in current_occupants:
                                        agent.x, agent.y = new_next_pos
                                        agent.path_index += 1
                            else:
                                # If no path to new spot, release claim and wait
                                claimed_spots.remove(target_pos)
                        # --- END REPLANNING ---
                    else:
                        agent.x, agent.y = next_pos
                        agent.path_index += 1

                    if agent.path_index >= len(agent.path):
                        agent.path = []
                        
                        if agent.interacting_with:
                            other_agent = self.agents.get(agent.interacting_with)
                            if other_agent and (other_agent.state == 'idle' or other_agent.interacting_with == agent.id):
                                agent.state = 'interacting'
                                other_agent.state = 'interacting'
                                other_agent.interacting_with = agent.id
                                agent.current_goal = f"Chatting with {other_agent.name}"
                                other_agent.current_goal = f"{agent.name} is coming over to talk to me."
                                interaction_duration = random.randint(15, 25)
                                agent.action_duration = interaction_duration
                                other_agent.action_duration = interaction_duration
                            else:
                                agent.state = 'idle'
                                agent.add_log("They seemed busy, so I decided not to interrupt.", self.world_state['time'], self.world_state['day_of_week'])
                                agent.interacting_with = None
                        else:
                            agent.state = 'idle'
                        agent.behavior_tree.reset() # Reset BT upon arrival
                        
        state_payload = {
            'agents': [agent.to_dict() for agent in self.agents.values()],
            'time': self.world_state['time'],
            'day_of_week': self.world_state['day_of_week']
        }

        # Write daily logs and story at 2 AM for the previous day
        if hour == 2 and minute == 0:
            prev_day_index = (day_index - 1) % 7
            prev_day_name = self.days[prev_day_index]
            day_number = day_index if hour != 0 else day_index + 1
            agent_ids = [agent.id for agent in self.agents.values()]
            for agent in self.agents.values():
                self.narrative_system.write_agent_diary(agent, prev_day_name, day_number)
            story = self.narrative_system.compile_daily_story(agent_ids, prev_day_name, day_number)
            self.daily_stories.append({'day': prev_day_name, 'text': story})
            self.narrative_system.reset_agent_diaries(agent_ids, prev_day_name, day_number)
            emit_daily_story({'day': prev_day_name, 'text': story})

        return [], state_payload