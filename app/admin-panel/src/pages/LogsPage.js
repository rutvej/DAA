import React, { useState, useEffect, useContext } from 'react';
import { AuthContext } from '../contexts/AuthContext';
import { Link } from 'react-router-dom';

const LogsPage = () => {
  const { token } = useContext(AuthContext);
  const [logs, setLogs] = useState([]);

  useEffect(() => {
    const fetchLogs = async () => {
      const response = await fetch(`${process.env.REACT_APP_API_URL}/logs`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      setLogs(data);
    };
    fetchLogs();
  }, [token]);

  return (
    <div className="logs-page">
      <div className="filters">
        <input type="text" placeholder="Search..." />
        <select>
          <option>All Statuses</option>
          <option>Pending</option>
          <option>In-Progress</option>
          <option>Completed</option>
        </select>
      </div>
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
          {logs.map((log) => (
            <tr key={log.id}>
              <td>{log.id}</td>
              <td>{log.status}</td>
              <td>{log.timestamp}</td>
              <td>
                <Link to={`/logs/${log.id}`}>View Details</Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default LogsPage;
