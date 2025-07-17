// --- Configuration & Global State ---
const CELL_SIZE = 40;
let isEngineReady = false;
// (MAP_LAYOUT, CELL_TYPES, PLACES, etc. data remains the same)
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
    ['G', 'P', 'G', 'H', 'H', 'H', 'P', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G', 'G'],
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
const CELL_TYPES = {
    'G': { class: 'grass', icon: '' }, 'P': { class: 'path', icon: '' },
    'H': { class: 'house', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3L2 12h3v8h6v-6h2v6h6v-8h3L12 3zm0 2.69l5 4.5V18h-3v-6h-4v6H7v-8.81l5-4.5z"/></svg>' },
    'C': { class: 'cafe', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M20 3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 2v3H4V5h16zM4 19V9h16v10H4zM6 11h2v2H6zm4 0h2v2h-2zm4 0h2v2h-2z"/></svg>' },
    'K': { class: 'park', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M17 12c-2.76 0-5 2.24-5 5s2.24 5 5 5 5-2.24 5-5-2.24-5-5-5zm-5-9c-2.76 0-5 2.24-5 5s2.24 5 5 5 5-2.24 5-5-2.24-5-5-5zM2 17c0 2.76 2.24 5 5 5s5-2.24 5-5-2.24-5-5-5-5 2.24-5 5z"/></svg>' },
    'S': { class: 'supply_store', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 14H4V8h16v10zm-5-7H9v2h6z"/></svg>' },
    'L': { class: 'college', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3L1 9l11 6 11-6-11-6zm0 10.99L5 9.75l7-3.75 7 3.75-7 3.75zM3 17.25V12h2v5.25c0 1.66 1.34 3 3 3h8c1.66 0 3-1.34 3-3V12h2v5.25c0 2.76-2.24 5-5 5H8c-2.76 0-5-2.24-5-5z"/></svg>' },
    'F': { class: 'grocery_pharmacy', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M7 18c-1.1 0-1.99.9-1.99 2S5.9 22 7 22s2-.9 2-2-.9-2-2-2zm10 0c-1.1 0-1.99.9-1.99 2S15.9 22 17 22s2-.9 2-2-.9-2-2-2zm-8.7-17.7c-.4-.4-.9-.3-1.2.1L3 8.2c-.2.2-.3.5-.3.8V15h16V9.5c0-.3-.1-.6-.3-.8l-4.1-7.8c-.3-.4-.8-.5-1.2-.1L12 3.8l-3.7-3.5zM12 13H5.76L4 9.5 5.76 6H12v7zm2-7h3.24L19 9.5 17.24 13H14V6z"/></svg>' },
    'D': { class: 'college_dorm', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M12 5.5c-2.76 0-5 2.24-5 5s2.24 5 5 5 5-2.24 5-5-2.24-5-5-5zm0 2c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zM2 19c0 2.76 2.24 5 5 5s5-2.24 5-5-2.24-5-5-5-5 2.24-5 5zm5 2c1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3 1.34 3 3 3zM17 19c0 2.76 2.24 5 5 5s5-2.24 5-5-2.24-5-5-5-5 2.24-5 5zm5 2c1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3 1.34 3 3 3z"/></svg>' },
    'B': { class: 'bar', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M3 10h18v2H3zm0-4h18v2H3zm0 8h18v2H3z"/></svg>' },
    'O': { class: 'co_living', icon: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>' }
};
const PLACES = {
    'co_living_space': {'type': 'Co-Living Space', 'coords': [[1,1], [2,1], [3,1], [4,1], [1,2], [2,2], [3,2], [4,2], [1,3], [2,3], [3,3], [4,3]]},
    'bar_hobbs': {'type': 'Bar', 'coords': [[7,3], [8,3], [7,4], [8,4]]},
    'cafe_hobbs': {'type': 'Cafe', 'coords': [[3,6], [4,6], [3,7], [4,7]]},
    'supply_store_harvey': {'type': 'Supply Store', 'coords': [[6,1], [7,1], [6,2], [7,2]]},
    'college_oak_hill': {'type': 'College', 'coords': [[18,1], [19,1], [20,1], [18,2], [19,2], [20,2], [18,3], [19,3], [20,3]]},
    'grocery_pharmacy_willow': {'type': 'Grocery & Pharmacy', 'coords': [[7,8], [8,8], [9,8], [10,8], [11,8], [7,9], [8,9], [9,9]]},
    'johnson_park': {'type': 'Park', 'coords': [[3,10], [4,10], [5,10], [3,11], [4,11], [5,11], [3,12], [4,12], [5,12]]},
    'main_house_area': {'type': 'House', 'coords': [[3,13], [4,13], [5,13], [3,14], [4,14], [5,14], [3,15], [4,15], [5,15]]},
    'college_dorm_main': {'type': 'College Dorm', 'coords': [[3,18], [4,18], [5,18], [3,19], [4,19], [5,19]]},
};
const map_place_ids = Array(MAP_ROWS).fill(null).map(() => Array(MAP_COLS).fill(null));
for (const placeId in PLACES) {
    PLACES[placeId].coords.forEach(coord => {
        const [x, y] = coord;
        if (y >= 0 && y < MAP_ROWS && x >= 0 && x < MAP_COLS) map_place_ids[y][x] = placeId;
    });
}

let AGENTS = {};
let selectedAgentId = null;
let isSimulationPaused = true;

const dom = {
    grid: document.getElementById('game-grid-container'),
    log: document.getElementById('log-output'),
    inspectorTitle: document.getElementById('inspector-title'),
    inspectorOutput: document.getElementById('inspector-output'),
    inspectorGoal: document.getElementById('inspector-goal'),
    inspectorNeeds: document.getElementById('inspector-needs'),
    time: document.getElementById('simulation-time'),
    pauseBtn: document.getElementById('pause-resume-btn'),
    roster: document.getElementById('agent-selection-panel'),
};

const socket = io();

socket.on('connect', () => logToUI('Successfully connected to simulation server.'));
socket.on('command_client_ready', () => {
    logToUI('Simulation engine is ready. Starting visualization.');
    isEngineReady = true;
    isSimulationPaused = false;
    dom.pauseBtn.disabled = false;
});

socket.on('simulation_state_update', (data) => {
    if (isSimulationPaused && isEngineReady) return; // Only pause if engine is ready
    
    const [hour, minute] = data.time;
    const ampm = hour >= 12 ? 'PM' : 'AM';
    const displayHour = hour % 12 === 0 ? 12 : hour % 12;
    const displayMinute = String(minute).padStart(2, '0');
    dom.time.textContent = `Day 1, ${displayHour}:${displayMinute} ${ampm}`;

    const serverAgents = data.agents;
    serverAgents.forEach(agentData => {
        if (!AGENTS[agentData.id]) logToUI(`${agentData.name} has entered the simulation.`);
        AGENTS[agentData.id] = agentData;
        updateAgentAvatar(agentData);
    });
    renderAgentSelectionPanel();
    if (selectedAgentId && AGENTS[selectedAgentId]) inspectAgent(selectedAgentId, false);
});

function gameLoop() {
    // The game loop is now only for potential future animations, not state updates.
    requestAnimationFrame(gameLoop);
}

// (The rest of the functions remain the same)
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
    dom.grid.appendChild(agentDiv);
}

function updateAgentAvatar(agent) {
    let agentDiv = document.getElementById(`agent-${agent.id}`);
    if (!agentDiv) createAgentAvatar(agent);
    agentDiv.style.left = `${agent.x * CELL_SIZE + 5}px`;
    agentDiv.style.top = `${agent.y * CELL_SIZE + 5}px`;
}

function inspectAgent(agentId, doLog = true) {
    selectedAgentId = agentId;
    const agent = AGENTS[agentId];
    if (!agent) return;
    if (doLog) logToUI(`Inspecting ${agent.name}.`);
    dom.inspectorTitle.textContent = `Inspector: ${agent.name}`;
    dom.inspectorOutput.innerHTML = `<p><span class="font-semibold">Location:</span> (${agent.x}, ${agent.y})</p><p><span class="font-semibold">Action:</span> ${agent.current_action}</p>`;
    dom.inspectorGoal.innerHTML = `<p class="font-semibold">Goal:</p><p class="text-blue-600 italic">"${agent.current_goal}"</p>`;
    let needsHTML = '<p class="font-semibold mt-2">Needs:</p>';
    for (const [need, value] of Object.entries(agent.needs)) {
        const color = value > 75 ? 'bg-red-500' : value > 50 ? 'bg-yellow-500' : 'bg-green-500';
        needsHTML += `<div class="capitalize mt-1"><span>${need}</span><div class="needs-bar-container"><div class="needs-bar ${color}" style="width: ${Math.round(value)}%;"></div></div></div>`;
    }
    dom.inspectorNeeds.innerHTML = needsHTML;
    highlightSelection(agentId);
}

function inspectMapCell(x, y) {
    selectedAgentId = null;
    const placeId = map_place_ids[y]?.[x];
    if (placeId && PLACES[placeId]) {
        const place = PLACES[placeId];
        dom.inspectorTitle.textContent = `Inspector: Location`;
        dom.inspectorOutput.innerHTML = `<p><span class="font-semibold">Name:</span> ${place.type}</p><p><span class="font-semibold">Coordinates:</span> (${x}, ${y})</p>`;
        dom.inspectorGoal.innerHTML = '';
        dom.inspectorNeeds.innerHTML = '';
        logToUI(`Inspected map cell (${x},${y}): ${place.type}.`);
    } else {
        dom.inspectorTitle.textContent = `Inspector`;
        dom.inspectorOutput.innerHTML = `<p class="text-gray-500">Just empty space at (${x},${y}).</p>`;
        dom.inspectorGoal.innerHTML = '';
        dom.inspectorNeeds.innerHTML = '';
    }
    highlightSelection(null);
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
    dom.roster.innerHTML = '<h2 class="text-xl font-semibold text-gray-800 w-full text-center mb-2">Agent Roster</h2>';
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

function logToUI(message) {
    dom.log.innerHTML = `<strong>[${new Date().toLocaleTimeString()}]</strong> ${message}<br>` + dom.log.innerHTML;
}

function renderMap() {
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

dom.pauseBtn.addEventListener('click', () => {
    isSimulationPaused = !isSimulationPaused;
    
    // *** FIX: Emit the correct event to the backend ***
    if (isSimulationPaused) {
        socket.emit('pause_simulation', {});
    } else {
        socket.emit('resume_simulation', {});
    }

    dom.pauseBtn.textContent = isSimulationPaused ? 'Resume' : 'Pause';
    dom.pauseBtn.classList.toggle('bg-yellow-500', !isSimulationPaused);
    dom.pauseBtn.classList.toggle('bg-green-500', isSimulationPaused);
    logToUI(`Simulation ${isSimulationPaused ? 'paused' : 'resumed'}.`);
});

window.onload = function() {
    renderMap();
    logToUI('Frontend loaded. Waiting for simulation engine...');
    dom.pauseBtn.disabled = true;
    gameLoop();
};
