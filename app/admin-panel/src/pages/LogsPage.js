import React, { useState, useEffect, useContext } from 'react';
import { AuthContext } from '../contexts/AuthContext';
import { Link } from 'react-router-dom';
import { logsApi } from '../services/api';

const LogsPage = () => {
  const { token } = useContext(AuthContext);
  const [logs, setLogs] = useState([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [limit] = useState(10);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchLogs = async () => {
      setIsLoading(true);
      setError('');
      try {
        const data = await logsApi.list({ token, page, limit, status: statusFilter || undefined });
        setLogs(Array.isArray(data) ? data : []);
      } catch (err) {
        setError(err.message || 'Unable to load logs.');
      } finally {
        setIsLoading(false);
      }
    };
    fetchLogs();
  }, [token, page, limit, statusFilter]);

  const filteredLogs = logs.filter((log) =>
    (log.id || '').toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div className="logs-page">
      <section className="page-header">
        <div>
          <p className="eyebrow">Log viewer</p>
          <h1>Logs</h1>
          <p className="subtle">Track ingestion, escalation, and suppression states.</p>
        </div>
        <div className="badge-row">
          <span className="badge badge-info">Page {page}</span>
          <span className="badge badge-ghost">{filteredLogs.length} results</span>
        </div>
      </section>
      <div className="filters">
        <input
          type="text"
          placeholder="Search by log id..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All Statuses</option>
          <option value="Logged (Threshold not reached)">Logged (Threshold not reached)</option>
          <option value="Escalated to Agent">Escalated to Agent</option>
          <option value="Suppressed (Debugging)">Suppressed (Debugging)</option>
        </select>
      </div>
      {isLoading ? (
        <div className="page-state">Loading logs...</div>
      ) : error ? (
        <div className="page-state">{error}</div>
      ) : (
        <table className="log-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Status</th>
              <th>Timestamp</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredLogs.map((log) => (
              <tr key={log.id}>
                <td>{log.id}</td>
                <td>
                  <span className={`status-pill status-${(log.status || 'unknown').toLowerCase().replace(/\\s+/g, '-')}`}>
                    {log.status || 'Unknown'}
                  </span>
                </td>
                <td>{log.timestamp || '—'}</td>
                <td>
                  <Link className="text-link" to={`/logs/${log.id}`}>
                    View Details
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="pagination">
        <button
          type="button"
          className="secondary-btn"
          onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
          disabled={page === 1}
        >
          Previous
        </button>
        <span className="pagination-meta">Page {page}</span>
        <button
          type="button"
          className="secondary-btn"
          onClick={() => setPage((prev) => prev + 1)}
          disabled={logs.length < limit}
        >
          Next
        </button>
      </div>
    </div>
  );
};

export default LogsPage;
