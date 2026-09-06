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


const state={hives:[
{id:"H001",location:"Assam",t:33.2,h:61,w:48.2,a:86},{id:"H002",location:"Muzaffarpur",t:36.8,h:72,w:42.5,a:58},{id:"H003",location:"North Bengal",t:31.5,h:55,w:51,a:91},{id:"H004",location:"Bihar",t:34,h:65,w:45.8,a:76}],batches:[],blocks:[],audits:[]};
function predictor(x){let s=100,r=[];if(x.t<30||x.t>36){s-=18;r.push("temperature outside preferred range")}if(x.h<45||x.h>75){s-=15;r.push("humidity unusual")}if(x.a<55){s-=22;r.push("bee activity low")}if(x.w<35){s-=15;r.push("hive weight low")}s=Math.max(0,Math.min(100,s));let risk=s>=80?"Low":s>=60?"Medium":"High";let base=Math.max(2,(x.w-30)*.65+x.a*.025);return{score:s,risk,ymin:(base*(.82+s/500)).toFixed(1),ymax:(base*(1.05+s/400)).toFixed(1),reason:r.join("; ")||"all monitored parameters are within demo baseline"}}
function hash(str){let h=2166136261;for(let i=0;i<str.length;i++){h^=str.charCodeAt(i);h=Math.imul(h,16777619)}return("00000000"+(h>>>0).toString(16)).slice(-8).repeat(8)}
function addBlock(type,payload){let prev=state.blocks.length?state.blocks[state.blocks.length-1].hash:"0".repeat(64);let raw=type+JSON.stringify(payload)+prev;let h=hash(raw);state.blocks.push({idx:state.blocks.length+1,ts:new Date().toLocaleString(),type,payload,prev,hash:h});}
function validChain(){let prev="0".repeat(64);for(const b of state.blocks){if(b.prev!==prev)return{ok:false,bad:b.idx};if(b.hash!==hash(b.type+JSON.stringify(b.payload)+b.prev))return{ok:false,bad:b.idx};prev=b.hash}return{ok:true}}
addBlock("GENESIS",{message:"HiveTrust demo ledger initialized"});
function card(t,v,s,c=""){return`<div class="card"><div class="muted">${t}</div><div class="metric ${c}">${v}</div><div class="muted">${s}</div></div>`}

/* ---------- Roles ---------- */
function applyRole(){document.querySelectorAll(".nav").forEach(b=>{b.style.display=ROLE_PAGES[role].includes(b.dataset.page)?"":"none"})}
function setRole(v){role=v;localStorage.setItem("hivetrust_role",v);if(!ROLE_PAGES[role].includes(page))page=ROLE_PAGES[role][0];applyRole();render()}

/* ---------- Harvest Integrity ---------- */
let harvestRecords=JSON.parse(localStorage.getItem("hivetrust_harvest_records")||"[]");
function saveHarvest(){localStorage.setItem("hivetrust_harvest_records",JSON.stringify(harvestRecords))}
function hiveMismatchCounts(){const c={};harvestRecords.filter(r=>r.status==="MISMATCH").forEach(r=>{(r.hives||[{hive:r.hive}]).forEach(h=>{c[h.hive]=(c[h.hive]||0)+1})});return c}

let harvestRows=[];
function freshHarvestRows(){const h=state.hives[0];harvestRows=[{hive:h.id,before:h.w,after:+(Math.max(1,h.w-8)).toFixed(1)}]}
function hrowHtml(row,i){return `<div class="hrow" data-i="${i}">
<div><label class="muted">Hive</label><select class="input hhive" oninput="updateExpected()">${state.hives.map(x=>`<option value="${x.id}" ${x.id===row.hive?"selected":""}>${x.id} — ${x.location}</option>`).join("")}</select></div>
<div><label class="muted">Pre-harvest (kg)</label><input class="input hbefore" type="number" step="0.1" value="${row.before}" oninput="updateExpected()"></div>
<div><label class="muted">Post-harvest (kg)</label><input class="input hafter" type="number" step="0.1" value="${row.after}" oninput="updateExpected()"></div>
<div>${harvestRows.length>1?`<button class="btn secondary" onclick="removeHarvestRow(${i})">✕</button>`:""}</div>
</div>`}
function syncHarvestRows(){const els=[...document.querySelectorAll(".hrow")];if(els.length)harvestRows=els.map(el=>({hive:el.querySelector(".hhive").value,before:+el.querySelector(".hbefore").value||0,after:+el.querySelector(".hafter").value||0}))}
function addHarvestRow(){syncHarvestRows();const h=state.hives[harvestRows.length%state.hives.length];harvestRows.push({hive:h.id,before:h.w,after:+(Math.max(1,h.w-8)).toFixed(1)});renderHarvestPage()}
function removeHarvestRow(i){syncHarvestRows();if(harvestRows.length>1){harvestRows.splice(i,1);renderHarvestPage()}}

function harvest(){freshHarvestRows();renderHarvestPage()}
function renderHarvestPage(){
$("#content").innerHTML=`<div class="hero"><div><div class="eyebrow" style="color:#9bc8ad">HARVEST INTEGRITY ENGINE</div><h2>Verify every kilogram from hive to honey batch.</h2><p>Compare pre/post hive weight with extracted honey — supports combining several hives into one harvest event — then record the verification on the blockchain demo ledger.</p></div><div style="font-size:70px">⚖️🍯</div></div>
<div class="section card"><div class="section-head"><h2>⚖️ New Harvest Verification</h2><span class="pill">Blockchain-linked</span></div>
<div id="hrows">${harvestRows.map((row,i)=>hrowHtml(row,i)).join("")}</div>
<button class="btn secondary" onclick="addHarvestRow()">+ Add Another Hive</button>
<div class="harvest-grid" style="margin-top:16px">
<div><label class="muted">Extracted honey (kg)</label><input id="extracted" class="input" type="number" step="0.1" value="8.0" oninput="updateExpected()"></div>
<div><label class="muted">Recorded batch quantity (kg)</label><input id="recorded" class="input" type="number" step="0.1" value="8.0"></div>
<div><label class="muted">Moisture content (%)</label><input id="moisture" class="input" type="number" step="0.5" value="18" oninput="updateExpected()"></div>
</div>
<div style="margin-top:12px"><button class="btn" onclick="verifyHarvest()">Verify & Add to Blockchain</button></div>
<div class="notice section" id="expectedBox" style="margin-top:12px"></div>
<p class="muted">Demo tolerance scales with hives combined (±0.5 kg per hive, +0.3 kg if moisture &gt;20%). Real deployment requires calibrated load cells and controlled weighing.</p></div>
<div id="harvestResult"></div>
<div class="section card"><div class="section-head"><h2>📜 Harvest Verification History</h2><div class="actions"><span class="muted">${harvestRecords.length} events</span><button class="btn secondary" onclick="exportHarvestCSV()">⬇ Export CSV</button><button class="btn secondary" onclick="window.print()">🖨 Print / PDF</button></div></div>${harvestRecords.length?harvestRecords.slice().reverse().map(harvestCard).join(""):"<div class='muted'>No harvest events yet.</div>"}</div>`;
updateExpected();
}
function updateExpected(){
syncHarvestRows();
const totalBefore=harvestRows.reduce((a,r)=>a+r.before,0),totalAfter=harvestRows.reduce((a,r)=>a+r.after,0);
const exp=Math.max(0,+(totalBefore-totalAfter).toFixed(2));
const ex=+($("#extracted")?.value)||0,moisture=+($("#moisture")?.value)||18;
const diff=+(ex-exp).toFixed(2);
const note=moisture>20?` High moisture (${moisture}%) means some natural weight loss during ripening/settling is expected.`:"";
$("#expectedBox").innerHTML=`⚖️ <b>Expected honey (combined ${harvestRows.length} hive${harvestRows.length>1?"s":""}):</b> ${exp.toFixed(1)} kg (Total pre ${totalBefore.toFixed(1)} − Total post ${totalAfter.toFixed(1)}). You entered <b>${ex.toFixed(1)} kg</b> as extracted — difference: <b>${diff>=0?"+":""}${diff.toFixed(1)} kg</b>.${note}`;
}
function explainMismatch(exp,extracted,recorded,tol,moisture){
const reasons=[];
const dWeightExtract=+(extracted-exp).toFixed(2);
if(Math.abs(dWeightExtract)>tol){
 if(dWeightExtract<0){
  reasons.push("Extracted honey is LESS than the combined hive weight loss — honey may have been left behind in frames/extractor, spilled during extraction, or extraction is incomplete.");
  reasons.push("Post-harvest weight may have been taken too early, before wax cappings/frames were fully removed.");
  if(moisture>20)reasons.push(`Moisture content is high (${moisture}%) — part of this gap can be normal evaporation/ripening loss, not necessarily an error. Re-check after settling.`);
  else reasons.push("Scale calibration or reading error at pre/post weighing is also possible.");
 }else{
  reasons.push("Extracted honey is MORE than the combined hive weight loss — wax cappings, frame residue, or water may have been weighed along with the honey.");
  reasons.push("Pre-harvest weight for one or more hives may have been recorded too low.");
  reasons.push("Worth a physical re-check of the listed hives — possible tampering or incorrect entry.");
 }
}
if(Math.abs(+(extracted-recorded).toFixed(2))>tol){
 if(recorded<extracted){
  reasons.push("Recorded batch quantity is LESS than honey actually extracted — possible spillage/loss during transfer, a transcription mistake, or diversion before batching (theft/pilferage risk).");
 }else{
  reasons.push("Recorded batch quantity is MORE than honey actually extracted — check for a data-entry error or honey from another harvest mixed into this record.");
 }
}
return reasons;
}
function harvestCard(r){
const hs=r.hives||[{hive:r.hive,before:r.before,after:r.after,drop:r.drop}];
return `<div class="event"><div class="section-head"><b>${r.id} · ${hs.map(h=>h.hive).join(" + ")}</b><span class="badge ${r.status==="MATCH"?"low":"high"}">${r.status}</span></div><div class="grid"><div><div class="muted">Expected (from weight)</div><b>${r.drop.toFixed(1)} kg</b></div><div><div class="muted">Extracted</div><b>${r.extracted.toFixed(1)} kg</b></div><div><div class="muted">Batch record</div><b>${r.recorded.toFixed(1)} kg</b></div><div><div class="muted">Moisture</div><b>${r.moisture!=null?r.moisture+"%":"—"}</b></div></div><p class="muted">${esc(r.explanation)}</p>${(r.reasons&&r.reasons.length)?`<ul style="margin:6px 0 0 18px;padding:0;color:#8d2e2e;font-size:13px">${r.reasons.map(x=>`<li style="margin:3px 0">${esc(x)}</li>`).join("")}</ul>`:""}<div class="hash">Blockchain verification hash: ${r.blockHash}</div><div style="margin-top:8px"><button class="btn secondary" onclick="openHarvestVerify('${r.id}')">🔍 Consumer Link (${r.id})</button></div></div>`}
function verifyHarvest(){
syncHarvestRows();
for(const row of harvestRows){if(row.before<0||row.after<0||row.after>row.before){$("#harvestResult").innerHTML=`<div class="dangerbox section"><b>Invalid measurement for ${esc(row.hive)}.</b><br>Post-harvest weight cannot exceed pre-harvest weight.</div>`;return}}
const extracted=+$("#extracted").value||0,recorded=+$("#recorded").value||0,moisture=+$("#moisture").value||18;
if(extracted<0||recorded<0){$("#harvestResult").innerHTML='<div class="dangerbox section"><b>Invalid measurement.</b></div>';return}
const drop=+harvestRows.reduce((a,r)=>a+(r.before-r.after),0).toFixed(2);
const tol=+(0.5*harvestRows.length+(moisture>20?0.3:0)).toFixed(2);
const wm=Math.abs(drop-extracted)<=tol,rm=Math.abs(extracted-recorded)<=tol,status=wm&&rm?"MATCH":"MISMATCH";
const reasons=status==="MISMATCH"?explainMismatch(drop,extracted,recorded,tol,moisture):[];
const hivesInfo=harvestRows.map(row=>({hive:row.hive,before:row.before,after:row.after,drop:+(row.before-row.after).toFixed(2)}));
const explanation=status==="MATCH"?`Combined weight reduction (${drop.toFixed(1)} kg across ${harvestRows.length} hive${harvestRows.length>1?"s":""}) matches extracted honey (${extracted.toFixed(1)} kg), and the batch record (${recorded.toFixed(1)} kg) is within tolerance.`:`Combined weight reduction (${drop.toFixed(1)} kg), extracted honey (${extracted.toFixed(1)} kg) and batch record (${recorded.toFixed(1)} kg) do not agree.`;
const r={id:"HI-"+Date.now().toString().slice(-8),hives:hivesInfo,hive:hivesInfo.map(h=>h.hive).join(" + "),before:hivesInfo.reduce((a,x)=>a+x.before,0),after:hivesInfo.reduce((a,x)=>a+x.after,0),drop,extracted,recorded,moisture,status,explanation,reasons,time:new Date().toLocaleString(),blockHash:""};
r.blockHash=hash(JSON.stringify(r));harvestRecords.push(r);saveHarvest();
addBlock("HARVEST_VERIFICATION",{harvest_id:r.id,hives:hivesInfo,weight_drop_kg:drop,extracted_kg:extracted,recorded_batch_kg:recorded,moisture_pct:moisture,status,tolerance_kg:tol,verification_hash:r.blockHash});
const resultHtml=`<div class="${status==="MATCH"?"success":"dangerbox"} section"><h2>${status==="MATCH"?"🟢 HARVEST VERIFIED":"🔴 WEIGHT ERROR — HARVEST MISMATCH"}</h2><p>${esc(explanation)}</p>
${reasons.length?`<div class="dangerbox" style="margin:10px 0"><b>Likely reason(s) — show this to the hive owner:</b><ul style="margin:8px 0 0 18px;padding:0">${reasons.map(x=>`<li style="margin:4px 0">${esc(x)}</li>`).join("")}</ul></div>`:""}
<div class="calc">Hives: ${hivesInfo.map(h=>`${h.hive} (${h.drop.toFixed(1)} kg)`).join(", ")}
Expected honey (from weight loss): ${drop.toFixed(1)} kg
Actually extracted: ${extracted.toFixed(1)} kg
Recorded batch: ${recorded.toFixed(1)} kg
Moisture content: ${moisture}%
Difference (extracted vs expected): ${(extracted-drop>=0?"+":"")}${(extracted-drop).toFixed(1)} kg
Blockchain: ${r.blockHash.slice(0,40)}…</div><p><b>${status==="MATCH"?"✓ Verified event added to blockchain ledger.":"⚠ Flagged event added to blockchain ledger for review."}</b> <button class="btn secondary" onclick="page='ledger';render()">Open Ledger</button> <button class="btn secondary" onclick="openHarvestVerify('${r.id}')">🔍 View as Consumer</button></p></div>`;
freshHarvestRows();renderHarvestPage();
$("#harvestResult").innerHTML=resultHtml;
}
function exportHarvestCSV(){
const rows=[["Harvest ID","Date","Hive(s)","Expected kg","Extracted kg","Recorded kg","Moisture %","Status","Reasons"]];
harvestRecords.forEach(r=>{const hs=r.hives||[{hive:r.hive}];rows.push([r.id,r.time,hs.map(h=>h.hive).join(" + "),r.drop.toFixed(1),r.extracted.toFixed(1),r.recorded.toFixed(1),(r.moisture??""),r.status,(r.reasons||[]).join(" | ")])});
const csv=rows.map(row=>row.map(c=>`"${String(c).replace(/"/g,'""')}"`).join(",")).join("\n");
const blob=new Blob([csv],{type:"text/csv;charset=utf-8;"});
const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="hivetrust_harvest_history.csv";document.body.appendChild(a);a.click();a.remove();
}



function consumerQRCard(b){
 const link=`${location.origin}${location.pathname}?v=${encodeURIComponent(b.token)}`;
 return `<div class="card"><div class="section-head"><h2>${esc(b.product)}</h2><span class="badge low">QR READY</span></div><div class="split"><div><div class="token">${esc(link)}</div><p class="muted">Use this official deep-link in the bottle QR. It opens the HiveTrust website's public preview.</p><div class="grid">${card("Bottle",b.token,"Unique token")}${card("Batch",b.batch,"Public")}${card("Origin",b.origin,"Public")}${card("Status",b.status,"Registry")}</div></div><div style="display:flex;justify-content:center;align-items:center"><div><div class="qr">QR<br>${esc(b.token.slice(-8))}</div><div class="muted" style="margin-top:8px;text-align:center">Demo QR artwork</div></div></div></div><button class="btn" style="margin-top:10px" onclick="openBottleToken('${esc(b.token)}')">Open Consumer Preview</button></div>`;
}

function iot(){
 const online=localDB.gateways.filter(g=>g.status==="ONLINE").length;
 $("#content").innerHTML=`<div class="hero"><div><div class="eyebrow" style="color:#9bc8ad">FIELD IOT ARCHITECTURE</div><h2>Hive → LoRa → Gateway → Internet → HiveTrust</h2><p>Hive nodes sleep between readings. Every 15 minutes they send sensor data through LoRa to a gateway. The gateway uses 4G/LTE (or Wi-Fi/Ethernet where available) to reach the HiveTrust backend.</p></div><div style="font-size:70px">📡🐝</div></div>
 <div class="grid section">${card("Gateways online",online+"/"+localDB.gateways.length,"LoRaWAN gateways",online===localDB.gateways.length?"low":"high")}${card("Sensor nodes",localDB.devices.length,"Provisioned demo devices")}${card("Reading interval","15 min","Configurable")}${card("On-demand","Read Now","Downlink request")}</div>
 <div class="section card"><div class="section-head"><h2>📡 Gateway status</h2><button class="btn secondary" onclick="simulateIoT()">Simulate 15-min cycle</button></div><div class="table-wrap"><table class="table"><thead><tr><th>Gateway</th><th>Apiary</th><th>Network</th><th>Backhaul</th><th>Battery</th><th>Signal</th><th>Last seen</th></tr></thead><tbody>${localDB.gateways.map(g=>`<tr><td><b>${g.id}</b></td><td>${g.apiary}</td><td>${g.network}</td><td>${g.backhaul}</td><td>${g.battery}%</td><td><span class="badge ${g.signal==="Good"?"low":"medium"}">${g.signal}</span></td><td>${g.lastSeen}</td></tr>`).join("")}</tbody></table></div></div>
 <div class="section card"><div class="section-head"><h2>🐝 Sensor nodes</h2><button class="btn" onclick="addDemoHiveDevice()">+ Provision New Hive</button></div><div class="table-wrap"><table class="table"><thead><tr><th>Device</th><th>Hive</th><th>Gateway</th><th>Status</th><th>Battery</th><th>Last reading</th><th>Action</th></tr></thead><tbody>${localDB.devices.map(d=>`<tr><td><b>${d.id}</b></td><td>${d.hive}</td><td>${d.gateway}</td><td><span class="badge ${d.status==="ONLINE"?"low":"high"}">${d.status}</span></td><td>${d.battery}%</td><td>${d.lastReading}</td><td><button class="btn secondary" onclick="readNow('${d.id}')">🔄 Read Now</button></td></tr>`).join("")}</tbody></table></div></div>
 <div class="split section"><div class="card"><h2>🔁 Data flow</h2>${["Sensor wakes every 15 minutes","Read SHT41 temperature/humidity + load cell weight + IMU activity + battery","Send a small LoRa packet","Gateway receives it and forwards via 4G/LTE","HiveTrust API stores the reading; website renders current + history","Important events can be anchored to blockchain"].map((x,i)=>`<div class="step"><div class="stepno">${i+1}</div><div>${x}</div></div>`).join("")}</div><div class="card"><h2>⚡ Gateway power & connectivity</h2><p class="muted">Hive nodes can be battery-only. The gateway normally needs more power because its LoRa receiver and cellular backhaul are active for long periods.</p><div class="code">Hives: battery + low-power sleep\nGateway: larger battery / optional solar\nBackhaul: 4G/LTE → Internet\nFallback: Wi-Fi/Ethernet if available\nNo 4G: buffer locally → upload when restored</div><div class="warn-strip" style="margin-top:10px"><b>Field rule:</b> Do a site survey before deployment. LoRa range depends on antenna, terrain, vegetation and regional radio settings.</div></div></div>`;
}
function simulateIoT(){localDB.devices.forEach(d=>{d.battery=Math.max(5,Math.min(100,d.battery-(Math.random()<.3?1:0)));d.lastReading=new Date().toLocaleString();d.status="ONLINE"});localDB.gateways.forEach(g=>{g.lastSeen=new Date().toLocaleString();g.battery=Math.max(5,g.battery-(Math.random()<.2?1:0))});saveDB();render()}
function readNow(id){const d=localDB.devices.find(x=>x.id===id);if(!d)return;d.lastReading=new Date().toLocaleString();saveDB();alert(`Fresh reading requested for ${d.hive}.\n\nDemo response:\nTemperature: 34.2°C\nHumidity: 64%\nWeight: 48.7 kg\nActivity: Normal\n\nProduction: this request would travel as a LoRaWAN downlink through the gateway.`);render()}
function addDemoHiveDevice(){const n=localDB.devices.length+1,id=`HT-HIVE-${String(n).padStart(3,"0")}`,hive=`H${String(n).padStart(3,"0")}`,gw=localDB.gateways[0]?.id||"HT-GW-001";localDB.devices.push({id,hive,gateway:gw,status:"ONLINE",lastReading:new Date().toLocaleString(),battery:96});saveDB();addBlock("DEVICE_PROVISIONED",{device_id:id,hive_id:hive,gateway_id:gw});iot()}

/* ---------- Render / nav ---------- */
function render(){document.querySelectorAll(".nav").forEach(b=>b.classList.toggle("active",b.dataset.page===page));$("#title").textContent={dashboard:"Dashboard",hives:"Smart Hives",batches:"Honey Batches",harvest:"Harvest Integrity",alerts:"Alerts",ledger:"Blockchain & Security",verify:"Consumer Verification",auth:"Bottle Authenticity",iot:"IoT Gateway",about:"Research Concept"}[page];({dashboard,hives,batches,harvest,alerts,ledger,verify,auth,iot,about}[page])()}
document.querySelectorAll(".nav").forEach(b=>b.onclick=()=>{page=b.dataset.page;render()});

function dashboard(){
let hs=state.hives.map(x=>({...x,...predictor(x)})),avg=Math.round(hs.reduce((a,x)=>a+x.score,0)/hs.length),risk=hs.filter(x=>x.risk==="High").length;
const mc=hiveMismatchCounts(),repeatedCount=Object.values(mc).filter(c=>c>=2).length,alertsCount=risk+repeatedCount;
$("#content").innerHTML=`<div class="hero"><div><div class="eyebrow" style="color:#9bc8ad">RESEARCH PROTOTYPE</div><h2>From hive monitoring to trusted honey.</h2><p>Monitor hive conditions, predict risk and yield, then connect each harvest to a tamper-evident provenance trail.</p><div class="actions"><button class="btn" onclick="simulate()">Simulate Sensor Cycle</button><button class="btn secondary" onclick="page='batches';render()">Create Honey Batch</button></div></div><div style="font-size:72px">🐝</div></div><div class="grid section">${card("Hives monitored",hs.length,"Demo IoT nodes")}${card("Average hive health",avg+"/100","Explainable demo score",avg>=80?"low":avg>=60?"medium":"high")}${card("Blockchain",validChain().ok?"VALID":"BROKEN","SHA-style demo ledger",validChain().ok?"low":"high")}<div class="card" style="cursor:pointer" onclick="page='alerts';render()"><div class="muted">Active alerts</div><div class="metric ${alertsCount?"high":"low"}">${alertsCount}</div><div class="muted">High risk + repeated mismatch</div></div></div><div class="split section"><div class="card"><div class="section-head"><h2>Hive overview</h2></div><div class="table-wrap"><table class="table"><thead><tr><th>Hive</th><th>Location</th><th>Health</th><th>Risk</th><th>Yield</th></tr></thead><tbody>${hs.map(x=>`<tr><td><b>${x.id}</b></td><td>${x.location}</td><td>${x.score}/100</td><td><span class="badge ${x.risk.toLowerCase()}">${x.risk}</span>${mc[x.id]>=2?` <span class="badge high">⚠ Repeated Mismatch</span>`:""}</td><td>${x.ymin}–${x.ymax} kg</td></tr>`).join("")}</tbody></table></div></div><div class="card"><h2>Prediction model</h2><p class="muted">Demo model combines temperature, humidity, hive weight and bee activity.</p><div class="code">Inputs → Sensor readings\n       ↓\nAI-style scoring\n       ↓\nHealth + Risk + Yield\n       ↓\nAction recommendation</div></div></div>`}
function simulate(){state.hives.forEach(x=>{x.t=+(x.t+(Math.random()-.5)*2).toFixed(1);x.h=Math.max(30,Math.min(85,+(x.h+(Math.random()-.5)*8).toFixed(1)));x.w=+(x.w+(Math.random()-.1)*1).toFixed(1);x.a=Math.max(20,Math.min(100,+(x.a+(Math.random()-.5)*10).toFixed(1)))});render()}
function hives(){
let hs=state.hives.map(x=>({...x,...predictor(x)}));const mc=hiveMismatchCounts();
$("#content").innerHTML=`<div class="card"><div class="section-head"><h2>Live hive monitoring</h2><button class="btn" onclick="simulate()">Simulate New Readings</button></div><div class="table-wrap"><table class="table"><thead><tr><th>Hive</th><th>Temp</th><th>Humidity</th><th>Weight</th><th>Activity</th><th>Health</th><th>Prediction</th></tr></thead><tbody>${hs.map(x=>`<tr><td><b>${x.id}</b><br><span class="muted">${x.location}</span></td><td>${x.t}°C</td><td>${x.h}%</td><td>${x.w} kg</td><td>${x.a}%</td><td><b>${x.score}/100</b></td><td><span class="badge ${x.risk.toLowerCase()}">${x.risk} risk</span><br><span class="muted">${x.ymin}–${x.ymax} kg expected</span></td></tr>`).join("")}</tbody></table></div></div><div class="grid section">${hs.map(x=>`<div class="card"><b>${x.id}</b><div class="muted">${x.location}</div><div style="text-align:center;padding:18px"><div class="big">${x.score}</div><div class="muted">Hive Health</div></div><div class="${x.risk==="High"?"dangerbox":x.risk==="Medium"?"notice":"success"}"><b>${x.risk} risk</b><br>${esc(x.reason)}</div>${mc[x.id]>=2?`<div class="dangerbox" style="margin-top:8px"><b>⚠ Repeated Mismatch</b><br>${mc[x.id]} flagged harvests recorded for this hive. Recommend a physical inspection.</div>`:""}</div>`).join("")}</div>`}
function batches(){let hs=state.hives;$("#content").innerHTML=`<div class="card"><div class="section-head"><h2>Create a harvest batch</h2></div><div class="actions"><select id="sel" class="input">${hs.map(x=>`<option value="${x.id}">${x.id} — ${x.location}</option>`).join("")}</select><button class="btn" onclick="createBatch()">Create Batch</button></div></div><div class="section card"><h2>Honey provenance</h2><div class="table-wrap"><table class="table"><thead><tr><th>Batch</th><th>Hive</th><th>Quantity</th><th>Quality</th><th>Action</th></tr></thead><tbody>${state.batches.length?state.batches.map(b=>`<tr><td><b>${b.id}</b></td><td>${b.hive}</td><td>${b.qty} kg</td><td><span class="badge low">Verified Demo</span></td><td><button class="btn secondary" onclick="showBatch('${b.id}')">Verify</button></td></tr>`).join(""):`<tr><td colspan="5" class="muted">No batches yet.</td></tr>`}</tbody></table></div></div><div id="detail"></div><div class="section"><h2>🔐 Bottle-level QR Registry</h2><p class="muted">Each bottle gets a unique public deep-link. Basic information is public; the detailed report requires the hidden lid code.</p>${localDB.bottles.map(consumerQRCard).join("")}</div>`}
function createBatch(){let id="HC-"+Date.now().toString().slice(-8),h=state.hives.find(x=>x.id===$("#sel").value),p=predictor(h),qty=+(Math.max(1,(h.w-30)*.7)).toFixed(1);state.batches.push({id,hive:h.id,location:h.location,qty,date:new Date().toLocaleDateString(),quality:"Verified Demo"});addBlock("HARVEST",{batch_id:id,hive_id:h.id,quantity_kg:qty});addBlock("QUALITY_STATUS",{batch_id:id,status:"Verified Demo"});batches()}
function showBatch(id){let b=state.batches.find(x=>x.id===id);$("#detail").innerHTML=`<div class="section card"><h2>🍯 Consumer Verification</h2><div class="split"><div><div class="grid">${card("Batch",b.id,"Unique provenance ID")}${card("Source Hive",b.hive,"Origin")}${card("Quantity",b.qty+" kg","Harvest quantity")}${card("Status","VERIFIED","Demo evidence","low")}</div><div class="success section">✓ Harvest event linked to the HiveTrust ledger.<br>✓ Quality status recorded.<br>✓ QR-ready verification page available.</div></div><div style="display:flex;justify-content:center;align-items:center"><div><div class="qr">QR<br>${b.id}</div><div class="muted" style="margin-top:8px;text-align:center">QR-ready demo</div></div></div></div></div>`}

/* ---------- Alerts ---------- */
function alerts(){
const hs=state.hives.map(x=>({...x,...predictor(x)}));
const mc=hiveMismatchCounts();
const highRisk=hs.filter(x=>x.risk==="High");
const repeated=Object.entries(mc).filter(([,c])=>c>=2);
const mismatches=harvestRecords.filter(r=>r.status==="MISMATCH").slice().reverse();
$("#content").innerHTML=`<div class="hero"><div><div class="eyebrow" style="color:#9bc8ad">ALERTS & INSPECTION QUEUE</div><h2>Everything that needs a human look, in one place.</h2><p>High-risk hives, repeated harvest mismatches and flagged verification events.</p></div><div style="font-size:70px">🚨</div></div>
<div class="grid section">${card("High-risk hives",highRisk.length,"Needs inspection",highRisk.length?"high":"low")}${card("Repeated mismatch hives",repeated.length,"2+ flagged harvests",repeated.length?"high":"low")}${card("Open harvest mismatches",mismatches.length,"Flagged verification events",mismatches.length?"high":"low")}${card("Chain state",validChain().ok?"VALID":"BROKEN","Ledger integrity",validChain().ok?"low":"high")}</div>
<div class="section card"><div class="section-head"><h2>🐝 High-risk hives</h2></div>${highRisk.length?highRisk.map(x=>`<div class="dangerbox" style="margin-bottom:8px"><b>${x.id} · ${x.location}</b> — ${esc(x.reason)}<br><button class="btn secondary" style="margin-top:6px" onclick="page='hives';render()">Inspect Hive</button></div>`).join(""):"<div class='muted'>No high-risk hives right now.</div>"}</div>
<div class="section card"><div class="section-head"><h2>⚠️ Repeated Mismatch Hives</h2></div>${repeated.length?repeated.map(([id,c])=>`<div class="dangerbox" style="margin-bottom:8px"><b>${id}</b> — ${c} mismatched harvests recorded. <b>Inspect This Hive.</b><br><button class="btn secondary" style="margin-top:6px" onclick="page='hives';render()">Go to Smart Hives</button></div>`).join(""):"<div class='muted'>No hive has repeated mismatches.</div>"}</div>
<div class="section card"><div class="section-head"><h2>🔴 Flagged Harvest Events</h2></div>${mismatches.length?mismatches.map(harvestCard).join(""):"<div class='muted'>No flagged harvest events.</div>"}</div>`;
}

/* ---------- Ledger ---------- */
function ledger(){let v=validChain(),bad=v.bad;$("#content").innerHTML=`<div class="${v.ok?"success":"dangerbox"}"><b>${v.ok?"✓ Ledger verified":"⚠ Tampering detected"}</b><br>${v.ok?"All demo blocks match their chained hashes.":"Broken block #"+bad+" detected. The chain no longer matches its integrity rules."}</div><div class="grid section">${card("Blocks",state.blocks.length,"Ledger entries")}${card("Chain state",v.ok?"VALID":"BROKEN",v.ok?"No mismatch":"Investigation required",v.ok?"low":"high")}${card("Detection","SHA-256 style","Hash + previous hash")}${card("Audit events",state.audits.length,"Security history")}</div><div class="section card"><div class="section-head"><h2>🛡️ Security Lab</h2><div class="actions"><button class="btn danger" onclick="tamper()">Run Tamper Test</button><button class="btn secondary" onclick="resetLedger()">Restore Demo Ledger</button></div></div><p class="muted">This test intentionally changes one stored block hash to demonstrate how a tamper-evident ledger detects inconsistency.</p>${v.ok?`<div class="success">Step 1: Chain is valid. Run the test to simulate unauthorized modification.</div>`:`<div class="notice"><b>Detection report</b><br>• Broken block: #${bad}<br>• Previous-hash link: MISMATCH<br>• Recomputed integrity: FAILED<br>• Action: record flagged for investigation</div>`}</div><div class="section card"><h2>🔗 Chain Explorer</h2><div class="chain">${state.blocks.slice().reverse().map(b=>`<div class="block"><b>Block #${b.idx}</b><div class="muted">${b.type} · ${b.ts}</div><hr><div class="muted">Current hash</div><p class="hash">${b.hash}</p><div class="muted">Previous hash</div><p class="hash">${b.prev}</p><details><summary>Payload</summary><pre>${esc(JSON.stringify(b.payload,null,2))}</pre></details></div>`).join("")}</div></div><div class="section card"><h2>📋 Security Audit Log</h2><div class="table-wrap"><table class="table"><thead><tr><th>Time</th><th>Action</th><th>Details</th></tr></thead><tbody>${state.audits.length?state.audits.map(a=>`<tr><td>${a.ts}</td><td><span class="badge high">${a.action}</span></td><td>${esc(a.details)}</td></tr>`).join(""):`<tr><td colspan="3" class="muted">No security events yet.</td></tr>`}</tbody></table></div></div>`}
function tamper(){if(!state.blocks.length)return;let b=state.blocks[0];let old=b.hash;b.hash="0".repeat(64);state.audits.unshift({ts:new Date().toLocaleString(),action:"TAMPER_TEST",details:`Block #${b.idx}: hash changed from ${old.slice(0,16)}… to 0000000000000000…`});ledger()}
function resetLedger(){state.blocks=[];state.audits=[];addBlock("GENESIS",{message:"HiveTrust demo ledger restored"});ledger()}

/* ---------- Consumer verify ---------- */
function verify(){$("#content").innerHTML=`<div class="hero"><div><div class="eyebrow" style="color:#9bc8ad">CONSUMER VIEW</div><h2>Verify your honey.</h2><p>Enter a batch ID or a harvest ID to view its demo provenance.</p><div class="actions"><input id="bid" class="input" placeholder="e.g. HC-12345678 or HI-12345678"><button class="btn" onclick="lookup()">Verify</button></div></div><div style="font-size:70px">🍯</div></div><div id="verifyResult" class="section"></div>`}
function lookup(){
const id=$("#bid").value.trim();
const b=state.batches.find(x=>x.id===id);
const h=harvestRecords.find(x=>x.id===id);
if(b){
 $("#verifyResult").innerHTML=`<div class="card"><h2>✓ Batch Verified</h2><div class="grid">${card("Batch",b.id,"Unique ID")}${card("Source Hive",b.hive,b.location)}${card("Quantity",b.qty+" kg","Harvest")}${card("Status","VERIFIED","Demo evidence","low")}</div><div class="success section">The batch is linked to a harvest event and quality status in the demo ledger.</div></div>`;
}else if(h){
 const hs=h.hives||[{hive:h.hive}];
 $("#verifyResult").innerHTML=`<div class="card"><h2>${h.status==="MATCH"?"✓ Harvest Verified":"⚠ Harvest Flagged for Review"}</h2><div class="grid">${card("Harvest ID",h.id,"Verification event")}${card("Hive(s)",hs.map(x=>x.hive).join(", "),"Source")}${card("Extracted",h.extracted.toFixed(1)+" kg","Reported quantity")}${card("Status",h.status,"Ledger status",h.status==="MATCH"?"low":"high")}</div><div class="${h.status==="MATCH"?"success":"notice"} section">${h.status==="MATCH"?"This harvest's weight and extraction records agree — verified on the HiveTrust ledger.":"This harvest was flagged for a measurement mismatch and is currently under review by the producer."}</div><div class="hash" style="margin-top:10px">Blockchain verification hash: ${h.blockHash}</div></div>`;
}else{
 $("#verifyResult").innerHTML=`<div class="notice">No demo batch or harvest event found for that ID. Try a Batch ID (HC-…) or a Harvest ID (HI-…).</div>`;
}
}
function openHarvestVerify(id){page="verify";render();$("#bid").value=id;lookup()}
function about(){$("#content").innerHTML=`<div class="hero"><div><div class="eyebrow" style="color:#9bc8ad">RESEARCH CONCEPT</div><h2>Monitor → Analyze → Predict → Verify → Track</h2><p>HiveTrust AI combines smart hive monitoring, predictive analysis and evidence-based honey provenance.</p></div></div><div class="grid section"><div class="card"><h2>🐝 IoT</h2><p class="muted">Temperature, humidity, weight and bee activity.</p></div><div class="card"><h2>🤖 AI</h2><p class="muted">Hive health, risk and yield prediction.</p></div><div class="card"><h2>🍯 Provenance</h2><p class="muted">Connect harvest batches to their source hive.</p></div><div class="card"><h2>🔗 Blockchain</h2><p class="muted">Tamper-evident event history for important records.</p></div></div><div class="section card"><h2>Research novelty</h2><p>Blockchain and QR traceability already exist in honey research. The stronger proposed contribution is integrating predictive hive intelligence with evidence-based provenance: <b>Monitor → Analyze → Predict → Verify → Track.</b></p><div class="code">Hive → Sensors → AI → Risk/Yield Prediction → Harvest → Quality Evidence → Ledger → Bottle Token → Public QR Preview → Hidden Lid Code → Detailed Consumer Report → Clone Detection</div></div>`}


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
