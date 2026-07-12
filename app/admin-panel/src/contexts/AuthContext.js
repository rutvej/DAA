import React, { createContext, useState, useEffect } from 'react';

const API_BASE =
  process.env.REACT_APP_API_URL ||
  window.location.protocol + '//' + window.location.hostname + ':8000';

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [authEnabled, setAuthEnabled] = useState(null); // null = not yet known
  const [booting, setBooting] = useState(true);

  // On mount: check /status/capabilities to know if auth is required.
  // If auth_enabled=false the backend returns dummy_token for any login —
  // we auto-acquire it so the panel works without user interaction.
  useEffect(() => {
    const init = async () => {
      try {
        const res = await fetch(`${API_BASE}/status/capabilities`);
        if (!res.ok) throw new Error('capabilities unavailable');
        const caps = await res.json();
        setAuthEnabled(caps.auth_enabled);

        if (!caps.auth_enabled) {
          // Auth is disabled — acquire (or reuse) the dummy token silently.
          if (!localStorage.getItem('token')) {
            try {
              const lr = await fetch(`${API_BASE}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: 'admin', password: 'admin' }),
              });
              if (lr.ok) {
                const { token: t } = await lr.json();
                setToken(t);
                localStorage.setItem('token', t);
              }
            } catch (_) {
              // login failed but auth is off — panel will still try requests
              // with no token; backend accepts them when DAA_AUTH_ENABLED=false
            }
          }
        }
      } catch (_) {
        // /status/capabilities not reachable (backend offline, image-only mode
        // without this endpoint, etc.) — fall back to whatever token exists.
        setAuthEnabled(true); // safe default: don't auto-bypass auth
      } finally {
        setBooting(false);
      }
    };

    init();
  }, []);

  const login = (newToken) => {
    setToken(newToken);
    localStorage.setItem('token', newToken);
  };

  const logout = () => {
    setToken(null);
    localStorage.removeItem('token');
  };

  return (
    <AuthContext.Provider value={{ token, login, logout, authEnabled, booting }}>
      {children}
    </AuthContext.Provider>
  );
};
