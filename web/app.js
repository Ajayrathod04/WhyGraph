/* WhyGraph front end: plain JavaScript, no build step, no external libraries.
   The graph picture is drawn by a small force-directed layout (see layout()) into an SVG. */
(function () {
  'use strict';

  const $ = (sel, el) => (el || document).querySelector(sel);
  const $$ = (sel, el) => Array.from((el || document).querySelectorAll(sel));
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const short = (s, n) => (String(s).length > n ? String(s).slice(0, n - 1) + '\u2026' : String(s));
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  const S = {
    tenant: null, health: null, nodes: [], edges: [], nodeMap: {}, pos: {},
    hl: { nodes: new Set(), edges: new Set() }, focus: true, view: { x: 0, y: 0, k: 1 }, nodeEls: {}, edgeEls: {}, busy: false,
  };

  const COLORS = { Decision: '#ffd83d', System: '#3df2c8', Person: '#ff3d9a', Document: '#ffffff', Team: '#b58cff', Project: '#7fddf0', Task: '#ff6a4d', ChangeRequest: '#ffa94d' };
  const RING = { Decision: 0.36, Task: 0.5, ChangeRequest: 0.5, System: 0.66, Project: 0.86, Team: 0.9, Document: 0.88, Person: 1.0 };

  // ------------------------------------------------------------------ helpers
  async function api(path, body) {
    const opt = body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {};
    const res = await fetch(path, opt);
    let data = null;
    try { data = await res.json(); } catch (e) { /* not json */ }
    if (!res.ok) throw new Error((data && data.error) || res.statusText || 'Request failed');
    return data;
  }

  let toastTimer = null;
  function toast(msg, isErr) {
    const t = $('#toast');
    t.textContent = msg;
    t.className = 'toast' + (isErr ? ' err' : '');
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, 4200);
  }

  function setBusy(on) {
    S.busy = on;
    ['#btn-ask', '#btn-run', '#btn-ingest', '#btn-reset'].forEach((s) => { const b = $(s); if (b) b.disabled = on; });
  }

  function citeHtml(id) {
    const n = S.nodeMap[id];
    const label = n ? short(n.name, 24) : id;
    const kind = id.split('_')[0];
    return `<button class="cite k-${esc(kind)}" data-id="${esc(id)}" title="${esc(id)}">${esc(label)}</button>`;
  }
  function inline(s) {
    let h = esc(s);
    h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    h = h.replace(/\[([a-z]{1,4}_[a-z0-9_]+)\]/g, (m, id) => citeHtml(id));
    return h.replace(/\n/g, '<br>');
  }
  function fmt(text) {
    return String(text || '').split(/\n{2,}/).map((p, i) => `<p style="animation-delay:${(i * 0.16).toFixed(2)}s">${inline(p)}</p>`).join('');
  }

  // ------------------------------------------------------------------ force-directed layout (pure function)
  function hash(str) {
    let h = 2166136261;
    for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
    return (h >>> 0) / 4294967295;
  }

  function layout(nodes, edges, prev) {
    prev = prev || {};
    const W = 1200, H = 800, cx = W / 2, cy = H / 2, R = H * 0.47;
    const idx = {};
    nodes.forEach((n, i) => { idx[n.id] = i; });
    const warm = Object.keys(prev).length > 0;
    const P = nodes.map((n) => {
      const p = prev[n.id];
      if (p) return { x: p.x, y: p.y };
      const a = hash(n.id) * Math.PI * 2;
      const r = (RING[n.label] || 0.7) * R * (0.85 + hash(n.id + 'r') * 0.3);
      return { x: cx + Math.cos(a) * r * 1.25, y: cy + Math.sin(a) * r };
    });
    const E = [];
    edges.forEach((e) => { const a = idx[e.source], b = idx[e.target]; if (a !== undefined && b !== undefined) E.push([a, b]); });
    const k = Math.sqrt((W * H) / Math.max(nodes.length, 1)) * 0.6;
    let temp = warm ? 8 : 60;
    const iters = warm ? 120 : 320;
    for (let it = 0; it < iters; it++) {
      const d = nodes.map(() => [0, 0]);
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          let dx = P[i].x - P[j].x, dy = P[i].y - P[j].y;
          let d2 = dx * dx + dy * dy;
          if (d2 < 0.01) { dx = hash(nodes[i].id + j) - 0.5; dy = hash(nodes[j].id + i) - 0.5; d2 = 0.25; }
          const dist = Math.sqrt(d2), f = (k * k) / dist;
          d[i][0] += (dx / dist) * f; d[i][1] += (dy / dist) * f;
          d[j][0] -= (dx / dist) * f; d[j][1] -= (dy / dist) * f;
        }
      }
      E.forEach(([a, b]) => {
        const dx = P[a].x - P[b].x, dy = P[a].y - P[b].y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 0.01, f = ((dist * dist) / k) * 0.9;
        d[a][0] -= (dx / dist) * f; d[a][1] -= (dy / dist) * f;
        d[b][0] += (dx / dist) * f; d[b][1] += (dy / dist) * f;
      });
      nodes.forEach((n, i) => {
        const dx = (P[i].x - cx) / 1.25, dy = P[i].y - cy;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const f = (dist - (RING[n.label] || 0.7) * R) * 0.35;
        d[i][0] -= (dx / dist) * f * 1.25; d[i][1] -= (dy / dist) * f;
      });
      nodes.forEach((n, i) => {
        if (warm && prev[n.id]) return; // existing nodes stay put; only new nodes settle into place
        const len = Math.sqrt(d[i][0] * d[i][0] + d[i][1] * d[i][1]) || 1;
        const step = Math.min(len, temp);
        P[i].x += (d[i][0] / len) * step; P[i].y += (d[i][1] / len) * step;
      });
      temp *= 0.985;
    }
    const out = {};
    nodes.forEach((n, i) => { out[n.id] = { x: P[i].x, y: P[i].y }; });
    return out;
  }

  // ------------------------------------------------------------------ graph rendering
  function shapeSvg(label) {
    switch (label) {
      case 'Decision': return '<rect class="shape" x="-17" y="-11" width="34" height="22" rx="7"/>';
      case 'System': return '<rect class="shape" x="-12" y="-12" width="24" height="24" rx="9"/>';
      case 'Person': return '<circle class="shape" r="10"/>';
      case 'Document': return '<path class="shape" d="M-9 -12 H3 L10 -5 V12 H-9 Z"/>';
      case 'Team': return '<rect class="shape" x="-14" y="-7" width="28" height="14" rx="7"/>';
      case 'Project': return '<path class="shape" d="M0 -11 L11 0 L0 11 L-11 0 Z"/>';
      case 'Task': return '<path class="shape" d="M-6 -10 H6 L12 0 L6 10 H-6 L-12 0 Z"/>';
      default: return '<rect class="shape" x="-11" y="-11" width="22" height="22" rx="3"/>';
    }
  }

  function renderLegend() {
    const present = new Set(S.nodes.map((n) => n.label));
    $('#legend').innerHTML = Object.keys(COLORS).filter((l) => present.has(l))
      .map((l) => `<span><i style="background:${COLORS[l]}"></i>${l}</span>`).join('');
    $('#graph-count').textContent = `${S.nodes.length} nodes \u00b7 ${S.edges.length} edges`;
  }

  function renderGraph() {
    const edgesG = $('#edges'), nodesG = $('#nodes');
    S.edgeEls = {}; S.nodeEls = {};
    edgesG.innerHTML = S.edges.map((e) => `<line class="edge" data-k="${esc(e.source)}|${esc(e.rel)}|${esc(e.target)}"/>`).join('');
    $$('line', edgesG).forEach((el) => { S.edgeEls[el.dataset.k] = el; });
    nodesG.innerHTML = S.nodes.map((n) => {
      const cls = ['node', 'n-' + n.label];
      if (n.label === 'Decision' && n.status === 'superseded') cls.push('superseded');
      if (n.label === 'Document' && n.status === 'outdated') cls.push('outdated');
      if (n.stale) cls.push('stale');
      const label = n.label === 'Person' || n.label === 'Team' ? short(n.name, 16) : short(n.name, 20);
      return `<g class="${cls.join(' ')}" data-id="${esc(n.id)}" tabindex="0" role="button" aria-label="${esc(n.label + ': ' + n.name)}">` +
        '<circle class="ring" r="22"/>' + (n.stale ? '<circle class="ping" r="16"/>' : '') + shapeSvg(n.label) +
        `<text y="${n.label === 'Decision' ? 25 : 24}" text-anchor="middle">${esc(label)}</text><title>${esc(n.label + ': ' + n.name + (n.status ? ' (' + n.status + ')' : ''))}</title></g>`;
    }).join('');
    $$('.node', nodesG).forEach((el) => { S.nodeEls[el.dataset.id] = el; });
    positionAll();
    applyHighlight();
    renderLegend();
  }

  function positionAll() {
    S.nodes.forEach((n) => {
      const p = S.pos[n.id], el = S.nodeEls[n.id];
      if (p && el) el.setAttribute('transform', `translate(${p.x.toFixed(1)},${p.y.toFixed(1)})`);
    });
    S.edges.forEach((e) => {
      const a = S.pos[e.source], b = S.pos[e.target], el = S.edgeEls[`${e.source}|${e.rel}|${e.target}`];
      if (!a || !b || !el) return;
      const dx = b.x - a.x, dy = b.y - a.y, len = Math.sqrt(dx * dx + dy * dy) || 1, cut = 15;
      el.setAttribute('x1', (a.x + (dx / len) * cut).toFixed(1)); el.setAttribute('y1', (a.y + (dy / len) * cut).toFixed(1));
      el.setAttribute('x2', (b.x - (dx / len) * cut).toFixed(1)); el.setAttribute('y2', (b.y - (dy / len) * cut).toFixed(1));
    });
  }

  function applyHighlight() {
    const svg = $('#graph');
    const any = S.hl.nodes.size > 0;
    svg.classList.toggle('has-hl', any && S.focus);
    Object.keys(S.nodeEls).forEach((id) => S.nodeEls[id].classList.toggle('hl', S.hl.nodes.has(id)));
    Object.keys(S.edgeEls).forEach((k) => S.edgeEls[k].classList.toggle('hl', S.hl.edges.has(k)));
    const labels = [];
    S.hl.edges.forEach((k) => {
      const [a, rel, b] = k.split('|');
      const pa = S.pos[a], pb = S.pos[b];
      if (pa && pb) labels.push(`<text class="edge-label" text-anchor="middle" x="${((pa.x + pb.x) / 2).toFixed(1)}" y="${((pa.y + pb.y) / 2).toFixed(1)}">${esc(rel)}</text>`);
    });
    $('#edge-labels').innerHTML = labels.join('');
  }

  function setHighlight(h) {
    S.hl = { nodes: new Set(h.nodes || []), edges: new Set((h.edges || []).map((e) => e.join('|'))) };
    applyHighlight();
    if (S.hl.nodes.size > 1) fitTo(Array.from(S.hl.nodes));
  }

  // ------------------------------------------------------------------ pan / zoom
  function applyView() { $('#viewport').setAttribute('transform', `translate(${S.view.x.toFixed(1)},${S.view.y.toFixed(1)}) scale(${S.view.k.toFixed(3)})`); }

  function fitTo(ids, maxK) {
    const pts = ids.map((i) => S.pos[i]).filter(Boolean);
    if (!pts.length) return;
    const r = $('#graph').getBoundingClientRect();
    const w = r.width || 800, h = r.height || 500, pad = 70;
    const minx = Math.min(...pts.map((p) => p.x)) - pad, maxx = Math.max(...pts.map((p) => p.x)) + pad;
    const miny = Math.min(...pts.map((p) => p.y)) - pad, maxy = Math.max(...pts.map((p) => p.y)) + pad;
    const k = clamp(Math.min(w / (maxx - minx), h / (maxy - miny)), 0.3, maxK || 1.6);
    S.view = { k, x: (w - (maxx - minx) * k) / 2 - minx * k, y: (h - (maxy - miny) * k) / 2 - miny * k };
    applyView();
  }
  function fitAll() { fitTo(Object.keys(S.pos), 1.2); }

  function centerOn(id) {
    const p = S.pos[id];
    if (!p) return;
    const r = $('#graph').getBoundingClientRect();
    const k = Math.max(S.view.k, 0.9);
    S.view = { k, x: r.width / 2 - p.x * k, y: r.height / 2 - p.y * k };
    applyView();
  }

  function initGraphEvents() {
    const svg = $('#graph');
    svg.addEventListener('wheel', (e) => {
      e.preventDefault();
      const r = svg.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
      const k = clamp(S.view.k * Math.exp(-e.deltaY * 0.0015), 0.25, 4);
      S.view.x = mx - (mx - S.view.x) * (k / S.view.k);
      S.view.y = my - (my - S.view.y) * (k / S.view.k);
      S.view.k = k;
      applyView();
    }, { passive: false });
    let pan = null, moved = false;
    svg.addEventListener('pointerdown', (e) => {
      if (e.target.closest('.node')) return;
      pan = { x: e.clientX, y: e.clientY, vx: S.view.x, vy: S.view.y };
      moved = false;
      svg.classList.add('panning');
    });
    window.addEventListener('pointermove', (e) => {
      if (!pan) return;
      if (Math.abs(e.clientX - pan.x) + Math.abs(e.clientY - pan.y) > 3) moved = true;
      S.view.x = pan.vx + (e.clientX - pan.x); S.view.y = pan.vy + (e.clientY - pan.y);
      applyView();
    });
    window.addEventListener('pointerup', () => { pan = null; svg.classList.remove('panning'); });
    svg.addEventListener('click', (e) => {
      const node = e.target.closest('.node');
      if (node) showNode(node.dataset.id);
      else if (!moved) $('#node-card').hidden = true;
    });
    svg.addEventListener('keydown', (e) => {
      const node = e.target.closest && e.target.closest('.node');
      if (node && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); showNode(node.dataset.id); }
    });
  }

  // ------------------------------------------------------------------ node card
  async function showNode(id) {
    const card = $('#node-card');
    const base = S.nodeMap[id] || { id, label: '', name: id };
    card.hidden = false;
    card.innerHTML = `<button class="close" aria-label="Close">x</button><h4>${esc(base.name)}</h4><div class="muted">${esc(base.label)} \u00b7 ${esc(id)}</div><p class="muted">Loading...</p>`;
    card.querySelector('.close').onclick = () => { card.hidden = true; };
    try {
      const d = await api(`/api/node?tenant=${S.tenant}&id=${encodeURIComponent(id)}`);
      const props = Object.entries(d.properties || {}).filter(([, v]) => v !== '' && v != null);
      const list = (items) => items.length ? '<ul>' + items.map((x) => `<li>${esc(x.rel)} ${x.id ? `<button class="cite" data-id="${esc(x.id)}">${esc(short(x.name || x.id, 28))}</button>` : ''}</li>`).join('') + '</ul>' : '<span class="muted">none</span>';
      card.innerHTML = `<button class="close" aria-label="Close">x</button><h4>${esc(base.name)}</h4><div class="muted">${esc(d.label || base.label)} \u00b7 ${esc(id)}</div>` +
        '<dl>' + props.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(short(v, 180))}</dd>`).join('') + '</dl>' +
        `<b>Points to</b>${list(d.out || [])}<b>Pointed to by</b>${list(d.in || [])}`;
      card.querySelector('.close').onclick = () => { card.hidden = true; };
    } catch (e) {
      card.querySelector('p').textContent = e.message;
    }
  }

  function focusNode(id) {
    if (!S.pos[id]) { toast('That item is not in the graph view yet.', true); return; }
    centerOn(id);
    const el = S.nodeEls[id];
    if (el) { el.classList.add('pulse'); setTimeout(() => el.classList.remove('pulse'), 1600); }
    showNode(id);
  }

  // ------------------------------------------------------------------ data loading
  async function loadGraph(keepPos) {
    const g = await api(`/api/graph?tenant=${S.tenant}`);
    S.nodes = g.nodes; S.edges = g.edges;
    S.nodeMap = {}; g.nodes.forEach((n) => { S.nodeMap[n.id] = n; });
    S.pos = layout(S.nodes, S.edges, keepPos ? S.pos : {});
    renderGraph();
    if (!keepPos) requestAnimationFrame(fitAll);
  }

  async function loadTasks() {
    const d = await api(`/api/tasks?tenant=${S.tenant}`);
    $('#badge-agents').textContent = d.stale.length;
    const card = $('#stale-card');
    if (d.stale.length) {
      card.className = 'stale-card';
      card.innerHTML = `<div class="big">${d.stale.length}</div><div><b>decision${d.stale.length > 1 ? 's' : ''} resting on outdated evidence</b></div>` +
        d.stale.map((s) => `<div class="stale-item"><button data-focus="${esc(s.id)}">${esc(s.title)}</button><div class="muted">Evidence ${citeHtml(s.doc)} was replaced${s.new ? ' by ' + citeHtml(s.new) : ''}. Status: ${esc(s.status.replace('_', ' '))}.</div></div>`).join('');
    } else {
      card.className = 'stale-card clean';
      card.innerHTML = '<b>All clear.</b> Every active decision rests on current evidence.';
    }
    $('#tasks').innerHTML = d.tasks.length ? d.tasks.map((t) => {
      const stage = t.stage;
      const steps = [['Analyst assesses', stage === 'assess' ? 'now' : 'done'], ['Archivist re-checks', stage === 'recheck' ? 'now' : (stage === 'done' ? 'done' : '')], ['Done', stage === 'done' ? 'done' : '']];
      const note = (t.note || '').split(' | ').map((x) => `<div class="muted small">${esc(x)}</div>`).join('');
      return `<div class="task"><div class="t">${esc(t.title)}</div><div class="steps">${steps.map(([l, c]) => `<span class="${c}">${l}</span>`).join('')}` +
        `${t.verdict ? `<span class="verdict ${esc(t.verdict)}">${esc(t.verdict.replace('_', ' '))}</span>` : ''}</div>${note}<div class="muted small">opened by ${esc(t.opened_by || 'analyst')} \u00b7 ${esc(t.id)}</div></div>`;
    }).join('') : '<p class="muted small">No tasks yet. Ingest a document or ask which decisions are stale.</p>';
  }

  async function loadMemory() {
    const m = await api(`/api/memory?tenant=${S.tenant}`);
    $('#mem-recent').innerHTML = m.recent.length ? m.recent.map((q) => `<li><button data-ask="${esc(q.text)}">${esc(short(q.text, 70))}</button> <span class="muted small">${esc(q.intent)}</span></li>`).join('') : '<li class="muted">Nothing asked yet.</li>';
    $('#mem-frequent').innerHTML = m.frequent.length ? m.frequent.map((d) => `<button data-focus="${esc(d.id)}">${esc(short(d.title, 34))} \u00b7 ${d.n}x</button>`).join('') : '<span class="muted small">Ask about a decision to see it here.</span>';
    $('#mem-playbooks').innerHTML = m.playbooks.map((p) => `<li><b>${esc(p.intent)}</b>: ${esc((p.steps || '').split(',').join(' \u2192 '))} <span class="muted small">used ${p.uses}x</span></li>`).join('');
  }

  async function loadChanges() {
    const d = await api(`/api/changes?tenant=${S.tenant}`);
    $('#badge-changes').textContent = d.changes.length;
    $('#changes').innerHTML = d.changes.length ? d.changes.map((c, i) => `<div class="cr"><header>${esc(c.title)}</header><pre>${esc(c.body)}</pre>` +
      `<footer><button class="btn small" data-download="${i}">Download .md</button> <button class="btn small ghost" data-focus="${esc(c.id)}">Show in graph</button></footer></div>`).join('') : '<p class="muted small">No change requests yet.</p>';
    S.changes = d.changes;
  }

  function refreshSide() {
    return Promise.all([loadTasks(), loadMemory(), loadChanges()]).catch((e) => toast(e.message, true));
  }

  // ------------------------------------------------------------------ answers
  function renderAnswer(r) {
    const empty = $('#answers-empty');
    if (empty) empty.remove();
    const el = document.createElement('article');
    el.className = 'answer';
    const tags = r.intents.map((i) => `<span class="tag t-${esc(i)}">${esc(i)}</span>`).join('');
    const pb = r.playbooks.map((p) => `${p.intent}: ${p.steps.join(' \u2192 ')}`).join('  |  ');
    const receipts = r.receipts.map((c, i) => {
      let params = JSON.stringify(c.params || {});
      if (params.length > 170) params = params.slice(0, 170) + '...';
      return `<div class="receipt-item"><div class="rn">${i + 1}. ${esc(c.name)}</div><div class="rm">${c.rows} rows \u00b7 ${c.ms} ms</div>` +
        `<pre class="code">${esc(c.cypher)}${params !== '{}' ? '\n// params ' + esc(params) : ''}</pre></div>`;
    }).join('');
    el.innerHTML = `<header>${esc(r.question)}</header>` +
      `<div class="meta">${tags}<span class="tag">${r.receipts.length} graph calls</span><span class="tag">${r.ms} ms</span><span class="tag">${esc(r.phrased_by)}</span></div>` +
      `<div class="body">${fmt(r.answer)}</div>` +
      (r.phrased_by !== 'graph facts' ? `<details><summary>Graph facts the answer is based on</summary><div class="body">${fmt(r.evidence)}</div></details>` : '') +
      `<details><summary>Playbook read from the graph: ${esc(pb || 'none')}</summary><div class="body muted small">Procedural memory: each intent has a (:Playbook) node whose steps the agent executes. Edit the node and the behaviour changes.</div></details>` +
      `<details><summary>Receipt: ${r.receipts.length} Cypher calls</summary>${receipts || '<p class="muted small">No graph calls.</p>'}</details>` +
      (r.plan ? '<div class="actions"><button class="btn small pink" data-open-changes="1">Open change request</button></div>' : '');
    $('#answers').prepend(el);
  }

  async function ask(question) {
    const input = $('#ask-input');
    const q = (question || input.value).trim();
    if (!q || S.busy) return;
    setBusy(true);
    try {
      const r = await api('/api/ask', { tenant: S.tenant, question: q });
      if (r.changed) await loadGraph(true);
      renderAnswer(r);
      setHighlight(r.highlight);
      input.value = '';
      refreshSide();
    } catch (e) {
      toast(e.message, true);
    } finally {
      setBusy(false);
    }
  }

  // ------------------------------------------------------------------ agents + ingest
  async function runAgents() {
    if (S.busy) return;
    setBusy(true);
    try {
      const r = await api('/api/agents/run', { tenant: S.tenant });
      $('#timeline').innerHTML = r.log.map((l, i) => `<div class="tl" style="animation-delay:${i * 0.25}s"><b class="a-${esc(l.agent)}">${esc(l.agent)}</b> ${esc(l.message)}</div>`).join('');
      await loadGraph(true);
      await refreshSide();
      toast('Agents finished the hand-off.');
    } catch (e) {
      toast(e.message, true);
    } finally {
      setBusy(false);
    }
  }

  async function ingest() {
    if (S.busy) return;
    const text = $('#ingest-text').value;
    setBusy(true);
    try {
      const r = await api('/api/ingest', { tenant: S.tenant, text });
      await loadGraph(true);
      setHighlight(r.highlight);
      const out = $('#ingest-result');
      out.className = 'result' + (r.ignored.length ? ' warn' : '');
      out.innerHTML = `<b>Archivist ingested</b> ${citeHtml(r.document.id)} <span class="muted small">(extractor: ${esc(r.extractor)})</span><br>` +
        (r.replaced ? `Marked ${citeHtml(r.replaced)} as <b>outdated</b>.<br>` : '') +
        (r.decisions.length ? 'Decisions: ' + r.decisions.map((d) => citeHtml(d.id)).join(' ') + '<br>' : '') +
        (r.tasks.length ? `<b>${r.tasks.length} decision(s) became stale</b>; task(s) opened for the Analyst: ${r.tasks.map((t) => citeHtml(t.decision)).join(' ')}.<br>` : 'No decision became stale.<br>') +
        (r.ignored.length ? `<span class="muted small">Ignored (not found in the graph): ${esc(r.ignored.join('; '))}</span><br>` : '') +
        (r.tasks.length ? '<button class="btn small" data-goto="agents">Go to Agents</button>' : '');
      refreshSide();
      toast('Document ingested.');
    } catch (e) {
      toast(e.message, true);
    } finally {
      setBusy(false);
    }
  }

  // ------------------------------------------------------------------ tenants + chrome
  function selectTab(name) {
    $$('.tab').forEach((t) => { const on = t.dataset.tab === name; t.classList.toggle('on', on); t.setAttribute('aria-selected', on ? 'true' : 'false'); });
    $$('.tabpane').forEach((p) => { const on = p.id === 'pane-' + name; p.classList.toggle('on', on); p.hidden = !on; });
  }

  function renderTenants() {
    const wrap = $('#tenants');
    wrap.innerHTML = S.health.tenants.map((t) => `<button role="tab" data-tenant="${esc(t.id)}" aria-selected="${t.id === S.tenant}" title="${esc(t.blurb)}">${esc(t.name)}</button>`).join('');
  }

  function renderTenantUi() {
    const t = S.health.tenants.find((x) => x.id === S.tenant);
    $('#chip-graph').textContent = 'graph: ' + t.graph;
    $('#examples').innerHTML = (t.examples || []).map((q) => `<button data-ask="${esc(q)}">${esc(q)}</button>`).join('');
    $('#ingest-text').value = '';
    $('#ingest-result').innerHTML = '';
    $('#ingest-result').className = '';
    $('#timeline').innerHTML = '';
    $('#answers').innerHTML = '<div class="empty" id="answers-empty"><div class="empty-title">Every answer comes with a receipt.</div><p>Pick an example above. The path the agent walked lights up in the graph, each claim carries a source tag, and the Cypher behind it is one click away.</p></div>';
    $('#node-card').hidden = true;
    S.hl = { nodes: new Set(), edges: new Set() };
  }

  async function switchTenant(id) {
    S.tenant = id;
    renderTenants();
    renderTenantUi();
    try {
      await loadGraph(false);
      await refreshSide();
    } catch (e) { toast(e.message, true); }
  }

  async function resetDemo() {
    if (!window.confirm('Reload the synthetic seed data for this team? Questions, tasks and change requests will be cleared.')) return;
    setBusy(true);
    try {
      await api('/api/reset', { tenant: S.tenant });
      await switchTenant(S.tenant);
      toast('Demo data reloaded.');
    } catch (e) { toast(e.message, true); } finally { setBusy(false); }
  }

  function downloadChange(i) {
    const c = (S.changes || [])[i];
    if (!c) return;
    const blob = new Blob([c.body], { type: 'text/markdown' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = c.id + '.md';
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  function initEvents() {
    $('#ask-form').addEventListener('submit', (e) => { e.preventDefault(); ask(); });
    $('#btn-run').addEventListener('click', runAgents);
    $('#btn-ingest').addEventListener('click', ingest);
    $('#btn-reset').addEventListener('click', resetDemo);
    $('#btn-fit').addEventListener('click', fitAll);
    $('#btn-clear').addEventListener('click', () => { S.hl = { nodes: new Set(), edges: new Set() }; applyHighlight(); });
    $('#btn-focus').addEventListener('click', (e) => {
      S.focus = !S.focus;
      e.currentTarget.setAttribute('aria-pressed', S.focus ? 'true' : 'false');
      applyHighlight();
    });
    $('#btn-sample').addEventListener('click', () => {
      const t = S.health.tenants.find((x) => x.id === S.tenant);
      $('#ingest-text').value = t.sample_document || '';
    });
    $$('.tab').forEach((t) => t.addEventListener('click', () => selectTab(t.dataset.tab)));
    document.addEventListener('click', (e) => {
      const t = e.target.closest('button');
      if (!t) return;
      if (t.dataset.tenant) switchTenant(t.dataset.tenant);
      else if (t.dataset.ask) { $('#ask-input').value = t.dataset.ask; ask(t.dataset.ask); }
      else if (t.classList.contains('cite') && t.dataset.id) focusNode(t.dataset.id);
      else if (t.dataset.focus) focusNode(t.dataset.focus);
      else if (t.dataset.openChanges) selectTab('changes');
      else if (t.dataset.goto) selectTab(t.dataset.goto);
      else if (t.dataset.download) downloadChange(Number(t.dataset.download));
    });
    initGraphEvents();
  }

  async function init() {
    initEvents();
    try {
      S.health = await api('/api/health');
    } catch (e) {
      S.health = { falkordb: false, error: e.message, tenants: [], llm: { mode: 'offline' } };
    }
    const dbChip = $('#chip-db');
    dbChip.classList.toggle('ok', !!S.health.falkordb);
    $('#chip-llm').textContent = S.health.llm.mode === 'llm' ? 'answers phrased by ' + S.health.llm.model : 'offline mode: graph facts only';
    if (!S.health.falkordb || !S.health.tenants.length) {
      const b = $('#banner');
      b.hidden = false;
      b.innerHTML = 'FalkorDB is not reachable. Start it with <code>docker compose up -d</code>, then reload this page.' + (S.health.error ? ' (' + esc(S.health.error) + ')' : '');
      return;
    }
    renderTenants();
    await switchTenant(S.health.tenants[0].id);
    window.addEventListener('resize', () => { if (!S.hl.nodes.size) fitAll(); });
  }

  document.addEventListener('DOMContentLoaded', init);
  if (typeof module !== 'undefined') module.exports = { layout, hash, inline, fmt };
})();
