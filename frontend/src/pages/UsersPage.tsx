import { FormEvent, useEffect, useMemo, useState } from 'react';

import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { ShellLayout } from '../components/ShellLayout';
import { useToast } from '../components/ToastProvider';
import type { Role, User } from '../types';
import { getApiErrorMessage } from '../utils/errors';

const TABLE_PAGE_SIZE = 10;

export function UsersPage() {
  const { user, refreshUser } = useAuth();
  const toast = useToast();
  const [users, setUsers] = useState<User[]>([]);
  const [page, setPage] = useState(1);

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<Role>('ASSIGNEE');
  const [receiveAlert, setReceiveAlert] = useState(true);

  const [profileName, setProfileName] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [profileMessage, setProfileMessage] = useState('');
  const [profileError, setProfileError] = useState('');

  const isSuperAdmin = user?.role === 'SUPER_ADMIN';

  const totalPages = useMemo(() => Math.max(1, Math.ceil(users.length / TABLE_PAGE_SIZE)), [users.length]);
  const pagedUsers = useMemo(() => {
    const start = (page - 1) * TABLE_PAGE_SIZE;
    return users.slice(start, start + TABLE_PAGE_SIZE);
  }, [users, page]);

  useEffect(() => {
    if (isSuperAdmin) {
      void loadUsers();
    }
  }, [isSuperAdmin]);

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  useEffect(() => {
    setProfileName(user?.full_name || '');
  }, [user?.full_name]);

  async function loadUsers() {
    try {
      const { data } = await api.get<User[]>('/users');
      setUsers(data);
      setPage(1);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to load users'));
    }
  }

  async function createUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await api.post('/users', {
        full_name: fullName,
        email,
        password,
        role,
        is_active: true,
        receive_alert: receiveAlert,
      });
      setFullName('');
      setEmail('');
      setPassword('');
      setRole('ASSIGNEE');
      setReceiveAlert(true);
      await loadUsers();
      toast.success('User created successfully');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to create user'));
    }
  }

  async function toggleReceiveAlert(item: User) {
    try {
      await api.patch(`/users/${item.id}`, { receive_alert: !item.receive_alert });
      await loadUsers();
      toast.success(`Receive alert ${item.receive_alert ? 'disabled' : 'enabled'} for ${item.full_name}`);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to update alert preference'));
    }
  }

  async function updateUserRole(item: User, nextRole: Role) {
    if (item.role === nextRole) return;
    try {
      await api.patch(`/users/${item.id}`, { role: nextRole });
      await loadUsers();
      toast.success(`Role updated for ${item.full_name}`);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to update user role'));
    }
  }

  async function deleteUser(item: User) {
    const ok = window.confirm(`Delete user "${item.full_name}" (${item.email})?`);
    if (!ok) return;
    try {
      await api.delete(`/users/${item.id}`);
      await loadUsers();
      toast.success('User deleted successfully');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to delete user'));
    }
  }

  async function updateMyProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setProfileMessage('');
    setProfileError('');

    const payload: Record<string, string> = {};
    const trimmedName = profileName.trim();
    if (trimmedName && trimmedName !== (user?.full_name || '')) {
      payload.full_name = trimmedName;
    }

    if (newPassword || currentPassword || confirmPassword) {
      if (!currentPassword) {
        setProfileError('Current password is required to change password.');
        return;
      }
      if (newPassword.length < 8) {
        setProfileError('New password must be at least 8 characters.');
        return;
      }
      if (newPassword !== confirmPassword) {
        setProfileError('New password and confirm password do not match.');
        return;
      }
      payload.current_password = currentPassword;
      payload.new_password = newPassword;
    }

    if (Object.keys(payload).length === 0) {
      setProfileError('No changes to update.');
      return;
    }

    try {
      await api.patch('/users/me', payload);
      await refreshUser();
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setProfileMessage('Profile updated successfully.');
      toast.success('Profile updated successfully');
    } catch (error) {
      const message = getApiErrorMessage(error, 'Failed to update profile.');
      setProfileError(message);
      toast.error(message);
    }
  }

  return (
    <ShellLayout>
      <section className="panel">
        <h2>My Profile</h2>
        <form className="form-grid three-col" onSubmit={updateMyProfile}>
          <label>
            Email
            <input value={user?.email || ''} disabled />
          </label>
          <label>
            Role
            <input value={user?.role || ''} disabled />
          </label>
          <label>
            Full Name
            <input value={profileName} onChange={(e) => setProfileName(e.target.value)} required />
          </label>
          <label>
            Current Password
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder="Required to change password"
            />
          </label>
          <label>
            New Password
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              minLength={8}
              placeholder="Min 8 chars"
            />
          </label>
          <label>
            Confirm New Password
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              minLength={8}
            />
          </label>
          {profileError ? <p className="error-box full-width">{profileError}</p> : null}
          {profileMessage ? <p className="full-width">{profileMessage}</p> : null}
          <div className="full-width">
            <button className="btn btn-primary" type="submit">
              Update Profile
            </button>
          </div>
        </form>
      </section>

      {isSuperAdmin ? (
        <>
          <section className="panel">
            <h2>Create User</h2>
            <form className="form-grid three-col" onSubmit={createUser}>
              <label>
                Full Name
                <input value={fullName} onChange={(e) => setFullName(e.target.value)} required />
              </label>
              <label>
                Email
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
              </label>
              <label>
                Password
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                />
              </label>
              <label>
                Role
                <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
                  <option value="ASSIGNEE">ASSIGNEE</option>
                  <option value="EMAIL_TEAM">EMAIL_TEAM</option>
                  <option value="SUPER_ADMIN">SUPER_ADMIN</option>
                </select>
              </label>
              <label className="checkbox-inline">
                <input type="checkbox" checked={receiveAlert} onChange={(e) => setReceiveAlert(e.target.checked)} />
                Receive Alerts
              </label>
              <div className="full-width">
                <button className="btn btn-primary" type="submit">
                  Create
                </button>
              </div>
            </form>
          </section>

          <section className="panel">
            <h2>Users</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Active</th>
                    <th>Receive Alert</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {pagedUsers.map((item) => (
                    <tr key={item.id}>
                      <td>{item.full_name}</td>
                      <td>{item.email}</td>
                      <td>
                        <select
                          value={item.role}
                          onChange={(e) => updateUserRole(item, e.target.value as Role)}
                          disabled={item.id === user?.id}
                        >
                          <option value="ASSIGNEE">ASSIGNEE</option>
                          <option value="EMAIL_TEAM">EMAIL_TEAM</option>
                          <option value="SUPER_ADMIN">SUPER_ADMIN</option>
                        </select>
                      </td>
                      <td>{item.is_active ? 'Yes' : 'No'}</td>
                      <td>
                        <label className="checkbox-inline">
                          <input
                            type="checkbox"
                            checked={item.receive_alert}
                            onChange={() => toggleReceiveAlert(item)}
                          />
                          {item.receive_alert ? 'Enabled' : 'Disabled'}
                        </label>
                      </td>
                      <td>
                        <button
                          className="btn btn-sm btn-outline"
                          type="button"
                          disabled={item.id === user?.id}
                          onClick={() => deleteUser(item)}
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="pager">
              <button className="btn btn-sm" type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                Prev
              </button>
              <span>
                Page {page} / {totalPages} ({users.length} rows)
              </span>
              <button
                className="btn btn-sm"
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          </section>
        </>
      ) : null}
    </ShellLayout>
  );
}
