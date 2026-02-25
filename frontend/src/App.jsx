import { useState, useRef } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import './App.css';
import { AuthProvider, useAuth } from './context/AuthContext';
import { analyzeAddress } from './api/analyze';
import Header from './components/Header';
import SearchForm from './components/SearchForm';
import LoadingOverlay from './components/LoadingOverlay';
import ErrorMessage from './components/ErrorMessage';
import ResultsPanel from './components/ResultsPanel';
import ProtectedRoute from './components/ProtectedRoute';
import AdminRoute from './components/AdminRoute';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import AdminPage from './pages/AdminPage';

// Main application view (requires auth via ProtectedRoute)
function MainApp() {
  const { getAccessToken, refreshAccessToken, logout } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const resultsRef = useRef(null);

  async function handleSearch(address) {
    setError(null);
    setLoading(true);
    try {
      const result = await analyzeAddress(address, {
        getToken: getAccessToken,
        refreshToken: refreshAccessToken,
        onAuthFailure: logout,
      });
      setData(result);
      setTimeout(() => {
        resultsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    } catch (err) {
      setError(`Erreur: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <LoadingOverlay visible={loading} />
      <div className="container">
        <Header />
        <ErrorMessage message={error} />
        <SearchForm onSubmit={handleSearch} loading={loading} />
        {data && (
          <div ref={resultsRef}>
            <ResultsPanel data={data} />
          </div>
        )}
      </div>
    </>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <AdminRoute>
                <AdminPage />
              </AdminRoute>
            }
          />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <MainApp />
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
