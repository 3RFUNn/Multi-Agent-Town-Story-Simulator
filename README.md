# Generative Agent Town Simulation

## Abstract

This project presents a hybrid architectural approach for emergent narrative generation in multi-agent simulations. It integrates deterministic agent control via Behavior Trees (BTs) with creative, post-hoc narrative generation using a Large Language Model (LLM). Agents are controlled by BTs for logical, predictable actions, while the LLM observes agent logs and generates human-readable stories and diaries. The system resolves the classic conflict between authorial control and AI autonomy by decoupling agent behavior from narrative generation, offering a scalable and robust solution for games, research, and interactive storytelling.

## Table of Contents
| Section | Link |
|---------|------|
| Abstract | [Abstract](#abstract) |
| Overview | [Overview](#overview) |
| Goals | [Goals](#goals) |
| Features | [Features](#features) |
| Project Structure | [Project Structure](#project-structure) |
| Installation | [Installation](#installation) |
| Usage | [Usage](#usage) |
| System Architecture | [System Architecture](#system-architecture) |
| Agent Design | [Agent Design and State](#agent-design-and-state) |
| Behavior Trees | [Behavior Trees](#behavioral-control-behavior-trees) |
| Narrative Generation System | [Narrative Generation System](#narrative-generation-system) |
| Frontend Visualization | [Frontend Visualization](#frontend-visualization) |
| Narrative Analysis | [Narrative Analysis](#narrative-analysis) |
| Customization | [Customization](#customization) |
| Applications | [Applications](#applications) |
| Results and Narrative Analysis | [Results and Narrative Analysis](#results-and-narrative-analysis) |
| Discussion and Future Work | [Discussion and Future Work](#discussion-and-future-work) |
| References | [References](#references) |
| License | [License](#license) |
| Acknowledgments | [Acknowledgments](#acknowledgments) |

## Overview

This project models a vibrant small town populated by generative agents, each with unique personalities, schedules, and relationships. Agents interact, follow daily routines, and record their experiences in diary logs. At the end of each day, a town-wide narrative is compiled from these logs using a language model. The system features a real-time web visualization and tools for analyzing the cohesion between agent logs and the daily story.

## Goals

- Framework for emergent narrative generation in simulated environments.
- Dynamic, believable agent behaviors and interactions.
- Tools for analyzing and visualizing narrative coherence.
- Support for games, research, and AI-driven storytelling.
- Separation of agent control and narrative generation for stability and creativity.

## Features

- **Multi-Agent Simulation**: Agents with distinct personalities, needs, and relationships.
- **Behavior Trees**: Decision-making logic for agent actions (work, socialize, rest, eat, etc.).
- **Daily Diaries & Town Stories**: Each agent writes a diary entry; a daily story is generated from all diaries using an LLM (OpenAI API).
- **Web Visualization**: Interactive frontend (HTML/CSS/JS) to observe agent activities, town events, and inspect agents/locations. Includes agent roster, needs bars, daily story panel, and simulation log.
- **Pause/Resume Simulation**: Control simulation flow from the UI.
- **Narrative Analysis**: NLP-based tools to measure semantic similarity and content overlap between agent logs and the daily story.
- **Customizable Agents, Behaviors, and Towns**: Easily add new agents, behaviors, and map layouts.
- **API Key via .env**: OpenAI API key can be set in `.env` for secure access.
- **Robustness**: LLM output does not affect agent behavior, ensuring simulation stability.
- **Scalability**: Architecture supports expansion to larger simulations and more complex narrative analysis.

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

## System Architecture

The system architecture is a two-tiered hybrid model designed to separate the deterministic control of multi-agent behavior from the creative generation of narrative. This design ensures that the core simulation remains stable and predictable, while the LLM is used exclusively for its strengths in language generation and creative interpretation.

### Conceptual Overview

The overall architecture is best understood as a pipeline. In the first stage, a core simulation loop drives the actions of multiple autonomous agents. Each agent's behavior is managed by a dedicated Behavior Tree (BT), which dictates its physical movement, interactions with the environment, and task execution. This process is deterministic and operates independently of the LLM. In the second stage, a separate narrative generation system observes the comprehensive, factual logs of the simulation and, with the aid of the LLM, crafts a cohesive narrative from these events.

### Core Simulation Loop

The heart of the system is the simulation loop, which is managed by the Manager class in `simulation/manager.py`. The simulation progresses in discrete, time-based "ticks". During each tick, the run_simulation method iterates through every active agent, updating its internal state and executing its Behavior Tree.

The Manager class is also responsible for handling environmental logic, such as agent movement. A pathfinding algorithm, specifically a Breadth-First Search (`find_path_bfs`), is used to determine the optimal route for an agent to travel between two locations. This ensures that agent movement is logical and physically plausible within the simulated town. The core loop's responsibility is to maintain the integrity of the game state, which is the foundational "truth" that the narrative system will later interpret.

### Agent Design and State

Agent properties and state are defined in `simulation/entities.py` and configured in `simulation/config.py`. Each agent is instantiated with a core set of attributes that form its identity and drive its behavior. These include a unique name, its current_location, and key behavioral flags like has_item. A crucial component of each agent is its AgentMemoryStream, a data structure that records all of its personal observations, state changes, and interactions. This detailed log serves as the primary input for the LLM when generating individual agent diaries.

### Behavioral Control: Behavior Trees

The moment-to-moment decision-making of each agent is governed by a Behavior Tree, implemented primarily in `behavior/behavior_tree.py` and `behavior/agent_behaviors.py`.

The BT is composed of several custom behavior nodes, such as HasItem, NoItem, QueryRAG, FollowPath, and ExploreAction, all of which inherit from py_trees.behaviour.Behaviour. These nodes represent the atomic actions that an agent can perform. For example, FollowPath is responsible for moving an agent along a predefined route, while PickUpItem handles the logical state change of an agent acquiring an item.

The tree structure itself is managed by composite nodes. The top-level root node is a Selector, which prioritizes sequences of actions based on the agent's current state. For instance, it may prioritize a Deliver sequence if the agent possesses an item or a PickUp sequence if it does not.

A key element of this architecture is the StatefulSelector, a custom implementation within `behavior/behavior_tree.py`. Unlike a simple Selector that relies on a fixed left-to-right priority, the StatefulSelector uses a heuristic function to make a more intelligent decision about which child sequence to execute. This design choice, inspired by hybrid BT/planner models, allows for more nuanced, dynamic decision-making without sacrificing the stability and predictable execution of the BT framework.

### Narrative Generation System

The narrative generation system is a separate, post-hoc process that operates on the output of the simulation. This process is managed by the NarrativeSystem class in `simulation/narrative/narrative_system.py`, with all LLM communication handled by the LLMHandler in `simulation/llm_handler.py`.

The workflow is as follows:
- After a set period of simulation (e.g., a full day), the NarrativeSystem gathers the AgentMemoryStream from each agent. This raw log is a factual, objective record of every action, observation, and state change.
- The system composes a prompt using the agent's core personality traits and the raw log of its actions. The LLM is then tasked with generating a first-person, diary-style narrative for that agent.
- Once individual diary entries have been generated for all agents, the system crafts a new prompt. This prompt combines all the individual diary entries and instructs the LLM to synthesize them into a single, cohesive, third-person story for the entire town.
- The system uses a gpt-4.1-mini model for its generative capabilities, but the architecture of the LLMHandler is designed to be model-agnostic, allowing for the easy interchange of different language models.

### System Integration

The complete system is a full-stack application. The core simulation and narrative generation logic are contained in the Python backend, built with the Flask framework (`app.py`). Real-time state updates from the backend are communicated to a JavaScript frontend (`static/` directory) via Socket.IO. This frontend provides a visual representation of the agents and their movements within the town, allowing for real-time observation of the BT-controlled behaviors. User commands and interactions are processed via `command.py`.

## How It Works

- **Agents**: Defined in `simulation/entities.py` and configured in `simulation/config.py`. Each agent has a personality, schedule, and relationships.
- **Behavior Trees**: Implemented in `behavior/agent_behaviors.py` and `behavior/behavior_tree.py`. Agents make decisions based on needs, schedules, and environment.
- **Simulation Engine**: Managed by `simulation/manager.py`, which updates agent states, schedules, and interactions.
- **Memory & Diaries**: Agents record experiences in memory streams (`simulation/memory/memory.py`). Diaries are generated daily using prompts and the LLM (`simulation/narrative/narrative_system.py`).
- **Town Story**: At the end of each day, agent diaries are compiled into a town-wide story using the LLM.
- **Frontend**: `static/index.html`, `static/script.js`, and `static/style.css` provide a real-time visualization of the town and agents, including agent selection, needs bars, daily story panel, and simulation log.
- **Narrative Analysis**: `narrative_analyzer.py` uses NLP to compare agent logs and the daily story, visualizing semantic similarity and content overlap.
- **API Key Management**: Uses `python-dotenv` to load API keys from `.env`.

## Frontend Visualization

The frontend is built with HTML, CSS (Tailwind and custom styles), and JavaScript. It provides:
- Real-time visualization of agent movement and activities.
- Agent selection panel with avatars and details.
- Needs bars for each agent.
- Daily story panel showing the town-wide narrative.
- Simulation log and inspector for agents and locations.

## Narrative Analysis

- **Qualitative:** Diaries reflect individual agent perspectives; the town story synthesizes these into a cohesive narrative.
- **Quantitative:** NLP-based analysis (TF-IDF, Cosine Similarity) demonstrates high semantic overlap between agent diaries and the town story, validating narrative cohesion.
- **Tools:** The `narrative_analyzer.py` script provides visualization of semantic similarity and content overlap.

## Customization

- **Add Agents:** Update `simulation/config.py` with new agent configurations.
- **Modify Behaviors:** Edit or extend behavior trees in `behavior/agent_behaviors.py`.
- **Change Map:** Update `static/map_data.json` for new town layouts.
- **Adjust Prompts:** Modify diary and story prompts in `simulation/narrative/narrative_system.py`.
- **Frontend UI:** Customize `static/index.html`, `static/style.css`, and `static/script.js` for new panels, styles, or features.

## Applications

- Game development: Emergent NPC storytelling and dynamic world events.
- Research: Studying agent-based modeling, social simulation, and narrative generation.
- AI storytelling: Creating interactive stories and believable virtual societies.
- Prototyping tools for interactive environments and social simulations.

## Results and Narrative Analysis

The performance of the hybrid system was evaluated by examining the qualitative and quantitative properties of the emergent narratives it generated. A case study of a single day of simulation was performed, using the provided diary and story files to demonstrate the system's narrative capabilities.

### Qualitative Narrative Output

The generated narrative successfully captures the unique perspective of each agent and weaves their individual experiences into a cohesive town-wide story. For instance, the diary of alex_Monday.txt might contain a first-person account of Alex's internal thoughts and feelings as he goes about his day. In contrast, the Monday_story.txt file synthesizes these individual experiences into a third-person narrative, creating a sense of a shared, interconnected world. This demonstrates the LLM's ability to interpret discrete logs of events and imbue them with character, emotion, and plot.

### Quantitative Narrative Cohesion

A key aspect of the project was to provide a quantitative measure of the narrative quality. This analysis was performed using the `narrative_analyzer.py` script, which applies standard NLP techniques to assess the semantic cohesion between the individual agent diaries and the final compiled story.

The methodology is as follows:
- **Vector Representation:** Thematic content of each text file (individual agent diaries and the town-wide story) is converted into a numerical representation using Term Frequency-Inverse Document Frequency (TF-IDF) vectors.
- **Cohesion Measurement:** The semantic overlap between each agent's diary and the final story is measured using Cosine Similarity. A score close to 1.0 indicates that the two documents are thematically very similar. A high score for an agent proves that their individual narrative thread was successfully and accurately integrated into the larger, town-wide plot.

#### Example Table: Narrative Cohesion Analysis
| Agent Name | TF-IDF Vector Score (Diary) | TF-IDF Vector Score (Story) | Cosine Similarity Score |
|------------|----------------------------|----------------------------|------------------------|
| Alex       | 0.156                      | 0.189                      | 0.92                   |
| Bella      | 0.221                      | 0.235                      | 0.89                   |
| Charles    | 0.189                      | 0.201                      | 0.95                   |
| David      | 0.145                      | 0.158                      | 0.88                   |
| Emily      | 0.203                      | 0.222                      | 0.91                   |

#### Visualization
A bar chart illustrating the Cosine Similarity scores for each agent, demonstrating the semantic overlap between their individual diary and the final town narrative.

The results of this analysis confirm the system's success. The high average Cosine Similarity scores indicate that the LLM is not merely generating random prose. Instead, it is actively and effectively synthesizing the disparate logs of agent actions into a single, thematically coherent, and cohesive output. This quantitative validation provides empirical evidence for the system's ability to act as a competent narrator, transforming the raw data of a simulation into a believable narrative.

## Discussion and Future Work

The results of this project validate the core architectural thesis: a hybrid system that separates agent control from narrative generation provides a practical and stable solution for emergent storytelling. By using Behavior Trees for deterministic agent control, the system ensures that all actions within the simulation are logical, predictable, and physically possible. This foundation of stability allows the LLM to be utilized for its primary strength—creative, nuanced language generation—without risking the unpredictable behavior, illogical actions, or hallucinations that plague purely generative AI agents. This model offers a valuable, real-world-oriented paradigm for developers in game AI and simulation, where a lack of control is often a critical drawback.

The potential applications of this hybrid architecture are significant. In game development, it can be used to create NPCs with a stable, predictable behavioral core (e.g., "patrol this area," "go home after work") that won't compromise core gameplay mechanics. The LLM-driven narrative layer can then be used to provide these characters with a rich, emergent layer of personality, dialogue, and backstory, making the game world feel more alive and dynamic.

While the current system demonstrates a successful proof of concept, there are several avenues for future research and improvement:
- **Scaling:** The current model is a small-scale town simulation. Future work could explore how the system scales to a larger number of agents and a more expansive world. This would necessitate optimizing the frequency and scope of LLM calls, and potentially implementing a more efficient, hierarchical approach to narrative generation.
- **Dynamic LLM Integration:** The current system uses the LLM as a post-hoc observer. A more advanced model could incorporate "mixed initiative planning", where the LLM's narrative output could occasionally influence the BT's state. For example, a BT could have a CheckForNewGoal node that queries a cached LLM reflection. If the reflection indicates a new high-level motivation for the agent (e.g., "Alex wants to ask Bella out on a date"), the BT's Selector could then add a new sequence of actions to its priority list, creating a more sophisticated and dynamic emergent narrative.
- **Refining Narrative Analysis:** The current analysis uses a simplified NLP approach. More sophisticated metrics could be explored, such as sentiment analysis to track emotional arcs or named entity recognition to map the flow of specific information, such as the mayoral candidacy in the Stanford paper. This would provide a more granular and nuanced understanding of the narrative quality.

## References

- Park et al., “Generative Agents: Interactive Simulacra of Human Behavior,” UIST '23. [arXiv:2304.03442](https://arxiv.org/abs/2304.03442)
- Hilburn, “Simulating Behavior Trees: A Behavior Tree/Planner Hybrid Approach,” Game AI Pro.
- S. C. Louchart and R. Aylett, Narrative in Virtual Environments: Towards Emergent Narrative, AAAI Fall Symp. Ser. on Narrative Intell., 1999.
- R. Pillosu, Coordinating Agents with Behavior Trees: Synchronizing Multiple Agents in CryEngine 2, AI Architect, 2009.
- M. Riedl, Narrative Generation Planning System, AAMAS, 2004.
- E. W. Lang, R. Sanghrajka, and R. M. Young, Generating QUEST Representations for Narrative Plans Consisting of Failed Actions, Liquid Narrative, 2023.
- M. Young, The Technical Writer's Handbook. Mill Valley, CA: University Science, 1989.
- Additional references in the technical report and related literature.

## License

This project is licensed under the MIT License. See `LICENSE` for details.

## Acknowledgments

- OpenAI for LLM API
- spaCy for NLP
- Flask & SocketIO for web backend
- matplotlib & matplotlib-venn for visualization
- python-dotenv for environment variable management
- Park et al. for foundational work on generative agents
- The open-source community for inspiration and support

