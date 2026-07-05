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

  const downloadPostmortem = () => {
    if (!fix || !fix.postmortem) return;
    const element = document.createElement("a");
    const file = new Blob([fix.postmortem], {type: 'text/markdown'});
    element.href = URL.createObjectURL(file);
    element.download = `postmortem-${fix.id}.md`;
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

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
          <div className="detail-block">
            <p className="detail-label">Pull Request URL</p>
            {fix.pull_request_url ? (
              <a href={fix.pull_request_url} target="_blank" rel="noopener noreferrer" className="pr-link" style={{ display: 'block', margin: '8px 0', color: '#1a73e8', textDecoration: 'underline' }}>
                {fix.pull_request_url}
              </a>
            ) : (
              <p className="detail-value">No Pull Request created yet</p>
            )}
            <p className="detail-label" style={{ marginTop: '16px' }}>Source / Proposed Changes</p>
            <pre className="code-block" style={{ marginTop: '8px' }}>{fix.generatedFix || 'Fix applied directly or detailed in the postmortem report below.'}</pre>
          </div>
        </div>
      </div>

      {fix.postmortem && (
        <div className="panel-card postmortem-panel" style={{ marginTop: '24px' }}>
          <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h3>Postmortem Report</h3>
              <span className="panel-meta">Automated root-cause analysis and prevention steps</span>
            </div>
            <button className="primary-btn" onClick={downloadPostmortem}>
              Download Postmortem (.md)
            </button>
          </div>
          <div className="postmortem-content" style={{ padding: '16px', backgroundColor: '#fafafa', border: '1px solid #e0e0e0', borderRadius: '4px', whiteSpace: 'pre-wrap', fontFamily: 'inherit', marginTop: '16px' }}>
            {fix.postmortem}
          </div>
        </div>
      )}
    </div>
  );
};

export default FixViewerPage;

