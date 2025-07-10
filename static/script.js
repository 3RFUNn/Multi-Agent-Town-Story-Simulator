// --- Configuration & Data ---
const CELL_SIZE = 40; // Pixels per grid cell

// Map layout based on the provided image
const MAP_LAYOUT = [
    ['G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
    ['G', 'O', 'O', 'O', 'O', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'L', 'L', 'L', 'L', 'L', 'P', 'P', 'P', 'P', 'P', 'P', 'G'],
    ['G', 'O', 'O', 'O', 'O', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'P', 'L', 'L', 'L', 'L', 'L', 'P', 'G', 'G', 'G', 'G', 'P', 'G'],
    ['G', 'O', 'O', 'O', 'O', 'P', 'G', 'B', 'B', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'P', 'L', 'L', 'L', 'L', 'L', 'P', 'G', 'G', 'G', 'G', 'P', 'G'],
    ['G', 'P', 'P', 'P', 'P', 'P', 'G', 'B', 'B', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'G', 'G', 'G', 'G', 'P', 'G'],
    ['G', 'P', 'G', 'G', 'G', 'G', 'G', 'P', 'P', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'P', 'G'],
    ['G', 'P', 'G', 'C', 'C', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'P', 'G'],
    ['G', 'P', 'G', 'C', 'C', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'P', 'G'],
    ['G', 'P', 'P', 'P', 'P', 'P', 'G', 'F', 'F', 'F', 'F', 'F', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'P', 'G'],
    ['G', 'P', 'G', 'G', 'G', 'G', 'G', 'F', 'F', 'F', 'F', 'F', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'P', 'G'],
    ['G', 'P', 'G', 'K', 'K', 'K', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'G'],
    ['G', 'P', 'G', 'K', 'K', 'K', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
    ['G', 'P', 'G', 'K', 'K', 'K', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
    ['G', 'P', 'G', 'H', 'H', 'H', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'], // Changed P to H for (3,13) to (5,13)
    ['G', 'P', 'G', 'H', 'H', 'H', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
    ['G', 'P', 'G', 'H', 'H', 'H', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
    ['G', 'P', 'P', 'P', 'P', 'P', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
    ['G', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
    ['G', 'P', 'G', 'D', 'D', 'D', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
    ['G', 'P', 'G', 'D', 'D', 'D', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
    ['G', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P', 'G'],
    ['G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G']
];

const MAP_ROWS = MAP_LAYOUT.length;
const MAP_COLS = MAP_LAYOUT[0].length;

// Map character codes to CSS classes and SVG icons
const CELL_TYPES = {
    'G': { class: 'grass', icon: '' },
    'P': { class: 'path', icon: '' },
    'H': { class: 'house', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3L2 12h3v8h6v-6h2v6h6v-8h3L12 3zm0 2.69l5 4.5V18h-3v-6h-4v6H7v-8.81l5-4.5z"/></svg>' }, // House
    'C': { class: 'cafe', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M20 3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 2v3H4V5h16zM4 19V9h16v10H4zM6 11h2v2H6zm4 0h2v2h-2zm4 0h2v2h-2z"/></svg>' }, // Cafe
    'K': { class: 'park', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M17 12c-2.76 0-5 2.24-5 5s2.24 5 5 5 5-2.24 5-5-2.24-5-5-5zm-5-9c-2.76 0-5 2.24-5 5s2.24 5 5 5 5-2.24 5-5-2.24-5-5-5zM2 17c0 2.76 2.24 5 5 5s5-2.24 5-5-2.24-5-5-5-5 2.24-5 5z"/></svg>' }, // Park (tree icon)
    'S': { class: 'supply_store', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 14H4V8h16v10zm-5-7H9v2h6z"/></svg>' }, // Supply Store (box icon)
    'L': { class: 'college', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3L1 9l11 6 11-6-11-6zm0 10.99L5 9.75l7-3.75 7 3.75-7 3.75zM3 17.25V12h2v5.25c0 1.66 1.34 3 3 3h8c1.66 0 3-1.34 3-3V12h2v5.25c0 2.76-2.24 5-5 5H8c-2.76 0-5-2.24-5-5z"/></svg>' }, // College (graduation cap)
    'F': { class: 'grocery_pharmacy', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M7 18c-1.1 0-1.99.9-1.99 2S5.9 22 7 22s2-.9 2-2-.9-2-2-2zm10 0c-1.1 0-1.99.9-1.99 2S15.9 22 17 22s2-.9 2-2-.9-2-2-2zm-8.7-17.7c-.4-.4-.9-.3-1.2.1L3 8.2c-.2.2-.3.5-.3.8V15h16V9.5c0-.3-.1-.6-.3-.8l-4.1-7.8c-.3-.4-.8-.5-1.2-.1L12 3.8l-3.7-3.5zM12 13H5.76L4 9.5 5.76 6H12v7zm2-7h3.24L19 9.5 17.24 13H14V6z"/></svg>' }, // Grocery/Pharmacy (shopping cart)
    'D': { class: 'college_dorm', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M12 5.5c-2.76 0-5 2.24-5 5s2.24 5 5 5 5-2.24 5-5-2.24-5-5-5zm0 2c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zM2 19c0 2.76 2.24 5 5 5s5-2.24 5-5-2.24-5-5-5-5 2.24-5 5zm5 2c1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3 1.34 3 3 3zM17 19c0 2.76 2.24 5 5 5s5-2.24 5-5-2.24-5-5-5-5 2.24-5 5zm5 2c1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3 1.34 3 3 3z"/></svg>' }, // College Dorm (bed icon)
    'B': { class: 'bar', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M3 10h18v2H3zm0-4h18v2H3zm0 8h18v2H3z"/></svg>' }, // Bar (drink icon, simplified)
    'O': { class: 'co_living', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>' } // Co-Living Space (group icon)
};


// Define named places with their coordinates and type
const PLACES = {
    'co_living_space': { type: 'Co-Living Space', name: 'Co-Living Space', coords: [[1,1],[2,1],[3,1],[4,1],[1,2],[2,2],[3,2],[4,2],[1,3],[2,3],[3,3],[4,3]] },
    'bar_hobbs': { type: 'Bar', name: 'Hobbs Bar', coords: [[7,3],[8,3],[7,4],[8,4]] },
    'cafe_hobbs': { type: 'Cafe', name: 'Hobbs Cafe', coords: [[3,6],[4,6],[3,7],[4,7]] },
    'supply_store_harvey': { type: 'Supply Store', name: 'Harvey Oak Supply Store', coords: [[6,1],[7,1],[6,2],[7,2]] },
    'college_oak_hill': { type: 'College', name: 'Oak Hill College', coords: [[18,1],[19,1],[20,1],[21,1],[22,1],[18,2],[19,2],[20,2],[21,2],[22,2],[18,3],[19,3],[20,3],[21,3],[22,3]] },
    'grocery_pharmacy_willow': { type: 'Grocery & Pharmacy', name: 'Willow Market and Pharmacy', coords: [[7,8],[8,8],[9,8],[10,8],[11,8],[7,9],[8,9],[9,9],[10,9],[11,9]] },
    'johnson_park': { type: 'Park', name: 'Johnson Park', coords: [[3,10],[4,10],[5,10],[3,11],[4,11],[5,11],[3,12],[4,12],[5,12]] },
    'main_house': { type: 'House', name: 'Main House Area', coords: [[3,13],[4,13],[5,13],[3,14],[4,14],[5,14],[3,15],[4,15],[5,15]] }, // Consolidated house area
    'college_dorm_main': { type: 'College Dorm', name: 'Main College Dorm', coords: [[3,18],[4,18],[5,18],[3,19],[4,19],[5,19]] },
};

// Create a reverse lookup for places: map_place_ids[y][x] = placeId
const map_place_ids = Array(MAP_ROWS).fill(null).map(() => Array(MAP_COLS).fill(null));
for (const placeId in PLACES) {
    PLACES[placeId].coords.forEach(coord => {
        const [x, y] = coord;
        if (y >= 0 && y < MAP_ROWS && x >= 0 && x < MAP_COLS) {
            map_place_ids[y][x] = placeId;
        }
    });
}

// Initial agent data with home locations
let AGENTS = [
    { id: 'emily', name: 'Emily Carter', x: 3, y: 14, icon: 'EC', color: '#FF69B4', currentAction: 'At home', home: {x: 3, y: 14}, destination: null, path: [], pathIndex: 0, isMoving: false, state: 'idle', actionEndTime: 0, individualLog: [] }, // Pink
    { id: 'sophia', name: 'Sophia Reyes', x: 3, y: 6, icon: 'SR', color: '#8A2BE2', currentAction: 'At home', home: {x: 3, y: 6}, destination: null, path: [], pathIndex: 0, isMoving: false, state: 'idle', actionEndTime: 0, individualLog: [] }, // Blue Violet
    { id: 'mia', name: 'Mia Bennett', x: 24, y: 14, icon: 'MB', color: '#DAA520', currentAction: 'At home', home: {x: 24, y: 14}, destination: null, path: [], pathIndex: 0, isMoving: false, state: 'idle', actionEndTime: 0, individualLog: [] }, // Goldenrod

    { id: 'ryan', name: 'Ryan Cooper', x: 24, y: 1, icon: 'RC', color: '#00CED1', currentAction: 'At home', home: {x: 24, y: 1}, destination: null, path: [], pathIndex: 0, isMoving: false, state: 'idle', actionEndTime: 0, individualLog: [] }, // Dark Turquoise
    { id: 'daniel', name: 'Daniel Park', x: 3, y: 18, icon: 'DP', color: '#FF4500', currentAction: 'At home', home: {x: 3, y: 18}, destination: null, path: [], pathIndex: 0, isMoving: false, state: 'idle', actionEndTime: 0, individualLog: [] }, // Orange Red
    { id: 'lucas', name: 'Lucas Brooks', x: 18, y: 1, icon: 'LB', color: '#32CD32', currentAction: 'At home', home: {x: 18, y: 1}, destination: null, path: [], pathIndex: 0, isMoving: false, state: 'idle', actionEndTime: 0, individualLog: [] }  // Lime Green
];

const AGENT_COLORS = ['#17a2b8', '#ff6347', '#663399', '#3cb371', '#ffa500', '#00bcd4', '#e91e63']; // More colors for dynamic agents
let nextAgentIdCounter = AGENTS.length;

// --- DOM Elements ---
const gameGridWrapper = document.getElementById('game-grid-wrapper');
const gameGridContainer = document.getElementById('game-grid-container');
const mainLogTitle = document.getElementById('main-log-title'); // New: Main Log Title
const logOutput = document.getElementById('log-output');
const inspectorTitle = document.getElementById('inspector-title'); // New: Inspector Title
const inspectorOutput = document.getElementById('inspector-output');
const simulationTimeDisplay = document.getElementById('simulation-time');
const addAgentBtn = document.getElementById('add-agent-btn');
const pauseResumeBtn = document.getElementById('pause-resume-btn');
const agentSelectionPanel = document.getElementById('agent-selection-panel');

let simulationDay = 1;
let simulationHour = 9;
let simulationMinute = 0;
let isSimulationPaused = false;
let currentViewedAgentLog = null; // Stores the ID of the agent whose individual log is being viewed

// --- Socket.IO Connection ---
const socket = io();

socket.on('connect', () => {
    console.log('Connected to Flask-SocketIO');
    logSimulation('Connected to simulation backend.');
    // When frontend connects, send initial state of all agents to command.py
    AGENTS.forEach(agent => {
        socket.emit('agent_state_update', {
            agentId: agent.id,
            state: agent.state,
            x: agent.x,
            y: agent.y
        });
    });
});

socket.on('log_message', (data) => {
    console.log('Log from Python:', data.message);
    logSimulation(`[Backend] ${data.message}`);
});

socket.on('set_agent_path', (data) => {
    const agent = AGENTS.find(a => a.id === data.agentId);
    if (agent) {
        // Store agent's current location *before* path is set as the starting point
        const startLocationName = getPlaceOrCoordinates(agent.x, agent.y);
        
        agent.path = data.path;
        agent.pathIndex = 0;
        agent.destination = { x: data.path[data.path.length - 1][0], y: data.path[data.path.length - 1][1] };
        
        if (agent.path.length > 1) {
            agent.isMoving = true;
            agent.state = 'moving';
            agent.currentAction = `Heading to ${data.destinationName || 'a new place'}`;
            logSimulation(`${agent.name} is moving from ${startLocationName} to ${data.destinationName || 'a new place'}.`, agent.id); // Log to individual
        } else if (agent.path.length === 1 && agent.x === agent.destination.x && agent.y === agent.destination.y) {
            agent.isMoving = false;
            agent.state = 'doing_action';
            const actionDurationMinutes = Math.floor(Math.random() * 31) + 30;
            agent.actionEndTime = getCurrentSimulationMinutes() + actionDurationMinutes;
            const placeAtDestination = getPlaceOrCoordinates(agent.x, agent.y);
            agent.currentAction = `Arrived at ${placeAtDestination} and is now performing an action.`;
            logSimulation(`${agent.name} is at ${placeAtDestination} and is now performing an action.`, agent.id); // Log to individual
            socket.emit('agent_state_update', {
                agentId: agent.id,
                state: agent.state,
                x: agent.x,
                y: agent.y
            });
        } else {
            agent.destination = null;
            agent.currentAction = `Stuck (command failed)`;
            agent.state = 'idle';
            logSimulation(`${agent.name} cannot find a valid path to destination.`, agent.id); // Log to individual
            socket.emit('agent_state_update', {
                agentId: agent.id,
                state: agent.state,
                x: agent.x,
                y: agent.y
            });
        }
    }
});

// Listen for command client readiness signal
socket.on('command_client_ready', () => {
    logSimulation("Command script is connected and ready. Starting simulation.");
    startSimulation();
});


// --- Map Rendering ---
function renderMap() {
    gameGridContainer.innerHTML = '';
    gameGridContainer.style.width = `${MAP_COLS * CELL_SIZE}px`;
    gameGridContainer.style.height = `${MAP_ROWS * CELL_SIZE}px`;
    gameGridContainer.style.gridTemplateColumns = `repeat(${MAP_COLS}, ${CELL_SIZE}px)`;
    gameGridContainer.style.gridTemplateRows = `repeat(${MAP_ROWS}, ${CELL_SIZE}px)`;


    for (let rowIndex = 0; rowIndex < MAP_ROWS; rowIndex++) {
        for (let colIndex = 0; colIndex < MAP_COLS; colIndex++) {
            const cellTypeChar = MAP_LAYOUT[rowIndex][colIndex];
            const cell = document.createElement('div');
            cell.classList.add('grid-cell', CELL_TYPES[cellTypeChar].class);
            cell.dataset.x = colIndex;
            cell.dataset.y = rowIndex;

            if (CELL_TYPES[cellTypeChar].icon) {
                cell.innerHTML = CELL_TYPES[cellTypeChar].icon;
            }

            cell.addEventListener('click', (event) => {
                event.stopPropagation();
                inspectMapCell(colIndex, rowIndex);
            });
            gameGridContainer.appendChild(cell);
        }
    }
}

// --- Agent Management ---
function placeAgents() {
    document.querySelectorAll('.agent-avatar').forEach(el => el.remove());

    AGENTS.forEach(agent => {
        const cell = gameGridContainer.querySelector(`[data-x="${agent.x}"][data-y="${agent.y}"]`);
        if (cell) {
            const agentDiv = document.createElement('div');
            agentDiv.id = `agent-${agent.id}`;
            agentDiv.classList.add('agent-avatar');
            agentDiv.style.backgroundColor = agent.color;
            agentDiv.textContent = agent.icon;
            agentDiv.title = agent.name;
            agentDiv.dataset.agentId = agent.id;
            agentDiv.addEventListener('click', (event) => {
                event.stopPropagation();
                toggleAgentLogView(agent.id); // Changed to toggle
            });
            cell.appendChild(agentDiv);
        }
    });
    renderAgentSelectionPanel();
}

function moveAgentStep(agent) {
    if (agent.path && agent.path.length > 0 && agent.pathIndex < agent.path.length) {
        const [nextX, nextY] = agent.path[agent.pathIndex];
        const oldX = agent.x;
        const oldY = agent.y;

        if (isCellOccupied(nextX, nextY, agent.id)) {
            agent.isMoving = false;
            agent.path = [];
            agent.state = 'idle';
            agent.currentAction = `Waiting for clear path at (${oldX},${oldY})`;
            logSimulation(`${agent.name} waiting: path to (${nextX},${nextY}) is blocked.`, agent.id); // Log to individual
            socket.emit('agent_state_update', {
                agentId: agent.id,
                state: agent.state,
                x: agent.x,
                y: agent.y
            });
            return;
        }


        agent.x = nextX;
        agent.y = nextY;

        const agentDiv = document.getElementById(`agent-${agent.id}`);
        const newCell = gameGridContainer.querySelector(`[data-x="${nextX}"][data-y="${nextY}"]`);

        if (agentDiv && newCell) {
            newCell.appendChild(agentDiv);
            // Removed per-step movement logging
        } else {
            console.error(`Failed to move agent ${agent.id} to (${nextX},${nextY}). Cell or agentDiv not found.`);
            agent.isMoving = false;
            agent.path = [];
            agent.state = 'idle';
            logSimulation(`${agent.name} encountered an error moving to (${nextX},${nextY}).`, agent.id); // Log to individual
            socket.emit('agent_state_update', {
                agentId: agent.id,
                state: agent.state,
                x: agent.x,
                y: agent.y
            });
        }

        agent.pathIndex++;

        if (agent.pathIndex >= agent.path.length) {
            agent.isMoving = false;
            agent.path = [];
            agent.destination = null;
            agent.state = 'doing_action';
            const actionDurationMinutes = Math.floor(Math.random() * 31) + 30;
            agent.actionEndTime = getCurrentSimulationMinutes() + actionDurationMinutes;

            const placeAtDestination = getPlaceOrCoordinates(agent.x, agent.y);
            agent.currentAction = `Relaxing at ${placeAtDestination}`;
            logSimulation(`${agent.name} arrived at ${placeAtDestination} and is now ${agent.currentAction}.`, agent.id); // Log to individual
            socket.emit('agent_state_update', {
                agentId: agent.id,
                state: agent.state,
                x: agent.x,
                y: agent.y
            });
        }
    } else {
        agent.isMoving = false;
        agent.path = [];
        if (agent.state !== 'idle' && agent.state !== 'doing_action') { // Prevent logging if already idle/doing action
             agent.state = 'idle';
             logSimulation(`${agent.name} finished its path or had no path. Now idle.`, agent.id); // Log to individual
             socket.emit('agent_state_update', {
                 agentId: agent.id,
                 state: agent.state,
                 x: agent.x,
                 y: agent.y
             });
        }
    }
}

function addRandomAgent() {
    const newAgentId = `agent${nextAgentIdCounter}`;
    const randomX = Math.floor(Math.random() * MAP_COLS);
    const randomY = Math.floor(Math.random() * MAP_ROWS);
    const newAgent = {
        id: newAgentId,
        name: `New Agent ${nextAgentIdCounter}`,
        x: randomX,
        y: randomY,
        icon: `A${nextAgentIdCounter}`,
        color: AGENT_COLORS[nextAgentIdCounter % AGENT_COLORS.length],
        currentAction: 'Exploring',
        home: {x: randomX, y: randomY},
        destination: null,
        path: [],
        pathIndex: 0,
        isMoving: false,
        state: 'idle',
        actionEndTime: 0,
        individualLog: [] // Initialize individual log for new agent
    };
    AGENTS.push(newAgent);
    placeAgents();
    toggleAgentLogView(newAgentId); // View new agent's log
    logSimulation(`New agent ${newAgent.name} added at (${randomX},${randomY}).`, newAgent.id); // Log to individual
    nextAgentIdCounter++;
    socket.emit('agent_state_update', {
        agentId: newAgent.id,
        state: newAgent.state,
        x: newAgent.x,
        y: newAgent.y
    });
}

// --- Pathfinding (BFS) ---
function isValid(x, y) {
    return x >= 0 && x < MAP_COLS && y >= 0 && y < MAP_ROWS;
}

function isTraversable(x, y) {
    if (!isValid(x, y)) return false;
    const cellType = MAP_LAYOUT[y][x];
    return cellType === 'P' ||
           cellType === 'G' ||
           cellType === 'H' ||
           cellType === 'C' ||
           cellType === 'K' ||
           cellType === 'S' ||
           cellType === 'L' ||
           cellType === 'F' ||
           cellType === 'D' ||
           cellType === 'B' ||
           cellType === 'O';
}

function findPath(startX, startY, targetX, targetY) {
    if (!isTraversable(startX, startY) || !isTraversable(targetX, targetY)) {
        return [];
    }
    if (startX === targetX && startY === targetY) {
        return [[targetX, targetY]];
    }

    const queue = [];
    const visited = new Set();
    const parentMap = new Map();

    queue.push([startX, startY]);
    visited.add(`${startX},${startY}`);
    parentMap.set(`${startX},${startY}`, null);

    const directions = [
        [0, 1], [0, -1], [1, 0], [-1, 0]
    ];

    while (queue.length > 0) {
        const [currentX, currentY] = queue.shift();

        if (currentX === targetX && currentY === targetY) {
            const path = [];
            let curr = `${targetX},${targetY}`;
            while (curr !== null) {
                const [x, y] = curr.split(',').map(Number);
                path.unshift([x, y]);
                curr = parentMap.get(curr);
            }
            return path;
        }

        for (const [dx, dy] of directions) {
            const nextX = currentX + dx;
            const nextY = currentY + dy;
            const nextCoord = `${nextX},${nextY}`;

            if (isValid(nextX, nextY) && isTraversable(nextX, nextY) && !visited.has(nextCoord)) {
                visited.add(nextCoord);
                parentMap.set(nextCoord, `${currentX},${currentY}`);
                queue.push([nextX, nextY]);
            }
        }
    }
    return [];
}

// --- Simulation Time ---
function getCurrentSimulationMinutes() {
    return (simulationDay - 1) * 24 * 60 + simulationHour * 60 + simulationMinute;
}

function updateSimulationTime() {
    if (isSimulationPaused) return;

    simulationMinute += 10;
    if (simulationMinute >= 60) {
        simulationMinute = 0;
        simulationHour++;
        if (simulationHour >= 24) {
            simulationHour = 0;
            simulationDay++;
        }
    }
    const ampm = simulationHour >= 12 ? 'PM' : 'AM';
    const displayHour = simulationHour % 12 === 0 ? 12 : simulationHour % 12;
    const displayMinute = simulationMinute < 10 ? '0' + simulationMinute : simulationMinute;
    simulationTimeDisplay.textContent = `Day ${simulationDay}, ${displayHour}:${displayMinute} ${ampm}`;
}

// --- Logging & Inspector ---
let selectedAgentId = null; // Currently selected agent for inspector/individual log view
const mainSimulationLog = []; // Stores the full main log

function logSimulation(message, agentId = null) {
    const timestamp = `[Day ${simulationDay}, ${simulationHour}:${simulationMinute < 10 ? '0' : ''}${simulationMinute}]`;
    const fullMessage = `${timestamp} ${message}`;

    // Add to main log
    mainSimulationLog.unshift(fullMessage); // Add to the top
    if (mainSimulationLog.length > 100) { // Keep main log from getting too long
        mainSimulationLog.pop();
    }
    
    // Add to individual agent log if agentId is provided
    if (agentId) {
        const agent = AGENTS.find(a => a.id === agentId);
        if (agent) {
            agent.individualLog.unshift(fullMessage);
            if (agent.individualLog.length > 50) { // Keep individual log shorter
                agent.individualLog.pop();
            }
        }
    }

    // Update the displayed log based on current view
    updateLogDisplay();
}

function updateLogDisplay() {
    logOutput.innerHTML = ''; // Clear current display
    let logToDisplay = [];

    if (currentViewedAgentLog) {
        const agent = AGENTS.find(a => a.id === currentViewedAgentLog);
        if (agent) {
            logToDisplay = agent.individualLog;
            mainLogTitle.textContent = `Log: ${agent.name}`;
        } else {
            // Agent no longer exists or ID is invalid, revert to main log
            currentViewedAgentLog = null;
            logToDisplay = mainSimulationLog;
            mainLogTitle.textContent = `Simulation Log`;
        }
    } else {
        logToDisplay = mainSimulationLog;
        mainLogTitle.textContent = `Simulation Log`;
    }

    logToDisplay.forEach(msg => {
        const logEntry = document.createElement('p');
        logEntry.innerHTML = msg; // Message already contains timestamp
        logOutput.appendChild(logEntry); // Append for chronological order in display
    });
}


let lastHighlightedCells = [];

function clearHighlight() {
    lastHighlightedCells.forEach(cell => cell.classList.remove('highlight-place'));
    lastHighlightedCells = [];
}

function inspectMapCell(x, y) {
    clearHighlight();
    selectedAgentId = null; // Deselect agent for inspector view
    currentViewedAgentLog = null; // Revert to main log view

    const placeId = map_place_ids[y]?.[x];
    if (placeId && PLACES[placeId]) {
        const place = PLACES[placeId];
        inspectorTitle.textContent = `Inspector: ${place.name}`;
        inspectorOutput.innerHTML = `
            <p><span class="font-semibold text-gray-700">Type:</span> ${place.type}</p>
            <p><span class="font-semibold text-gray-700">Name:</span> ${place.name}</p>
            <p><span class="font-semibold text-gray-700">Coordinates:</span> (${x}, ${y}) - Part of ${place.name}</p>
        `;
        place.coords.forEach(coord => {
            const [px, py] = coord;
            const cell = gameGridContainer.querySelector(`[data-x="${px}"][data-y="${py}"]`);
            if (cell) {
                cell.classList.add('highlight-place');
                lastHighlightedCells.push(cell);
            }
        });
        logSimulation(`Inspected map cell (${x},${y}): ${place.name}.`); // Log to main
    } else {
        inspectorTitle.textContent = `Inspector`;
        inspectorOutput.innerHTML = `<p class="text-gray-500">No named place at (${x},${y}).</p>`;
        logSimulation(`Inspected map cell (${x},${y}): No named place.`); // Log to main
    }
    // Clear agent visual highlights and selection panel highlights
    document.querySelectorAll('.agent-avatar').forEach(div => div.classList.remove('ring-2', 'ring-blue-500'));
    document.querySelectorAll('#agent-selection-panel button').forEach(btn => btn.classList.remove('ring-2', 'ring-blue-500', 'bg-blue-100'));
    updateLogDisplay(); // Refresh log to main view
}

function inspectAgent(agentId) {
    clearHighlight();
    selectedAgentId = agentId; // Set selected agent for inspector view
    
    const agent = AGENTS.find(a => a.id === agentId);
    if (agent) {
        inspectorTitle.textContent = `Inspector: ${agent.name}`;
        inspectorOutput.innerHTML = `
            <p><span class="font-semibold text-gray-700">Name:</span> ${agent.name}</p>
            <p><span class="font-semibold text-gray-700">Location:</span> (${agent.x}, ${agent.y})</p>
            <p><span class="font-semibold text-gray-700">State:</span> ${agent.state.replace('_', ' ').toUpperCase()}</p>
            <p><span class="font-semibold text-gray-700">Current Action:</span> ${agent.currentAction}</p>
            ${agent.destination ? `<p><span class="font-semibold text-gray-700">Destination:</span> (${agent.destination.x}, ${agent.destination.y})</p>` : ''}
        `;
        // Highlight agent avatar on map
        document.querySelectorAll('.agent-avatar').forEach(div => div.classList.remove('ring-2', 'ring-blue-500'));
        const agentAvatar = document.getElementById(`agent-${agentId}`);
        if (agentAvatar) {
            agentAvatar.classList.add('ring-2', 'ring-blue-500');
        }
        // Highlight agent in selection panel
        document.querySelectorAll('#agent-selection-panel button').forEach(btn => btn.classList.remove('ring-2', 'ring-blue-500', 'bg-blue-100'));
        const selectedBtn = document.querySelector(`#agent-selection-panel button[data-agent-id="${agentId}"]`);
        if (selectedBtn) {
            selectedBtn.classList.add('ring-2', 'ring-blue-500', 'bg-blue-100');
        }

        logSimulation(`Inspected Agent: ${agent.name}.`); // Log to main
        currentViewedAgentLog = agentId; // Set individual log view
        updateLogDisplay(); // Refresh log to individual view
    }
}

// New function to toggle individual agent log view
function toggleAgentLogView(agentId) {
    if (currentViewedAgentLog === agentId) {
        // If already viewing this agent's log, revert to main log
        currentViewedAgentLog = null;
        selectedAgentId = null; // Also deselect for inspector
        clearHighlight(); // Clear map highlight
        // Clear agent visual highlights and selection panel highlights
        document.querySelectorAll('.agent-avatar').forEach(div => div.classList.remove('ring-2', 'ring-blue-500'));
        document.querySelectorAll('#agent-selection-panel button').forEach(btn => btn.classList.remove('ring-2', 'ring-blue-500', 'bg-blue-100'));
        inspectorTitle.textContent = `Inspector`;
        inspectorOutput.innerHTML = `<p class="text-gray-500">Click on an agent or a map cell.</p>`;
        updateLogDisplay(); // Show main log
    } else {
        // View this agent's log
        inspectAgent(agentId); // This will set currentViewedAgentLog and update display
    }
}


function renderAgentSelectionPanel() {
    agentSelectionPanel.innerHTML = '<h2 class="text-xl font-semibold text-gray-800 w-full text-center mb-2">Agents</h2>';
    AGENTS.forEach(agent => {
        const agentBtn = document.createElement('button');
        agentBtn.classList.add(
            'px-3', 'py-1', 'rounded-full', 'text-sm', 'font-medium', 'shadow-sm',
            'hover:bg-gray-200', 'transition-colors', 'flex', 'items-center', 'gap-1'
        );
        agentBtn.style.backgroundColor = agent.color;
        agentBtn.style.color = 'white';
        agentBtn.dataset.agentId = agent.id;
        agentBtn.innerHTML = `<span class="text-white">${agent.icon}</span> ${agent.name}`;

        agentBtn.addEventListener('click', () => toggleAgentLogView(agent.id)); // Changed to toggle
        agentSelectionPanel.appendChild(agentBtn);

        if (agent.id === selectedAgentId) {
            agentBtn.classList.add('ring-2', 'ring-blue-500', 'bg-blue-100');
        }
    });
}


// Helper to get place name or coordinates for logging
function getPlaceOrCoordinates(x, y) {
    const placeId = map_place_ids[y]?.[x];
    return placeId && PLACES[placeId] ? PLACES[placeId].name : `(${x},${y})`;
}


// --- Scrolling with Arrow Keys and Touch ---
let isDragging = false;
let startX, startY;
let scrollLeft, scrollTop;

gameGridWrapper.addEventListener('mousedown', (e) => {
    isDragging = true;
    gameGridWrapper.classList.add('cursor-grabbing');
    startX = e.pageX - gameGridWrapper.offsetLeft;
    startY = e.pageY - gameGridWrapper.offsetTop;
    scrollLeft = gameGridWrapper.scrollLeft;
    scrollTop = gameGridWrapper.scrollTop;
});

gameGridWrapper.addEventListener('mouseleave', () => {
    isDragging = false;
    gameGridWrapper.classList.remove('cursor-grabbing');
});

gameGridWrapper.addEventListener('mouseup', () => {
    isDragging = false;
    gameGridWrapper.classList.remove('cursor-grabbing');
});

gameGridWrapper.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    e.preventDefault();
    const x = e.pageX - gameGridWrapper.offsetLeft;
    const y = e.pageY - gameGridWrapper.offsetTop;
    const walkX = (x - startX) * 1;
    const walkY = (y - startY) * 1;
    gameGridWrapper.scrollLeft = scrollLeft - walkX;
    gameGridWrapper.scrollTop = scrollTop - walkY;
});

gameGridWrapper.addEventListener('touchstart', (e) => {
    isDragging = true;
    startX = e.touches[0].pageX - gameGridWrapper.offsetLeft;
    startY = e.touches[0].pageY - gameGridWrapper.offsetTop;
    scrollLeft = gameGridWrapper.scrollLeft;
    scrollTop = gameGridWrapper.scrollTop;
}, { passive: true });

gameGridWrapper.addEventListener('touchend', () => {
    isDragging = false;
});

gameGridWrapper.addEventListener('touchmove', (e) => {
    if (!isDragging) return;
    const x = e.touches[0].pageX - gameGridWrapper.offsetLeft;
    const y = e.touches[0].pageY - gameGridWrapper.offsetTop;
    const walkX = (x - startX) * 1;
    const walkY = (y - startY) * 1;
    gameGridWrapper.scrollLeft = scrollLeft - walkX;
    gameGridWrapper.scrollTop = scrollTop - walkY;
}, { passive: true });

document.addEventListener('keydown', (e) => {
    const scrollAmount = 80;
    switch (e.key) {
        case 'ArrowUp':
            gameGridWrapper.scrollTop -= scrollAmount;
            e.preventDefault();
            break;
        case 'ArrowDown':
            gameGridWrapper.scrollTop += scrollAmount;
            e.preventDefault();
            break;
        case 'ArrowLeft':
            gameGridWrapper.scrollLeft -= scrollAmount;
            e.preventDefault();
            break;
        case 'ArrowRight':
            gameGridWrapper.scrollLeft += scrollAmount;
            e.preventDefault();
            break;
    }
});

// --- Simulation Loop ---
let simulationInterval;
let agentTickInterval;

// Helper function to check if a cell is occupied by any agent
function isCellOccupied(x, y, excludeAgentId = null) {
    return AGENTS.some(agent => agent.x === x && agent.y === y && agent.id !== excludeAgentId);
}

function startSimulation() {
    if (simulationInterval) clearInterval(simulationInterval);
    if (agentTickInterval) clearInterval(agentTickInterval);

    simulationInterval = setInterval(updateSimulationTime, 1000);

    agentTickInterval = setInterval(() => {
        if (isSimulationPaused) return;

        AGENTS.forEach(agent => {
            const currentSimMinutes = getCurrentSimulationMinutes();

            if (agent.state === 'idle') {
                agent.currentAction = `Waiting for command...`;
            } else if (agent.state === 'moving') {
                moveAgentStep(agent);
            } else if (agent.state === 'doing_action') {
                if (currentSimMinutes >= agent.actionEndTime) {
                    agent.state = 'idle';
                    agent.currentAction = `Finished action at ${getPlaceOrCoordinates(agent.x, agent.y)}. Waiting for command...`;
                    logSimulation(`${agent.name} finished its action and is now idle.`, agent.id); // Log to individual
                    socket.emit('agent_state_update', {
                        agentId: agent.id,
                        state: agent.state,
                        x: agent.x,
                        y: agent.y
                    });
                }
            }
            if (agent.id === selectedAgentId) {
                inspectAgent(agent.id);
            }
        });
    }, 500);
}

// --- Pause/Resume Functionality ---
function toggleSimulationPause() {
    isSimulationPaused = !isSimulationPaused;
    if (isSimulationPaused) {
        pauseResumeBtn.textContent = 'Resume Simulation';
        pauseResumeBtn.classList.remove('bg-yellow-500', 'hover:bg-yellow-600');
        pauseResumeBtn.classList.add('bg-green-500', 'hover:bg-green-600');
        logSimulation('Simulation Paused.');
    } else {
        pauseResumeBtn.textContent = 'Pause Simulation';
        pauseResumeBtn.classList.remove('bg-green-500', 'hover:bg-green-600');
        pauseResumeBtn.classList.add('bg-yellow-500', 'hover:bg-yellow-600');
        logSimulation('Simulation Resumed.');
    }
}


// --- Initial Setup ---
window.onload = function() {
    renderMap();
    placeAgents();

    clearInterval(simulationInterval);
    clearInterval(agentTickInterval);


    addAgentBtn.addEventListener('click', addRandomAgent);
    pauseResumeBtn.addEventListener('click', toggleSimulationPause);
};