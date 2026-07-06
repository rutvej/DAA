import React, { useEffect, useState } from 'react';

const API = process.env.REACT_APP_API_URL || (window.location.protocol + '//' + window.location.hostname + ':8000');

const StatusBadge = ({ status }) => {
  const colors = {
    investigating: '#f59e0b',
    pr_open: '#3b82f6',
    resolved: '#22c55e',
    cooldown: '#8b5cf6',
    human_required: '#ef4444',
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

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(null);

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
            Live SHA256-deduplicated incident tracker · auto-refreshes every 10s
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
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
