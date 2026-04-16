import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/common/ProtectedRoute';
import Layout from './components/common/Layout';

const LoginPage = lazy(() => import('./pages/LoginPage'));
const RegisterPage = lazy(() => import('./pages/RegisterPage'));
const WorkflowListPage = lazy(() => import('./pages/WorkflowListPage'));
const BuilderPage = lazy(() => import('./pages/BuilderPage'));
const ToolsPage = lazy(() => import('./pages/ToolsPage'));
const ExecutionPage = lazy(() => import('./pages/ExecutionPage'));
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const TeamPage = lazy(() => import('./pages/TeamPage'));
const SetPasswordPage = lazy(() => import('./pages/SetPasswordPage'));

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Toaster position="top-right" />
        <Suspense
          fallback={
            <div className="min-h-screen flex items-center justify-center bg-gray-50">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
            </div>
          }
        >
          <Routes>
            {/* Public routes */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route
              path="/set-password"
              element={
                <ProtectedRoute>
                  <SetPasswordPage />
                </ProtectedRoute>
              }
            />

            {/* Builder — full-screen, no app sidebar layout */}
            <Route
              path="/workflows/:id"
              element={
                <ProtectedRoute>
                  <BuilderPage />
                </ProtectedRoute>
              }
            />

            {/* Execution — new execution or view existing */}
            <Route
              path="/workflows/:id/execute"
              element={
                <ProtectedRoute>
                  <ExecutionPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/workflows/:id/execute/:executionId"
              element={
                <ProtectedRoute>
                  <ExecutionPage />
                </ProtectedRoute>
              }
            />

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
        </Suspense>
      </AuthProvider>
    </BrowserRouter>
  );
}
