import { FormEvent, useEffect, useMemo, useState } from 'react';
import { Navigate } from 'react-router-dom';

import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { ShellLayout } from '../components/ShellLayout';
import type { Role, User } from '../types';

const TABLE_PAGE_SIZE = 10;

export function UsersPage() {
  const { user } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [page, setPage] = useState(1);

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<Role>('ASSIGNEE');
  const [receiveAlert, setReceiveAlert] = useState(true);

  const totalPages = useMemo(() => Math.max(1, Math.ceil(users.length / TABLE_PAGE_SIZE)), [users.length]);
  const pagedUsers = useMemo(() => {
    const start = (page - 1) * TABLE_PAGE_SIZE;
    return users.slice(start, start + TABLE_PAGE_SIZE);
  }, [users, page]);

  useEffect(() => {
    if (user?.role === 'SUPER_ADMIN') {
      void loadUsers();
    }
  }, [user?.role]);

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  if (user?.role !== 'SUPER_ADMIN') {
    return <Navigate to="/dashboard" replace />;
  }

  async function loadUsers() {
    const { data } = await api.get<User[]>('/users');
    setUsers(data);
    setPage(1);
  }

  async function createUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
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
  }

  async function toggleReceiveAlert(item: User) {
    await api.patch(`/users/${item.id}`, { receive_alert: !item.receive_alert });
    await loadUsers();
  }

  return (
    <ShellLayout>
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
              </tr>
            </thead>
            <tbody>
              {pagedUsers.map((item) => (
                <tr key={item.id}>
                  <td>{item.full_name}</td>
                  <td>{item.email}</td>
                  <td>{item.role}</td>
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
    </ShellLayout>
  );
}
