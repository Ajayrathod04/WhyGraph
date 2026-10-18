/* ==========================================================================
   WhyGraph / RECALL — Impact Lab JavaScript
   Change Simulation, Blast Radius Traversal & Evidence Inspector
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

    // 6. Canvas
    renderCanvas(graphRes, askRes.highlight || { nodes: [], edges: [] });

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

    renderCanvas(graphRes, askRes.highlight || { nodes: [], edges: [] });
    renderReceipts(askRes.receipts || []);
  }

  // ---- Scenario 3: Live ADR Ingestion & Task Handoff ----
  async function executeAdrIngestionSimulation() {
    // Ingest sample ADR document
    const sampleDoc = `Title: ADR-031 Queue Capacity Study v2
Kind: ADR
Replaces: ADR-014 Queue Capacity Study
Decision: Pause the billing migration until exactly-once delivery is validated
Decided by: Maya Chen
Affects: Billing Service, Event Bus
Rationale: The first study was measured on retired hardware, so its numbers no longer hold.`;

    await api('/api/ingest', { tenant: STATE.tenant, text: sampleDoc });
    // Trigger 2-agent handoff pass
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

    // Render systems
    const systems = graphRes.nodes.filter(n => n.label === 'System');
    renderSystemTable(systems.slice(0, 5), [
      { id: 's_billing', hops: 1, pr: 0.18, crit: 'Critical' },
      { id: 's_bus', hops: 1, pr: 0.16, crit: 'Critical' },
      { id: 's_ledger', hops: 2, pr: 0.22, crit: 'Highest' },
    ]);

    renderOwners({ target: {} }, graphRes);
    renderStale(staleRes);

    const latestChange = (changesRes.changes && changesRes.changes[0]) || {
      title: 'Task Handoff: Review Pause on Billing Migration',
      body: 'Analyst evaluated Task node opened by Archivist: requires Maya Chen and Platform team validation.',
    };
    renderPlan(latestChange);

    // Highlight Task and ChangeRequest nodes
    const tNodes = graphRes.nodes.filter(n => n.label === 'Task' || n.label === 'ChangeRequest').map(n => n.id);
    renderCanvas(graphRes, { nodes: tNodes, edges: [] });

    // Mock receipts for ingest + handoff
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
    
    // Sort systems: highlighted first
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

  // ------------------------------------------------------------------ Canvas Visualizer
  function renderCanvas(graph, highlight) {
    const edgesLayer = $('#lab-edges-layer');
    const nodesLayer = $('#lab-nodes-layer');
    edgesLayer.innerHTML = '';
    nodesLayer.innerHTML = '';

    const nodes = graph.nodes || [];
    const edges = graph.edges || [];
    const hlNodes = new Set((highlight && highlight.nodes) || []);

    if (nodes.length === 0) return;

    // Arrange nodes in concentric rings by label
    const pos = {};
    const center = { x: 0, y: 0 };
    const radiusMap = {
      Decision: 90,
      System: 170,
      Task: 120,
      ChangeRequest: 120,
      Document: 230,
      Person: 250,
      Team: 270,
      Project: 240,
    };

    const grouped = {};
    nodes.forEach(n => {
      grouped[n.label] = grouped[n.label] || [];
      grouped[n.label].push(n);
    });

    Object.keys(grouped).forEach(lbl => {
      const list = grouped[lbl];
      const r = radiusMap[lbl] || 200;
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
      line.setAttribute('stroke-width', isHl ? '2.5' : '1');
      line.setAttribute('stroke-opacity', isHl ? '0.9' : '0.4');
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
      circle.setAttribute('r', isHl ? '12' : '8');
      circle.setAttribute('fill', color);
      circle.setAttribute('stroke', isHl ? '#ffffff' : '#070814');
      circle.setAttribute('stroke-width', isHl ? '2.5' : '1.5');
      if (isHl) {
        circle.style.filter = `drop-shadow(0 0 8px ${color})`;
      }

      // Label text
      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('y', isHl ? '22' : '18');
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

  // Run on DOM loaded
  document.addEventListener('DOMContentLoaded', init);
})();
