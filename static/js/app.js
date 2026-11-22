/**
 * RESQ 4.0 Main Application Controller
 * Manages tabs, state, real-time updates, multi-agent interactions,
 * test suites, and demonstration playback.
 */

let currentIncidents = [];
let activeIncidentId = null;
let activeTab = 'queue';
let demoInterval = null;
let currentDemoStep = 1;

document.addEventListener('DOMContentLoaded', async () => {
    initApp();
    setupEventListeners();
    await loadIncidents();
    API.initSSE(handleRealtimeEvent);
});

function initApp() {
    mapController.init();
}

function setupEventListeners() {
    // Navigation Tabs
    document.querySelectorAll('[data-tab]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const target = btn.getAttribute('data-tab');
            switchTab(target);
        });
    });

    // Language Toggle
    const langSelect = document.getElementById('voice-lang-select');
    if (langSelect) {
        langSelect.addEventListener('change', (e) => {
            voiceInterface.setLanguage(e.target.value);
        });
    }

    // Mic Record Button
    const recordBtn = document.getElementById('btn-record');
    if (recordBtn) {
        recordBtn.addEventListener('click', async () => {
            const isRecording = await voiceInterface.toggleRecording('waveform-canvas', (transcript) => {
                const input = document.getElementById('voice-transcript-input');
                if (input) input.value = transcript;
            });
            recordBtn.innerHTML = isRecording ? 
                `<span class="w-3 h-3 rounded-full bg-red-500 animate-ping mr-2"></span> Stop Recording` : 
                `<i class="fas fa-microphone mr-2"></i> Push to Talk`;
            recordBtn.className = isRecording ? 
                'px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg flex items-center font-semibold text-sm transition pulse-red' : 
                'px-4 py-2 bg-cyan-600 hover:bg-cyan-700 text-white rounded-lg flex items-center font-semibold text-sm transition';
        });
    }

    // Submit Voice Intake Button
    const submitIntakeBtn = document.getElementById('btn-submit-intake');
    if (submitIntakeBtn) {
        submitIntakeBtn.addEventListener('click', async () => {
            const input = document.getElementById('voice-transcript-input');
            const lang = document.getElementById('voice-lang-select').value;
            if (!input || !input.value.trim()) return alert('Please enter or record an emergency utterance.');
            if (!activeIncidentId) return alert('Please select an active incident from the queue.');

            try {
                await API.post(`/api/incidents/${activeIncidentId}/voice-intake`, {
                    transcript: input.value.trim(),
                    language: lang
                });
                input.value = '';
                await selectIncident(activeIncidentId);
            } catch (err) {
                alert('Error submitting intake: ' + err.message);
            }
        });
    }
}

function switchTab(tabId) {
    activeTab = tabId;
    document.querySelectorAll('[data-tab]').forEach(btn => {
        if (btn.getAttribute('data-tab') === tabId) {
            btn.className = 'px-4 py-2 text-sm font-semibold rounded-lg bg-cyan-600 text-white shadow-lg shadow-cyan-900/30 transition';
        } else {
            btn.className = 'px-4 py-2 text-sm font-semibold rounded-lg bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-700 transition';
        }
    });

    ['tab-queue', 'tab-detail', 'tab-demo', 'tab-scenarios', 'tab-benchmarks'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.toggle('hidden', id !== `tab-${tabId}`);
    });

    if (tabId === 'benchmarks') loadBenchmarks();
    if (tabId === 'scenarios') loadScenarios();
    if (tabId === 'demo') loadDemoSteps();
}

// ----------------- Real-time Event Handler -----------------
function handleRealtimeEvent(msg) {
    console.log('SSE Event:', msg.event, msg.data);
    
    // Refresh incident queue silently
    loadIncidents(false);

    // If current active incident updated, re-render detail
    if (activeIncidentId && msg.data && msg.data.incident_id === activeIncidentId) {
        renderIncidentDetail(msg.data);
    }
}

// ----------------- Incident Queue & Detail -----------------
async function loadIncidents(autoSelectFirst = true) {
    try {
        const data = await API.get('/api/incidents');
        currentIncidents = data;
        renderQueueTable(data);
        
        if (autoSelectFirst && data.length > 0 && !activeIncidentId) {
            selectIncident(data[0].incident_id);
        }
    } catch (err) {
        console.error('Failed to load incidents:', err);
    }
}

function renderQueueTable(incidents) {
    const tbody = document.getElementById('queue-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (incidents.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center py-8 text-slate-500">No active incidents in queue. Click "New Incident" to initialize.</td></tr>`;
        return;
    }

    incidents.forEach(inc => {
        const tr = document.createElement('tr');
        tr.className = `border-b border-slate-800 hover:bg-slate-800/40 cursor-pointer transition ${inc.incident_id === activeIncidentId ? 'bg-cyan-950/30 border-l-4 border-l-cyan-500' : ''}`;
        tr.onclick = () => selectIncident(inc.incident_id);

        const urgencyClass = inc.urgency === 'CRITICAL' ? 'badge-critical font-bold' : (inc.urgency === 'HIGH' ? 'text-amber-400 bg-amber-950/40 border border-amber-600/40' : 'text-slate-400');
        const connClass = inc.connection_state === 'DISCONNECTED' ? 'badge-disconnected font-bold' : 'text-emerald-400';

        tr.innerHTML = `
            <td class="py-3 px-4 font-mono font-bold text-xs text-cyan-400">${inc.incident_id}</td>
            <td class="py-3 px-4 font-semibold text-sm text-slate-200">${inc.category}</td>
            <td class="py-3 px-4"><span class="px-2 py-0.5 rounded text-xs ${urgencyClass}">${inc.urgency}</span></td>
            <td class="py-3 px-4"><span class="px-2 py-0.5 rounded text-xs ${connClass}">${inc.connection_state}</span></td>
            <td class="py-3 px-4 text-xs text-slate-300 max-w-[160px] truncate">${inc.locations.incident_location.description}</td>
            <td class="py-3 px-4"><span class="px-2 py-0.5 rounded text-xs ${inc.locations.incident_location.verification_status === 'UNCERTAIN' ? 'badge-uncertain' : 'badge-verified'}">${inc.locations.incident_location.verification_status}</span></td>
            <td class="py-3 px-4"><span class="px-2.5 py-1 rounded text-xs font-semibold bg-slate-800 border border-slate-700 text-slate-300">${inc.state}</span></td>
            <td class="py-3 px-4 text-xs text-slate-400 font-mono">${inc.assigned_operator || 'Unassigned'}</td>
        `;
        tbody.appendChild(tr);
    });

    const countEl = document.getElementById('queue-count');
    if (countEl) countEl.innerText = `${incidents.length} Active`;
}

async function selectIncident(incident_id) {
    activeIncidentId = incident_id;
    try {
        const inc = await API.get(`/api/incidents/${incident_id}`);
        renderIncidentDetail(inc);
        // Switch to detail view if in mobile or user triggered
    } catch (err) {
        console.error('Error fetching incident:', err);
    }
}

function renderIncidentDetail(inc) {
    // Header Info
    const idEl = document.getElementById('detail-id');
    const stateEl = document.getElementById('detail-state');
    const connEl = document.getElementById('detail-conn');
    const catEl = document.getElementById('detail-category');

    if (idEl) idEl.innerText = inc.incident_id;
    if (stateEl) stateEl.innerText = inc.state;
    if (connEl) {
        connEl.innerText = inc.connection_state;
        connEl.className = inc.connection_state === 'DISCONNECTED' ? 'px-2.5 py-1 rounded-full text-xs font-bold badge-disconnected' : 'px-2.5 py-1 rounded-full text-xs font-bold badge-verified';
    }
    if (catEl) catEl.innerText = inc.category;

    // Dual-Location Cards
    const callerLoc = inc.locations.caller_location;
    const incidentLoc = inc.locations.incident_location;

    const callerEl = document.getElementById('loc-caller-desc');
    const callerStatus = document.getElementById('loc-caller-status');
    const callerPrec = document.getElementById('loc-caller-precision');

    if (callerEl) callerEl.innerText = callerLoc.description || 'Not provided';
    if (callerStatus) callerStatus.innerText = callerLoc.verification_status;
    if (callerPrec) callerPrec.innerText = callerLoc.precision;

    const incLocEl = document.getElementById('loc-incident-desc');
    const incLocStatus = document.getElementById('loc-incident-status');
    const incLocPrec = document.getElementById('loc-incident-precision');

    if (incLocEl) incLocEl.innerText = incidentLoc.description || 'Not specified';
    if (incLocStatus) {
        incLocStatus.innerText = incidentLoc.verification_status;
        incLocStatus.className = incidentLoc.verification_status === 'UNCERTAIN' ? 'px-2 py-0.5 rounded text-xs font-semibold badge-uncertain' : 'px-2 py-0.5 rounded text-xs font-semibold badge-verified';
    }
    if (incLocPrec) incLocPrec.innerText = incidentLoc.precision;

    const sepBadge = document.getElementById('loc-separation-badge');
    if (sepBadge) {
        sepBadge.classList.toggle('hidden', !inc.locations.is_separated);
        if (inc.locations.is_separated) {
            sepBadge.innerText = `DUAL-LOCATION SEPARATION: ${inc.locations.separation_rationale || 'Caller is away from incident'}`;
        }
    }

    // Render Leaflet Map
    mapController.renderDualLocations(inc.locations);

    // Provenance Fields List
    renderProvenanceFields(inc.fields);

    // Multi-Agent Reasoning Panel
    renderAgentReasoning(inc.reasoning, inc.follow_up_queue);

    // Coordination Actions
    renderCoordinationActions(inc.coordination_actions);

    // Timeline Audit Trail
    loadTimeline(inc.incident_id);
}

function renderProvenanceFields(fields) {
    const container = document.getElementById('fields-container');
    if (!container) return;
    container.innerHTML = '';

    const keys = Object.keys(fields);
    if (keys.length === 0) {
        container.innerHTML = `<div class="text-slate-500 text-sm py-4 italic">No structured fields extracted yet. Use voice intake above.</div>`;
        return;
    }

    keys.forEach(k => {
        const f = fields[k];
        const card = document.createElement('div');
        card.className = 'p-3 bg-slate-900/80 border border-slate-800 rounded-lg flex flex-col gap-1.5';

        const historyCount = f.history.length;
        const historyBtn = historyCount > 0 ? 
            `<span class="text-xs text-cyan-400 bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-800 cursor-pointer" title="Has ${historyCount} previous revisions">${historyCount} Revisions</span>` : '';

        card.innerHTML = `
            <div class="flex items-center justify-between">
                <span class="text-xs font-bold uppercase tracking-wider text-slate-400 font-mono">${f.field_name.replace('_', ' ')}</span>
                <div class="flex items-center gap-2">
                    ${historyBtn}
                    <span class="px-2 py-0.5 rounded text-xs font-semibold ${f.verification_status === 'INDEPENDENTLY_VERIFIED' ? 'badge-verified' : 'badge-uncertain'}">${f.verification_status}</span>
                </div>
            </div>
            <div class="text-sm font-semibold text-slate-100">${f.current_value}</div>
            <div class="flex items-center justify-between text-xs text-slate-500 pt-1 border-t border-slate-800/60">
                <span>Source: <strong class="text-slate-400">${f.source}</strong> (Confidence: ${(f.confidence * 100).toFixed(0)}%)</span>
                <button onclick="promptFieldOverride('${f.field_name}', '${f.current_value}')" class="text-cyan-400 hover:text-cyan-300 text-xs font-semibold flex items-center gap-1">
                    <i class="fas fa-edit"></i> Edit / Verify
                </button>
            </div>
        `;
        container.appendChild(card);
    });
}

function renderAgentReasoning(reasoning, followUps) {
    const urgencyEl = document.getElementById('reasoning-urgency');
    const compScoreEl = document.getElementById('reasoning-completeness');
    const missingEl = document.getElementById('reasoning-missing');
    const contraEl = document.getElementById('reasoning-contradictions');
    const recsEl = document.getElementById('reasoning-recs');
    const followUpCard = document.getElementById('follow-up-card');

    if (urgencyEl) urgencyEl.innerText = reasoning.urgency_explanation || 'Pending triage';
    if (compScoreEl) {
        const pct = Math.round((reasoning.completeness_score || 0) * 100);
        compScoreEl.innerHTML = `
            <div class="w-full bg-slate-800 rounded-full h-2.5 mt-1 overflow-hidden">
                <div class="bg-cyan-500 h-2.5 rounded-full" style="width: ${pct}%"></div>
            </div>
            <span class="text-xs text-slate-400 mt-1 block">${pct}% of required intake fields collected</span>
        `;
    }

    if (missingEl) {
        if (reasoning.missing_critical_fields && reasoning.missing_critical_fields.length > 0) {
            missingEl.innerHTML = reasoning.missing_critical_fields.map(m => `<span class="px-2 py-1 rounded bg-red-950/60 border border-red-800/60 text-red-300 text-xs flex items-center gap-1"><i class="fas fa-exclamation-circle"></i> ${m}</span>`).join('');
        } else {
            missingEl.innerHTML = `<span class="text-emerald-400 text-xs"><i class="fas fa-check-circle"></i> No critical fields missing</span>`;
        }
    }

    if (contraEl) {
        if (reasoning.contradictions && reasoning.contradictions.length > 0) {
            contraEl.innerHTML = reasoning.contradictions.map(c => `<div class="p-2 rounded bg-amber-950/50 border border-amber-800 text-amber-300 text-xs"><i class="fas fa-triangle-exclamation mr-1"></i> ${c}</div>`).join('');
        } else {
            contraEl.innerHTML = `<span class="text-slate-500 text-xs italic">No contradictions detected</span>`;
        }
    }

    if (recsEl) {
        if (reasoning.operator_action_recommendations && reasoning.operator_action_recommendations.length > 0) {
            recsEl.innerHTML = reasoning.operator_action_recommendations.map(r => `<li class="text-xs text-slate-300">${r}</li>`).join('');
        } else {
            recsEl.innerHTML = `<li class="text-xs text-slate-500">None</li>`;
        }
    }

    // Adaptive Follow-Up Question
    if (followUpCard) {
        if (followUps && followUps.length > 0) {
            const q = followUps[0];
            followUpCard.classList.remove('hidden');
            document.getElementById('follow-up-text').innerText = `"${q.question_text}"`;
            document.getElementById('follow-up-rationale').innerText = q.rationale;
            document.getElementById('btn-speak-question').onclick = () => {
                voiceInterface.speak(q.question_text, q.language);
            };
        } else {
            followUpCard.classList.add('hidden');
        }
    }
}

function renderCoordinationActions(actions) {
    const list = document.getElementById('coordination-actions-list');
    if (!list) return;
    list.innerHTML = '';

    if (!actions || actions.length === 0) {
        list.innerHTML = `<div class="text-slate-500 text-xs py-3 italic">No coordination actions dispatched yet. Operators can propose below.</div>`;
        return;
    }

    actions.forEach(a => {
        const item = document.createElement('div');
        item.className = 'p-3 bg-slate-900 border border-slate-800 rounded-lg flex flex-col gap-2';

        const isApproved = a.operator_approved;
        const statusBadge = a.status === 'ACKNOWLEDGED' ? 'badge-verified' : (a.status === 'SENT' ? 'badge-inferred' : 'badge-uncertain');

        item.innerHTML = `
            <div class="flex items-center justify-between">
                <span class="font-bold text-xs text-slate-200">${a.action_type}</span>
                <span class="px-2 py-0.5 rounded text-xs font-semibold ${statusBadge}">${a.status}</span>
            </div>
            <div class="text-xs text-slate-400">Target Agency: <strong class="text-slate-200">${a.target_agency}</strong></div>
            <div class="text-xs text-slate-500 font-mono">Key: ${a.idempotency_key}</div>
            
            <div class="flex items-center justify-between pt-2 border-t border-slate-800">
                <span class="text-xs text-slate-400">Human Approval: <strong>${isApproved ? 'Approved by ' + a.operator_id : 'PENDING'}</strong></span>
                <div class="flex gap-2">
                    ${!isApproved ? `<button onclick="approveAction('${a.action_id}')" class="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-semibold">Authorize Dispatch</button>` : ''}
                    ${isApproved && a.status === 'SENT' ? `<button onclick="simulateAgencyAck('${a.action_id}')" class="px-2 py-1 bg-cyan-700 hover:bg-cyan-600 text-white rounded text-xs font-semibold">Simulate ACK</button>` : ''}
                </div>
            </div>
        `;
        list.appendChild(item);
    });
}

async function loadTimeline(incident_id) {
    const container = document.getElementById('timeline-container');
    if (!container) return;

    try {
        const events = await API.get(`/api/incidents/${incident_id}/timeline`);
        container.innerHTML = '';
        if (events.length === 0) {
            container.innerHTML = `<div class="text-slate-500 text-xs py-3 italic">No timeline events recorded yet.</div>`;
            return;
        }

        events.reverse().forEach(evt => {
            const row = document.createElement('div');
            row.className = 'flex gap-3 text-xs mb-3';
            const icon = evt.is_failure_event ? 
                '<div class="w-6 h-6 rounded-full bg-red-950 border border-red-500 text-red-400 flex items-center justify-center shrink-0"><i class="fas fa-bolt"></i></div>' : 
                '<div class="w-6 h-6 rounded-full bg-slate-800 border border-slate-700 text-cyan-400 flex items-center justify-center shrink-0"><i class="fas fa-circle-check"></i></div>';

            const timeStr = new Date(evt.timestamp).toLocaleTimeString();
            row.innerHTML = `
                ${icon}
                <div class="flex-1">
                    <div class="flex items-center justify-between">
                        <strong class="text-slate-200">${evt.actor}</strong>
                        <span class="text-slate-500 font-mono text-[10px]">${timeStr}</span>
                    </div>
                    <div class="text-slate-300 mt-0.5">${evt.summary}</div>
                </div>
            `;
            container.appendChild(row);
        });
    } catch (err) {
        console.error('Failed to load timeline:', err);
    }
}

// ----------------- Operator Controls -----------------
async function acknowledgeCurrentIncident() {
    if (!activeIncidentId) return;
    try {
        await API.post(`/api/incidents/${activeIncidentId}/acknowledge`, { operator_id: 'Operator-Lead' });
        await selectIncident(activeIncidentId);
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

async function promptFieldOverride(fieldName, currentValue) {
    if (!activeIncidentId) return;
    const newVal = prompt(`Enter verified value for '${fieldName}':`, currentValue);
    if (!newVal || newVal === currentValue) return;
    const reason = prompt(`Provide audit reason for verification/override:`, 'Visual verification via CCTV / Ground unit');
    if (!reason) return;

    try {
        await API.post(`/api/incidents/${activeIncidentId}/override-field`, {
            field_name: fieldName,
            new_value: newVal,
            reason: reason,
            operator_id: 'Operator-Lead'
        });
        await selectIncident(activeIncidentId);
    } catch (err) {
        alert('Error overriding field: ' + err.message);
    }
}

async function approveAction(actionId) {
    if (!activeIncidentId) return;
    try {
        await API.post(`/api/incidents/${activeIncidentId}/approve-action`, {
            action_id: actionId,
            operator_id: 'Operator-Lead'
        });
        await selectIncident(activeIncidentId);
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

async function simulateAgencyAck(actionId) {
    if (!activeIncidentId) return;
    try {
        await API.post(`/api/incidents/${activeIncidentId}/simulate-ack`, {
            action_id: actionId,
            responder_ref: 'EMS-ALS-UNIT-108'
        });
        await selectIncident(activeIncidentId);
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

async function proposeAction(actionType, targetAgency) {
    if (!activeIncidentId) return alert('Select an active incident first.');
    try {
        await API.post(`/api/incidents/${activeIncidentId}/propose-action`, {
            action_type: actionType,
            target_agency: targetAgency
        });
        await selectIncident(activeIncidentId);
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

// ----------------- Failure Simulator Triggers -----------------
async function simulateCallerDisconnect() {
    if (!activeIncidentId) return alert('Select an active incident first.');
    try {
        await API.post(`/api/incidents/${activeIncidentId}/disconnect`, {
            reason: 'Abrupt line drop / tower cell handover loss'
        });
        await selectIncident(activeIncidentId);
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

async function simulateAIFailure() {
    if (!activeIncidentId) return alert('Select an active incident first.');
    try {
        await API.post(`/api/incidents/${activeIncidentId}/ai-failure`, {
            agent_name: 'Voice Intelligence Agent',
            error_msg: 'Upstream ASR WebSocket 504 Timeout'
        });
        await selectIncident(activeIncidentId);
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

async function simulateBackendRestart() {
    try {
        const res = await API.post('/api/recovery/restart-backend');
        alert(`Backend Restart & Durable Recovery Complete!\n${res.message}`);
        await loadIncidents();
        if (activeIncidentId) await selectIncident(activeIncidentId);
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

async function triggerDuplicateActionTest() {
    if (!activeIncidentId) return alert('Select an active incident first.');
    try {
        const key = `TEST-DUP-IDEMP-${Date.now()}`;
        // Call 1
        const r1 = await API.post(`/api/incidents/${activeIncidentId}/propose-action`, {
            action_type: 'DISPATCH_EMS',
            target_agency: '108 Ambulance',
            idempotency_key: key
        });
        // Call 2 with identical key
        const r2 = await API.post(`/api/incidents/${activeIncidentId}/propose-action`, {
            action_type: 'DISPATCH_EMS',
            target_agency: '108 Ambulance',
            idempotency_key: key
        });
        
        alert(`Duplicate Action Test Result:\nCall 1 Action ID: ${r1.action_id}\nCall 2 Action ID: ${r2.action_id}\nIdentical: ${r1.action_id === r2.action_id ? 'YES (Deduplication Successful!)' : 'NO'}`);
        await selectIncident(activeIncidentId);
    } catch (err) {
        alert('Error: ' + err.message);
    }
}

async function createNewIncident(category = 'Road Accident', lang = 'en') {
    try {
        const inc = await API.post('/api/incidents', { category, language: lang });
        await loadIncidents();
        selectIncident(inc.incident_id);
    } catch (err) {
        alert('Error creating incident: ' + err.message);
    }
}

// ----------------- 3-Minute Demonstration Runner -----------------
async function loadDemoSteps() {
    try {
        const steps = await API.get('/api/demo/steps');
        const container = document.getElementById('demo-steps-container');
        if (!container) return;
        container.innerHTML = '';

        steps.forEach(s => {
            const card = document.createElement('div');
            card.id = `demo-step-card-${s.step}`;
            card.className = `p-4 resq-card border border-slate-800 rounded-lg flex flex-col gap-2 transition cursor-pointer hover:border-cyan-500/60`;
            card.onclick = () => runDemoStep(s.step);

            card.innerHTML = `
                <div class="flex items-center justify-between">
                    <span class="font-mono text-xs font-bold text-cyan-400 bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-800">STEP ${s.step} • ${s.timeframe}</span>
                    <button class="px-3 py-1 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-xs font-semibold">Run Step</button>
                </div>
                <div class="text-sm font-bold text-slate-100">${s.title}</div>
                <div class="text-xs text-slate-400">${s.narrative}</div>
                <div id="demo-step-result-${s.step}" class="hidden mt-2 p-2.5 rounded bg-slate-900 border border-slate-800 font-mono text-xs text-slate-300"></div>
            `;
            container.appendChild(card);
        });
    } catch (err) {
        console.error('Failed to load demo steps:', err);
    }
}

async function runDemoStep(stepNumber) {
    try {
        const resBox = document.getElementById(`demo-step-result-${stepNumber}`);
        if (resBox) {
            resBox.classList.remove('hidden');
            resBox.innerHTML = `<span class="text-cyan-400"><i class="fas fa-spinner fa-spin mr-1"></i> Executing step ${stepNumber}...</span>`;
        }

        const res = await API.post(`/api/demo/step/${stepNumber}`, {});
        if (resBox) {
            resBox.innerHTML = `
                <div class="text-emerald-400 font-bold mb-1"><i class="fas fa-check-circle mr-1"></i> Step ${stepNumber} Succeeded</div>
                <div class="text-slate-300">${JSON.stringify(res, null, 2)}</div>
            `;
        }
        if (res.incident_id) {
            activeIncidentId = res.incident_id;
            await loadIncidents(false);
            selectIncident(res.incident_id);
        }
    } catch (err) {
        alert('Demo step error: ' + err.message);
    }
}

async function startAutoDemo() {
    let current = 1;
    const autoBtn = document.getElementById('btn-auto-demo');
    if (autoBtn) autoBtn.disabled = true;

    for (let i = 1; i <= 7; i++) {
        await runDemoStep(i);
        // Wait 3 seconds between steps
        await new Promise(r => setTimeout(r, 2800));
    }
    if (autoBtn) autoBtn.disabled = false;
    alert('3-Minute Demonstration sequence fully executed!');
}

// ----------------- 10 Required Test Scenarios Runner -----------------
async function loadScenarios() {
    try {
        const scenarios = await API.get('/api/scenarios');
        const container = document.getElementById('scenarios-container');
        if (!container) return;
        container.innerHTML = '';

        scenarios.forEach(s => {
            const card = document.createElement('div');
            card.id = `scenario-card-${s.id}`;
            card.className = 'p-4 resq-card border border-slate-800 rounded-lg flex flex-col gap-2';

            card.innerHTML = `
                <div class="flex items-center justify-between">
                    <span class="font-mono text-xs font-bold text-slate-400">${s.id}</span>
                    <span id="badge-${s.id}" class="px-2 py-0.5 rounded text-xs font-semibold bg-slate-800 text-slate-400">NOT RUN</span>
                </div>
                <div class="text-sm font-bold text-slate-100">${s.title}</div>
                <div class="text-xs text-slate-400">${s.description}</div>
                ${s.input_text ? `<div class="text-xs text-cyan-300 font-mono bg-slate-900 p-2 rounded border border-slate-800">"${s.input_text}"</div>` : ''}
                <div class="flex justify-between items-center mt-2 pt-2 border-t border-slate-800">
                    <button onclick="runSingleScenario('${s.id}')" class="px-3 py-1 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-xs font-semibold">Run Test</button>
                    <div id="result-${s.id}" class="text-xs text-slate-400 font-mono"></div>
                </div>
            `;
            container.appendChild(card);
        });
    } catch (err) {
        console.error('Failed to load scenarios:', err);
    }
}

async function runSingleScenario(scenarioId) {
    const badge = document.getElementById(`badge-${scenarioId}`);
    const resBox = document.getElementById(`result-${scenarioId}`);
    if (badge) {
        badge.className = 'px-2 py-0.5 rounded text-xs font-semibold bg-amber-900/60 text-amber-300';
        badge.innerText = 'RUNNING...';
    }

    try {
        const res = await API.post(`/api/scenarios/run/${scenarioId}`);
        if (badge) {
            badge.className = res.passed ? 'badge-verified font-bold' : 'badge-critical font-bold';
            badge.innerText = res.passed ? 'PASSED (100%)' : 'FAILED';
        }
        if (resBox) resBox.innerText = res.details || res.error || '';
    } catch (err) {
        if (badge) {
            badge.className = 'badge-critical font-bold';
            badge.innerText = 'ERROR';
        }
    }
}

async function runAllTestScenarios() {
    const runAllBtn = document.getElementById('btn-run-all-scenarios');
    if (runAllBtn) runAllBtn.disabled = true;

    try {
        const res = await API.post('/api/scenarios/run-all');
        const summaryEl = document.getElementById('scenarios-summary');
        if (summaryEl) {
            summaryEl.innerHTML = `
                <div class="p-3 bg-emerald-950/60 border border-emerald-500 text-emerald-300 rounded-lg text-sm font-bold flex items-center justify-between">
                    <span><i class="fas fa-check-double mr-2"></i> All ${res.total_scenarios} Scenarios Executed</span>
                    <span>Passed: ${res.total_passed}/${res.total_scenarios} (${res.pass_rate_pct}%)</span>
                </div>
            `;
        }
        res.results.forEach(r => {
            const badge = document.getElementById(`badge-${r.scenario_id}`);
            const resBox = document.getElementById(`result-${r.scenario_id}`);
            if (badge) {
                badge.className = r.passed ? 'badge-verified font-bold' : 'badge-critical font-bold';
                badge.innerText = r.passed ? 'PASSED (100%)' : 'FAILED';
            }
            if (resBox) resBox.innerText = r.details || r.error || '';
        });
    } catch (err) {
        alert('Error running all scenarios: ' + err.message);
    } finally {
        if (runAllBtn) runAllBtn.disabled = false;
    }
}

// ----------------- Baseline Evaluation & Benchmarks -----------------
async function loadBenchmarks() {
    try {
        const data = await API.get('/api/evaluation/benchmarks');
        const tbody = document.getElementById('benchmarks-tbody');
        if (tbody) {
            tbody.innerHTML = '';
            data.metrics.forEach(m => {
                const tr = document.createElement('tr');
                tr.className = 'border-b border-slate-800 text-xs';
                tr.innerHTML = `
                    <td class="py-3 px-4 font-semibold text-slate-200">${m.metric}</td>
                    <td class="py-3 px-4 text-cyan-400 font-mono">${m.proposed_target}</td>
                    <td class="py-3 px-4 text-slate-400">${m.baseline_a}</td>
                    <td class="py-3 px-4 text-slate-400">${m.baseline_b}</td>
                    <td class="py-3 px-4 font-bold text-emerald-400 bg-emerald-950/20">${m.resq_4}</td>
                    <td class="py-3 px-4"><span class="badge-verified px-2 py-0.5 rounded text-[11px] font-bold">${m.status}</span></td>
                `;
                tbody.appendChild(tr);
            });
        }

        const fbody = document.getElementById('features-tbody');
        if (fbody) {
            fbody.innerHTML = '';
            data.feature_matrix.forEach(f => {
                const tr = document.createElement('tr');
                tr.className = 'border-b border-slate-800 text-xs';
                tr.innerHTML = `
                    <td class="py-3 px-4 font-bold text-slate-300">${f.feature}</td>
                    <td class="py-3 px-4 text-slate-400">${f.baseline_a}</td>
                    <td class="py-3 px-4 text-slate-400">${f.baseline_b}</td>
                    <td class="py-3 px-4 text-cyan-300 font-semibold bg-cyan-950/20">${f.resq_4}</td>
                `;
                fbody.appendChild(tr);
            });
        }
    } catch (err) {
        console.error('Failed to load benchmarks:', err);
    }
}
