# simulation/narrative/narrative_system.py

import os
import datetime
from simulation.llm_handler import LLMHandler

DAILY_LOG_DIR = os.path.join(os.path.dirname(__file__), 'daily_logs')
os.makedirs(DAILY_LOG_DIR, exist_ok=True)

class NarrativeSystem:
    """
    Handles diary log generation for agents and compiles daily town stories.
    """
    def __init__(self, llm_handler):
        self.llm = llm_handler

    def write_agent_diary(self, agent, day_name):
        # Compose a rich, context-aware prompt for the agent's diary
        memories = agent.memory_stream.get_memories_for_day(day_name)
        background = getattr(agent, 'background', "")
        prompt = (
            f"You are {agent.name}, a resident of a lively town.\n"
            f"Background: {background}\n"
            f"Today is {day_name}. Here are your key memories and experiences for the day:\n"
            f"" + "\n".join([f"- {m.event}" for m in memories]) + "\n"
            "Write a detailed, believable diary entry for this day. Include your thoughts, feelings, and any notable events or interactions. Use a natural, personal tone. End with a reflection or hope for tomorrow."
        )
        diary_entry = self.llm.generate_narrative(prompt)
        log_path = os.path.join(DAILY_LOG_DIR, f"{agent.id}_{day_name}.txt")
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(diary_entry + "\n")
        return diary_entry

    def compile_daily_story(self, agent_ids, day_name):
        # Read all agent diaries for the day
        entries = []
        for agent_id in agent_ids:
            log_path = os.path.join(DAILY_LOG_DIR, f"{agent_id}_{day_name}.txt")
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8') as f:
                    entries.append(f.read())
        # Compose a rich prompt for the town-wide story
        prompt = (
            f"Here are the diary entries of all agents for {day_name}:\n"
            f"" + "\n---\n".join(entries) + "\n"
            "Write a vivid, engaging story summarizing the day in the town. Capture the atmosphere, major events, and how the lives of the agents intertwined. Use a narrative style as if you are a storyteller describing the town's day for a local newspaper. End with a closing remark or teaser for the next day."
        )
        story = self.llm.generate_narrative(prompt)
        story_path = os.path.join(DAILY_LOG_DIR, f"{day_name}_story.txt")
        with open(story_path, 'w', encoding='utf-8') as f:
            f.write(story)
        return story

    def reset_agent_diaries(self, agent_ids, day_name):
        for agent_id in agent_ids:
            log_path = os.path.join(DAILY_LOG_DIR, f"{agent_id}_{day_name}.txt")
            if os.path.exists(log_path):
                os.remove(log_path)
