import React, { useState, useEffect, useContext } from 'react';
import { useParams, Link } from 'react-router-dom';
import { AuthContext } from '../contexts/AuthContext';
import { logsApi } from '../services/api';

const LogDetailsPage = () => {
  const { token } = useContext(AuthContext);
  const { id } = useParams();
  const [log, setLog] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchLog = async () => {
      setError('');
      try {
        const data = await logsApi.get({ token, id });
        setLog(data);
      } catch (err) {
        setError(err.message || 'Unable to load log.');
      }
    };
    fetchLog();
  }, [token, id]);

  if (!log) {
    return <div className="page-state">{error ? error : 'Loading log...'}</div>;
  }

  return (
    <div className="details-page">
      <section className="page-header">
        <div>
          <p className="eyebrow">Log details</p>
          <h1>Log {log.id}</h1>
          <p className="subtle">Full payload and status context for review.</p>
        </div>
        <div className="badge-row">
          <span className={`badge badge-status status-${(log.status || 'unknown').toLowerCase().replace(/\\s+/g, '-')}`}>
            {log.status || 'Unknown'}
          </span>
          {log.fixId ? (
            <Link className="primary-btn" to={`/fix/${log.fixId}`}>
              View fix
            </Link>
          ) : null}
        </div>
      </section>

      <div className="panel-card">
        <div className="detail-grid">
          <div>
            <p className="detail-label">Log ID</p>
            <p className="detail-value">{log.id}</p>
          </div>
          <div>
            <p className="detail-label">Status</p>
            <p className="detail-value">{log.status || 'Unknown'}</p>
          </div>
          <div>
            <p className="detail-label">Timestamp</p>
            <p className="detail-value">{log.timestamp || '—'}</p>
          </div>
        </div>
        <div className="detail-block">
          <p className="detail-label">Log content</p>
          <pre className="code-block">{log.content}</pre>
        </div>
      </div>
    </div>
  );
};

export default LogDetailsPage;
