const $ = (id) => document.getElementById(id);
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labels = {age:'Age',sex:'Sex',dispatch_reason:'Dispatch reason',chief_complaint:'Chief complaint',symptom_onset:'Symptom onset',mental_status:'Mental status',primary_impression:'Primary impression',systolic_bp:'Systolic pressure',diastolic_bp:'Diastolic pressure',heart_rate:'Heart rate',spo2:'Initial oxygen saturation',spo2_context:'Oxygen context',oxygen_given:'Oxygen administered',oxygen_flow_lpm:'Oxygen flow',oxygen_route:'Oxygen route',post_treatment_spo2:'Post-treatment saturation',treatment_response:'Treatment response',transported:'Transport',destination:'Destination',transport_priority:'Transport priority',transport_justification:'Transport rationale',medications_given:'Medication administration'};
const units = {age:'years',systolic_bp:'mmHg',diastolic_bp:'mmHg',heart_rate:'bpm',spo2:'%',post_treatment_spo2:'%',oxygen_flow_lpm:'L/min'};
const sections = [ ['PATIENT',['age','sex']], ['PRESENTATION',['dispatch_reason','chief_complaint','symptom_onset','mental_status','primary_impression']], ['VITALS',['systolic_bp','diastolic_bp','heart_rate','spo2','spo2_context']], ['INTERVENTIONS',['oxygen_given','oxygen_flow_lpm','oxygen_route','post_treatment_spo2','treatment_response','medications_given']], ['TRANSPORT',['transported','destination','transport_priority','transport_justification']] ];
let lastFingerprint = '', latest;
const selectedId = location.pathname.match(/^\/encounters\/([^/]+)\/?$/)?.[1];
let lastRecent = 0;
const dateLabel = value => value ? new Date(value).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit',second:'2-digit',timeZoneName:'short'}) : '';
let openFacts = new Set();
const friendly = (key) => labels[key] || (key.startsWith('medications.') ? `Medication ${Number(key.split('.')[1])+1} · ${key.split('.')[2]}` : key.replaceAll('_',' '));
function factHtml(key, f) {
  const value = f.status === 'uncertain' ? (typeof f.value === 'string' ? `${f.value} · uncertain` : 'Uncertain — clarification needed') : f.status === 'conflicting' ? `${f.value} · conflicting` : f.explicitly_unknown ? 'Explicitly unspecified' : f.value == null ? 'Not documented' : typeof f.value === 'boolean' ? f.value ? 'Yes' : 'No' : f.value;
  const long = String(value).length > 28 || f.value == null;
  const history = (f.history || []).map(h => `<div class="history-entry"><strong>${esc(h.status)}</strong> · ${esc(h.value ?? 'unspecified')}<q>${esc(h.evidence)}</q><small>Medic · ${esc(h.turn_id)}</small></div>`).join('');
  return `<details class="fact ${esc(f.status)}" data-field="${esc(key)}" ${openFacts.has(key)?'open':''}><summary><span class="fact-label">${esc(friendly(key))}</span><span class="fact-value ${long?'long':''}">${esc(value)}${f.status==='confirmed'&&units[key]?`<span class="unit">${units[key]}</span>`:''}</span></summary><div class="source"><strong>${esc(f.status)}${f.explicitly_unknown?' · explicitly unspecified':''}</strong><q>${esc(f.evidence)}</q><small>Source: medic · ${esc(f.turn_id)}</small>${history}</div></details>`;
}
function render(data) {
  latest = data;
  const facts = data.encounter.facts, issues = data.issues;
  const started = data.call_status !== 'waiting';
  const complete = data.call_status === 'complete';
  const historical = data.is_current === false;
  $('encounter-mode').textContent = historical ? 'HISTORICAL ENCOUNTER · READ ONLY' : data.call_active ? 'LIVE ENCOUNTER' : 'CURRENT ENCOUNTER';
  $('history-notice').hidden = !historical;
  $('return-live').hidden = !historical;
  $('reset').hidden = historical;
  const statuses = {waiting:'Waiting',narrative:'Listening',reconciling:'Reviewing',complete:'Complete',incomplete:'Incomplete'};
  document.body.className = complete?'complete':data.call_active?'listening':'';
  $('call-status').textContent = `${historical?'Historical · ':''}${statuses[data.call_status] || 'Waiting'}`;
  const phone = data.phone_number || '';
  $('phone').textContent = phone.replace(/^\+1(\d{3})(\d{3})(\d{4})$/, '+1 ($1) $2-$3') || 'Voice line not configured';
  $('phone').href = phone ? `tel:${phone}` : '#';
  $('line-label').textContent = data.connection === 'connected' ? 'GUAVA VOICE LINE · CONNECTED' : data.connection === 'offline' ? 'GUAVA VOICE LINE · OFFLINE' : `GUAVA VOICE LINE · ${data.connection.toUpperCase()}`;
  $('reset').disabled = data.call_active;
  $('reset').title = data.call_active ? 'End the active call before starting a new demo' : 'Start a new encounter; previous encounters are saved';
  $('ready-banner').hidden = !complete;
  const error = data.error || data.connection_error;
  $('network-error').hidden = !error;
  $('network-error').textContent = error || '';
  const known = Object.keys(facts).length;
  $('empty-state').hidden = known > 0;
  $('encounter-sections').hidden = known === 0;
  $('encounter-meta').textContent = `ENCOUNTER ${data.encounter.id} · ${dateLabel(data.encounter.started_at)} · ${known} sourced facts${data.processing?' · Updating…':''}`;
  document.querySelector('#ready-banner .export-link').href = `/api/encounters/${encodeURIComponent(data.encounter.id)}/draft`;
  document.querySelector('#source-drawer .export-link').href = `/api/encounters/${encodeURIComponent(data.encounter.id)}/report`;
  const fingerprint = JSON.stringify(facts);
  if (fingerprint !== lastFingerprint) {
    openFacts = new Set([...document.querySelectorAll('.fact[open]')].map(el=>el.dataset.field));
    $('encounter-sections').innerHTML = sections.map(([title, keys], index) => {
      const all = title === 'INTERVENTIONS' ? [...keys, ...Object.keys(facts).filter(k=>k.startsWith('medications.'))] : keys;
      const visible = all.filter(k=>facts[k] && (facts[k].value != null || facts[k].explicitly_unknown || facts[k].history?.length || ['uncertain','conflicting'].includes(facts[k].status)));
      if (!visible.length) return '';
      return `<section class="fact-section"><div class="section-title"><span class="section-number">0${index+1}</span>${title}</div><div class="fact-grid">${visible.map(k=>factHtml(k,facts[k])).join('')}</div></section>`;
    }).join('');
    lastFingerprint = fingerprint;
  }
  const groups = [
    ['Patient information',['age','sex'],[]],
    ['Clinical presentation',['chief_complaint'],['chief_complaint','raw_narrative']],
    ['Initial assessment',['mental_status','spo2','systolic_bp','heart_rate','primary_impression'],['mental_status','spo2','systolic_bp','diastolic_bp','heart_rate','primary_impression']],
    ['Intervention',['oxygen_given','medications_given'],['oxygen_route','medications.']],
    ['Treatment response',['post_treatment_spo2','treatment_response'],['post_treatment_spo2','treatment_response','.response']],
    ['Transport rationale',['transport_justification'],['transport_justification','destination','transported']],
  ];
  $('review-list').innerHTML = groups.map(([label,keys,targets]) => {
    const related = started ? issues.filter(i=>targets.some(t=>i.field.includes(t))) : [];
    const blocked = related.some(i=>i.blocking);
    const present = keys.some(k=>facts[k]?.status==='confirmed') || (label==='Treatment response'&&Object.entries(facts).some(([k,f])=>k.endsWith('.response')&&f.status==='confirmed'));
    const advisory = related.length > 0 && !blocked;
    const state = blocked?'unresolved':advisory?'advisory':present?'resolved':'waiting';
    return `<div class="review-row ${state}"><span class="indicator">${state==='resolved'?'✓':state==='advisory'?'–':'○'}</span>${label}${advisory?'<span class="row-note">Advisory</span>':''}</div>`;
  }).join('');
  const blocking = issues.filter(i=>i.blocking).length;
  const advisories = issues.filter(i=>!i.blocking).length;
  $('issue-count').textContent = !started?'Awaiting encounter':complete?'0 blocking issues':`${blocking} unresolved issue${blocking===1?'':'s'}`;
  $('rule-count').textContent = started&&advisories?`${advisories} advisor${advisories===1?'y':'ies'}`:'12 prototype rules';
  $('issues').innerHTML = !started?'':issues.map(i=>`<div class="issue ${i.severity}"><div class="issue-title"><span class="issue-rule">${esc(i.rule)}</span>${esc(friendly(i.field))}${!i.blocking?' · advisory':''}</div><p>${esc(i.reason)}</p></div>`).join('');
  $('spoken-line').textContent = complete ? "Encounter ready for clinician review." : data.current_question?.text || (data.call_active?'Capturing encounter narrative.':'Awaiting encounter narrative.');
  $('conversation-caption').textContent = complete?'The clinician establishes clinical truth and reviews the final record.':data.current_question?'Selected from the unresolved documentation issues.':data.processing?'Updating structured encounter…':'Follow-up questions address unresolved documentation issues.';
  $('source-count').textContent = `${data.turns.length} source statement${data.turns.length===1?'':'s'} · ${known} facts`;
  $('narrative').textContent = data.turns.map(t=>t.text).join('\n\n') || "Source statements will appear here.";
  $('trail').innerHTML = data.history.map(q=>`<div class="trail-entry"><span class="issue-rule">${esc(q.code.replaceAll('_',' '))}</span><br>${esc(q.text)}</div>`).join('') || 'Follow-up questions will appear here.';
}
let pollInFlight=false;
async function poll(){
  if(pollInFlight)return;
  pollInFlight=true;
  try{
    const endpoint = selectedId ? `/api/encounters/${encodeURIComponent(selectedId)}` : '/api/encounter/current';
    const r=await fetch(endpoint,{cache:'no-store'});
    if(!r.ok)throw Error(r.status===404?'That encounter was not found. Return to the current encounter.':'Dashboard connection lost. Reconnecting…');
    render(await r.json());
    if(Date.now()-lastRecent>2000){
      const recent=await fetch('/api/encounters',{cache:'no-store'});
      if(recent.ok){
        const {encounters}=await recent.json();
        $('recent-count').textContent = ` · ${encounters.length} saved`;
        $('recent-encounters').innerHTML=encounters.map(e=>`<a class="recent-entry ${e.id===latest.encounter.id?'selected':''}" href="/encounters/${encodeURIComponent(e.id)}"><span><strong>${esc(e.id)}</strong><small>${esc(dateLabel(e.started_at))}</small></span><span class="recent-status">${e.call_active?'LIVE CALL':e.is_current?'CURRENT':'HISTORICAL'} · ${esc(e.status.replaceAll('_',' '))}</span></a>`).join('') || 'No encounters yet.';
        lastRecent=Date.now();
      }
    }
  }
  catch(e){$('network-error').hidden=false;$('network-error').textContent=e.message;$('call-status').textContent='Disconnected';}
  finally{pollInFlight=false;}
}
$('reset').addEventListener('click',async()=>{
  $('reset').disabled=true;
  try{const r=await fetch('/api/encounter/reset',{method:'POST'});if(!r.ok){const e=await r.json();throw Error(e.detail||'Reset unavailable');}lastFingerprint='';lastRecent=0;render(await r.json());if(selectedId){location.assign('/');return;}$('toast').textContent='New encounter started. Previous encounters are saved.';}
  catch(e){$('toast').textContent=e.message;}
  $('toast').hidden=false;setTimeout(()=>$('toast').hidden=true,3500);await poll();
});
poll();setInterval(poll,750);
