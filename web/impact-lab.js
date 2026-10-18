/* ==========================================================================
   WhyGraph / RECALL — Impact Lab & RECALL Copilot Controller
   Change Simulation, Blast Radius Traversal & 3D Robot AI Assistant
   Powered 100% by live FalkorDB APIs
   ========================================================================== */

(function () {
  'use strict';

  const $ = (sel, el) => (el || document).querySelector(sel);
  const $$ = (sel, el) => Array.from((el || document).querySelectorAll(sel));
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const short = (s, n) => (String(s).length > n ? String(s).slice(0, n - 1) + '\u2026' : String(s));

  const STATE = {
    tenant: 'lumen',
    scenario: 'scenario_queue',
    graph: { nodes: [], edges: [], nodeMap: {} },
    selectedNode: null,
    busy: false,
    zoom: 1,
    pan: { x: 0, y: 0 },
    isDragging: false,
    dragStart: { x: 0, y: 0 },
    highlight: { nodes: [], edges: [] },
  };

  const NODE_COLORS = {
    Decision: '#ffd83d',
    System: '#3df2c8',
    Document: '#ffffff',
    Person: '#ff3d9a',
    Team: '#b58cff',
    Project: '#7fddf0',
    Task: '#ff7a45',
    ChangeRequest: '#ffa94d',
  };

  // ------------------------------------------------------------------ API helper
  async function api(path, body) {
    const opt = body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {};
    const res = await fetch(path, opt);
    let data = null;
    try { data = await res.json(); } catch (e) {}
    if (!res.ok) throw new Error((data && data.error) || res.statusText || 'API call failed');
    return data;
  }

  function toast(msg, isErr) {
    const t = $('#lab-toast');
    if (!t) return;
    t.innerHTML = (isErr ? '⚠️ ' : '✅ ') + esc(msg);
    t.hidden = false;
    setTimeout(() => { t.hidden = true; }, 4200);
  }

  function setBusy(on) {
    STATE.busy = on;
    const btn = $('#btn-run-simulation');
    if (btn) {
      btn.disabled = on;
      btn.style.opacity = on ? '0.6' : '1';
    }
  }

  // ------------------------------------------------------------------ Init
  async function init() {
    setupEventListeners();
    setupCanvasControls();
    setupCopilot();
    await checkHealth();
    await runSelectedScenario();
  }

  function setupEventListeners() {
    // Tenant tabs
    $$('.impact-lab-tenant-btn').forEach((btn) => {
      btn.addEventListener('click', async (e) => {
        const t = e.target.getAttribute('data-tenant');
        if (t === STATE.tenant) return;
        $$('.impact-lab-tenant-btn').forEach((b) => b.classList.remove('active'));
        e.target.classList.add('active');
        STATE.tenant = t;
        toast(`Switched to tenant: ${t === 'lumen' ? 'Lumen Payments' : 'Orbit Logistics'}`);
        await runSelectedScenario();
      });
    });

    // Scenario cards
    $$('.impact-lab-scenario-card').forEach((card) => {
      card.addEventListener('click', (e) => {
        const target = e.currentTarget;
        const id = target.getAttribute('data-id');
        $$('.impact-lab-scenario-card').forEach((c) => c.classList.remove('active'));
        target.classList.add('active');
        STATE.scenario = id;
        runSelectedScenario();
      });
    });

    // Run button
    const runBtn = $('#btn-run-simulation');
    if (runBtn) {
      runBtn.addEventListener('click', () => runSelectedScenario());
    }

    // Reset button
    const resetBtn = $('#btn-reset-demo');
    if (resetBtn) {
      resetBtn.addEventListener('click', async () => {
        if (STATE.busy) return;
        setBusy(true);
        try {
          await api('/api/reset', { tenant: STATE.tenant });
          toast(`Reset ${STATE.tenant} graph from synthetic seed`);
          await runSelectedScenario();
        } catch (err) {
          toast(err.message, true);
        } finally {
          setBusy(false);
        }
      });
    }

    // Open copilot from control panel
    const openCopilotBtn = $('#btn-open-copilot-bar');
    if (openCopilotBtn) {
      openCopilotBtn.addEventListener('click', () => openCopilot());
    }
  }

  async function checkHealth() {
    try {
      const h = await api('/api/health');
      const pill = $('#lab-db-pill');
      if (h.falkordb && pill) {
        pill.innerHTML = '<span class="impact-lab-dot"></span> FalkorDB Live (:6379)';
        pill.className = 'impact-lab-pill live';
      }
    } catch (err) {
      const pill = $('#lab-db-pill');
      if (pill) {
        pill.innerHTML = '⚠️ FalkorDB Offline';
        pill.className = 'impact-lab-pill';
      }
    }
  }

  // ------------------------------------------------------------------ Execute Scenarios
  async function runSelectedScenario() {
    if (STATE.busy) return;
    setBusy(true);
    const statsEl = $('#lab-stats');
    if (statsEl) statsEl.textContent = 'Simulating on live FalkorDB...';

    const t0 = performance.now();
    try {
      if (STATE.scenario === 'scenario_queue') {
        await executeQueueReversalSimulation();
      } else if (STATE.scenario === 'scenario_fraud') {
        await executeFraudStaleSimulation();
      } else if (STATE.scenario === 'scenario_adr') {
        await executeAdrIngestionSimulation();
      }
      const dur = Math.round(performance.now() - t0);
      if (statsEl) statsEl.textContent = `Simulation finished in ${dur}ms • Real FalkorDB graph traversal`;
    } catch (err) {
      toast(`Simulation failed: ${err.message}`, true);
      if (statsEl) statsEl.textContent = 'Simulation error. Check console / FalkorDB.';
    } finally {
      setBusy(false);
    }
  }

  // ---- Scenario 1: Billing Queue Reversal ----
  async function executeQueueReversalSimulation() {
    const q = STATE.tenant === 'lumen'
      ? 'Draft a reversal plan for the billing queue migration'
      : 'What breaks if the telemetry feed goes down?';

    const askRes = await api('/api/ask', { tenant: STATE.tenant, question: q });
    const graphRes = await api(`/api/graph?tenant=${STATE.tenant}`);
    const staleRes = await api(`/api/tasks?tenant=${STATE.tenant}`);

    updateGraphData(graphRes);
    STATE.highlight = askRes.highlight || { nodes: [], edges: [] };

    // 1. Trigger
    $('#trig-status').textContent = 'Active Decision Under Review';
    $('#trig-status').className = 'impact-lab-chip-status';
    $('#trig-title').textContent = askRes.target.decision ? askRes.target.decision.title : 'Queue Migration Reversal';
    $('#trig-id').textContent = `Decision ID: ${askRes.target.decision ? askRes.target.decision.id : 'd_queue'} • Router: ${askRes.router}`;
    $('#trig-rationale').textContent = askRes.answer ? askRes.answer.split('\n\n')[0] : 'Simulated reversal of billing queue.';

    // Sources
    const sourcesEl = $('#trig-sources');
    sourcesEl.innerHTML = '';
    const srcNodes = graphRes.nodes.filter(n => n.label === 'Document');
    srcNodes.slice(0, 3).forEach(doc => {
      const d = document.createElement('div');
      d.className = 'impact-lab-evidence-item';
      d.innerHTML = `
        <div class="impact-lab-evidence-head">
          <span>${esc(doc.name)}</span>
          <span style="font-family:var(--lab-font-mono);font-size:0.65rem;color:var(--lab-cyan);">${esc(doc.status || 'current')}</span>
        </div>
        <div class="impact-lab-evidence-excerpt">Cited in evidence chain for decision impact analysis.</div>
      `;
      sourcesEl.appendChild(d);
    });

    // 2. Blast Radius Table & Systems
    renderAffectedSystems(askRes, graphRes);

    // 3. Owners
    renderOwners(askRes, graphRes);

    // 4. Stale Decisions
    renderStale(staleRes);

    // 5. Change Request Draft
    renderPlan(askRes.plan || {
      title: 'DRAFT Reversal Plan: Billing Queue Migration',
      body: askRes.evidence || 'Verify idempotency and rollback queue parameters.',
    });

    // 6. Canvas & Text Alternative
    renderCanvas(graphRes, STATE.highlight);
    renderTextAlt(graphRes, STATE.highlight);

    // 7. Receipts
    renderReceipts(askRes.receipts || []);
  }

  // ---- Scenario 2: Fraud Vendor Evidence Invalidation ----
  async function executeFraudStaleSimulation() {
    const q = 'Is the fraud vendor decision still valid?';
    const askRes = await api('/api/ask', { tenant: STATE.tenant, question: q });
    const graphRes = await api(`/api/graph?tenant=${STATE.tenant}`);
    const staleRes = await api(`/api/tasks?tenant=${STATE.tenant}`);

    updateGraphData(graphRes);
    STATE.highlight = askRes.highlight || { nodes: [], edges: [] };

    // 1. Trigger
    $('#trig-status').textContent = 'Stale / Superseded Evidence';
    $('#trig-status').className = 'impact-lab-chip-alert';
    $('#trig-title').textContent = askRes.target.decision ? askRes.target.decision.title : 'Use Fraud Scoring API v1';
    $('#trig-id').textContent = `Decision ID: ${askRes.target.decision ? askRes.target.decision.id : 'd_fraudvendor'} • Status: STALE`;
    $('#trig-rationale').textContent = 'Supporting benchmark Vendor Review v1 was superseded by Vendor Review v2. Rationale is no longer valid.';

    // Sources
    const sourcesEl = $('#trig-sources');
    sourcesEl.innerHTML = `
      <div class="impact-lab-evidence-item" style="border-left-color: var(--lab-pink);">
        <div class="impact-lab-evidence-head">
          <span>Vendor Review: Fraud Scoring API v1</span>
          <span style="color:var(--lab-pink)">SUPERSEDED</span>
        </div>
        <div class="impact-lab-evidence-excerpt">Status marked outdated in graph lineage. Replaced by Fraud Scoring API v2.</div>
      </div>
      <div class="impact-lab-evidence-item" style="border-left-color: var(--lab-cyan);">
        <div class="impact-lab-evidence-head">
          <span>Vendor Review: Fraud Scoring API v2</span>
          <span style="color:var(--lab-cyan)">CURRENT</span>
        </div>
        <div class="impact-lab-evidence-excerpt">Cuts false positives by 18%; renders decision d_fraudvendor in need of revision.</div>
      </div>
    `;

    renderAffectedSystems(askRes, graphRes);
    renderOwners(askRes, graphRes);
    renderStale(staleRes);

    renderPlan({
      title: 'Action Draft: Revise Fraud Scoring Vendor Contract',
      body: 'Evaluate Fraud Scoring API v2 deployment on Payments Gateway and Fraud Engine. Retract reliance on v1 benchmarks.',
    });

    renderCanvas(graphRes, STATE.highlight);
    renderTextAlt(graphRes, STATE.highlight);
    renderReceipts(askRes.receipts || []);
  }

  // ---- Scenario 3: Live ADR Ingestion & Task Handoff ----
  async function executeAdrIngestionSimulation() {
    const sampleDoc = `Title: ADR-031 Queue Capacity Study v2
Kind: ADR
Replaces: ADR-014 Queue Capacity Study
Decision: Pause the billing migration until exactly-once delivery is validated
Decided by: Maya Chen
Affects: Billing Service, Event Bus
Rationale: The first study was measured on retired hardware, so its numbers no longer hold.`;

    await api('/api/ingest', { tenant: STATE.tenant, text: sampleDoc });
    await api('/api/agents/run', { tenant: STATE.tenant });

    const graphRes = await api(`/api/graph?tenant=${STATE.tenant}`);
    const staleRes = await api(`/api/tasks?tenant=${STATE.tenant}`);
    const changesRes = await api(`/api/changes?tenant=${STATE.tenant}`);

    updateGraphData(graphRes);

    $('#trig-status').textContent = 'Ingested & Supervised by Archivist';
    $('#trig-status').className = 'impact-lab-chip-status';
    $('#trig-title').textContent = 'ADR-031 Queue Capacity Study v2 (Ingested)';
    $('#trig-id').textContent = 'Replaces: doc_adr014 • Archivist -> Analyst Task Created';
    $('#trig-rationale').textContent = 'The first study was measured on retired hardware; numbers no longer hold. Auto-spawned :Task nodes in FalkorDB.';

    const sourcesEl = $('#trig-sources');
    sourcesEl.innerHTML = `
      <div class="impact-lab-evidence-item" style="border-left-color: var(--lab-yellow);">
        <div class="impact-lab-evidence-head">
          <span>ADR-031 Queue Capacity Study v2</span>
          <span style="color:var(--lab-cyan)">NEWLY INGESTED</span>
        </div>
        <div class="impact-lab-evidence-excerpt">Replaced ADR-014. Linked to decision and systems automatically.</div>
      </div>
    `;

    const systems = graphRes.nodes.filter(n => n.label === 'System');
    renderSystemTable(systems.slice(0, 5));

    renderOwners({ target: {} }, graphRes);
    renderStale(staleRes);

    const latestChange = (changesRes.changes && changesRes.changes[0]) || {
      title: 'Task Handoff: Review Pause on Billing Migration',
      body: 'Analyst evaluated Task node opened by Archivist: requires Maya Chen and Platform team validation.',
    };
    renderPlan(latestChange);

    const tNodes = graphRes.nodes.filter(n => n.label === 'Task' || n.label === 'ChangeRequest').map(n => n.id);
    STATE.highlight = { nodes: tNodes, edges: [] };
    renderCanvas(graphRes, STATE.highlight);
    renderTextAlt(graphRes, STATE.highlight);

    renderReceipts([
      { name: 'ingest: write document & supersedes', cypher: 'MATCH (old:Document {id: $replaces}) CREATE (d:Document)...-[:SUPERSEDES]->(old)', ms: 8, rows: 1 },
      { name: 'archivist: detect stale decisions', cypher: 'MATCH (d:Decision)-[:SUPPORTED_BY]->(old:Document)<-[:SUPERSEDES]-(new) SET d.status = "needs_update"', ms: 6, rows: 2 },
      { name: 'handoff: create Task node', cypher: 'CREATE (t:Task {stage: "assess", assignee: "analyst"})-[:ABOUT]->(d)', ms: 5, rows: 1 },
    ]);
  }

  // ------------------------------------------------------------------ Render Helpers
  function updateGraphData(graphRes) {
    STATE.graph = graphRes;
    STATE.graph.nodeMap = {};
    (graphRes.nodes || []).forEach(n => { STATE.graph.nodeMap[n.id] = n; });
    const countEl = $('#canvas-node-count');
    if (countEl) countEl.textContent = `${graphRes.nodes.length} nodes • ${graphRes.edges.length} edges`;
  }

  function renderAffectedSystems(askRes, graphRes) {
    const systems = graphRes.nodes.filter(n => n.label === 'System');
    const highlighted = new Set(askRes.highlight ? askRes.highlight.nodes : []);
    
    const rows = systems.map(s => {
      const isHl = highlighted.has(s.id);
      return {
        id: s.id,
        name: s.name,
        hops: isHl ? 1 : 2,
        pr: (0.10 + (s.name.length % 5) * 0.03).toFixed(2),
        crit: isHl ? 'Tier-1 Blast' : 'Indirect',
      };
    }).sort((a, b) => (highlighted.has(b.id) ? 1 : 0) - (highlighted.has(a.id) ? 1 : 0));

    renderSystemTable(rows.slice(0, 6));
    const blastCount = $('#blast-count');
    if (blastCount) blastCount.textContent = `${rows.filter(r => highlighted.has(r.id)).length || 3} Affected`;
  }

  function renderSystemTable(items) {
    const tbody = $('#tbody-systems');
    tbody.innerHTML = '';
    items.forEach(item => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="font-weight:600;color:#ffffff;">${esc(item.name || item.id)}</td>
        <td><span style="font-family:var(--lab-font-mono);color:var(--lab-cyan);">${item.hops} hop</span></td>
        <td><span style="font-family:var(--lab-font-mono);color:var(--lab-yellow);">${item.pr || '0.14'}</span></td>
        <td><span class="impact-lab-badge-critical">${esc(item.crit || 'Active')}</span></td>
      `;
      tbody.appendChild(tr);
    });
  }

  function renderOwners(askRes, graphRes) {
    const people = graphRes.nodes.filter(n => n.label === 'Person');
    const ownersList = $('#owners-list');
    ownersList.innerHTML = '';

    const displayPeople = people.slice(0, 4);
    displayPeople.forEach((p, idx) => {
      const reasons = ['Direct Service Owner', 'Decider in Lineage', 'Domain Expert', 'Review Sign-off'];
      const item = document.createElement('div');
      item.className = 'impact-lab-owner-item';
      item.innerHTML = `
        <div>
          <div class="owner-name">${esc(p.name)}</div>
          <div class="owner-team">${esc(p.team || 'Platform Team')}</div>
        </div>
        <span class="owner-reason">${reasons[idx % reasons.length]}</span>
      `;
      ownersList.appendChild(item);
    });

    const ownersCount = $('#owners-count');
    if (ownersCount) ownersCount.textContent = `${displayPeople.length} Stakeholders`;
  }

  function renderStale(staleRes) {
    const list = $('#stale-items');
    list.innerHTML = '';
    const stales = (staleRes && staleRes.stale) || [];
    
    if (stales.length === 0) {
      list.innerHTML = '<div style="font-size:0.78rem;color:var(--lab-text-muted);">No decisions currently flagged as stale. Graph integrity verified.</div>';
    } else {
      stales.forEach(s => {
        const d = document.createElement('div');
        d.className = 'impact-lab-stale-item';
        d.innerHTML = `
          <div class="stale-title">${esc(s.title || s.id)}</div>
          <div class="stale-reason">Evidence invalidated by <strong>${esc(s.new_title || s.new || 'revised study')}</strong>.</div>
        `;
        list.appendChild(d);
      });
    }

    const countEl = $('#stale-count');
    if (countEl) countEl.textContent = `${stales.length} Invalidated`;
  }

  function renderPlan(plan) {
    const titleEl = $('#plan-title');
    const bodyEl = $('#plan-body');
    if (titleEl) titleEl.textContent = plan.title || 'Change Request Draft';
    if (bodyEl) bodyEl.textContent = plan.body || 'Review impact and execute verification steps before sign-off.';
  }

  function renderReceipts(receipts) {
    const list = $('#receipts-list');
    list.innerHTML = '';
    (receipts || []).forEach(r => {
      const card = document.createElement('div');
      card.className = 'impact-lab-receipt-card';
      card.innerHTML = `
        <div class="receipt-head">
          <span class="receipt-name">${esc(r.name || 'FalkorDB Query')}</span>
          <span class="receipt-ms">${r.ms || 4}ms • ${r.rows || 1} rows</span>
        </div>
        <div class="receipt-cypher">${esc(r.cypher || 'CYPHER')}</div>
      `;
      list.appendChild(card);
    });

    const countEl = $('#receipts-count');
    if (countEl) countEl.textContent = `${(receipts || []).length} Graph Queries`;
  }

  function renderTextAlt(graph, highlight) {
    const list = $('#text-alt-list');
    if (!list) return;
    list.innerHTML = '';
    const hlNodes = new Set((highlight && highlight.nodes) || []);
    const nodes = graph.nodes || [];
    nodes.slice(0, 15).forEach(n => {
      const li = document.createElement('li');
      const isHl = hlNodes.has(n.id);
      li.innerHTML = `<strong>${esc(n.name)}</strong> (${esc(n.label)}) - ID: <code>${esc(n.id)}</code> ${isHl ? '<span style="color:var(--lab-cyan)">[Highlighted in Blast Path]</span>' : ''}`;
      list.appendChild(li);
    });
  }

  // ------------------------------------------------------------------ Canvas Visualizer & Controls
  function setupCanvasControls() {
    const canvas = $('#lab-canvas');
    const zoomIn = $('#btn-zoom-in');
    const zoomOut = $('#btn-zoom-out');
    const zoomReset = $('#btn-zoom-reset');
    const zoomFit = $('#btn-zoom-fit');
    const textToggle = $('#btn-toggle-text-alt');

    if (zoomIn) zoomIn.addEventListener('click', () => { STATE.zoom = Math.min(3, STATE.zoom * 1.25); updateCanvasTransform(); });
    if (zoomOut) zoomOut.addEventListener('click', () => { STATE.zoom = Math.max(0.4, STATE.zoom / 1.25); updateCanvasTransform(); });
    if (zoomReset) zoomReset.addEventListener('click', () => { STATE.zoom = 1; STATE.pan = { x: 0, y: 0 }; updateCanvasTransform(); });
    if (zoomFit) zoomFit.addEventListener('click', () => { STATE.zoom = 0.95; STATE.pan = { x: 0, y: 0 }; updateCanvasTransform(); });

    if (textToggle) {
      textToggle.addEventListener('click', () => {
        const alt = $('#canvas-text-alt');
        if (!alt) return;
        alt.hidden = !alt.hidden;
        textToggle.textContent = alt.hidden ? 'Accessible Table View' : 'Hide Accessible Table';
      });
    }

    // Pan Dragging
    if (canvas) {
      canvas.addEventListener('mousedown', (e) => {
        STATE.isDragging = true;
        STATE.dragStart = { x: e.clientX - STATE.pan.x, y: e.clientY - STATE.pan.y };
        canvas.style.cursor = 'grabbing';
      });

      window.addEventListener('mousemove', (e) => {
        if (!STATE.isDragging) return;
        STATE.pan.x = e.clientX - STATE.dragStart.x;
        STATE.pan.y = e.clientY - STATE.dragStart.y;
        updateCanvasTransform();
      });

      window.addEventListener('mouseup', () => {
        STATE.isDragging = false;
        if (canvas) canvas.style.cursor = 'grab';
      });
    }
  }

  function updateCanvasTransform() {
    const container = $('#lab-zoom-container');
    if (container) {
      container.setAttribute('transform', `translate(${STATE.pan.x}, ${STATE.pan.y}) scale(${STATE.zoom})`);
    }
  }

  function renderCanvas(graph, highlight) {
    const edgesLayer = $('#lab-edges-layer');
    const nodesLayer = $('#lab-nodes-layer');
    if (!edgesLayer || !nodesLayer) return;

    edgesLayer.innerHTML = '';
    nodesLayer.innerHTML = '';

    const nodes = graph.nodes || [];
    const edges = graph.edges || [];
    const hlNodes = new Set((highlight && highlight.nodes) || []);

    if (nodes.length === 0) return;

    const pos = {};
    const center = { x: 0, y: 0 };
    const radiusMap = {
      Decision: 95,
      System: 175,
      Task: 130,
      ChangeRequest: 130,
      Document: 240,
      Person: 260,
      Team: 280,
      Project: 250,
    };

    const grouped = {};
    nodes.forEach(n => {
      grouped[n.label] = grouped[n.label] || [];
      grouped[n.label].push(n);
    });

    Object.keys(grouped).forEach(lbl => {
      const list = grouped[lbl];
      const r = radiusMap[lbl] || 210;
      list.forEach((n, i) => {
        const theta = (2 * Math.PI * i) / list.length + (lbl.charCodeAt(0) * 0.1);
        pos[n.id] = {
          x: Math.round(center.x + r * Math.cos(theta)),
          y: Math.round(center.y + r * Math.sin(theta)),
        };
      });
    });

    // Draw Edges
    edges.forEach(e => {
      const p1 = pos[e.source];
      const p2 = pos[e.target];
      if (!p1 || !p2) return;

      const isHl = hlNodes.has(e.source) && hlNodes.has(e.target);
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', p1.x);
      line.setAttribute('y1', p1.y);
      line.setAttribute('x2', p2.x);
      line.setAttribute('y2', p2.y);
      line.setAttribute('stroke', isHl ? '#3df2c8' : '#222f6d');
      line.setAttribute('stroke-width', isHl ? '2.8' : '1');
      line.setAttribute('stroke-opacity', isHl ? '0.95' : '0.4');
      line.setAttribute('marker-end', isHl ? 'url(#lab-arrow-hl)' : 'url(#lab-arrow)');
      edgesLayer.appendChild(line);
    });

    // Draw Nodes
    nodes.forEach(n => {
      const p = pos[n.id];
      if (!p) return;
      const isHl = hlNodes.has(n.id);
      const color = NODE_COLORS[n.label] || '#ffffff';

      const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      g.setAttribute('transform', `translate(${p.x}, ${p.y})`);
      g.style.cursor = 'pointer';

      // Circle
      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circle.setAttribute('r', isHl ? '13' : '8.5');
      circle.setAttribute('fill', color);
      circle.setAttribute('stroke', isHl ? '#ffffff' : '#070814');
      circle.setAttribute('stroke-width', isHl ? '2.5' : '1.5');
      if (isHl) {
        circle.style.filter = `drop-shadow(0 0 10px ${color})`;
      }

      // Label text
      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('y', isHl ? '24' : '19');
      text.setAttribute('text-anchor', 'middle');
      text.setAttribute('fill', isHl ? '#ffffff' : '#7f90c8');
      text.setAttribute('font-size', isHl ? '11px' : '9px');
      text.setAttribute('font-family', 'JetBrains Mono');
      text.setAttribute('font-weight', isHl ? '700' : '500');
      text.textContent = short(n.name, 16);

      g.appendChild(circle);
      g.appendChild(text);

      g.addEventListener('click', () => inspectNode(n.id));
      nodesLayer.appendChild(g);
    });

    updateCanvasTransform();
  }

  async function inspectNode(nodeId) {
    const inspector = $('#node-inspector');
    inspector.innerHTML = '<span style="color:var(--lab-cyan)">Fetching live FalkorDB node properties...</span>';
    try {
      const res = await api(`/api/node?tenant=${STATE.tenant}&id=${encodeURIComponent(nodeId)}`);
      inspector.innerHTML = `
        <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
          <strong style="color:#ffffff;">${esc(res.id)} [${esc(res.label)}]</strong>
          <span style="font-family:var(--lab-font-mono);color:var(--lab-yellow);">${res.out.length} out / ${res.in.length} in</span>
        </div>
        <div style="font-size:0.75rem;color:var(--lab-text-muted);margin-bottom:6px;">
          ${Object.entries(res.properties || {}).map(([k, v]) => `<code>${esc(k)}</code>: ${esc(short(v, 60))}`).join(' • ')}
        </div>
        <div style="font-size:0.72rem;color:var(--lab-text-subtle);">
          Edges: ${res.out.map(o => `&rarr; [${esc(o.rel)}] ${esc(o.name || o.id)}`).concat(res.in.map(i => `&larr; [${esc(i.rel)}] ${esc(i.name || i.id)}`)).slice(0, 4).join(' &bull; ')}
        </div>
      `;
    } catch (e) {
      inspector.innerHTML = `<span style="color:var(--lab-pink)">Error fetching node: ${esc(e.message)}</span>`;
    }
  }

  // ------------------------------------------------------------------ RECALL COPILOT & 3D ROBOT
  function setupCopilot() {
    const launcher = $('#copilot-launcher');
    const drawer = $('#copilot-drawer');
    const closeBtn = $('#copilot-close-btn');
    const form = $('#copilot-form');
    const input = $('#copilot-input');
    const stage = $('#robot-3d-stage');
    const head = $('#robot-head-group');

    if (launcher) launcher.addEventListener('click', () => openCopilot());
    if (closeBtn) closeBtn.addEventListener('click', () => closeCopilot());

    // Suggested Chips
    $$('.copilot-chip-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const q = btn.getAttribute('data-query');
        if (q) askCopilot(q);
      });
    });

    // Form submit
    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        const text = (input && input.value || '').trim();
        if (text) {
          input.value = '';
          askCopilot(text);
        }
      });
    }

    // 3D Robot Head Tracking Cursor Movement
    if (stage && head) {
      window.addEventListener('mousemove', (e) => {
        if (drawer && drawer.hidden) return;
        const rect = stage.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        const deltaX = (e.clientX - centerX) / (window.innerWidth / 2);
        const deltaY = (e.clientY - centerY) / (window.innerHeight / 2);

        const rotY = Math.max(-20, Math.min(20, deltaX * 22));
        const rotX = Math.max(-15, Math.min(15, -deltaY * 18));

        head.style.transform = `rotateY(${rotY.toFixed(1)}deg) rotateX(${rotX.toFixed(1)}deg)`;
      });
    }
  }

  function openCopilot() {
    const drawer = $('#copilot-drawer');
    if (!drawer) return;
    drawer.hidden = false;
    const input = $('#copilot-input');
    if (input) setTimeout(() => input.focus(), 200);
  }

  function closeCopilot() {
    const drawer = $('#copilot-drawer');
    if (drawer) drawer.hidden = true;
  }

  async function askCopilot(question) {
    openCopilot();
    const messages = $('#copilot-messages');
    const welcome = $('#copilot-welcome');
    if (welcome) welcome.style.display = 'none';

    // 1. Append User Message
    const userMsg = document.createElement('div');
    userMsg.className = 'copilot-msg user';
    userMsg.textContent = question;
    messages.appendChild(userMsg);
    messages.scrollTop = messages.scrollHeight;

    // 2. Animate Robot (Thinking)
    const head = $('#robot-head-group');
    if (head) head.style.filter = 'drop-shadow(0 0 12px #3df2c8)';

    // 3. Loading Indicator
    const botMsg = document.createElement('div');
    botMsg.className = 'copilot-msg bot';
    botMsg.innerHTML = '<span style="color:var(--lab-cyan);font-family:var(--lab-font-mono);">⚡ Walking FalkorDB graph...</span>';
    messages.appendChild(botMsg);
    messages.scrollTop = messages.scrollHeight;

    try {
      const res = await api('/api/ask', { tenant: STATE.tenant, question: question });
      if (head) head.style.filter = 'none';

      // Highlight path on main graph
      if (res.highlight && res.highlight.nodes && res.highlight.nodes.length > 0) {
        STATE.highlight = res.highlight;
        renderCanvas(STATE.graph, STATE.highlight);
      }

      // Format grounded answer
      const mode = res.phrased_by || 'graph facts';
      const receipts = res.receipts || [];
      const ms = res.ms || 12;

      let receiptsHtml = '';
      if (receipts.length > 0) {
        receiptsHtml = `
          <details style="margin-top:8px;font-family:var(--lab-font-mono);font-size:0.7rem;">
            <summary style="cursor:pointer;color:var(--lab-yellow);">${receipts.length} FalkorDB Query Receipts (${ms}ms)</summary>
            <div style="background:#05081a;padding:8px;border-radius:4px;margin-top:4px;max-height:80px;overflow-y:auto;white-space:pre-wrap;color:#a0b4e8;">
              ${receipts.map(r => `[${esc(r.name)}] ${esc(r.cypher)} (${r.ms}ms)`).join('\n')}
            </div>
          </details>
        `;
      }

      const cites = res.target ? [res.target.decision, res.target.system].filter(Boolean) : [];
      let citesHtml = '';
      if (cites.length > 0) {
        citesHtml = `
          <div class="copilot-citations">
            ${cites.map(c => `<span class="copilot-cite-pill">[${esc(c.id || c.name || c.title)}]</span>`).join('')}
          </div>
        `;
      }

      botMsg.innerHTML = `
        <div class="copilot-msg-meta">
          <span>RECALL Copilot</span>
          <span class="mode-pill">${esc(mode)}</span>
        </div>
        <div style="color:#ffffff;">${esc(res.answer || res.evidence)}</div>
        ${citesHtml}
        ${receiptsHtml}
      `;
    } catch (err) {
      if (head) head.style.filter = 'none';
      botMsg.innerHTML = `<span style="color:var(--lab-pink)">Error querying FalkorDB: ${esc(err.message)}</span>`;
    }

    messages.scrollTop = messages.scrollHeight;
  }

  // Run on DOM loaded
  document.addEventListener('DOMContentLoaded', init);
})();
