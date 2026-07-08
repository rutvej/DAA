import React, { useState, useEffect, useContext } from 'react';
import { AuthContext } from '../contexts/AuthContext';

const API = process.env.REACT_APP_API_URL || (window.location.protocol + '//' + window.location.hostname + ':8000');

const DashboardPage = () => {
  const { token } = useContext(AuthContext);
  const [stats, setStats] = useState(null);
  const [error, setError] = useState('');

  const fetchDashboardData = async () => {
    setError('');
    try {
      const res = await fetch(`${API}/dashboard`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        throw new Error('Failed to fetch dashboard data');
      }
      const data = await res.json();
      setStats(data);
    } catch (err) {
      setError(err.message || 'Unable to load dashboard data.');
    }
  };

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 10000);
    return () => clearInterval(interval);
  }, [token]);

  if (!stats) {
    return <div className="page-state">{error ? error : 'Loading dashboard...'}</div>;
  }

  return (
    <div className="dashboard" style={{ padding: 32 }}>
      <section className="page-header" style={{ marginBottom: 24 }}>
        <div>
          <p className="eyebrow" style={{ color: '#3b82f6', textTransform: 'uppercase', fontSize: 12, fontWeight: 700, margin: 0 }}>Overview</p>
          <h1 style={{ fontSize: 28, fontWeight: 800, margin: '4px 0 0' }}>DAA SRE Control Center</h1>
          <p className="subtle" style={{ color: '#6b7280', margin: '4px 0 0' }}>Real-time telemetry, auto-diagnosis, and closed-loop remediation status.</p>
        </div>
      </section>

      <div className="stats-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 20, marginBottom: 32 }}>
        <div className="stat-card" style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 20 }}>
          <p className="stat-label" style={{ color: '#ef4444', fontWeight: 600, fontSize: 14, margin: 0 }}>Active Incidents</p>
          <p className="stat-value" style={{ fontSize: 32, fontWeight: 800, margin: '8px 0 0' }}>{stats.active_incidents}</p>
          <p className="stat-meta" style={{ color: '#6b7280', fontSize: 12, margin: '4px 0 0' }}>Under investigation</p>
        </div>
        <div className="stat-card" style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 20 }}>
          <p className="stat-label" style={{ color: '#3b82f6', fontWeight: 600, fontSize: 14, margin: 0 }}>Open PRs</p>
          <p className="stat-value" style={{ fontSize: 32, fontWeight: 800, margin: '8px 0 0' }}>{stats.open_prs}</p>
          <p className="stat-meta" style={{ color: '#6b7280', fontSize: 12, margin: '4px 0 0' }}>Fixes proposed to Git</p>
        </div>
        <div className="stat-card" style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 20 }}>
          <p className="stat-label" style={{ color: '#22c55e', fontWeight: 600, fontSize: 14, margin: 0 }}>Fix Success Rate</p>
          <p className="stat-value" style={{ fontSize: 32, fontWeight: 800, margin: '8px 0 0' }}>{stats.fix_rate_percent}%</p>
          <p className="stat-meta" style={{ color: '#6b7280', fontSize: 12, margin: '4px 0 0' }}>Auto-remediation rate</p>
        </div>
        <div className="stat-card" style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 20 }}>
          <p className="stat-label" style={{ color: '#f59e0b', fontWeight: 600, fontSize: 14, margin: 0 }}>Firing Alerts</p>
          <p className="stat-value" style={{ fontSize: 32, fontWeight: 800, margin: '8px 0 0' }}>{stats.active_alerts}</p>
          <p className="stat-meta" style={{ color: '#6b7280', fontSize: 12, margin: '4px 0 0' }}>Prometheus webhooks</p>
        </div>
      </div>

      <div className="card-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: 24 }}>
        <div className="panel-card" style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 24 }}>
          <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>Recent Incidents</h3>
            <span className="panel-meta" style={{ color: '#6b7280', fontSize: 13 }}>Real-time feed</span>
          </div>
          <table className="log-table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
                <th style={{ padding: '8px 0', color: '#374151' }}>App</th>
                <th style={{ padding: '8px 0', color: '#374151' }}>Status</th>
                <th style={{ padding: '8px 0', color: '#374151', textAlign: 'right' }}>Errors</th>
              </tr>
            </thead>
            <tbody>
              {stats.recent_incidents.map((inc) => (
                <tr key={inc.id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                  <td style={{ padding: '12px 0', fontWeight: 600 }}>{inc.app_name}</td>
                  <td style={{ padding: '12px 0' }}>
                    <span style={{
                      background: inc.status === 'resolved' ? '#d1fae5' : (inc.status === 'investigating' ? '#fef3c7' : (inc.status === 'escalated' || inc.status === 'human_required' ? '#fee2e2' : '#e5e7eb')),
                      color: inc.status === 'resolved' ? '#065f46' : (inc.status === 'investigating' ? '#92400e' : (inc.status === 'escalated' || inc.status === 'human_required' ? '#991b1b' : '#374151')),
                      padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700, textTransform: 'uppercase'
                    }}>
                      {inc.status}
                    </span>
                  </td>
                  <td style={{ padding: '12px 0', textAlign: 'right', fontWeight: 700 }}>{inc.occurrence_count}</td>
                </tr>
              ))}
              {stats.recent_incidents.length === 0 && (
                <tr>
                  <td colSpan="3" style={{ padding: '24px 0', textAlign: 'center', color: '#9ca3af' }}>No incidents logged yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="panel-card" style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 24 }}>
          <div className="panel-header" style={{ marginBottom: 16 }}>
            <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>System Summary</h3>
            <span className="panel-meta" style={{ color: '#6b7280', fontSize: 13 }}>DAA cluster health</span>
          </div>
          <div style={{ display: 'grid', gap: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #f3f4f6', paddingBottom: 10 }}>
              <span style={{ color: '#374151' }}>Total Logs Aggregated</span>
              <span style={{ fontWeight: 700 }}>{stats.total_logs}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #f3f4f6', paddingBottom: 10 }}>
              <span style={{ color: '#374151' }}>Total Incidents Escalated</span>
              <span style={{ fontWeight: 700 }}>{stats.total_incidents}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #f3f4f6', paddingBottom: 10 }}>
              <span style={{ color: '#374151' }}>Total Resolved via PR</span>
              <span style={{ fontWeight: 700 }}>{stats.resolved_incidents}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: 10 }}>
              <span style={{ color: '#374151' }}>Incident Deduplication Ratio</span>
              <span style={{ fontWeight: 700, color: '#22c55e' }}>
                {stats.total_logs > 0 ? `${round((1 - stats.total_incidents / stats.total_logs) * 100, 1)}%` : '0%'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

function round(value, precision) {
  var multiplier = Math.pow(10, precision || 0);
  return Math.round(value * multiplier) / multiplier;
}

export default DashboardPage;
