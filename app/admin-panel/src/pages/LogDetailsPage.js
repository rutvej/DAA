import React, { useState, useEffect, useContext } from 'react';
import { useParams } from 'react-router-dom';
import { AuthContext } from '../contexts/AuthContext';

const LogDetailsPage = () => {
  const { token } = useContext(AuthContext);
  const { id } = useParams();
  const [log, setLog] = useState(null);

  useEffect(() => {
    const fetchLog = async () => {
      const response = await fetch(`${process.env.REACT_APP_API_URL}/logs/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      setLog(data);
    };
    fetchLog();
  }, [token, id]);

  if (!log) {
    return <div>Loading...</div>;
  }

  return (
    <div className="log-details">
      <h3>Log Details</h3>
      <p>ID: {log.id}</p>
      <p>Status: {log.status}</p>
      <p>Timestamp: {log.timestamp}</p>
      <pre>{log.content}</pre>
    </div>
  );
};

export default LogDetailsPage;
