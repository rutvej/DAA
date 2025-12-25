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
      <div className="logo">Admin Panel</div>
      <div className="user-info">
        <span>Welcome, Admin</span>
        <button onClick={logout}>Logout</button>
      </div>
    </header>
  );
};

const Sidebar = () => (
  <nav className="sidebar">
    <NavLink to="/dashboard">Dashboard</NavLink>
    <NavLink to="/logs">Logs</NavLink>
  </nav>
);

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
                  <Route path="/logs" element={<LogsPage />} />
                  <Route path="/logs/:id" element={<LogDetailsPage />} />
                  <Route path="/fix/:id" element={<FixViewerPage />} />
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
