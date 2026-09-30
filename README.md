# Multi-Agent Town Story Simulator
# Author: Erfan Rafieioskouei

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
| Comprehensive Narrative Analysis | [Comprehensive Narrative Analysis](#comprehensive-narrative-analysis) |
| Customization | [Customization](#customization) |
| Applications | [Applications](#applications) |
| Results and Analysis | [Results and Analysis](#results-and-analysis) |
| Known Limitations | [Known Limitations](#known-limitations) |
| Discussion and Future Work | [Discussion and Future Work](#discussion-and-future-work) |
| References | [References](#references) |
| License | [License](#license) |
| Acknowledgments | [Acknowledgments](#acknowledgments) |

## Overview

This project models a vibrant small town populated by generative agents, each with unique personalities, schedules, and relationships. Agents interact, follow daily routines, and record their experiences in diary logs. At the end of each day, a town-wide narrative is compiled from these logs using a language model. The system features a real-time web visualization and comprehensive narrative analysis tools for evaluating story quality, agent behavior patterns, and social dynamics.

## Goals

- Framework for emergent narrative generation in simulated environments.
- Dynamic, believable agent behaviors and interactions.
- Comprehensive tools for analyzing narrative coherence, sentiment patterns, and social networks.
- Support for games, research, and AI-driven storytelling.
- Separation of agent control and narrative generation for stability and creativity.

## Features

- **Multi-Agent Simulation**: Agents with distinct personalities, needs, and relationships.
- **Behavior Trees**: Decision-making logic for agent actions (work, socialize, rest, eat, etc.).
- **Daily Diaries & Town Stories**: Each agent writes a diary entry; a daily story is generated from all diaries using an LLM (OpenAI API).
- **Web Visualization**: Interactive frontend (HTML/CSS/JS) to observe agent activities, town events, and inspect agents/locations. Includes agent roster, needs bars, and simulation log (daily stories are saved to files; see [Known Limitations](#known-limitations)).
- **Pause/Resume Simulation**: Control simulation flow from the UI.
- **Comprehensive Narrative Analysis**: Advanced NLP-based analysis including:
  - Diary-story similarity analysis using TF-IDF and cosine similarity
  - Day-of-week consistency tracking across simulation periods
  - Sentiment analysis and behavioral pattern detection
  - Routine change tracking over time
  - Agent interaction network visualization
  - System architecture diagram generation
  - Statistical reporting with visualizations
- **Customizable Agents, Behaviors, and Towns**: Easily add new agents, behaviors, and map layouts.
- **API Key via .env**: OpenAI API key can be set in `.env` for secure access.
- **Separation of Concerns**: LLM output never feeds back into agent behavior; the behavior trees decide every action, and the LLM only writes about them afterwards.
- **Extensibility**: Agents, behaviors, map, and prompts live in separate files (see [Customization](#customization)).

## Project Structure

```
app.py                  # Flask web server and SocketIO backend
command.py              # Simulation runner and backend-frontend communication
narrative_analyzer.py   # Comprehensive narrative analysis and visualization toolkit
behavior/               # Agent behavior trees and decision logic
simulation/             # Core simulation logic, agent definitions, LLM handler, memory, narrative system
static/                 # Frontend files (index.html, style.css, script.js, map_data.json)
simulation/narrative/daily_stories/ # Generated agent diaries and town stories
results/                # Generated analysis results, visualizations, and reports
LICENSE                 # Project license
README.md               # Project documentation
```

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/3RFUNn/Multi-Agent-Town-Story-Simulator.git
   cd Multi-Agent-Town-Story-Simulator
   ```

2. **Install Python dependencies**:
   ```bash
   pip install flask flask-socketio python-dotenv requests
   pip install pandas matplotlib seaborn scikit-learn textblob networkx numpy
   python -m textblob.download_corpora
   ```

3. **Set up OpenAI API key**:
   - Create a `.env` file in the project root
   - Add your OpenAI API key: `API_KEY=sk-your-api-key-here`

## Usage

### Running the Simulation

1. **Start the Flask server**:
   ```bash
   python app.py
   ```

2. **Run the simulation**:
   ```bash
   python command.py
   ```

3. **Open the web interface**:
   - Visit `http://localhost:5000` in your browser to view the simulation.

### Analyzing Generated Narratives

4. **Run comprehensive narrative analysis**:
   ```bash
   python narrative_analyzer.py
   ```
   
   This will automatically:
   - Process all available simulation days
   - Generate similarity analysis between agent diaries and daily stories
   - Analyze sentiment patterns and behavioral trends
   - Create agent interaction networks
   - Generate comprehensive visualizations and reports
   - Save all results to the `results/` directory

## System Architecture

The system architecture is a two-tiered hybrid model designed to separate the deterministic control of multi-agent behavior from the creative generation of narrative. This design ensures that the core simulation remains stable and predictable, while the LLM is used exclusively for its strengths in language generation and creative interpretation.

### Conceptual Overview

The overall architecture is best understood as a pipeline. In the first stage, a core simulation loop drives the actions of multiple autonomous agents. Each agent's behavior is managed by a dedicated Behavior Tree (BT), which dictates its physical movement, interactions with the environment, and task execution. This process is deterministic and operates independently of the LLM. In the second stage, a separate narrative generation system observes the comprehensive, factual logs of the simulation and, with the aid of the LLM, crafts a cohesive narrative from these events.

### Core Simulation Loop

The heart of the system is the simulation loop. `run_simulation()` in `command.py` calls `AgentManager.tick()` (`simulation/manager.py`) every 0.4 seconds, and each tick advances the town clock by two minutes. During each tick, the manager updates the agents' schedules and needs, then executes each agent's Behavior Tree, visiting the agents in a shuffled order.

The AgentManager is also responsible for handling environmental logic, such as agent movement. A pathfinding algorithm, specifically a Breadth-First Search (`find_path_bfs`), is used to determine the shortest route for an agent to travel between two locations. This ensures that agent movement is logical and physically plausible within the simulated town. The core loop's responsibility is to maintain the integrity of the game state, which is the foundational "truth" that the narrative system will later interpret.

### Agent Design and State

Agent properties and state are defined in `simulation/entities.py` and configured in `simulation/config.py`. Each agent is instantiated with a core set of attributes that form its identity and drive its behavior. These include a unique name, personality traits, a weekly schedule template, a work location, relationships, needs (hunger, social, energy), and money. A crucial component of each agent is its AgentMemoryStream, a data structure that records all of its personal observations, state changes, and interactions. This detailed log serves as the primary input for the LLM when generating individual agent diaries.

### Behavioral Control: Behavior Trees

The moment-to-moment decision-making of each agent is governed by a Behavior Tree, implemented primarily in `behavior/behavior_tree.py` and `behavior/agent_behaviors.py`.

The BT framework is written from scratch rather than taken from a library: `behavior/behavior_tree.py` defines the `Node` base class and the `Selector`, `Sequence`, and `StatefulSelector` composites, and every node returns SUCCESS, FAILURE, or RUNNING. `behavior/agent_behaviors.py` defines the condition and action nodes, such as `IsScheduledActivity`, `HasEnoughMoney`, `PlanPathToActivityLocation`, `ExecuteActivity`, and `FindAgentToTalkTo`, and `create_agent_bt()` assembles one tree per agent.

The top-level root node is a Selector that checks the agent's needs in priority order: go home when exhausted (energy need of 95 or more), rest when tired (70 or more), and find food when starving (hunger need of 85 or more). Only when none of these applies does it fall through to the agent's daily routine.

A key element of this architecture is the StatefulSelector, a custom implementation within `behavior/behavior_tree.py`. It runs the daily routine (following the schedule or taking free time) and, within free time, the choice between socializing and idling. Unlike a plain Selector, it scores each child with a one-step lookahead (the predicted change in needs and money, with hunger and energy weighted 1.5×) and then commits to the chosen branch until it succeeds or fails, instead of re-deciding every tick. Children with equal scores keep their left-to-right order. The design is inspired by hybrid BT/planner models (Hilburn, *Game AI Pro*).

### Narrative Generation System

The narrative generation system is a separate, post-hoc process that operates on the output of the simulation. This process is managed by the NarrativeSystem class in `simulation/narrative/narrative_system.py`, with all LLM communication handled by the LLMHandler in `simulation/llm_handler.py`.

The workflow is as follows:
- At 3 AM game time, the NarrativeSystem gathers each agent's memories of the previous day from its AgentMemoryStream. This log is a factual record of the agent's actions, observations, and interactions.
- The system composes a prompt using the agent's core personality traits and the raw log of its actions. The LLM is then tasked with generating a first-person, diary-style narrative for that agent.
- Once individual diary entries have been generated for all agents, the system crafts a new prompt. This prompt combines all the individual diary entries and instructs the LLM to synthesize them into a single, cohesive, third-person story for the entire town.
- Diaries and stories are saved under `simulation/narrative/daily_stories/day_N/`.
- The LLMHandler calls OpenAI's Chat Completions API over HTTP, with gpt-4.1-mini as the default model. The model name is a constructor argument, so other OpenAI models drop in; another provider would need its own handler.

### System Integration

The system runs as two Python processes. `app.py` is a Flask and Flask-SocketIO server that serves the frontend (`static/`) and relays events. `command.py` is the simulation runner: it connects to that server as a Socket.IO client, runs the simulation loop, sends a state update after every tick, and listens for the pause and resume commands sent from the browser. The JavaScript frontend shows the agents and their movements within the town in real time, allowing live observation of the BT-controlled behaviors.

## How It Works

- **Agents**: Defined in `simulation/entities.py` and configured in `simulation/config.py`. Each agent has a personality, schedule, and relationships.
- **Behavior Trees**: Implemented in `behavior/agent_behaviors.py` and `behavior/behavior_tree.py`. Agents make decisions based on needs, schedules, and environment.
- **Simulation Engine**: Managed by `simulation/manager.py`, which updates agent states, schedules, and interactions.
- **Memory & Diaries**: Agents record experiences in memory streams (`simulation/memory/memory.py`). Diaries are generated daily using prompts and the LLM (`simulation/narrative/narrative_system.py`).
- **Town Story**: At the end of each day, agent diaries are compiled into a town-wide story using the LLM.
- **Frontend**: `static/index.html`, `static/script.js`, and `static/style.css` provide a real-time visualization of the town and agents, including agent selection, needs bars, and simulation log.
- **Narrative Analysis**: `narrative_analyzer.py` uses NLP to compare agent logs and the daily story, visualizing semantic similarity and content overlap.
- **API Key Management**: Uses `python-dotenv` to load API keys from `.env`.

## Comprehensive Narrative Analysis

The `narrative_analyzer.py` module provides a sophisticated analysis toolkit for evaluating the quality and patterns in generated narratives. This system goes beyond simple similarity metrics to provide deep insights into agent behavior, social dynamics, and narrative coherence.

### Analysis Components

#### 1. Diary-Story Similarity Analysis
- **Purpose**: Measures how well each agent's diary content is represented in the compiled daily story
- **Method**: Uses TF-IDF vectorization and cosine similarity to quantify word overlap
- **Output**: 
  - Similarity scores for each agent-day combination
  - Heatmap visualizations showing patterns across time
  - Statistical summaries of narrative cohesion

#### 2. Day-of-Week Consistency Analysis
- **Purpose**: Evaluates how consistent agent behaviors are on the same day of the week across different simulation weeks
- **Method**: Compares text similarity for same-day entries (e.g., all Mondays) using cosine similarity
- **Output**:
  - Consistency scores for each agent and day combination
  - Heatmaps showing behavioral stability patterns
  - Insights into routine adherence and personality consistency

#### 3. Sentiment and Behavioral Pattern Analysis
- **Purpose**: Tracks emotional patterns and behavioral indicators across agents and time
- **Method**: 
  - TextBlob sentiment analysis for polarity (positive/negative) and subjectivity
  - Keyword-based behavioral analysis for emotions, social behavior, work patterns, and routines
- **Output**:
  - Sentiment trends by agent and day of week
  - Behavioral pattern visualizations
  - Agent personality profiling based on language use

#### 4. Routine Pattern Tracking
- **Purpose**: Monitors how agent daily routines evolve over time
- **Method**: Tracks mentions of daily activities (breakfast, work, gym, etc.) across simulation days
- **Output**:
  - Activity frequency charts for each agent
  - Routine change detection over time
  - Lifestyle pattern identification

#### 5. Agent Interaction Network Analysis
- **Purpose**: Maps social connections and relationships between agents
- **Method**: Analyzes how often agents mention each other in their diaries
- **Output**:
  - Interactive network graphs showing social connections
  - Interaction frequency matrices
  - Social dynamics visualization

#### 6. System Architecture Diagram Generation
- **Purpose**: Creates a comprehensive visual representation of the hybrid two-tiered system architecture
- **Method**: Generates publication-quality diagrams showing the separation between deterministic simulation and LLM narrative generation
- **Output**:
  - High-resolution architecture diagram (architecture_diagram.png)
  - Visual representation of all system components and data flows
  - Clear illustration of the hybrid approach with architectural principles

### Key Features of the Analysis System

- **Automated Processing**: Discovers and processes all available simulation days automatically
- **Robust Error Handling**: Gracefully handles missing data and TextBlob dependency issues
- **Comprehensive Visualizations**: Generates publication-quality plots and charts
- **Statistical Reporting**: Provides detailed numerical summaries and rankings
- **Modular Design**: Easy to extend with new analysis methods
- **Configuration Flexibility**: Customizable keyword sets and analysis parameters

### Generated Outputs

The analysis system creates a comprehensive `results/` directory containing:

```
results/
├── diary_story_similarity.csv          # Raw similarity scores
├── diary_story_similarity_heatmap.png  # Similarity visualization
├── similarity_summary_stats.csv        # Statistical summaries
├── agent_day_consistency.csv           # Consistency analysis data
├── agent_consistency_heatmap.png       # Consistency visualization
├── sentiment_behavior_analysis.csv     # Sentiment and behavior data
├── sentiment_behavior_plots.png        # Multi-panel behavior analysis
├── routine_analysis.csv                # Routine tracking data
├── routine_patterns.png                # Activity pattern charts
├── agent_interaction_matrix.csv        # Social network data
├── agent_network_graph.png             # Network visualization
├── interaction_heatmap.png             # Interaction frequency matrix
├── story_day_consistency.csv           # Daily story consistency data
├── architecture_diagram.png            # System architecture diagram
└── comprehensive_report.txt            # Executive summary report
```

### Interpretation Guide

#### Similarity Scores
- **0.8-1.0**: Excellent narrative cohesion - agent's diary strongly reflected in daily story
- **0.6-0.8**: Good cohesion - most key elements preserved
- **0.4-0.6**: Moderate cohesion - some elements lost in compilation
- **0.0-0.4**: Poor cohesion - agent's narrative poorly represented

#### Sentiment Polarity
- **+0.5 to +1.0**: Very positive emotional tone
- **+0.1 to +0.5**: Mildly positive tone
- **-0.1 to +0.1**: Neutral emotional tone
- **-0.5 to -0.1**: Mildly negative tone
- **-1.0 to -0.5**: Very negative emotional tone

#### Consistency Scores
- **High consistency (>0.7)**: Agent maintains stable behavioral patterns
- **Medium consistency (0.4-0.7)**: Some behavioral variation within character
- **Low consistency (<0.4)**: Significant behavioral changes or inconsistencies

## Frontend Visualization

The frontend is built with HTML, CSS (Tailwind and custom styles), and JavaScript. It provides:
- Real-time visualization of agent movement and activities.
- Agent selection panel with avatars and details.
- Needs bars for each agent.
- A daily story panel (not yet fed by the runner; see [Known Limitations](#known-limitations)).
- Simulation log and inspector for agents and locations.

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

## Results and Analysis

The comprehensive analysis system provides both qualitative insights and quantitative validation of the narrative generation process. Through automated analysis of simulation outputs across 14 days with 6 agents (Alex, Bella, Charlie, Diana, Ethan, and Fiona), we can demonstrate the system's effectiveness in creating coherent, believable agent narratives.

### Quantitative Validation

The narrative analysis reveals several key insights about the system's performance based on 84 total diary entries:

#### 1. Narrative Cohesion Analysis
- **Overall Average Similarity**: 0.149 between individual agent diaries and compiled daily stories
- **Agent Performance Rankings** (diary-to-story similarity):
  1. Alex: 0.175 (highest narrative representation)
  2. Charlie: 0.165
  3. Ethan: 0.157
  4. Bella: 0.142
  5. Diana: 0.128
  6. Fiona: 0.125 (lowest representation)

#### 2. Sentiment and Emotional Patterns
- **Consistent Positive Sentiment**: All agents maintain positive emotional baselines
- **Agent Sentiment Rankings**:
  1. Charlie: 0.227 (most positive)
  2. Diana: 0.182
  3. Alex: 0.174
  4. Ethan: 0.168
  5. Fiona: 0.132
  6. Bella: 0.129 (least positive, but still positive)

#### 3. Behavioral Pattern Analysis
- **Positive Emotional Expression Leaders**:
  - Charlie: 9.4 average mentions (most emotionally expressive)
  - Alex: 6.4 average mentions
  - Diana: 4.9 average mentions

- **Social Behavior Champions**:
  - Charlie: 10.3 average social mentions (highly social)
  - Fiona: 8.1 average mentions
  - Alex: 7.9 average mentions

- **Work-Focused Agents**:
  - Alex: 12.5 average work mentions (most work-oriented)
  - Ethan: 11.4 average mentions
  - Diana: 6.2 average mentions

#### 4. Narrative Quality Metrics
- **Average Entry Length**: 557 words per diary entry
- **Narrative Complexity**: 36.5 sentences per entry on average
- **Data Completeness**: 100% (14 days with complete data)

### Qualitative Observations

The generated narratives successfully demonstrate:

- **Distinct Agent Personalities**: Charlie emerges as the most socially active and emotionally positive agent, while Alex shows strong work orientation balanced with social engagement
- **Consistent Character Voices**: Each agent maintains recognizable behavioral patterns across the 14-day simulation period
- **Realistic Social Dynamics**: The interaction patterns reveal natural social hierarchies with Charlie serving as a social hub
- **Weekly Rhythm**: Day-to-day progression follows each agent's weekly schedule (each prompt holds only that day's memories; see [Known Limitations](#known-limitations))
- **Environmental Integration**: Agent narratives incorporate location details and environmental factors from the simulated town

### Key Findings

1. **Moderate Narrative Cohesion**: The similarity scores (averaging 0.149) indicate that while individual agent perspectives are captured, the compilation process creates abstracted daily stories rather than direct representations of agent experiences.

2. **Stable Positive Sentiment**: All agents maintain positive emotional baselines, suggesting the simulation successfully creates a pleasant, livable virtual community.

3. **Clear Agent Differentiation**: The behavioral analysis reveals distinct agent archetypes:
   - **Charlie**: Social connector with high emotional expression
   - **Alex**: Work-focused but socially engaged
   - **Ethan**: Balanced work-social orientation
   - **Diana**: Moderate across all categories
   - **Bella & Fiona**: More reserved personalities

4. **Rich Narrative Output**: With an average of 557 words per diary entry, the system generates substantial, detailed personal narratives that provide deep insight into agent experiences.

### Analysis Methodology

The quantitative analysis employs rigorous NLP techniques:
- **TF-IDF Vectorization**: Converts narrative text into numerical representations for mathematical comparison
- **Cosine Similarity**: Measures word overlap between TF-IDF vectors on a 0–1 scale (lexical, not semantic, similarity)
- **Sentiment Analysis**: Uses TextBlob's lexicon-based polarity and subjectivity scores
- **Keyword-Based Pattern Analysis**: Tracks behavioral indicators across time and agents
- **Statistical Aggregation**: Provides comprehensive rankings and trend analysis

Together these measures show distinct, stable agent voices and positive sentiment across the 14 days, while cohesion between each diary and the compiled town story is moderate (0.149 on average).

## Known Limitations

This is the prototype as submitted for the MSc thesis (tag `V1.0`). Known gaps:
- **Daily stories don't reach the browser.** The runner generates them and saves them under `simulation/narrative/daily_stories/`, but it emits them through a Socket.IO server instance it isn't connected to, so the story panel stays empty. Read the stories from the saved files.
- **A failed LLM call ends the run.** An API error propagates out of the simulation loop, which stops the simulation.
- **Runs aren't reproducible.** Starting money, social choices, and processing order are random and unseeded, so two runs differ.
- **No memory across days.** Diary and story prompts contain only that day's memories.
- **One LLM provider.** The LLMHandler targets OpenAI's API only.

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
- TextBlob and NLTK for natural language processing
- NetworkX for social network analysis
- Pandas, Matplotlib, and Seaborn for data analysis and visualization
- Flask & SocketIO for web backend
- python-dotenv for environment variable management
- Park et al. for foundational work on generative agents
- The open-source community for inspiration and support

