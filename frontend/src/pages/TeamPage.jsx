import { useCallback, useEffect, useMemo, useState } from 'react';
import toast from 'react-hot-toast';
import { useAuth } from '../hooks/useAuth';
import {
  listTenantUsers,
  inviteTenantUser,
  updateTenantUserRole,
  removeTenantUser,
} from '../api/team';


const ROLE_OPTIONS = ['editor', 'viewer'];


export default function TeamPage() {
  const { user } = useAuth();
  const isOwner = user?.role === 'owner';

  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('editor');
  const [inviting, setInviting] = useState(false);
  const [temporaryPassword, setTemporaryPassword] = useState('');

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await listTenantUsers();
      setUsers(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load team users');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const sortedUsers = useMemo(() => {
    return [...users].sort((a, b) => {
      if (a.role === 'owner' && b.role !== 'owner') return -1;
      if (a.role !== 'owner' && b.role === 'owner') return 1;
      return a.email.localeCompare(b.email);
    });
  }, [users]);

  const handleInvite = useCallback(
    async (e) => {
      e.preventDefault();
      setTemporaryPassword('');

      if (!isOwner) {
        toast.error('Only owners can invite users');
        return;
      }

      setInviting(true);
      const tid = toast.loading('Inviting user...');
      try {
        const invited = await inviteTenantUser({
          email: inviteEmail.trim(),
          role: inviteRole,
        });
        toast.dismiss(tid);
        toast.success('User invited');
        if (invited?.temporary_password) {
          setTemporaryPassword(invited.temporary_password);
        }
        setInviteEmail('');
        setInviteRole('editor');
        await loadUsers();
      } catch (err) {
        toast.dismiss(tid);
        toast.error(err.response?.data?.detail || 'Invite failed');
      } finally {
        setInviting(false);
      }
    },
    [inviteEmail, inviteRole, isOwner, loadUsers]
  );

  const handleRoleChange = useCallback(
    async (targetUserId, nextRole) => {
      if (!isOwner) return;
      const tid = toast.loading('Updating role...');
      try {
        await updateTenantUserRole(targetUserId, nextRole);
        toast.dismiss(tid);
        toast.success('Role updated');
        await loadUsers();
      } catch (err) {
        toast.dismiss(tid);
        toast.error(err.response?.data?.detail || 'Failed to update role');
      }
    },
    [isOwner, loadUsers]
  );

  const handleRemove = useCallback(
    async (targetUserId) => {
      if (!isOwner) return;
      const tid = toast.loading('Removing user...');
      try {
        await removeTenantUser(targetUserId);
        toast.dismiss(tid);
        toast.success('User removed');
        await loadUsers();
      } catch (err) {
        toast.dismiss(tid);
        toast.error(err.response?.data?.detail || 'Failed to remove user');
      }
    },
    [isOwner, loadUsers]
  );

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Team</h1>
        <p className="text-sm text-gray-600 mt-1">
          Invite editors/viewers and manage tenant access.
        </p>
      </div>

      {isOwner && (
        <form
          onSubmit={handleInvite}
          className="bg-white border border-gray-200 rounded-xl p-4 flex flex-col md:flex-row gap-3"
        >
          <input
            type="email"
            required
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            placeholder="user@company.com"
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm"
          />
          <select
            value={inviteRole}
            onChange={(e) => setInviteRole(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
          >
            {ROLE_OPTIONS.map((role) => (
              <option key={role} value={role}>
                {role}
              </option>
            ))}
          </select>
          <button
            type="submit"
            disabled={inviting}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm disabled:opacity-50"
          >
            {inviting ? 'Inviting...' : 'Invite'}
          </button>
        </form>
      )}

      {temporaryPassword && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-900">
          <p className="font-medium">Temporary password (show once)</p>
          <p className="mt-1 font-mono">{temporaryPassword}</p>
          <p className="mt-1 text-xs">
            Share it securely. User will be redirected to set a new password on first sign-in.
          </p>
        </div>
      )}

      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        {loading ? (
          <div className="p-4 text-sm text-gray-500">Loading users...</div>
        ) : error ? (
          <div className="p-4 text-sm text-red-600">{error}</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="text-left px-4 py-3 font-medium">Email</th>
                <th className="text-left px-4 py-3 font-medium">Name</th>
                <th className="text-left px-4 py-3 font-medium">Role</th>
                <th className="text-left px-4 py-3 font-medium">Status</th>
                <th className="text-left px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sortedUsers.map((teamUser) => (
                <tr key={teamUser.id} className="border-t border-gray-100">
                  <td className="px-4 py-3">{teamUser.email}</td>
                  <td className="px-4 py-3">{teamUser.full_name || '—'}</td>
                  <td className="px-4 py-3">
                    {isOwner && teamUser.id !== user?.id ? (
                      <select
                        value={teamUser.role}
                        onChange={(e) => handleRoleChange(teamUser.id, e.target.value)}
                        className="px-2 py-1 border border-gray-300 rounded"
                      >
                        {ROLE_OPTIONS.map((role) => (
                          <option key={role} value={role}>
                            {role}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span>{teamUser.role}</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {teamUser.is_active ? 'active' : 'inactive'}
                    {teamUser.must_change_password ? ' (password reset required)' : ''}
                  </td>
                  <td className="px-4 py-3">
                    {isOwner && teamUser.id !== user?.id ? (
                      <button
                        onClick={() => handleRemove(teamUser.id)}
                        className="text-red-600 hover:underline"
                      >
                        Remove
                      </button>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
