/* Town Simulator V2 — dashboard frontend.
 *
 * Single-file vanilla JS, organized as:
 *   1. constants + state
 *   2. dom lookup
 *   3. ws module (auto-reconnect with backoff)
 *   4. message dispatch / handlers
 *   5. render: map, agents, roster, inspector, log, stories, header
 *   6. REST inspector deep-dive (relationships + diary, refreshed while selected)
 *
 * Rules honored throughout:
 *   - all dynamic text goes through textContent (never innerHTML),
 *     EXCEPT the static map-cell SVG icons provided by the server in init.map.cell_types
 *   - DOM is created once and updated in place (map rebuilds only on re-init)
 *   - every handler guards against missing fields; nothing here should throw
 */
"use strict";

(() => {
  /* ------------------------------------------------------------------ */
  /* 1. constants + state                                                */
  /* ------------------------------------------------------------------ */

  const CELL = 24;                 // px — keep in sync with --cell in style.css
  const LOG_CAP = 200;             // max log entries kept (array and DOM nodes)
  const REL_REFRESH_MS = 5000;     // relationships re-fetch cadence while selected
  const DIARY_SNIPPET = 300;       // chars shown before "Show more"
  const KNOWN_STATES = ["idle", "moving", "doing_action", "interacting"];

  const state = {
    connected: false,
    everConnected: false,
    paused: false,
    seed: null,
    runDir: null,
    time: null,                    // last {tick, day_index, weekday, hour, minute, label}
    map: null,                     // {layout, cell_types, places}
    placeGrid: [],                 // placeGrid[y][x] -> place id | null
    agents: new Map(),             // id -> latest AGENT object
    selectedId: null,
    logs: [],                      // newest first, capped at LOG_CAP
    logFilter: "",                 // "" = all agents
    stories: [],                   // [{day, text}] newest first
    diaries: new Map(),            // agent id -> {day, text}
    diaryExpanded: false,
    relationships: null,           // null = loading, {} = none, else REST map
  };

  // live DOM handles for in-place updates
  const chips = new Map();         // agent id -> chip element on the map
  const rosterRows = new Map();    // agent id -> {row, badge}
  const storyCards = new Map();    // story day title -> {card, textEl}
  let lastPersonalityKey = null;   // avoids rebuilding tags every tick

  /* ------------------------------------------------------------------ */
  /* 2. dom lookup                                                       */
  /* ------------------------------------------------------------------ */

  const $ = (id) => document.getElementById(id);
  const dom = {
    clock: $("clock"),
    connDot: $("conn-dot"),
    connText: $("conn-text"),
    pauseBtn: $("pause-btn"),
    seed: $("seed"),
    mapPanel: $("map-panel"),
    mapGrid: $("map-grid"),
    stories: $("stories"),
    roster: $("roster"),
    inspEmpty: $("insp-empty"),
    inspPlace: $("insp-place"),
    inspPlaceName: $("insp-place-name"),
    inspPlaceCells: $("insp-place-cells"),
    inspAgent: $("insp-agent"),
    inspChip: $("insp-chip"),
    inspName: $("insp-name"),
    inspMood: $("insp-mood"),
    inspState: $("insp-state"),
    inspGoal: $("insp-goal"),
    inspAction: $("insp-action"),
    inspMoney: $("insp-money"),
    needFills: {
      hunger: $("need-hunger-fill"),
      social: $("need-social-fill"),
      fatigue: $("need-fatigue-fill"),
    },
    needVals: {
      hunger: $("need-hunger-val"),
      social: $("need-social-val"),
      fatigue: $("need-fatigue-val"),
    },
    inspPersonality: $("insp-personality"),
    inspBt: $("insp-bt"),
    relList: $("insp-rel-list"),
    diaryBox: $("insp-diary"),
    diaryTitle: $("insp-diary-title"),
    diaryText: $("insp-diary-text"),
    diaryToggle: $("insp-diary-toggle"),
    logFilter: $("log-filter"),
    logList: $("log-list"),
  };

  /* ------------------------------------------------------------------ */
  /* 3. ws module                                                        */
  /* ------------------------------------------------------------------ */

  const ws = (() => {
    let sock = null;
    let attempt = 0;
    let timer = null;

    function connect() {
      clearTimeout(timer);
      const proto = location.protocol === "https:" ? "wss:" : "ws:";
      try {
        sock = new WebSocket(proto + "//" + location.host + "/ws");
      } catch (e) {
        scheduleReconnect();
        return;
      }
      sock.onopen = () => {
        attempt = 0;
        setConnected(true);
      };
      sock.onmessage = (ev) => {
        let msg = null;
        try { msg = JSON.parse(ev.data); } catch (e) { return; }
        if (msg && typeof msg === "object") {
          try { dispatch(msg); } catch (e) { /* never let one bad message kill the socket */ }
        }
      };
      sock.onclose = () => {
        setConnected(false);
        scheduleReconnect();
      };
      sock.onerror = () => {
        try { sock.close(); } catch (e) { /* already closed */ }
      };
    }

    function scheduleReconnect() {
      clearTimeout(timer);
      const delay = Math.min(500 * Math.pow(2, Math.min(attempt, 5)), 8000)
        + Math.floor(Math.random() * 250);
      attempt += 1;
      timer = setTimeout(connect, delay);
    }

    function send(obj) {
      if (sock && sock.readyState === WebSocket.OPEN) {
        try { sock.send(JSON.stringify(obj)); } catch (e) { /* dropped */ }
      }
    }

    return { connect, send };
  })();

  function setConnected(on) {
    state.connected = on;
    if (on) state.everConnected = true;
    dom.connDot.classList.toggle("connected", on);
    dom.connText.textContent = on
      ? "connected"
      : (state.everConnected ? "reconnecting…" : "connecting…");
    document.body.classList.toggle("offline", !on);
    dom.pauseBtn.disabled = !on;
  }

  /* ------------------------------------------------------------------ */
  /* 4. message dispatch / handlers                                      */
  /* ------------------------------------------------------------------ */

  function dispatch(msg) {
    switch (msg.type) {
      case "init":   handleInit(msg); break;
      case "tick":   handleTick(msg); break;
      case "logs":   handleLogs(msg); break;
      case "story":  handleStory(msg); break;
      case "diary":  handleDiary(msg); break;
      case "paused": handlePaused(msg); break;
      default: break; // unknown message types are ignored
    }
  }

  function handleInit(msg) {
    state.map = (msg.map && typeof msg.map === "object") ? msg.map : null;
    state.seed = (msg.seed !== undefined) ? msg.seed : null;
    state.runDir = msg.run_dir || null;
    state.paused = !!msg.paused;

    // stories: server sends chronological — display newest first
    const stories = Array.isArray(msg.stories) ? msg.stories : [];
    state.stories = stories
      .filter((s) => s && typeof s.text === "string")
      .map((s) => ({ day: String(s.day || ""), text: s.text }))
      .reverse();

    buildPlaceGrid();
    renderMap();

    const snap = (msg.snapshot && typeof msg.snapshot === "object") ? msg.snapshot : {};
    state.time = snap.time || null;
    resetAgents(Array.isArray(snap.agents) ? snap.agents : []);

    renderRoster();
    rebuildLogFilterOptions();
    renderStories();
    renderClock();
    renderPauseButton();
    renderSeed();

    // restore selection cleanly after a re-init
    if (state.selectedId && !state.agents.has(state.selectedId)) {
      selectAgent(null);
    } else if (state.selectedId) {
      applySelectionHighlight();
      lastPersonalityKey = null;
      renderInspectorAgent();
      scheduleDetailFetch(true);
    }
  }

  function handleTick(msg) {
    if (msg.time && typeof msg.time === "object") {
      state.time = msg.time;
      renderClock();
    }
    const list = Array.isArray(msg.agents) ? msg.agents : [];
    for (const a of list) {
      if (!a || !a.id) continue;
      const isNew = !state.agents.has(a.id);
      state.agents.set(a.id, a);
      if (isNew) {
        createChip(a);
        addRosterRow(a);
        addLogFilterOption(a);
      }
      updateChip(a);
      updateRosterRow(a);
    }
    if (state.selectedId) renderInspectorLive();
  }

  function handleLogs(msg) {
    const items = Array.isArray(msg.items) ? msg.items : [];
    for (const it of items) {
      if (!it || typeof it.text !== "string") continue;
      const entry = {
        agent: it.agent || "",
        name: it.name || it.agent || "",
        text: it.text,
        t: it.t || "",
      };
      state.logs.unshift(entry);
      if (!state.logFilter || state.logFilter === entry.agent) {
        dom.logList.prepend(makeLogNode(entry));
      }
    }
    if (state.logs.length > LOG_CAP) state.logs.length = LOG_CAP;
    while (dom.logList.children.length > LOG_CAP) {
      dom.logList.lastElementChild.remove();
    }
  }

  function handleStory(msg) {
    if (!msg || typeof msg.text !== "string") return;
    const day = String(msg.day || "");
    const existing = state.stories.find((s) => s.day === day);
    if (existing) {
      existing.text = msg.text;
      const card = storyCards.get(day);
      if (card) { card.textEl.textContent = msg.text; return; }
    } else {
      state.stories.unshift({ day, text: msg.text });
    }
    renderStories();
  }

  function handleDiary(msg) {
    if (!msg || !msg.agent) return;
    state.diaries.set(msg.agent, { day: msg.day, text: msg.text || "" });
    if (state.selectedId === msg.agent) renderDiary();
  }

  function handlePaused(msg) {
    state.paused = !!(msg && msg.value);
    renderPauseButton();
  }

  /* ------------------------------------------------------------------ */
  /* 5a. header renders                                                  */
  /* ------------------------------------------------------------------ */

  function renderClock() {
    const t = state.time;
    if (!t) { dom.clock.textContent = "--"; return; }
    let label = t.label;
    if (!label) {
      const h = Number(t.hour), m = Number(t.minute);
      if (Number.isFinite(h) && Number.isFinite(m)) {
        const ampm = h >= 12 ? "PM" : "AM";
        const h12 = h % 12 === 0 ? 12 : h % 12;
        label = (t.weekday ? t.weekday + " " : "")
          + String(h12).padStart(2, "0") + ":" + String(m).padStart(2, "0") + " " + ampm;
      } else {
        label = "--";
      }
    }
    const dayNum = Number(t.day_index);
    dom.clock.textContent = Number.isFinite(dayNum)
      ? label + "  ·  Day " + (dayNum + 1)
      : label;
  }

  function renderPauseButton() {
    dom.pauseBtn.textContent = state.paused ? "Resume" : "Pause";
    dom.pauseBtn.classList.toggle("is-paused", state.paused);
  }

  function renderSeed() {
    if (state.seed === null || state.seed === undefined) {
      dom.seed.hidden = true;
      return;
    }
    dom.seed.hidden = false;
    dom.seed.textContent = "seed " + state.seed;
    if (state.runDir) dom.seed.title = String(state.runDir);
  }

  /* ------------------------------------------------------------------ */
  /* 5b. map                                                             */
  /* ------------------------------------------------------------------ */

  function buildPlaceGrid() {
    state.placeGrid = [];
    const layout = state.map && Array.isArray(state.map.layout) ? state.map.layout : [];
    for (let y = 0; y < layout.length; y++) {
      const row = Array.isArray(layout[y]) ? layout[y] : [];
      state.placeGrid.push(new Array(row.length).fill(null));
    }
    const places = (state.map && state.map.places) || {};
    for (const pid of Object.keys(places)) {
      const coords = places[pid] && Array.isArray(places[pid].coords) ? places[pid].coords : [];
      for (const c of coords) {
        if (!Array.isArray(c) || c.length < 2) continue;
        const x = Number(c[0]), y = Number(c[1]);
        if (state.placeGrid[y] && x >= 0 && x < state.placeGrid[y].length) {
          state.placeGrid[y][x] = pid;
        }
      }
    }
  }

  function renderMap() {
    chips.clear();
    dom.mapGrid.textContent = ""; // clears cells and chips
    const layout = state.map && Array.isArray(state.map.layout) ? state.map.layout : [];
    const types = (state.map && state.map.cell_types) || {};
    const places = (state.map && state.map.places) || {};

    const rows = layout.length;
    let cols = 0;
    for (const row of layout) if (Array.isArray(row) && row.length > cols) cols = row.length;

    dom.mapGrid.style.gridTemplateColumns = "repeat(" + Math.max(cols, 1) + ", " + CELL + "px)";
    dom.mapGrid.style.width = (cols * CELL) + "px";
    dom.mapGrid.style.height = (rows * CELL) + "px";

    const frag = document.createDocumentFragment();
    for (let y = 0; y < rows; y++) {
      const row = Array.isArray(layout[y]) ? layout[y] : [];
      for (let x = 0; x < cols; x++) {
        const code = row[x];
        const info = (code !== undefined && types[code]) ? types[code] : null;
        const cell = document.createElement("div");
        cell.className = "cell" + (info && info.class ? " " + info.class : "");
        cell.dataset.x = String(x);
        cell.dataset.y = String(y);
        // Trusted static SVG icon from server map data — the ONLY innerHTML use.
        if (info && typeof info.icon === "string" && info.icon) {
          cell.innerHTML = info.icon;
        }
        const pid = state.placeGrid[y] ? state.placeGrid[y][x] : null;
        if (pid) {
          cell.classList.add("place");
          const p = places[pid];
          if (p && p.type) cell.title = p.type;
        }
        frag.appendChild(cell);
      }
    }
    dom.mapGrid.appendChild(frag);
  }

  // one delegated click handler for all map cells (agents stopPropagation)
  dom.mapGrid.addEventListener("click", (ev) => {
    const cell = ev.target.closest ? ev.target.closest(".cell") : null;
    if (!cell || !dom.mapGrid.contains(cell)) return;
    const x = Number(cell.dataset.x), y = Number(cell.dataset.y);
    const pid = state.placeGrid[y] ? state.placeGrid[y][x] : null;
    if (pid) showPlace(pid);
    else selectAgent(null); // clicking open ground clears the selection
  });

  /* ------------------------------------------------------------------ */
  /* 5c. agent chips on the map                                          */
  /* ------------------------------------------------------------------ */

  function resetAgents(list) {
    state.agents.clear();
    // renderMap() already emptied the grid, so just recreate chips
    for (const a of list) {
      if (!a || !a.id) continue;
      state.agents.set(a.id, a);
      createChip(a);
    }
  }

  function createChip(a) {
    if (chips.has(a.id)) return;
    const el = document.createElement("button");
    el.type = "button";
    el.className = "chip agent-chip";
    el.style.backgroundColor = a.color || "#7d8590";
    el.title = a.name || a.id;
    el.dataset.id = a.id;

    const label = document.createElement("span");
    label.className = "chip-label";
    label.textContent = a.icon || String(a.name || a.id).slice(0, 2).toUpperCase();

    const bubble = document.createElement("span");
    bubble.className = "chip-bubble";
    bubble.textContent = "\u{1F4AC}";

    el.append(label, bubble);
    el.addEventListener("click", (ev) => {
      ev.stopPropagation();
      selectAgent(a.id);
    });
    chips.set(a.id, el);
    dom.mapGrid.appendChild(el);
    updateChip(a);
  }

  function updateChip(a) {
    const el = chips.get(a.id);
    if (!el) return;
    const x = Number(a.x), y = Number(a.y);
    if (Number.isFinite(x) && Number.isFinite(y)) {
      el.style.transform = "translate(" + (x * CELL) + "px, " + (y * CELL) + "px)";
    }
    el.classList.toggle("talking", !!a.interacting_with);
    el.classList.toggle("selected", state.selectedId === a.id);
  }

  /* ------------------------------------------------------------------ */
  /* 5d. roster (built once per init, updated in place)                  */
  /* ------------------------------------------------------------------ */

  function renderRoster() {
    rosterRows.clear();
    dom.roster.textContent = "";
    for (const a of state.agents.values()) addRosterRow(a);
  }

  function addRosterRow(a) {
    if (rosterRows.has(a.id)) return;
    const row = document.createElement("button");
    row.type = "button";
    row.className = "roster-row";
    row.dataset.id = a.id;

    const chip = document.createElement("span");
    chip.className = "chip static-chip";
    chip.style.backgroundColor = a.color || "#7d8590";
    chip.textContent = a.icon || String(a.name || a.id).slice(0, 2).toUpperCase();

    const name = document.createElement("span");
    name.className = "roster-name";
    name.textContent = a.name || a.id;

    const badge = document.createElement("span");
    badge.className = "badge";

    row.append(chip, name, badge);
    row.addEventListener("click", () => selectAgent(a.id));
    rosterRows.set(a.id, { row, badge });
    dom.roster.appendChild(row);
    updateRosterRow(a);
  }

  function updateRosterRow(a) {
    const r = rosterRows.get(a.id);
    if (!r) return;
    const s = a.state || "idle";
    if (r.badge.textContent !== s) {
      r.badge.textContent = s;
      r.badge.className = "badge" + (KNOWN_STATES.includes(s) ? " state-" + s : "");
    }
  }

  function applySelectionHighlight() {
    for (const [id, el] of chips) el.classList.toggle("selected", id === state.selectedId);
    for (const [id, r] of rosterRows) r.row.classList.toggle("selected", id === state.selectedId);
  }

  /* ------------------------------------------------------------------ */
  /* 5e. inspector                                                       */
  /* ------------------------------------------------------------------ */

  function showInspectorMode(mode) {
    dom.inspEmpty.hidden = mode !== "empty";
    dom.inspPlace.hidden = mode !== "place";
    dom.inspAgent.hidden = mode !== "agent";
  }

  function selectAgent(id) {
    clearInterval(detailTimer);
    detailTimer = null;
    state.selectedId = id || null;
    state.relationships = null;
    state.diaryExpanded = false;
    lastPersonalityKey = null;
    applySelectionHighlight();
    if (state.selectedId) {
      showInspectorMode("agent");
      renderInspectorAgent();
      scheduleDetailFetch(true);
    } else {
      showInspectorMode("empty");
    }
  }

  function showPlace(pid) {
    clearInterval(detailTimer);
    detailTimer = null;
    state.selectedId = null;
    applySelectionHighlight();
    const p = (state.map && state.map.places && state.map.places[pid]) || null;
    dom.inspPlaceName.textContent = (p && p.type) ? p.type : prettify(pid);
    const n = p && Array.isArray(p.coords) ? p.coords.length : 0;
    dom.inspPlaceCells.textContent = n ? String(n) : "--";
    showInspectorMode("place");
  }

  // full render on selection change (identity, tags, rel placeholder, diary)
  function renderInspectorAgent() {
    const a = state.agents.get(state.selectedId);
    if (!a) { showInspectorMode("empty"); return; }
    dom.inspChip.style.backgroundColor = a.color || "#7d8590";
    dom.inspChip.textContent = a.icon || String(a.name || a.id).slice(0, 2).toUpperCase();
    renderInspectorLive();
    renderRelationships();
    renderDiary();
  }

  // cheap per-tick refresh of the live fields
  function renderInspectorLive() {
    const a = state.agents.get(state.selectedId);
    if (!a) return;

    dom.inspName.textContent = a.name || a.id || "--";
    dom.inspMood.textContent = a.mood ? "mood: " + a.mood : "";
    const s = a.state || "idle";
    if (dom.inspState.textContent !== s) {
      dom.inspState.textContent = s;
      dom.inspState.className = "badge" + (KNOWN_STATES.includes(s) ? " state-" + s : "");
    }
    dom.inspGoal.textContent = a.goal ? "“" + a.goal + "”" : "—";
    dom.inspAction.textContent = a.action || "—";
    dom.inspMoney.textContent = Number.isFinite(Number(a.money))
      ? "$" + Number(a.money).toFixed(2)
      : "—";

    const needs = (a.needs && typeof a.needs === "object") ? a.needs : {};
    for (const key of ["hunger", "social", "fatigue"]) {
      const v = clamp(Number(needs[key]), 0, 100);
      const fill = dom.needFills[key];
      const val = dom.needVals[key];
      if (fill) {
        fill.style.width = v.toFixed(1) + "%";        // width transition animates this
        fill.style.backgroundColor = needColor(v);
      }
      if (val) val.textContent = String(Math.round(v));
    }

    const personality = Array.isArray(a.personality) ? a.personality : [];
    const pKey = personality.join("|");
    if (pKey !== lastPersonalityKey) {
      lastPersonalityKey = pKey;
      dom.inspPersonality.textContent = "";
      for (const trait of personality) {
        const tag = document.createElement("span");
        tag.className = "tag";
        tag.textContent = String(trait);
        dom.inspPersonality.appendChild(tag);
      }
    }

    const bt = Array.isArray(a.bt_path) ? a.bt_path : [];
    dom.inspBt.textContent = bt.length ? bt.join(" › ") : "—";
  }

  function renderRelationships() {
    dom.relList.textContent = "";
    const rel = state.relationships;
    if (rel === null) {
      dom.relList.appendChild(makeRelHint("loading…"));
      return;
    }
    const entries = Object.entries(rel || {});
    if (!entries.length) {
      dom.relList.appendChild(makeRelHint("No relationships yet."));
      return;
    }
    entries.sort((p, q) => (Number(q[1] && q[1].affinity) || 0) - (Number(p[1] && p[1].affinity) || 0));
    for (const [otherId, r] of entries) {
      const li = document.createElement("li");
      li.className = "rel-row";

      const name = document.createElement("span");
      name.className = "rel-name";
      const other = state.agents.get(otherId);
      name.textContent = (other && other.name) ? other.name : prettify(otherId);

      const type = document.createElement("span");
      type.className = "rel-type";
      type.textContent = (r && r.type) ? String(r.type) : "";

      const aff = document.createElement("span");
      aff.className = "rel-aff mono";
      const n = Number(r && r.affinity);
      aff.textContent = Number.isFinite(n) ? n.toFixed(1) : "--";

      li.append(name, type, aff);
      dom.relList.appendChild(li);
    }
  }

  function makeRelHint(text) {
    const li = document.createElement("li");
    li.className = "hint";
    li.textContent = text;
    return li;
  }

  function renderDiary() {
    const d = state.selectedId ? state.diaries.get(state.selectedId) : null;
    if (!d || !d.text) {
      dom.diaryBox.hidden = true;
      return;
    }
    dom.diaryBox.hidden = false;
    const dayNum = Number(d.day);
    dom.diaryTitle.textContent = Number.isFinite(dayNum) ? "Diary — Day " + dayNum : "Diary";
    const long = d.text.length > DIARY_SNIPPET;
    if (long && !state.diaryExpanded) {
      dom.diaryText.textContent = d.text.slice(0, DIARY_SNIPPET).trimEnd() + "…";
    } else {
      dom.diaryText.textContent = d.text;
    }
    dom.diaryToggle.hidden = !long;
    dom.diaryToggle.textContent = state.diaryExpanded ? "Show less" : "Show more";
  }

  dom.diaryToggle.addEventListener("click", () => {
    state.diaryExpanded = !state.diaryExpanded;
    renderDiary();
  });

  /* ------------------------------------------------------------------ */
  /* 6. REST deep-dive for the selected agent                            */
  /* ------------------------------------------------------------------ */

  let detailTimer = null;
  let detailSeq = 0;

  function scheduleDetailFetch(immediate) {
    clearInterval(detailTimer);
    detailTimer = null;
    if (!state.selectedId) return;
    if (immediate) fetchAgentDetail();
    detailTimer = setInterval(fetchAgentDetail, REL_REFRESH_MS);
  }

  function fetchAgentDetail() {
    const id = state.selectedId;
    if (!id) return;
    const seq = ++detailSeq;
    fetch("/api/agents/" + encodeURIComponent(id))
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data || seq !== detailSeq || state.selectedId !== id) return; // stale
        state.relationships = (data.relationships && typeof data.relationships === "object")
          ? data.relationships : {};
        if (data.diary && typeof data.diary.text === "string") {
          state.diaries.set(id, { day: data.diary.day, text: data.diary.text });
        }
        renderRelationships();
        renderDiary();
      })
      .catch(() => { /* server unreachable — header already shows reconnecting */ });
  }

  /* ------------------------------------------------------------------ */
  /* 5f. event log                                                       */
  /* ------------------------------------------------------------------ */

  function makeLogNode(entry) {
    const div = document.createElement("div");
    div.className = "log-item";
    div.dataset.agent = entry.agent;

    const t = document.createElement("span");
    t.className = "log-t";
    t.textContent = entry.t;

    const name = document.createElement("span");
    name.className = "log-name";
    name.textContent = entry.name ? entry.name + ": " : "";

    const text = document.createElement("span");
    text.className = "log-text";
    text.textContent = entry.text;

    div.append(t, name, text);
    return div;
  }

  function rebuildLogList() {
    dom.logList.textContent = "";
    const frag = document.createDocumentFragment();
    for (const entry of state.logs) {
      if (state.logFilter && entry.agent !== state.logFilter) continue;
      frag.appendChild(makeLogNode(entry)); // state.logs is newest-first already
    }
    dom.logList.appendChild(frag);
  }

  function rebuildLogFilterOptions() {
    const prev = state.logFilter;
    dom.logFilter.textContent = "";
    const all = document.createElement("option");
    all.value = "";
    all.textContent = "All agents";
    dom.logFilter.appendChild(all);
    for (const a of state.agents.values()) {
      const opt = document.createElement("option");
      opt.value = a.id;
      opt.textContent = a.name || a.id;
      dom.logFilter.appendChild(opt);
    }
    state.logFilter = state.agents.has(prev) ? prev : "";
    dom.logFilter.value = state.logFilter;
    rebuildLogList();
  }

  function addLogFilterOption(a) {
    for (const opt of dom.logFilter.options) {
      if (opt.value === a.id) return;
    }
    const opt = document.createElement("option");
    opt.value = a.id;
    opt.textContent = a.name || a.id;
    dom.logFilter.appendChild(opt);
  }

  dom.logFilter.addEventListener("change", () => {
    state.logFilter = dom.logFilter.value;
    rebuildLogList();
  });

  /* ------------------------------------------------------------------ */
  /* 5g. stories                                                         */
  /* ------------------------------------------------------------------ */

  function renderStories() {
    storyCards.clear();
    dom.stories.textContent = "";
    if (!state.stories.length) {
      const hint = document.createElement("p");
      hint.className = "hint";
      hint.textContent = "No stories yet. They appear at the end of each simulated day.";
      dom.stories.appendChild(hint);
      return;
    }
    for (const s of state.stories) {
      const card = document.createElement("article");
      card.className = "story-card";

      const h = document.createElement("h3");
      h.textContent = s.day || "Story";

      const text = document.createElement("div");
      text.className = "story-text";
      text.textContent = s.text;

      card.append(h, text);
      storyCards.set(s.day, { card, textEl: text });
      dom.stories.appendChild(card);
    }
  }

  /* ------------------------------------------------------------------ */
  /* misc helpers + boot                                                 */
  /* ------------------------------------------------------------------ */

  function clamp(n, lo, hi) {
    if (!Number.isFinite(n)) return lo;
    return Math.min(hi, Math.max(lo, n));
  }

  // green (low) -> amber -> red (high) as the need value rises
  function needColor(v) {
    const hue = Math.round(120 - clamp(v, 0, 100) * 1.2);
    return "hsl(" + hue + ", 62%, 44%)";
  }

  function prettify(id) {
    return String(id || "")
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
  }

  dom.pauseBtn.addEventListener("click", () => {
    ws.send({ type: state.paused ? "resume" : "pause" });
    // authoritative state comes back via {"type":"paused"}
  });

  showInspectorMode("empty");
  renderPauseButton();
  ws.connect();
})();
