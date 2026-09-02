const $=s=>document.querySelector(s);const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let page="dashboard";
let role=localStorage.getItem("hivetrust_role")||"owner";
const ROLE_PAGES={owner:["dashboard","hives","batches","harvest","alerts","about"],auditor:["dashboard","harvest","alerts","ledger","about"],consumer:["verify","about"]};
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

/* ---------- Render / nav ---------- */
function render(){document.querySelectorAll(".nav").forEach(b=>b.classList.toggle("active",b.dataset.page===page));$("#title").textContent={dashboard:"Dashboard",hives:"Smart Hives",batches:"Honey Batches",harvest:"Harvest Integrity",alerts:"Alerts",ledger:"Blockchain & Security",verify:"Consumer Verification",about:"Research Concept"}[page];({dashboard,hives,batches,harvest,alerts,ledger,verify,about}[page])()}
document.querySelectorAll(".nav").forEach(b=>b.onclick=()=>{page=b.dataset.page;render()});

function dashboard(){
let hs=state.hives.map(x=>({...x,...predictor(x)})),avg=Math.round(hs.reduce((a,x)=>a+x.score,0)/hs.length),risk=hs.filter(x=>x.risk==="High").length;
const mc=hiveMismatchCounts(),repeatedCount=Object.values(mc).filter(c=>c>=2).length,alertsCount=risk+repeatedCount;
$("#content").innerHTML=`<div class="hero"><div><div class="eyebrow" style="color:#9bc8ad">RESEARCH PROTOTYPE</div><h2>From hive monitoring to trusted honey.</h2><p>Monitor hive conditions, predict risk and yield, then connect each harvest to a tamper-evident provenance trail.</p><div class="actions"><button class="btn" onclick="simulate()">Simulate Sensor Cycle</button><button class="btn secondary" onclick="page='batches';render()">Create Honey Batch</button></div></div><div style="font-size:72px">🐝</div></div><div class="grid section">${card("Hives monitored",hs.length,"Demo IoT nodes")}${card("Average hive health",avg+"/100","Explainable demo score",avg>=80?"low":avg>=60?"medium":"high")}${card("Blockchain",validChain().ok?"VALID":"BROKEN","SHA-style demo ledger",validChain().ok?"low":"high")}<div class="card" style="cursor:pointer" onclick="page='alerts';render()"><div class="muted">Active alerts</div><div class="metric ${alertsCount?"high":"low"}">${alertsCount}</div><div class="muted">High risk + repeated mismatch</div></div></div><div class="split section"><div class="card"><div class="section-head"><h2>Hive overview</h2></div><div class="table-wrap"><table class="table"><thead><tr><th>Hive</th><th>Location</th><th>Health</th><th>Risk</th><th>Yield</th></tr></thead><tbody>${hs.map(x=>`<tr><td><b>${x.id}</b></td><td>${x.location}</td><td>${x.score}/100</td><td><span class="badge ${x.risk.toLowerCase()}">${x.risk}</span>${mc[x.id]>=2?` <span class="badge high">⚠ Repeated Mismatch</span>`:""}</td><td>${x.ymin}–${x.ymax} kg</td></tr>`).join("")}</tbody></table></div></div><div class="card"><h2>Prediction model</h2><p class="muted">Demo model combines temperature, humidity, hive weight and bee activity.</p><div class="code">Inputs → Sensor readings\n       ↓\nAI-style scoring\n       ↓\nHealth + Risk + Yield\n       ↓\nAction recommendation</div></div></div>`}
function simulate(){state.hives.forEach(x=>{x.t=+(x.t+(Math.random()-.5)*2).toFixed(1);x.h=Math.max(30,Math.min(85,+(x.h+(Math.random()-.5)*8).toFixed(1)));x.w=+(x.w+(Math.random()-.1)*1).toFixed(1);x.a=Math.max(20,Math.min(100,+(x.a+(Math.random()-.5)*10).toFixed(1)))});render()}
function hives(){
let hs=state.hives.map(x=>({...x,...predictor(x)}));const mc=hiveMismatchCounts();
$("#content").innerHTML=`<div class="card"><div class="section-head"><h2>Live hive monitoring</h2><button class="btn" onclick="simulate()">Simulate New Readings</button></div><div class="table-wrap"><table class="table"><thead><tr><th>Hive</th><th>Temp</th><th>Humidity</th><th>Weight</th><th>Activity</th><th>Health</th><th>Prediction</th></tr></thead><tbody>${hs.map(x=>`<tr><td><b>${x.id}</b><br><span class="muted">${x.location}</span></td><td>${x.t}°C</td><td>${x.h}%</td><td>${x.w} kg</td><td>${x.a}%</td><td><b>${x.score}/100</b></td><td><span class="badge ${x.risk.toLowerCase()}">${x.risk} risk</span><br><span class="muted">${x.ymin}–${x.ymax} kg expected</span></td></tr>`).join("")}</tbody></table></div></div><div class="grid section">${hs.map(x=>`<div class="card"><b>${x.id}</b><div class="muted">${x.location}</div><div style="text-align:center;padding:18px"><div class="big">${x.score}</div><div class="muted">Hive Health</div></div><div class="${x.risk==="High"?"dangerbox":x.risk==="Medium"?"notice":"success"}"><b>${x.risk} risk</b><br>${esc(x.reason)}</div>${mc[x.id]>=2?`<div class="dangerbox" style="margin-top:8px"><b>⚠ Repeated Mismatch</b><br>${mc[x.id]} flagged harvests recorded for this hive. Recommend a physical inspection.</div>`:""}</div>`).join("")}</div>`}
function batches(){let hs=state.hives;$("#content").innerHTML=`<div class="card"><div class="section-head"><h2>Create a harvest batch</h2></div><div class="actions"><select id="sel" class="input">${hs.map(x=>`<option value="${x.id}">${x.id} — ${x.location}</option>`).join("")}</select><button class="btn" onclick="createBatch()">Create Batch</button></div></div><div class="section card"><h2>Honey provenance</h2><div class="table-wrap"><table class="table"><thead><tr><th>Batch</th><th>Hive</th><th>Quantity</th><th>Quality</th><th>Action</th></tr></thead><tbody>${state.batches.length?state.batches.map(b=>`<tr><td><b>${b.id}</b></td><td>${b.hive}</td><td>${b.qty} kg</td><td><span class="badge low">Verified Demo</span></td><td><button class="btn secondary" onclick="showBatch('${b.id}')">Verify</button></td></tr>`).join(""):`<tr><td colspan="5" class="muted">No batches yet.</td></tr>`}</tbody></table></div></div><div id="detail"></div>`}
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
function about(){$("#content").innerHTML=`<div class="hero"><div><div class="eyebrow" style="color:#9bc8ad">RESEARCH CONCEPT</div><h2>Monitor → Analyze → Predict → Verify → Track</h2><p>HiveTrust AI combines smart hive monitoring, predictive analysis and evidence-based honey provenance.</p></div></div><div class="grid section"><div class="card"><h2>🐝 IoT</h2><p class="muted">Temperature, humidity, weight and bee activity.</p></div><div class="card"><h2>🤖 AI</h2><p class="muted">Hive health, risk and yield prediction.</p></div><div class="card"><h2>🍯 Provenance</h2><p class="muted">Connect harvest batches to their source hive.</p></div><div class="card"><h2>🔗 Blockchain</h2><p class="muted">Tamper-evident event history for important records.</p></div></div><div class="section card"><h2>Research novelty</h2><p>Blockchain and QR traceability already exist in honey research. The stronger proposed contribution is integrating predictive hive intelligence with evidence-based provenance: <b>Monitor → Analyze → Predict → Verify → Track.</b></p><div class="code">Hive → Sensors → AI → Risk/Yield Prediction → Harvest → Quality Evidence → Ledger → QR → Consumer</div></div>`}

function init(){
if($("#roleSel"))$("#roleSel").value=role;
if(!ROLE_PAGES[role].includes(page))page=ROLE_PAGES[role][0];
applyRole();
render();
}
init();
