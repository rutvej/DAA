import React, { useEffect, useState, useRef } from 'react';

const API = process.env.REACT_APP_API_URL || (window.location.protocol + '//' + window.location.hostname + ':8000');
const WS_BASE = API.replace(/^http/, 'ws');

const StatusBadge = ({ status }) => {
  const colors = {
    investigating: '#f59e0b',
    pr_open: '#3b82f6',
    resolved: '#22c55e',
    cooldown: '#8b5cf6',
    human_required: '#ef4444',
    escalated: '#ef4444',
    ticket_created: '#06b6d4',
  };
  return (
    <span style={{
      background: colors[status] || '#6b7280',
      color: '#fff',
      padding: '2px 10px',
      borderRadius: 12,
      fontSize: 12,
      fontWeight: 600,
      textTransform: 'uppercase',
      letterSpacing: 1,
    }}>
      {status?.replace('_', ' ')}
    </span>
  );
};

const LiveReActTerminal = ({ incidentId, appName }) => {
  const [steps, setSteps] = useState([]);
  const [status, setStatus] = useState('connecting');
  const [isPaused, setIsPaused] = useState(false);
  const bottomRef = useRef(null);
  const wsRef = useRef(null);

  useEffect(() => {
    let ws = new WebSocket(`${WS_BASE}/status/incidents/${incidentId}/stream`);
    wsRef.current = ws;

    ws.onopen = () => setStatus('connected');
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'heartbeat') return;
        if (data.type === 'error') {
          setStatus('error');
          return;
        }
        setSteps(prev => [...prev, data]);
      } catch (e) {
        // ignore malformed packet
      }
    };
    ws.onerror = () => {
      if (ws.readyState !== WebSocket.OPEN) {
        const fallbackWs = new WebSocket(`${WS_BASE}/api/v1/incidents/${incidentId}/stream`);
        wsRef.current = fallbackWs;
        fallbackWs.onopen = () => setStatus('connected');
        fallbackWs.onmessage = ws.onmessage;
        fallbackWs.onclose = () => setStatus('disconnected');
      } else {
        setStatus('error');
      }
    };
    ws.onclose = () => setStatus('disconnected');

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, [incidentId]);

  useEffect(() => {
    if (!isPaused && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [steps, isPaused]);

  const getStepIcon = (type) => {
    switch (type) {
      case 'tool_call': return '🛠️';
      case 'observation': return '👁️';
      case 'finished': return '🏁';
      default: return '🤖';
    }
  };

  const getStepColor = (type) => {
    switch (type) {
      case 'tool_call': return '#60a5fa';
      case 'observation': return '#34d399';
      case 'finished': return '#c084fc';
      default: return '#fbbf24';
    }
  };

  return (
    <div style={{
      background: '#0d1117', border: '1px solid #30363d', borderRadius: 10,
      marginTop: 16, overflow: 'hidden', fontFamily: "'Fira Code', 'JetBrains Mono', 'Courier New', monospace",
      color: '#c9d1d9', fontSize: 13, boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
      gridColumn: '1/-1',
    }}>
      <div style={{
        background: '#161b22', padding: '10px 16px', display: 'flex',
        justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #30363d'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#ff5f56' }} />
          <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#ffbd2e' }} />
          <div style={{ width: 12, height: 12, borderRadius: '50%', background: '#27c93f' }} />
          <span style={{ marginLeft: 8, fontWeight: 700, color: '#f0f6fc', fontSize: 12, letterSpacing: 0.5 }}>
            ⚡ ReAct Streamer: {appName}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 11 }}>
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            color: status === 'connected' ? '#34d399' : status === 'connecting' ? '#fbbf24' : '#ef4444',
            background: 'rgba(255,255,255,0.05)', padding: '3px 8px', borderRadius: 6
          }}>
            <span style={{
              width: 6, height: 6, borderRadius: '50%',
              background: status === 'connected' ? '#34d399' : status === 'connecting' ? '#fbbf24' : '#ef4444',
              display: 'inline-block'
            }} />
            {status.toUpperCase()}
          </span>
          <button
            onClick={() => setIsPaused(!isPaused)}
            style={{
              background: isPaused ? '#f59e0b' : 'transparent', color: isPaused ? '#000' : '#8b949e',
              border: '1px solid #30363d', borderRadius: 4, padding: '2px 8px', cursor: 'pointer',
              fontSize: 11, fontWeight: 600
            }}
          >
            {isPaused ? '▶ Resume Auto-Scroll' : '⏸ Pause Scroll'}
          </button>
          <button
            onClick={() => setSteps([])}
            style={{
              background: 'transparent', color: '#8b949e', border: '1px solid #30363d',
              borderRadius: 4, padding: '2px 8px', cursor: 'pointer', fontSize: 11
            }}
          >
            Clear
          </button>
        </div>
      </div>

      <div style={{ padding: 16, maxHeight: 380, overflowY: 'auto' }}>
        {steps.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '32px 0', color: '#8b949e' }}>
            <div style={{ fontSize: 24, marginBottom: 8 }}>⏳</div>
            <p style={{ margin: 0 }}>Waiting for live ReAct thought steps (`Thought -> Tool Call -> Observation`)...</p>
            <p style={{ margin: '4px 0 0', fontSize: 11 }}>The agent reasoning stream will appear here in real time.</p>
          </div>
        ) : (
          steps.map((step, idx) => (
            <div key={idx} style={{
              marginBottom: 14, paddingBottom: 14,
              borderBottom: idx === steps.length - 1 ? 'none' : '1px dashed rgba(255,255,255,0.08)'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <span style={{ fontWeight: 700, color: getStepColor(step.type), display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span>{getStepIcon(step.type)}</span>
                  <span style={{ textTransform: 'uppercase', fontSize: 11, letterSpacing: 0.8 }}>
                    {step.type.replace('_', ' ')}
                  </span>
                  {step.tool && <span style={{ color: '#f0f6fc', background: '#1f2937', padding: '1px 6px', borderRadius: 4, fontSize: 11 }}>{step.tool}</span>}
                </span>
                <span style={{ fontSize: 11, color: '#6e7681' }}>
                  {step.timestamp || ''} {step.elapsed_ms ? `(+${step.elapsed_ms}ms)` : ''}
                </span>
              </div>

              {step.type === 'tool_call' && (
                <div>
                  {step.thought && <p style={{ margin: '0 0 8px 0', color: '#fbbf24', fontSize: 12 }}>{step.thought}</p>}
                  {step.tool_input && (
                    <pre style={{
                      margin: 0, background: '#161b22', padding: 10, borderRadius: 6,
                      border: '1px solid #21262d', overflowX: 'auto', color: '#7ee787', fontSize: 12
                    }}>
                      {step.tool_input}
                    </pre>
                  )}
                </div>
              )}

              {step.type === 'observation' && (
                <pre style={{
                  margin: 0, background: '#161b22', padding: 10, borderRadius: 6,
                  border: '1px solid #21262d', overflowX: 'auto', color: '#a5d6ff', fontSize: 12,
                  maxHeight: 200, overflowY: 'auto'
                }}>
                  {step.observation}
                </pre>
              )}

              {step.type === 'finished' && (
                <div style={{
                  background: 'rgba(192, 132, 252, 0.1)', border: '1px solid rgba(192, 132, 252, 0.3)',
                  padding: 12, borderRadius: 6, color: '#e879f9'
                }}>
                  {step.summary}
                </div>
              )}

              {step.type === 'thought' && (
                <p style={{ margin: 0, color: '#fbbf24', lineHeight: 1.5 }}>
                  {step.thought}
                </p>
              )}
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
};

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(null);
  const [activeStreamerId, setActiveStreamerId] = useState(null);

  const token = localStorage.getItem('token');

  const fetchIncidents = () => {
    setLoading(true);
    fetch(`${API}/incidents/`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.json())
      .then(data => { setIncidents(Array.isArray(data) ? data : []); setLoading(false); })
      .catch(() => { setError('Failed to load incidents'); setLoading(false); });
  };

  useEffect(() => {
    fetchIncidents();
    const interval = setInterval(fetchIncidents, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{ padding: 32 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700 }}>Active Incidents</h1>
          <p style={{ margin: '4px 0 0', color: '#6b7280', fontSize: 14 }}>
            Live SHA256-Debugging incident tracker · auto-refreshes every 10s
          </p>
        </div>
        <button onClick={fetchIncidents} style={{
          background: '#3b82f6', color: '#fff', border: 'none',
          padding: '8px 18px', borderRadius: 8, cursor: 'pointer', fontWeight: 600,
        }}>
          Refresh
        </button>
      </div>

      {loading && <p style={{ color: '#6b7280' }}>Loading incidents…</p>}
      {error && <p style={{ color: '#ef4444' }}>{error}</p>}

      {!loading && incidents.length === 0 && (
        <div style={{
          textAlign: 'center', padding: '64px 32px',
          border: '2px dashed #e5e7eb', borderRadius: 12, color: '#9ca3af',
        }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>✅</div>
          <p style={{ margin: 0, fontWeight: 600 }}>No active incidents</p>
          <p style={{ margin: '8px 0 0', fontSize: 14 }}>All systems are operating normally.</p>
        </div>
      )}

      <div style={{ display: 'grid', gap: 16 }}>
        {incidents.map(inc => (
          <div
            key={inc.id}
            onClick={() => setSelected(selected?.id === inc.id ? null : inc)}
            style={{
              background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12,
              padding: 20, cursor: 'pointer',
              boxShadow: selected?.id === inc.id ? '0 0 0 2px #3b82f6' : 'none',
              transition: 'box-shadow 0.15s',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                  <span style={{ fontWeight: 700, fontSize: 16 }}>{inc.app_name}</span>
                  <StatusBadge status={inc.status} />
                </div>
                <div style={{ fontSize: 13, color: '#6b7280', fontFamily: 'monospace' }}>
                  SHA256: {inc.fingerprint?.slice(0, 24)}…
                </div>
              </div>
              <div style={{ textAlign: 'right', fontSize: 13 }}>
                <div style={{ fontWeight: 700, fontSize: 20, color: inc.occurrence_count > 5 ? '#ef4444' : '#111' }}>
                  {inc.occurrence_count}
                </div>
                <div style={{ color: '#9ca3af' }}>occurrences</div>
              </div>
            </div>

            {selected?.id === inc.id && (
              <div style={{
                marginTop: 16, paddingTop: 16, borderTop: '1px solid #f3f4f6',
                display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: 13,
              }}>
                <div><b>ID:</b> <span style={{ fontFamily: 'monospace', fontSize: 11 }}>{inc.id}</span></div>
                <div><b>Agent Attempts:</b> {inc.agent_attempts ?? 0}</div>
                <div><b>First Seen:</b> {inc.first_seen_at ? new Date(inc.first_seen_at).toLocaleString() : '—'}</div>
                <div><b>Last Seen:</b> {inc.last_seen_at ? new Date(inc.last_seen_at).toLocaleString() : '—'}</div>
                {inc.pr_url && (
                  <div style={{ gridColumn: '1/-1' }}>
                    <b>PR:</b>{' '}
                    <a href={inc.pr_url} target="_blank" rel="noreferrer" style={{ color: '#3b82f6' }}>
                      {inc.pr_url}
                    </a>
                  </div>
                )}
                {inc.ticket_url && (
                  <div style={{ gridColumn: '1/-1' }}>
                    <b>Ticket:</b>{' '}
                    <a href={inc.ticket_url} target="_blank" rel="noreferrer" style={{ color: '#f59e0b' }}>
                      {inc.ticket_url}
                    </a>
                  </div>
                )}
                {inc.root_cause_summary && (
                  <div style={{ gridColumn: '1/-1' }}>
                    <b>Root Cause:</b>
                    <p style={{ margin: '4px 0 0', color: '#374151', lineHeight: 1.5 }}>
                      {inc.root_cause_summary}
                    </p>
                  </div>
                )}

                <div style={{ gridColumn: '1/-1', marginTop: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <button
                    onClick={(e) => { e.stopPropagation(); setActiveStreamerId(activeStreamerId === inc.id ? null : inc.id); }}
                    style={{
                      background: activeStreamerId === inc.id ? '#ef4444' : '#10b981',
                      color: '#fff', border: 'none', padding: '6px 14px', borderRadius: 6,
                      fontWeight: 600, cursor: 'pointer', fontSize: 13, display: 'flex', alignItems: 'center', gap: 6,
                      boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
                    }}
                  >
                    <span>⚡</span>
                    <span>{activeStreamerId === inc.id ? 'Close Live ReAct Terminal' : 'Open Live ReAct Terminal (ReAct Streamer)'}</span>
                  </button>
                </div>

                {activeStreamerId === inc.id && (
                  <LiveReActTerminal incidentId={inc.id} appName={inc.app_name} />
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
