import React, { useState, useEffect, useContext } from 'react';
import { AuthContext } from '../contexts/AuthContext';

const DashboardPage = () => {
  const { token } = useContext(AuthContext);
  const [dashboardData, setDashboardData] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      const response = await fetch('/dashboard', {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      setDashboardData(data);
    };
    fetchData();
  }, [token]);

  if (!dashboardData) {
    return <div>Loading...</div>;
  }

  return (
    <div className="dashboard">
      <div className="card">
        <h3>Pending Tasks</h3>
        <p>{dashboardData.pendingTasks}</p>
      </div>
      <div className="card">
        <h3>In-Progress Tasks</h3>
        <p>{dashboardData.inProgressTasks}</p>
      </div>
      <div className="card">
        <h3>Completed Tasks</h3>
        <p>{dashboardData.completedTasks}</p>
      </div>
      <div className="card" style={{ gridColumn: '1 / -1' }}>
        <h3>Recent Logs</h3>
        <table className="log-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Status</th>
              <th>Timestamp</th>
              <th>Summary</th>
            </tr>
          </thead>
          <tbody>
            {dashboardData.recentLogs.map((log) => (
              <tr key={log.id}>
                <td>{log.id}</td>
                <td>{log.status}</td>
                <td>{log.timestamp}</td>
                <td>{log.summary}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default DashboardPage;
