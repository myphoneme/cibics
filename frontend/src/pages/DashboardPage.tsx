import { useEffect, useMemo, useState } from 'react';

import { useAuth } from '../auth/AuthContext';
import { api } from '../api/client';
import { ShellLayout } from '../components/ShellLayout';
import { useToast } from '../components/ToastProvider';
import type { AssigneeSummary, DashboardSummary, StatusSummary } from '../types';
import { getApiErrorMessage } from '../utils/errors';

const TABLE_PAGE_SIZE = 10;

export function DashboardPage() {
  const { user } = useAuth();
  const toast = useToast();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [assigneeSummary, setAssigneeSummary] = useState<AssigneeSummary[]>([]);
  const [statusSummary, setStatusSummary] = useState<StatusSummary[]>([]);
  const [assigneePage, setAssigneePage] = useState(1);

  const assigneePages = useMemo(
    () => Math.max(1, Math.ceil(assigneeSummary.length / TABLE_PAGE_SIZE)),
    [assigneeSummary.length],
  );

  const visibleAssignees = useMemo(() => {
    const start = (assigneePage - 1) * TABLE_PAGE_SIZE;
    return assigneeSummary.slice(start, start + TABLE_PAGE_SIZE);
  }, [assigneeSummary, assigneePage]);

  useEffect(() => {
    void loadData();
  }, []);

  useEffect(() => {
    if (assigneePage > assigneePages) {
      setAssigneePage(assigneePages);
    }
  }, [assigneePage, assigneePages]);

  async function loadData() {
    try {
      const [summaryRes, statusRes] = await Promise.all([
        api.get<DashboardSummary>('/dashboard/summary'),
        api.get<StatusSummary[]>('/dashboard/by-status'),
      ]);

      setSummary(summaryRes.data);
      setStatusSummary(statusRes.data);

      if (user?.role !== 'ASSIGNEE') {
        const assigneeRes = await api.get<AssigneeSummary[]>('/dashboard/by-assignee');
        setAssigneeSummary(assigneeRes.data);
        setAssigneePage(1);
      }
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to load dashboard data'));
    }
  }

  return (
    <ShellLayout>
      <section className="grid-cards">
        <Card title="Total Records" value={summary?.total_records ?? 0} tone="primary" icon={<IconStack />} />
        <Card
          title="Client Email Captured"
          value={summary?.with_client_email ?? 0}
          tone="success"
          icon={<IconMail />}
        />
        <Card
          title="Need Email Follow-up"
          value={summary?.without_client_email ?? 0}
          tone="warning"
          icon={<IconBell />}
        />
        <Card
          title="Email Alerts Pending"
          value={summary?.alerts_pending ?? 0}
          tone="danger"
          icon={<IconAlert />}
        />
      </section>

      <section className="panel panel-accent">
        <h2>Status Breakdown</h2>
        <div className="status-grid">
          {statusSummary.map((item) => (
            <div key={item.status} className="status-item">
              <span>{item.status.replace(/_/g, ' ')}</span>
              <strong>{item.count}</strong>
            </div>
          ))}
        </div>
      </section>

      {user?.role !== 'ASSIGNEE' ? (
        <section className="panel panel-accent">
          <h2>Group by Assignee</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Assignee</th>
                  <th>Total</th>
                  <th>With Email</th>
                  <th>Alerts</th>
                  <th>Proposal Sent</th>
                  <th>PO Received</th>
                </tr>
              </thead>
              <tbody>
                {visibleAssignees.map((item) => (
                  <tr key={item.assignee_name}>
                    <td>{item.assignee_name}</td>
                    <td>{item.total}</td>
                    <td>{item.with_client_email}</td>
                    <td>{item.alerts_pending}</td>
                    <td>{item.proposal_sent}</td>
                    <td>{item.po_received}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pager">
            <button
              className="btn btn-sm"
              type="button"
              disabled={assigneePage <= 1}
              onClick={() => setAssigneePage((p) => p - 1)}
            >
              Prev
            </button>
            <span>
              Page {assigneePage} / {assigneePages} ({assigneeSummary.length} rows)
            </span>
            <button
              className="btn btn-sm"
              type="button"
              disabled={assigneePage >= assigneePages}
              onClick={() => setAssigneePage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        </section>
      ) : null}
    </ShellLayout>
  );
}

function Card({
  title,
  value,
  tone,
  icon,
}: {
  title: string;
  value: number;
  tone: 'primary' | 'success' | 'warning' | 'danger';
  icon: React.ReactNode;
}) {
  return (
    <div className={`card-stat tone-${tone}`}>
      <div className="card-head">
        <h3>{title}</h3>
        <span className="metric-chip" aria-hidden="true">
          {icon}
        </span>
      </div>
      <strong>{value}</strong>
    </div>
  );
}

function IconStack() {
  return (
    <svg viewBox="0 0 24 24" className="svg-icon" aria-hidden="true">
      <path d="M12 3 3 8l9 5 9-5-9-5Zm0 8-9-5m9 5 9-5" fill="none" stroke="currentColor" strokeWidth="2" />
      <path d="m3 12 9 5 9-5m-18 4 9 5 9-5" fill="none" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}

function IconMail() {
  return (
    <svg viewBox="0 0 24 24" className="svg-icon" aria-hidden="true">
      <rect x="3" y="5" width="18" height="14" rx="2" fill="none" stroke="currentColor" strokeWidth="2" />
      <path d="m4 7 8 6 8-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function IconBell() {
  return (
    <svg viewBox="0 0 24 24" className="svg-icon" aria-hidden="true">
      <path
        d="M6 9a6 6 0 1 1 12 0v5l2 2H4l2-2V9Zm4.5 10a1.5 1.5 0 0 0 3 0"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconAlert() {
  return (
    <svg viewBox="0 0 24 24" className="svg-icon" aria-hidden="true">
      <path
        d="M12 3 2.8 19h18.4L12 3Zm0 5v5m0 4h.01"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
