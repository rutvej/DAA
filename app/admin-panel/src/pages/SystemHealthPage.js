import React, { useEffect, useState, useContext } from 'react';
import { AuthContext } from '../contexts/AuthContext';
import { healthApi } from '../services/api';

const SystemHealthPage = () => {
  const { token } = useContext(AuthContext);
  const [services, setServices] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const loadHealth = async () => {
    setIsLoading(true);
    setError('');
    try {
      const data = await healthApi.list({ token });
      setServices(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || 'Unable to load system health.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadHealth();
  }, [token]);

  return (
    <div className="health-page">
      <section className="page-header">
        <div>
          <p className="eyebrow">System health</p>
          <h1>Service status</h1>
          <p className="subtle">Track uptime and degraded services in real time.</p>
        </div>
        <div className="badge-row">
          <button type="button" className="secondary-btn" onClick={loadHealth} disabled={isLoading}>
            {isLoading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </section>

      {isLoading ? (
        <div className="page-state">Loading health checks...</div>
      ) : error ? (
        <div className="page-state">{error}</div>
      ) : (
        <div className="health-grid">
          {services.map((service) => (
            <div className="panel-card" key={service.serviceName}>
              <div className="panel-header">
                <h3>{service.serviceName}</h3>
                <span className={`status-pill status-${(service.status || 'unknown').toLowerCase()}`}>
                  {service.status || 'Unknown'}
                </span>
              </div>
              <p className="panel-meta">Last checked: {service.lastChecked || 'Recently'}</p>
              <p className="subtle">Monitor logs for anomalies or repeated failures.</p>
            </div>
          ))}
          {services.length === 0 ? <p className="empty-state">No services reported.</p> : null}
        </div>
      )}
    </div>
  );
};

export default SystemHealthPage;
