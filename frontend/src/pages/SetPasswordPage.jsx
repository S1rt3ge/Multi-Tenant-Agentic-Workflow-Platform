import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';


export default function SetPasswordPage() {
  const { user, setPassword } = useAuth();
  const navigate = useNavigate();

  const [currentPassword, setCurrentPassword] = useState('');
  const [password, setPasswordValue] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const requiresInitialSet = Boolean(user?.must_change_password);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setSubmitting(true);
    try {
      await setPassword(password, requiresInitialSet ? null : currentPassword || null);
      navigate('/workflows', { replace: true });
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to set password');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md bg-white border border-gray-200 rounded-xl p-8 space-y-5">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Set your password</h1>
          <p className="text-sm text-gray-600 mt-1">
            {requiresInitialSet
              ? 'You were invited. Set a new password to activate your account.'
              : 'Update your account password.'}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {!requiresInitialSet && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="current-password">
                Current password
              </label>
              <input
                id="current-password"
                type="password"
                required
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
              />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="new-password">
              New password
            </label>
            <input
              id="new-password"
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPasswordValue(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="confirm-password">
              Confirm password
            </label>
            <input
              id="confirm-password"
              type="password"
              required
              minLength={6}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            />
          </div>

          {error && <div className="text-sm text-red-600">{error}</div>}

          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-blue-600 text-white py-2.5 rounded-lg text-sm font-medium disabled:opacity-50"
          >
            {submitting ? 'Saving...' : 'Save password'}
          </button>
        </form>
      </div>
    </div>
  );
}
