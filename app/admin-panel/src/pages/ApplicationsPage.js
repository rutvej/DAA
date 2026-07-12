import React, { useEffect, useState } from 'react';

const API = process.env.REACT_APP_API_URL || (window.location.protocol + '//' + window.location.hostname + ':8000');

const inputStyle = {
  width: '100%', padding: '8px 12px', border: '1px solid #d1d5db',
  borderRadius: 8, fontSize: 14, boxSizing: 'border-box', marginTop: 4,
};

const labelStyle = { fontSize: 13, fontWeight: 600, color: '#374151', display: 'block', marginTop: 12 };

export default function ApplicationsPage() {
  const [apps, setApps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);

  const token = localStorage.getItem('token');

  const [form, setForm] = useState({
    name: '', description: '', language: 'python', repository_url: '', allowed_ip: '',
    threshold: '3', window_seconds: '60', cooldown_minutes: '30',
    severity_keywords: 'FATAL,OOMKill,DatabaseDeadlock',
  });

  const fetchApps = () => {
    setLoading(true);
    fetch(`${API}/applications/`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(d => { setApps(Array.isArray(d) ? d : []); setLoading(false); })
      .catch(() => { setError('Failed to load applications'); setLoading(false); });
  };

  useEffect(() => { fetchApps(); }, []);

  const handleChange = e => setForm(f => ({ ...f, [e.target.name]: e.target.value }));

  const handleSubmit = async e => {
    e.preventDefault();
    setSubmitting(true);
    setError('');
    setSuccess('');
    try {
      // 1. Create application
      const appRes = await fetch(`${API}/applications/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          name: form.name.trim(),
          description: form.description.trim(),
          language: form.language,
          repository_url: form.repository_url.trim(),
          allowed_ip: form.allowed_ip.trim() || null,
        }),
      });
      if (!appRes.ok) {
        const body = await appRes.json();
        throw new Error(body.detail || `HTTP ${appRes.status}`);
      }
      const app = await appRes.json();

      // 2. Create escalation policy
      await fetch(`${API}/applications/${app.id}/escalation-policies`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          rule_type: 'error_rate_threshold',
          condition_value: parseInt(form.threshold, 10),
          window_seconds: parseInt(form.window_seconds, 10),
          cooldown_minutes: parseInt(form.cooldown_minutes, 10),
          severity_keywords: JSON.stringify(form.severity_keywords.split(',').map(s => s.trim())),
        }),
      });

      setSuccess(`✅ Registered "${form.name}" with escalation policy.`);
      setShowForm(false);
      setForm({ name: '', description: '', language: 'python', repository_url: '', allowed_ip: '', threshold: '3', window_seconds: '60', cooldown_minutes: '30', severity_keywords: 'FATAL,OOMKill,DatabaseDeadlock' });
      fetchApps();
    } catch (ex) {
      setError(ex.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ padding: 32 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700 }}>Applications</h1>
          <p style={{ margin: '4px 0 0', color: '#6b7280', fontSize: 14 }}>
            Register services and set escalation thresholds for autonomous SRE coverage
          </p>
        </div>
        <button
          onClick={() => { setShowForm(!showForm); setError(''); setSuccess(''); }}
          style={{
            background: showForm ? '#6b7280' : '#3b82f6', color: '#fff',
            border: 'none', padding: '8px 18px', borderRadius: 8, cursor: 'pointer', fontWeight: 600,
          }}>
          {showForm ? 'Cancel' : '+ Register Application'}
        </button>
      </div>

      {success && <div style={{ background: '#d1fae5', border: '1px solid #6ee7b7', borderRadius: 8, padding: '10px 16px', marginBottom: 16, fontSize: 14 }}>{success}</div>}
      {error && <div style={{ background: '#fee2e2', border: '1px solid #fca5a5', borderRadius: 8, padding: '10px 16px', marginBottom: 16, fontSize: 14 }}>❌ {error}</div>}

      {showForm && (
        <form onSubmit={handleSubmit} style={{
          background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12,
          padding: 24, marginBottom: 24,
        }}>
          <h3 style={{ margin: '0 0 16px', fontSize: 16 }}>New Application</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 24px' }}>
            <div>
              <label style={labelStyle}>Service Name *</label>
              <input name="name" required value={form.name} onChange={handleChange} placeholder="checkout-service" style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>Language</label>
              <select name="language" value={form.language} onChange={handleChange} style={inputStyle}>
                {['python', 'node', 'go', 'java', 'ruby', 'dotnet'].map(l => <option key={l}>{l}</option>)}
              </select>
            </div>
            <div style={{ gridColumn: '1/-1' }}>
              <label style={labelStyle}>Repository URL</label>
              <input name="repository_url" value={form.repository_url} onChange={handleChange} placeholder="https://github.com/org/repo" style={inputStyle} />
            </div>
            <div style={{ gridColumn: '1/-1' }}>
              <label style={labelStyle}>Description</label>
              <input name="description" value={form.description} onChange={handleChange} placeholder="Handles e-commerce checkout and payments" style={inputStyle} />
            </div>
            <div style={{ gridColumn: '1/-1' }}>
              <label style={labelStyle}>Allowed Application IP (CORS & telemetry access restriction)</label>
              <input name="allowed_ip" value={form.allowed_ip} onChange={handleChange} placeholder="e.g. 192.168.1.41 (Leave blank to allow any IP)" style={inputStyle} />
            </div>
          </div>

          <h4 style={{ margin: '20px 0 4px', color: '#374151' }}>Escalation Policy</h4>
          <p style={{ margin: '0 0 12px', fontSize: 13, color: '#6b7280' }}>
            DAA will escalate to the agent after <b>N errors</b> in <b>W seconds</b>. Identical errors are SHA256-Debugging.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0 16px' }}>
            <div>
              <label style={labelStyle}>Escalate after N errors</label>
              <input name="threshold" type="number" min="1" value={form.threshold} onChange={handleChange} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>Within seconds</label>
              <input name="window_seconds" type="number" min="10" value={form.window_seconds} onChange={handleChange} style={inputStyle} />
            </div>
            <div>
              <label style={labelStyle}>Cooldown (minutes)</label>
              <input name="cooldown_minutes" type="number" min="1" value={form.cooldown_minutes} onChange={handleChange} style={inputStyle} />
            </div>
            <div style={{ gridColumn: '1/-1' }}>
              <label style={labelStyle}>Severity keywords (comma-separated — trigger immediately)</label>
              <input name="severity_keywords" value={form.severity_keywords} onChange={handleChange} placeholder="FATAL,OOMKill,DatabaseDeadlock" style={inputStyle} />
            </div>
          </div>

          <button
            type="submit"
            disabled={submitting}
            style={{
              marginTop: 20, background: submitting ? '#9ca3af' : '#3b82f6',
              color: '#fff', border: 'none', padding: '10px 24px',
              borderRadius: 8, cursor: submitting ? 'not-allowed' : 'pointer', fontWeight: 700,
            }}>
            {submitting ? 'Registering…' : 'Register Application'}
          </button>
        </form>
      )}

      {loading && <p style={{ color: '#6b7280' }}>Loading applications…</p>}

      {!loading && apps.length === 0 && !showForm && (
        <div style={{
          textAlign: 'center', padding: '64px 32px',
          border: '2px dashed #e5e7eb', borderRadius: 12, color: '#9ca3af',
        }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>🔌</div>
          <p style={{ margin: 0, fontWeight: 600 }}>No applications registered yet</p>
          <p style={{ margin: '8px 0 16px', fontSize: 14 }}>Register your first microservice to start autonomous SRE coverage.</p>
          <button onClick={() => setShowForm(true)} style={{
            background: '#3b82f6', color: '#fff', border: 'none',
            padding: '10px 24px', borderRadius: 8, cursor: 'pointer', fontWeight: 600,
          }}>
            Register First Application
          </button>
        </div>
      )}

      <div style={{ display: 'grid', gap: 12 }}>
        {apps.map(app => (
          <div key={app.id} style={{
            background: '#fff', border: '1px solid #e5e7eb',
            borderRadius: 12, padding: '16px 20px',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 4 }}>{app.name}</div>
              <div style={{ fontSize: 13, color: '#6b7280' }}>
                {app.language && <span style={{ marginRight: 16 }}>🔤 {app.language}</span>}
                {app.repository_url && <span style={{ marginRight: 16 }}>📁 {app.repository_url}</span>}
                {app.allowed_ip && <span style={{ color: '#b91c1c', fontWeight: 600 }}>🔒 IP Restriction: {app.allowed_ip}</span>}
                {!app.allowed_ip && <span style={{ color: '#6b7280' }}>🔓 IP Restriction: None (Any IP)</span>}
              </div>
              {app.description && <div style={{ fontSize: 13, color: '#9ca3af', marginTop: 4 }}>{app.description}</div>}
              {app.token && (
                <div style={{ fontSize: 12, color: '#16a34a', marginTop: 6, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontWeight: 600 }}>🔑 SDK Token:</span>
                  <input readOnly value={app.token} onClick={e => e.target.select()} style={{
                    fontSize: 11, padding: '2px 6px', border: '1px solid #e5e7eb', borderRadius: 4, width: 350, background: '#f9fafb', fontFamily: 'monospace'
                  }} />
                </div>
              )}
            </div>
            <div style={{ textAlign: 'right', fontSize: 13, color: '#6b7280' }}>
              <div style={{
                background: '#eff6ff', color: '#1d4ed8',
                padding: '4px 10px', borderRadius: 8, fontWeight: 600,
              }}>
                {app.escalation_policies?.length ?? 0} policy
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
