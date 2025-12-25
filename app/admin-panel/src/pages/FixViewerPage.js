import React, { useState, useEffect, useContext } from 'react';
import { useParams } from 'react-router-dom';
import { AuthContext } from '../contexts/AuthContext';

const FixViewerPage = () => {
  const { token } = useContext(AuthContext);
  const { id } = useParams();
  const [fix, setFix] = useState(null);

  useEffect(() => {
    const fetchFix = async () => {
      const response = await fetch(`/fixes/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();
      setFix(data);
    };
    fetchFix();
  }, [token, id]);

  if (!fix) {
    return <div>Loading...</div>;
  }

  return (
    <div className="fix-viewer">
      <div className="log-details">
        <h3>Log Details</h3>
        {/* ... log content ... */}
      </div>
      <div className="code-diff">
        <h3>Code Diff</h3>
        <pre>{fix.generatedFix}</pre>
      </div>
    </div>
  );
};

export default FixViewerPage;
