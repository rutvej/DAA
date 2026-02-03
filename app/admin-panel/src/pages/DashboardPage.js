import React, { useState, useEffect, useContext } from 'react';
import { AuthContext } from '../contexts/AuthContext';
import { logsApi, healthApi } from '../services/api';

const DashboardPage = () => {
  const { token } = useContext(AuthContext);
  const [dashboardData, setDashboardData] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchData = async () => {
      setError('');
      try {
        const [logsResponse, healthResponse] = await Promise.all([
          logsApi.list({ token, limit: 50 }),
          healthApi.list({ token }),
        ]);

        const logs = Array.isArray(logsResponse) ? logsResponse : [];
        const health = Array.isArray(healthResponse) ? healthResponse : [];

        const counts = logs.reduce(
          (acc, log) => {
            const status = (log.status || '').toLowerCase();
            if (status.includes('pending')) acc.pending += 1;
            else if (status.includes('progress')) acc.inProgress += 1;
            else if (status.includes('complete')) acc.completed += 1;
            else if (status.includes('fail')) acc.failed += 1;
            else acc.other += 1;
            return acc;
          },
          { pending: 0, inProgress: 0, completed: 0, failed: 0, other: 0 }
        );

        setDashboardData({
          counts,
          recentLogs: logs.slice(0, 6),
          health,
        });
      } catch (err) {
        setError(err.message || 'Unable to load dashboard data.');
      }
    };
    fetchData();
  }, [token]);

  if (!dashboardData) {
    return <div className="page-state">{error ? error : 'Loading dashboard...'}</div>;
  }

  return (
    <div className="dashboard">
      <section className="page-header">
        <div>
          <p className="eyebrow">Overview</p>
          <h1>System dashboard</h1>
          <p className="subtle">A quick snapshot of logs, fixes, and service health.</p>
        </div>
        <div className="badge-row">
          <span className="badge badge-info">Last 50 logs</span>
          <span className="badge badge-ghost">Auto-refresh off</span>
        </div>
      </section>

      <div className="stats-grid">
        <div className="stat-card">
          <p className="stat-label">Pending</p>
          <p className="stat-value">{dashboardData.counts.pending}</p>
          <p className="stat-meta">Awaiting analysis</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">In progress</p>
          <p className="stat-value">{dashboardData.counts.inProgress}</p>
          <p className="stat-meta">Processing fixes</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Completed</p>
          <p className="stat-value">{dashboardData.counts.completed}</p>
          <p className="stat-meta">Ready to review</p>
        </div>
        <div className="stat-card">
          <p className="stat-label">Failed</p>
          <p className="stat-value">{dashboardData.counts.failed}</p>
          <p className="stat-meta">Needs attention</p>
        </div>
      </div>

      <div className="card-grid">
        <div className="panel-card">
          <div className="panel-header">
            <h3>Recent logs</h3>
            <span className="panel-meta">Showing latest six</span>
          </div>
          <table className="log-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Status</th>
                <th>Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {dashboardData.recentLogs.map((log) => (
                <tr key={log.id}>
                  <td>{log.id}</td>
                  <td>
                    <span className={`status-pill status-${(log.status || 'unknown').toLowerCase().replace(/\\s+/g, '-')}`}>
                      {log.status || 'Unknown'}
                    </span>
                  </td>
                  <td>{log.timestamp || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="panel-card">
          <div className="panel-header">
            <h3>System health</h3>
            <span className="panel-meta">Live service status</span>
          </div>
          <div className="health-list">
            {dashboardData.health.map((service) => (
              <div className="health-item" key={service.serviceName}>
                <div>
                  <p className="health-title">{service.serviceName}</p>
                  <p className="health-meta">{service.lastChecked || 'Recently checked'}</p>
                </div>
                <span className={`status-pill status-${(service.status || 'unknown').toLowerCase()}`}>
                  {service.status || 'Unknown'}
                </span>
              </div>
            ))}
            {dashboardData.health.length === 0 ? (
              <p className="empty-state">No health data available.</p>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
