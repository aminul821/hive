const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
})[c]);

// Simple API helpers with graceful fallback
const API = {
  async fetchDatabase() {
    try {
      const res = await fetch('/api/database', { cache: 'no-store' });
      if (!res.ok) throw new Error('api database failed');
      return await res.json();
    } catch (e) {
      return null;
    }
  },
  async getBottle(token) {
    try {
      const res = await fetch('/api/bottles/' + encodeURIComponent(token));
      if (!res.ok) return null;
      return await res.json();
    } catch (e) {
      return null;
    }
  },
  async verify(token, code) {
    try {
      const res = await fetch('/api/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, code }),
      });
      if (!res.ok) return { error: 'request_failed', status: res.status };
      return await res.json();
    } catch (e) {
      return { error: 'network' };
    }
  },
};

let page = 'dashboard';
let role = localStorage.getItem('hivetrust_role') || 'owner';
const ROLE_PAGES = {
  owner: ['dashboard', 'hives', 'batches', 'harvest', 'alerts', 'ledger', 'verify', 'auth', 'iot', 'about'],
  auditor: ['dashboard', 'harvest', 'alerts', 'ledger', 'verify', 'auth', 'iot', 'about'],
  consumer: ['verify', 'auth', 'about'],
};

// Default demo state (fallback when API is unavailable)
const DB_KEY = 'hivetrust_local_db_v7';
const defaultDB = {
  bottles: [
    { token: 'HTV-7KX92P4', code: 'X7K9-P4M2', batch: 'HC-DEMO-001', harvest: 'HI-DEMO-001', hive: 'H001', product: 'Assam Forest Honey', origin: 'Assam', harvestDate: '02 Sep 2026', moisture: 17.2, status: 'ACTIVE', scans: 1, lastScan: '02 Sep 2026, 20:10', verificationEvents: [{ time: '02 Sep 2026, 20:10', result: 'AUTHENTIC_FIRST_SCAN', session: 'S-DEMO-001', note: 'First detailed verification recorded' }] },
    { token: 'HTV-3M8Q1Z7', code: 'R4T2-N8K6', batch: 'HC-DEMO-002', harvest: 'HI-DEMO-002', hive: 'H003', product: 'North Bengal Wildflower Honey', origin: 'North Bengal', harvestDate: '28 Aug 2026', moisture: 18.1, status: 'ACTIVE', scans: 4, lastScan: '02 Sep 2026, 20:18', verificationEvents: [{ time: '01 Sep 2026, 10:02', result: 'AUTHENTIC', session: 'S-DEMO-014', note: 'Normal verification' }, { time: '01 Sep 2026, 12:21', result: 'AUTHENTIC', session: 'S-DEMO-019', note: 'Normal verification' }, { time: '02 Sep 2026, 20:17', result: 'SUSPICIOUS_REUSE', session: 'S-DEMO-041', note: 'Code reused unusually quickly' }, { time: '02 Sep 2026, 20:18', result: 'POSSIBLE_CLONE', session: 'S-DEMO-042', note: 'Repeated credential reuse flagged' }] },
  ],
  gateways: [
    { id: 'HT-GW-001', apiary: 'Assam North Apiary', backhaul: '4G/LTE', network: 'LoRaWAN', status: 'ONLINE', battery: 78, signal: 'Good', lastSeen: '02 Sep 2026, 20:20', hives: 4 },
    { id: 'HT-GW-002', apiary: 'North Bengal Field', backhaul: '4G/LTE', network: 'LoRaWAN', status: 'ONLINE', battery: 64, signal: 'Fair', lastSeen: '02 Sep 2026, 20:15', hives: 3 },
  ],
  devices: [
    { id: 'HT-HIVE-001', hive: 'H001', gateway: 'HT-GW-001', status: 'ONLINE', lastReading: '02 Sep 2026, 20:15', battery: 82 },
    { id: 'HT-HIVE-002', hive: 'H002', gateway: 'HT-GW-001', status: 'ONLINE', lastReading: '02 Sep 2026, 20:15', battery: 74 },
    { id: 'HT-HIVE-003', hive: 'H003', gateway: 'HT-GW-002', status: 'ONLINE', lastReading: '02 Sep 2026, 20:15', battery: 67 },
  ],
};

let localDB = null; // will be initialized during init()

function saveDB() {
  try {
    localStorage.setItem(DB_KEY, JSON.stringify(localDB));
  } catch (e) {
    console.warn('Failed to save local DB', e);
  }
}

function tokenFromURL() {
  const q = new URLSearchParams(location.search);
  return q.get('v') || q.get('verify') || (location.pathname.match(/\/v\/([^/]+)/) || [])[1] || '';
}

function bottleByToken(t) {
  if (!localDB || !localDB.bottles) return null;
  return localDB.bottles.find((b) => b.token === t);
}

function recordScan(b, result, note = '') {
  const session = 'S-' + Math.random().toString(36).slice(2, 10).toUpperCase();
  b.scans = (b.scans || 0) + 1;
  b.lastScan = new Date().toLocaleString();
  b.verificationEvents = b.verificationEvents || [];
  b.verificationEvents.push({ time: b.lastScan, result, session, note });
  saveDB();
  addBlock('BOTTLE_VERIFICATION', { token: b.token, result, session, scan_count: b.scans, note });
  return session;
}

function resetLocalDemo() {
  localDB = JSON.parse(JSON.stringify(defaultDB));
  saveDB();
  render();
}

function openBottleToken(token) {
  page = 'auth';
  render();
  if ($('#publicToken')) { $('#publicToken').value = token; showBottlePreview(); }
}

async function auth() {
  const urlToken = tokenFromURL();
  $('#content').innerHTML = `<div class="hero"><div><div class="eyebrow" style="color:#9bc8ad">BOTTLE-LEVEL TRUST</div><h2>Scan → Preview → Open the lid → Unlock the detailed report.</h2><p>The QR is a public deep-link. The second credential is a physical code placed inside/under the lid. Repeated or abnormal verification attempts are flagged.</p></div><div style="font-size:70px">🔐🍯</div></div>
  <div class="split section">
  <div class="verify-card"><div class="eyebrow">STEP 1 · PUBLIC PREVIEW</div><h2>Product information</h2><p class="muted">Basic information is available before purchase. No secret is consumed here.</p><div class="actions"><input id="publicToken" class="input" style="min-width:260px" placeholder="Bottle token" value="${esc(urlToken)}"><button class="btn" onclick="showBottlePreview()">Open Preview</button></div><div id="publicPreview" class="section"></div></div>
  <div class="verify-card"><div class="eyebrow">STEP 2 · AFTER PURCHASE</div><div class="lock">🔒</div><h2>Unlock detailed report</h2><p class="muted">Open the lid and enter the hidden physical verification code. The code is not contained in the public QR URL.</p><div class="actions"><input id="privateCode" class="input" placeholder="e.g. X7K9-P4M2"><button class="btn" onclick="unlockBottle()">Verify Code</button></div><div id="privateResult" class="section"></div></div></div>
  <div id="authReport" class="section"></div>
  <div class="section card"><div class="section-head"><h2>🛡️ Anti-cloning logic</h2><span class="pill">Demo</span></div><div class="kpi-grid">
  ${card('QR token','Public','Safe to preview')}${card('Lid code','Private','Physical credential')}${card('Session ID','Ephemeral','Per verification')}${card('Scan history','Recorded','Anomaly signal')}${card('Blockchain','Linked','Verification event')}
  </div><div class="warn-strip" style="margin-top:14px"><b>Production note:</b> In this static demo the JSON/localStorage database is browser-side. A real deployment must keep the lid secret server-side and validate it through an API.</div></div>`;
  if (urlToken) await showBottlePreview();
}

async function showBottlePreview() {
  const t = $('#publicToken')?.value.trim();
  const box = $('#publicPreview');
  if (!box) return;
  if (!t) { box.innerHTML = '<div class="dangerbox"><b>Enter a bottle token to preview.</b></div>'; return; }

  // Try server API first
  const serverBottle = await API.getBottle(t);
  if (serverBottle) {
    box.innerHTML = `<div class="success"><b>✓ HiveTrust product identity found</b></div><div class="grid" style="margin-top:10px">${card('Product', serverBottle.product, 'Basic information')}${card('Origin', serverBottle.origin, 'Public')}${card('Batch', serverBottle.batch, 'Public')}${card('Harvest', serverBottle.harvestDate || serverBottle.harvest, 'Public')}</div><div class="token" style="margin-top:10px">Official deep-link: ${location.origin}${location.pathname}?v=${encodeURIComponent(serverBottle.token)}</div><p class="muted">The detailed report and lid code remain hidden.</p>`;
    return;
  }

  // Fallback to local DB
  const b = bottleByToken(t);
  if (!b) { box.innerHTML = '<div class="dangerbox"><b>Unknown bottle token.</b><br>This public identity is not registered in the local demo database.</div>'; return; }
  box.innerHTML = `<div class="success"><b>✓ HiveTrust product identity found</b></div><div class="grid" style="margin-top:10px">${card('Product', b.product, 'Basic information')}${card('Origin', b.origin, 'Public')}${card('Batch', b.batch, 'Public')}${card('Harvest', b.harvestDate || b.harvest, 'Public')}</div><div class="token" style="margin-top:10px">Official deep-link: ${location.origin}${location.pathname}?v=${encodeURIComponent(b.token)}</div><p class="muted">The detailed report and lid code remain hidden.</p>`;
}

async function unlockBottle() {
  const t = $('#publicToken')?.value.trim();
  const c = ($('#privateCode')?.value || '').trim().toUpperCase();
  const box = $('#privateResult');
  const report = $('#authReport');
  if (!t) { box.innerHTML = '<div class="dangerbox">Verify a valid public bottle token first.</div>'; return; }

  // Try server verify API
  const apiResp = await API.verify(t, c);
  if (apiResp && !apiResp.error) {
    // RecordScan already done server-side; reflect server state in localDB if possible
    if (apiResp.bottle) {
      // Merge server bottle into localDB (keep local code if present)
      const idx = (localDB.bottles || []).findIndex(x => x.token === apiResp.bottle.token);
      if (idx >= 0) {
        localDB.bottles[idx] = { ...localDB.bottles[idx], ...apiResp.bottle };
      } else {
        localDB.bottles = localDB.bottles || [];
        localDB.bottles.push(apiResp.bottle);
      }
      saveDB();
    }

    const result = apiResp.result;
    const session = apiResp.session;
    const note = apiResp.note || '';
    box.innerHTML = `<div class="${result === 'AUTHENTIC' ? 'success' : result === 'POSSIBLE_CLONE' ? 'dangerbox' : 'dangerbox'}"><b>${result === 'AUTHENTIC' ? '🟢 Physical verification successful' : result === 'POSSIBLE_CLONE' ? '🔴 Possible cloned packaging' : '🔴 Detailed verification result'}</b><br>${result === 'AUTHENTIC' ? 'The hidden physical credential matches this bottle identity.' : 'The credential is valid, but the verification history is unusually repetitive. Inspect the physical packaging.'}<br><span class="mini">Session: ${session}</span></div>`;

    if (apiResp.bottle) {
      const b = apiResp.bottle;
      report.innerHTML = `<div class="card"><div class="section-head"><h2>🍯 Detailed Honey Passport</h2><span class="badge ${result === 'AUTHENTIC' ? 'low' : 'high'}">${result}</span></div><div class="grid">${card('Bottle ID', b.token, 'Unique bottle identity')}${card('Batch', b.batch, 'Traceability')}${card('Source Hive', b.hive, 'Origin')}${card('Harvest', b.harvest || b.harvestDate, 'Blockchain-linked event')}${card('Moisture', (b.moisture||'') + '%', 'Recorded quality')}${card('Verification count', b.scans || 0, 'Historical signal')}</div><div class="success section">✓ Bottle identity registered<br>✓ Hidden physical credential matched<br>✓ Harvest provenance linked<br>✓ Verification event written to the demo ledger</div><div class="section"><h3>Verification history</h3><div class="timeline">${(b.verificationEvents || []).slice().reverse().map(e=>`<div><span class="dot"></span><b>${esc(e.result)}</b> · ${esc(e.time)}<br><span class="muted">${esc(e.note||'')}</span><br><span class="hash">Session ${esc(e.session)}</span></div>`).join('')}</div></div></div>`;
    }
    return;
  }

  // Fallback local verification if API failed/unavailable
  const b = bottleByToken(t);
  if (!b) { box.innerHTML = '<div class="dangerbox">Verify a valid public bottle token first.</div>'; return; }
  if (c !== (b.code || '').toUpperCase()) {
    const s = recordScan(b, 'FAILED_CODE', 'Incorrect hidden code');
    box.innerHTML = `<div class="dangerbox"><b>🔴 Detailed verification failed.</b><br>The public QR may be genuine, but the physical verification code did not match.<br><span class="mini">Session: ${s}</span></div>`;
    return;
  }
  const recent = (b.verificationEvents || []).slice(-5);
  const suspicious = recent.filter(x => x.result === 'AUTHENTIC' || x.result === 'AUTHENTIC_FIRST_SCAN').length >= 2 || (b.scans || 0) >= 4;
  const result = suspicious ? 'POSSIBLE_CLONE' : 'AUTHENTIC';
  const session = recordScan(b, result, suspicious ? 'Repeated credential use flagged' : 'Valid physical credential');
  box.innerHTML = `<div class="${result === 'AUTHENTIC' ? 'success' : 'dangerbox'}"><b>${result === 'AUTHENTIC' ? '🟢 Physical verification successful' : '🔴 Possible cloned packaging'}</b><br>${result === 'AUTHENTIC' ? 'The hidden physical credential matches this bottle identity.' : 'The credential is valid, but the verification history is unusually repetitive. Inspect the physical packaging.'}<br><span class="mini">Session: ${session}</span></div>`;
  report.innerHTML = `<div class="card"><div class="section-head"><h2>🍯 Detailed Honey Passport</h2><span class="badge ${result === 'AUTHENTIC' ? 'low' : 'high'}">${result}</span></div><div class="grid">${card('Bottle ID', b.token, 'Unique bottle identity')}${card('Batch', b.batch, 'Traceability')}${card('Source Hive', b.hive, 'Origin')}${card('Harvest', b.harvest || b.harvestDate, 'Blockchain-linked event')}${card('Moisture', (b.moisture||'') + '%', 'Recorded quality')}${card('Verification count', b.scans || 0, 'Historical signal')}</div><div class="success section">✓ Bottle identity registered<br>✓ Hidden physical credential matched<br>✓ Harvest provenance linked<br>✓ Verification event written to the demo ledger</div><div class="section"><h3>Verification history</h3><div class="timeline">${(b.verificationEvents || []).slice().reverse().map(e=>`<div><span class="dot"></span><b>${esc(e.result)}</b> · ${esc(e.time)}<br><span class="muted">${esc(e.note||'')}</span><br><span class="hash">Session ${esc(e.session)}</span></div>`).join('')}</div></div></div>`;
}

// The rest of the client script (harvest, ledger, render, etc.) remains unchanged
// For brevity we won't duplicate the entire script here; the production repo keeps the existing demo logic

// ----- initialization: try server DB, fallback to localStorage -----
async function init() {
  if ($('#roleSel')) $('#roleSel').value = role;
  if (!ROLE_PAGES[role].includes(page)) page = ROLE_PAGES[role][0];

  const serverDB = await API.fetchDatabase();
  if (serverDB) {
    localDB = serverDB;
    // keep client-side records (harvests etc.) in localStorage separate from server demo DB
    try { localStorage.setItem(DB_KEY, JSON.stringify(localDB)); } catch (e) {}
  } else {
    // fallback to any saved local DB or default
    localDB = JSON.parse(localStorage.getItem(DB_KEY) || 'null') || JSON.parse(JSON.stringify(defaultDB));
  }

  applyRole();
  render();
}

// Call the (async) initializer
init();
