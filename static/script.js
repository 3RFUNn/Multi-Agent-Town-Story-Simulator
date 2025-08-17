// script.js
// Main frontend logic for Generative Agent Simulation.
// Handles map rendering, agent avatars, UI updates, Socket.IO events, and simulation controls.
// All major functions and event handlers are documented below.

// --- Configuration & Global State ---
const CELL_SIZE = 40;
let isEngineReady = false;

// --- Data Loaded from JSON ---
let MAP_LAYOUT = [];
let CELL_TYPES = {};
let PLACES = {};

const map_place_ids = [];
let AGENTS = {};
let selectedAgentId = null;
let isSimulationPaused = true;
let mainLog = [];
let DAILY_STORIES = [];

const dom = {
    grid: document.getElementById('game-grid-container'),
    log: document.getElementById('log-output'),
    logTitle: document.getElementById('main-log-title'),
    inspectorTitle: document.getElementById('inspector-title'),
    inspectorOutput: document.getElementById('inspector-output'),
    inspectorGoal: document.getElementById('inspector-goal'),
    inspectorNeeds: document.getElementById('inspector-needs'),
    time: document.getElementById('simulation-time'),
    pauseBtn: document.getElementById('pause-resume-btn'),
    roster: document.getElementById('agent-selection-panel'),
};

const socket = io();

// --- Socket.IO Event Handlers ---
socket.on('connect', () => logToMain('Successfully connected to simulation server.'));
socket.on('command_client_ready', () => {
    logToMain('Simulation engine is ready. Starting visualization.');
    isEngineReady = true;
    isSimulationPaused = false;
    dom.pauseBtn.disabled = false;
});

socket.on('simulation_state_update', (data) => {
    if (isSimulationPaused && isEngineReady) return;
    
    const [hour, minute] = data.time;
    const dayOfWeek = data.day_of_week; // Get the day of the week from the payload
    const ampm = hour >= 12 ? 'PM' : 'AM';
    const displayHour = hour % 12 === 0 ? 12 : hour % 12;
    const displayMinute = String(minute).padStart(2, '0');
    
    // BUG FIX: Use the dayOfWeek variable instead of "Day 1"
    dom.time.textContent = `${dayOfWeek}, ${displayHour}:${displayMinute} ${ampm}`;

    const serverAgents = data.agents;
    serverAgents.forEach(agentData => {
        if (!AGENTS[agentData.id]) logToMain(`${agentData.name} has entered the simulation.`);
        AGENTS[agentData.id] = agentData;
        updateAgentAvatar(agentData);
    });
    renderAgentSelectionPanel();
    if (selectedAgentId && AGENTS[selectedAgentId]) {
        inspectAgent(selectedAgentId, false);
    }
});

// REMOVE OLD DAILY STORY PANEL
const dailyStoryPanel = document.getElementById('daily-story-panel');
if (dailyStoryPanel) dailyStoryPanel.remove();

// CREATE NEW PANEL FOR FULL DAILY STORIES
function renderFullDailyStories() {
    let panel = document.getElementById('full-daily-story-panel');
    if (!panel) {
        panel = document.createElement('div');
        panel.id = 'full-daily-story-panel';
        panel.className = 'mt-8 p-4 bg-white rounded-lg shadow-lg max-h-[700px] overflow-y-auto';
        panel.innerHTML = `<h2 class="text-xl font-semibold text-gray-800 mb-3">All Town Daily Stories</h2><ul id="full-daily-story-list" class="space-y-2"></ul>`;
        document.getElementById('game-area').appendChild(panel);
    }
    const storyList = document.getElementById('full-daily-story-list');
    storyList.innerHTML = '';
    DAILY_STORIES.forEach(story => {
        const li = document.createElement('li');
        li.className = 'bg-gray-100 p-3 rounded shadow';
        li.innerHTML = `<strong>${story.day}</strong>:<br><span>${story.text}</span>`;
        storyList.appendChild(li);
    });
}

// Update to use new panel
socket.on('new_daily_story', (storyData) => {
    // Only add if not already present for the same day (prevents duplicates)
    if (!DAILY_STORIES.some(story => story.day === storyData.day)) {
        DAILY_STORIES.push({ day: storyData.day, text: storyData.text });
        renderFullDailyStories();
    }
});

// --- UI Rendering Functions ---
// createAgentAvatar: Creates and displays agent avatars on the map.
// updateAgentAvatar: Updates agent avatar position and interaction state.
// inspectAgent: Shows agent details in the inspector panel.
// inspectMapCell: Shows location details in the inspector panel.
// logToMain: Adds messages to the main simulation log.
// renderLog: Renders log entries in the log panel.
// renderMap: Draws the simulation map grid and cells.
// highlightSelection: Highlights selected agent/avatar in UI.
// renderAgentSelectionPanel: Renders agent roster buttons.
// renderDailyStoryPanel: Renders daily story list in the UI.
// addDailyStory: Adds a new daily story to the list.

function createAgentAvatar(agent) {
    const agentDiv = document.createElement('div');
    agentDiv.id = `agent-${agent.id}`;
    agentDiv.className = 'agent-avatar';
    agentDiv.style.backgroundColor = agent.color;
    agentDiv.textContent = agent.icon;
    agentDiv.title = agent.name;
    agentDiv.dataset.agentId = agent.id;
    agentDiv.style.transition = 'top 0.5s linear, left 0.5s linear';
    agentDiv.onclick = (e) => { e.stopPropagation(); inspectAgent(agent.id, true); };
    
    const speechBubble = document.createElement('div');
    speechBubble.className = 'speech-bubble';
    speechBubble.innerHTML = '💬';
    speechBubble.style.display = 'none';
    agentDiv.appendChild(speechBubble);

    dom.grid.appendChild(agentDiv);
}

function updateAgentAvatar(agent) {
    let agentDiv = document.getElementById(`agent-${agent.id}`);
    if (!agentDiv) createAgentAvatar(agent);
    agentDiv.style.left = `${agent.x * CELL_SIZE + 5}px`;
    agentDiv.style.top = `${agent.y * CELL_SIZE + 5}px`;

    const speechBubble = agentDiv.querySelector('.speech-bubble');
    speechBubble.style.display = agent.interacting_with ? 'block' : 'none';
}

function inspectAgent(agentId, doLog = true) {
    selectedAgentId = agentId;
    const agent = AGENTS[agentId];
    if (!agent) return;

    if (doLog) logToMain(`Now inspecting ${agent.name}'s personal log.`);
    
    dom.inspectorTitle.textContent = `Inspector: ${agent.name}`;
    dom.inspectorOutput.innerHTML = `<p><span class="font-semibold">Action:</span> ${agent.current_action}</p><p><span class="font-semibold">Money:</span> $${agent.money.toFixed(2)}</p><p><span class="font-semibold">Personality:</span> ${agent.personality.join(', ')}</p>`;
    dom.inspectorGoal.innerHTML = `<p class="font-semibold">Goal:</p><p class="text-blue-600 italic">"${agent.current_goal}"</p>`;
    
    let needsHTML = '<p class="font-semibold mt-2">Needs:</p>';
    for (const [need, value] of Object.entries(agent.needs)) {
        const color = value > 75 ? 'bg-red-500' : value > 50 ? 'bg-yellow-500' : 'bg-green-500';
        needsHTML += `<div class="capitalize mt-1"><span>${need}</span><div class="needs-bar-container"><div class="needs-bar ${color}" style="width: ${Math.round(value)}%;"></div></div></div>`;
    }
    dom.inspectorNeeds.innerHTML = needsHTML;
    
    dom.logTitle.textContent = `${agent.name}'s Log`;
    renderLog(agent.log);
    
    highlightSelection(agentId);
}

function inspectMapCell(x, y) {
    if (selectedAgentId) {
        logToMain("Switched back to main simulation log.");
    }
    selectedAgentId = null;
    const placeId = map_place_ids[y]?.[x];
    if (placeId && PLACES[placeId]) {
        const place = PLACES[placeId];
        dom.inspectorTitle.textContent = `Inspector: Location`;
        dom.inspectorOutput.innerHTML = `<p><span class="font-semibold">Name:</span> ${place.type}</p>`;
        dom.inspectorGoal.innerHTML = '';
        dom.inspectorNeeds.innerHTML = '';
    } else {
        dom.inspectorTitle.textContent = `Inspector`;
        dom.inspectorOutput.innerHTML = `<p class="text-gray-500">Click on an agent or a map cell.</p>`;
        dom.inspectorGoal.innerHTML = '';
        dom.inspectorNeeds.innerHTML = '';
    }
    
    dom.logTitle.textContent = 'Simulation Log';
    renderLog(mainLog);
    highlightSelection(null);
}

function logToMain(message) {
    const entry = `<strong>[${new Date().toLocaleTimeString()}]</strong> ${message}`;
    mainLog.unshift(entry);
    if (mainLog.length > 100) mainLog.pop();
    if (!selectedAgentId) {
        renderLog(mainLog);
    }
}

function renderLog(logArray) {
    dom.log.innerHTML = logArray.join('<br>');
}

function renderMap() {
    const MAP_ROWS = MAP_LAYOUT.length;
    const MAP_COLS = MAP_LAYOUT[0].length;

    dom.grid.innerHTML = '';
    dom.grid.style.width = `${MAP_COLS * CELL_SIZE}px`;
    dom.grid.style.height = `${MAP_ROWS * CELL_SIZE}px`;
    dom.grid.style.gridTemplateColumns = `repeat(${MAP_COLS}, ${CELL_SIZE}px)`;

    for (let y = 0; y < MAP_ROWS; y++) {
        for (let x = 0; x < MAP_COLS; x++) {
            const cell = document.createElement('div');
            const type = MAP_LAYOUT[y][x];
            cell.className = `grid-cell ${CELL_TYPES[type].class}`;
            if (CELL_TYPES[type].icon) cell.innerHTML = CELL_TYPES[type].icon;
            cell.dataset.x = x; cell.dataset.y = y;
            cell.onclick = () => inspectMapCell(x, y);
            dom.grid.appendChild(cell);
        }
    }
}

function highlightSelection(agentId) {
    document.querySelectorAll('.agent-avatar').forEach(div => {
        div.classList.toggle('ring-4', div.dataset.agentId === agentId);
        div.classList.toggle('ring-blue-500', div.dataset.agentId === agentId);
    });
    document.querySelectorAll('#agent-selection-panel button').forEach(btn => {
        btn.classList.toggle('ring-2', btn.dataset.agentId === agentId);
        btn.classList.toggle('ring-blue-500', btn.dataset.agentId === agentId);
    });
}

function renderAgentSelectionPanel() {
    dom.roster.innerHTML = ''; // Clear roster before re-rendering
    Object.values(AGENTS).forEach(agent => {
        const btn = document.createElement('button');
        btn.dataset.agentId = agent.id;
        btn.className = 'px-3 py-1 rounded-full text-sm font-medium shadow-sm hover:bg-gray-200 transition-colors flex items-center gap-1';
        btn.style.backgroundColor = agent.color;
        btn.style.color = 'white';
        btn.innerHTML = `<span class="text-white">${agent.icon}</span> ${agent.name}`;
        btn.onclick = () => inspectAgent(agent.id, true);
        dom.roster.appendChild(btn);
    });
}

function renderDailyStoryPanel() {
    const storyList = document.getElementById('daily-story-list');
    storyList.innerHTML = '';
    DAILY_STORIES.forEach(story => {
        const li = document.createElement('li');
        li.className = 'bg-gray-100 p-3 rounded shadow';
        li.innerHTML = `<strong>${story.day}</strong>:<br><span>${story.text}</span>`;
        storyList.appendChild(li);
    });
}

function addDailyStory(day, text) {
    DAILY_STORIES.push({ day, text });
    renderDailyStoryPanel();
}

// --- Simulation Controls ---
// Pause/resume button toggles simulation state and updates UI.
dom.pauseBtn.addEventListener('click', () => {
    isSimulationPaused = !isSimulationPaused;
    if (isSimulationPaused) {
        socket.emit('pause_simulation', {});
    } else {
        socket.emit('resume_simulation', {});
    }
    dom.pauseBtn.textContent = isSimulationPaused ? 'Resume Simulation' : 'Pause Simulation';
    dom.pauseBtn.classList.toggle('bg-yellow-500', !isSimulationPaused);
    dom.pauseBtn.classList.toggle('hover:bg-yellow-600', !isSimulationPaused);
    dom.pauseBtn.classList.toggle('bg-green-500', isSimulationPaused);
    dom.pauseBtn.classList.toggle('hover:bg-green-600', isSimulationPaused);
    logToMain(`Simulation ${isSimulationPaused ? 'paused' : 'resumed'}.`);
});

// --- Initialization ---
// initialize: Loads map data and sets up the frontend UI.
async function initialize() {
    logToMain('Frontend loaded. Fetching map data...');
    try {
        const response = await fetch('/map_data.json');
        const data = await response.json();

        MAP_LAYOUT = data.layout;
        CELL_TYPES = data.cell_types;
        PLACES = data.places;
        
        const MAP_ROWS = MAP_LAYOUT.length;
        const MAP_COLS = MAP_LAYOUT[0].length;

        for (let i = 0; i < MAP_ROWS; i++) {
            map_place_ids.push(Array(MAP_COLS).fill(null));
        }

        for (const placeId in PLACES) {
            PLACES[placeId].coords.forEach(coord => {
                const [x, y] = coord;
                if (y >= 0 && y < MAP_ROWS && x >= 0 && x < MAP_COLS) {
                    map_place_ids[y][x] = placeId;
                }
            });
        }
        
        renderMap();
        logToMain('Map data loaded. Waiting for simulation engine...');
        dom.pauseBtn.disabled = true;

    } catch (error) {
        console.error("Failed to load map data:", error);
        logToMain("Error: Could not load map data. Please check the console.");
    }
}

// --- Main Entry Point ---
window.onload = initialize;