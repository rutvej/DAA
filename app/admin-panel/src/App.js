import React, { useContext } from 'react';
import { BrowserRouter as Router, Routes, Route, NavLink, Navigate } from 'react-router-dom';
import './App.css';
import { AuthProvider, AuthContext } from './contexts/AuthContext';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import LogsPage from './pages/LogsPage';
import LogDetailsPage from './pages/LogDetailsPage';
import FixViewerPage from './pages/FixViewerPage';
import SystemHealthPage from './pages/SystemHealthPage';
import IncidentsPage from './pages/IncidentsPage';
import ApplicationsPage from './pages/ApplicationsPage';


// Layout
const MainLayout = ({ children }) => (
  <div className="App">
    <Header />
    <div style={{ display: 'flex', flexGrow: 1 }}>
      <Sidebar />
      <div className="content">
        {children}
      </div>
    </div>
  </div>
);

const Header = () => {
  const { logout } = useContext(AuthContext);
  return (
    <header className="header">
      <div className="logo">
        <span className="logo-mark">DAA</span>
        <div>
          <p className="logo-title">Admin Panel</p>
          <p className="logo-subtitle">Operations Console</p>
        </div>
      </div>
      <div className="user-info">
        <span>Welcome, Admin</span>
        <button className="ghost-btn" onClick={logout}>Logout</button>
      </div>
    </header>
  );
};

const Sidebar = () => {
  const navClass = ({ isActive }) => (isActive ? 'active' : undefined);
  return (
    <nav className="sidebar">
      <div className="nav-section">
        <p className="nav-title">Overview</p>
        <NavLink to="/dashboard" className={navClass}>Dashboard</NavLink>
        <NavLink to="/health" className={navClass}>System Health</NavLink>
      </div>
      <div className="nav-section">
        <p className="nav-title">Incidents</p>
        <NavLink to="/incidents" className={navClass}>Active Incidents</NavLink>
        <NavLink to="/logs" className={navClass}>Error Logs</NavLink>
      </div>
      <div className="nav-section">
        <p className="nav-title">Configuration</p>
        <NavLink to="/applications" className={navClass}>Applications</NavLink>
      </div>
    </nav>
  );
};

const AppRoutes = () => {
  const { token } = useContext(AuthContext);

  return (
    <Router>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route
          path="/*"
          element={
            token ? (
              <MainLayout>
                <Routes>
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/health" element={<SystemHealthPage />} />
                  <Route path="/logs" element={<LogsPage />} />
                  <Route path="/logs/:id" element={<LogDetailsPage />} />
                  <Route path="/fix/:id" element={<FixViewerPage />} />
                  <Route path="/incidents" element={<IncidentsPage />} />
                  <Route path="/applications" element={<ApplicationsPage />} />
                  <Route path="*" element={<Navigate to="/dashboard" />} />
                </Routes>
              </MainLayout>
            ) : (
              <Navigate to="/login" />
            )
          }
        />
      </Routes>
    </Router>
  );
};

// App
function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}

export default App;
