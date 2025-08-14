# simulation/narrative/narrative_system.py

import os
import datetime
import shutil
from simulation.llm_handler import LLMHandler

DAILY_STORY_DIR = os.path.join(os.path.dirname(__file__), 'daily_stories')
os.makedirs(DAILY_STORY_DIR, exist_ok=True)

class NarrativeSystem:
    """
    Handles diary log generation for agents and compiles daily town stories.
    """
    def __init__(self, llm_handler):
        self.llm = llm_handler

    def write_agent_diary(self, agent, day_name, day_number):
        # Compose a diary prompt influenced by personality and behaviors
        memories = agent.memory_stream.get_memories_for_day(day_name)
        background = getattr(agent, 'background', "")
        personality = ', '.join(agent.personality_names)
        prompt = (
            f"You are {agent.name}, a resident of a lively town.\n"
            f"Background: {background}\n"
            f"Personality traits: {personality}\n"
            f"Today is {day_name}. Here are your key memories and experiences for the day:\n"
            f"" + "\n".join([f"- {m.event}" for m in memories]) + "\n"
            "Write a casual, personal diary entry for this day, reflecting your personality and behaviors. Mention what you did, how you felt, and any notable events or interactions. Be natural and authentic, not poetic or dramatic. End with a simple reflection or thought for tomorrow."
        )
        diary_entry = self.llm.generate_narrative(prompt)
        day_folder = os.path.join(DAILY_STORY_DIR, f"day_{day_number}")
        os.makedirs(day_folder, exist_ok=True)
        log_path = os.path.join(day_folder, f"{agent.id}_{day_name}.txt")
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(diary_entry + "\n")
        return diary_entry

    def compile_daily_story(self, agent_ids, day_name, day_number):
        # Read all agent diaries for the day
        day_folder = os.path.join(DAILY_STORY_DIR, f"day_{day_number}")
        entries = []
        for agent_id in agent_ids:
            log_path = os.path.join(day_folder, f"{agent_id}_{day_name}.txt")
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8') as f:
                    entries.append(f.read())
        # Compose a more realistic, human narrative prompt for the town-wide story
        prompt = (
            f"Here are the diary entries of all agents for {day_name}:\n"
            f"" + "\n---\n".join(entries) + "\n"
            "Write a realistic, human-like summary of how the day went for the town and its people. Focus on the atmosphere, the events, and how people felt. Use clear, natural language, avoid advanced or novel-like storytelling. Make it sound like a real person describing the day in a sensible, relatable way. End with a simple closing thought or anticipation for tomorrow."
        )
        story = self.llm.generate_narrative(prompt, max_tokens=2048)
        story_path = os.path.join(day_folder, f"{day_name}_story.txt")
        with open(story_path, 'w', encoding='utf-8') as f:
            f.write(story)
        return story

    def reset_agent_diaries(self, agent_ids, day_name, day_number):
        # No deletion needed; diaries are now stored per day in daily_stories
        pass
