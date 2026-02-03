import React, { useState, useEffect, useContext } from 'react';
import { useParams, Link } from 'react-router-dom';
import { AuthContext } from '../contexts/AuthContext';
import { fixesApi, logsApi } from '../services/api';

const FixViewerPage = () => {
  const { token } = useContext(AuthContext);
  const { id } = useParams();
  const [fix, setFix] = useState(null);
  const [log, setLog] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchFix = async () => {
      setError('');
      try {
        const data = await fixesApi.get({ token, id });
        setFix(data);
        if (data.logId) {
          const logData = await logsApi.get({ token, id: data.logId });
          setLog(logData);
        }
      } catch (err) {
        setError(err.message || 'Unable to load fix.');
      }
    };
    fetchFix();
  }, [token, id]);

  if (!fix) {
    return <div className="page-state">{error ? error : 'Loading fix...'}</div>;
  }

  return (
    <div className="fix-viewer">
      <section className="page-header">
        <div>
          <p className="eyebrow">Fix review</p>
          <h1>Fix {fix.id}</h1>
          <p className="subtle">Generated remediation and linked log context.</p>
        </div>
        <div className="badge-row">
          {fix.logId ? (
            <Link className="secondary-btn" to={`/logs/${fix.logId}`}>
              View log
            </Link>
          ) : null}
        </div>
      </section>
      <div className="fix-columns">
        <div className="panel-card">
          <div className="panel-header">
            <h3>Log context</h3>
            <span className="panel-meta">{log ? `Log ${log.id}` : 'No log data'}</span>
          </div>
          {log ? (
            <div className="detail-block">
              <p className="detail-label">Status</p>
              <p className="detail-value">{log.status || 'Unknown'}</p>
              <p className="detail-label">Timestamp</p>
              <p className="detail-value">{log.timestamp || '—'}</p>
              <p className="detail-label">Log content</p>
              <pre className="code-block">{log.content}</pre>
            </div>
          ) : (
            <p className="empty-state">Log details are unavailable.</p>
          )}
        </div>
        <div className="panel-card">
          <div className="panel-header">
            <h3>Generated fix</h3>
            <span className="panel-meta">Review carefully before applying</span>
          </div>
          <pre className="code-block">{fix.generatedFix || 'No fix content available.'}</pre>
        </div>
      </div>
    </div>
  );
};

export default FixViewerPage;
