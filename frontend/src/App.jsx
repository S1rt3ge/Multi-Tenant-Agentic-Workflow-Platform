import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/common/ProtectedRoute';
import Layout from './components/common/Layout';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import WorkflowListPage from './pages/WorkflowListPage';
import ToolsPage from './pages/ToolsPage';

// Placeholder pages for future modules
function DashboardPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-4">Dashboard</h1>
      <p className="text-gray-500">Module 6 — analytics and cost tracking.</p>
    </div>
  );
}

function TeamPage() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-4">Team</h1>
      <p className="text-gray-500">Team management — part of Module 1.</p>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Toaster position="top-right" />
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Protected routes with sidebar layout */}
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route path="/workflows" element={<WorkflowListPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/tools" element={<ToolsPage />} />
            <Route path="/team" element={<TeamPage />} />
          </Route>

          {/* Default redirect */}
          <Route path="*" element={<Navigate to="/workflows" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
