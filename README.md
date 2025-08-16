# Generative Agent Town Simulation

## Overview

This project is a narrative-driven multi-agent town simulation for games, research, and interactive storytelling. It models a vibrant small town populated by generative agents, each with unique personalities, schedules, and relationships. Agents interact, follow daily routines, and record their experiences in diary logs. At the end of each day, a town-wide narrative is compiled from these logs using a language model. The system features a real-time web visualization and tools for analyzing the cohesion between agent logs and the daily story.

## Goals

- Framework for emergent narrative generation in simulated environments.
- Dynamic, believable agent behaviors and interactions.
- Tools for analyzing and visualizing narrative coherence.
- Support for games, research, and AI-driven storytelling.

## Features

- **Multi-Agent Simulation**: Agents with distinct personalities, needs, and relationships.
- **Behavior Trees**: Decision-making logic for agent actions (work, socialize, rest, eat, etc.).
- **Daily Diaries & Town Stories**: Each agent writes a diary entry; a daily story is generated from all diaries using an LLM (OpenAI API).
- **Web Visualization**: Interactive frontend (HTML/CSS/JS) to observe agent activities, town events, and inspect agents/locations. Includes agent roster, needs bars, daily story panel, and simulation log.
- **Pause/Resume Simulation**: Control simulation flow from the UI.
- **Narrative Analysis**: NLP-based tools to measure semantic similarity and content overlap between agent logs and the daily story.
- **Customizable Agents, Behaviors, and Towns**: Easily add new agents, behaviors, and map layouts.
- **API Key via .env**: OpenAI API key can be set in `.env` for secure access.

## Project Structure

```
app.py                  # Flask web server and SocketIO backend
command.py              # Simulation runner and backend-frontend communication
narrative_analyzer.py   # Narrative analysis and visualization
behavior/               # Agent behavior trees and decision logic
simulation/             # Core simulation logic, agent definitions, LLM handler, memory, narrative system
static/                 # Frontend files (index.html, style.css, script.js, map_data.json)
simulation/narrative/daily_stories/ # Generated agent diaries and town stories
LICENSE                 # Project license
README.md               # Project documentation
```

## Installation

1. **Clone the repository**:
   ```
   git clone https://github.com/yourusername/Final-Project.git
   cd Final-Project
   ```

2. **Install Python dependencies**:
   ```
   pip install flask flask-socketio spacy scikit-learn matplotlib matplotlib-venn python-dotenv
   python -m spacy download en_core_web_sm
   ```

3. **Set up OpenAI API key**:
   - Add your OpenAI API key to `.env` as `API_KEY=sk-...`

## Usage

1. **Start the Flask server**:
   ```
   python app.py
   ```

2. **Run the simulation**:
   ```
   python command.py
   ```

3. **Open the web interface**:
   - Visit `http://localhost:5000` in your browser to view the simulation.

4. **Analyze narratives**:
   ```
   python narrative_analyzer.py
   ```
   - This will process all available days in `simulation/narrative/daily_stories/` and visualize the results.

## How It Works

- **Agents**: Defined in `simulation/entities.py` and configured in `simulation/config.py`. Each agent has a personality, schedule, and relationships.
- **Behavior Trees**: Implemented in `behavior/agent_behaviors.py` and `behavior/behavior_tree.py`. Agents make decisions based on needs, schedules, and environment.
- **Simulation Engine**: Managed by `simulation/manager.py`, which updates agent states, schedules, and interactions.
- **Memory & Diaries**: Agents record experiences in memory streams (`simulation/memory/memory.py`). Diaries are generated daily using prompts and the LLM (`simulation/narrative/narrative_system.py`).
- **Town Story**: At the end of each day, agent diaries are compiled into a town-wide story using the LLM.
- **Frontend**: `static/index.html`, `static/script.js`, and `static/style.css` provide a real-time visualization of the town and agents, including agent selection, needs bars, daily story panel, and simulation log.
- **Narrative Analysis**: `narrative_analyzer.py` uses NLP to compare agent logs and the daily story, visualizing semantic similarity and content overlap.
- **API Key Management**: Uses `python-dotenv` to load API keys from `.env`.

## Customization

- **Add Agents**: Update `simulation/config.py` with new agent configurations.
- **Modify Behaviors**: Edit or extend behavior trees in `behavior/agent_behaviors.py`.
- **Change Map**: Update `static/map_data.json` for new town layouts.
- **Adjust Prompts**: Modify diary and story prompts in `simulation/narrative/narrative_system.py`.
- **Frontend UI**: Customize `static/index.html`, `static/style.css`, and `static/script.js` for new panels, styles, or features.

## Applications

- Game development: Emergent NPC storytelling and dynamic world events.
- Research: Studying agent-based modeling, social simulation, and narrative generation.
- AI storytelling: Creating interactive stories and believable virtual societies.

## License

This project is licensed under the MIT License. See `LICENSE` for details.

## Acknowledgments

- OpenAI for LLM API
- spaCy for NLP
- Flask & SocketIO for web backend
- matplotlib & matplotlib-venn for visualization
- python-dotenv for environment variable management

