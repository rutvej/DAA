import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { authApi } from '../services/api';

const RegisterPage = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');
    setIsSubmitting(true);
    try {
      const data = await authApi.register({ username, password });
      setMessage(data.message || 'Registration successful.');
    } catch (err) {
      setError(err.message || 'Registration failed.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="auth-heading">
          <p className="eyebrow">Admin Panel</p>
          <h1>Create account</h1>
          <p className="subtle">Register an admin identity for the operations team.</p>
        </div>
        <form onSubmit={handleSubmit} className="auth-form">
          <label>
            Username
            <input
              type="text"
              placeholder="admin"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              placeholder="Create a password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          {error ? <div className="form-error">{error}</div> : null}
          {message ? <div className="form-success">{message}</div> : null}
          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Creating...' : 'Register'}
          </button>
        </form>
        <div className="auth-footer">
          <span>Already registered?</span>
          <Link to="/login">Back to login</Link>
        </div>
      </div>
    </div>
  );
};

export default RegisterPage;
