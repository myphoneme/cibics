import { useEffect, useMemo, useState } from 'react';

import { useAuth } from '../auth/AuthContext';
import { api } from '../api/client';
import { ShellLayout } from '../components/ShellLayout';
import { useToast } from '../components/ToastProvider';
import type {
  AssigneeSummary,
  DashboardSummary,
  StageProgressDetailResponse,
  StageProgressResponse,
  StatusSummary,
} from '../types';
import { getApiErrorMessage } from '../utils/errors';

const TABLE_PAGE_SIZE = 10;
const PROGRESS_DAYS = 7;

export function DashboardPage() {
  const { user } = useAuth();
  const toast = useToast();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [assigneeSummary, setAssigneeSummary] = useState<AssigneeSummary[]>([]);
  const [statusSummary, setStatusSummary] = useState<StatusSummary[]>([]);
  const [assigneePage, setAssigneePage] = useState(1);
  const [progressStart, setProgressStart] = useState(() => getWeekStart(new Date()));
  const [stageProgress, setStageProgress] = useState<StageProgressResponse | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailData, setDetailData] = useState<StageProgressDetailResponse | null>(null);

  const assigneePages = useMemo(
    () => Math.max(1, Math.ceil(assigneeSummary.length / TABLE_PAGE_SIZE)),
    [assigneeSummary.length],
  );
  const poReceivedCount = useMemo(
    () => statusSummary.find((item) => item.status === 'PO_RECEIVED')?.count ?? 0,
    [statusSummary],
  );

  const visibleAssignees = useMemo(() => {
    const start = (assigneePage - 1) * TABLE_PAGE_SIZE;
    return assigneeSummary.slice(start, start + TABLE_PAGE_SIZE);
  }, [assigneeSummary, assigneePage]);

  useEffect(() => {
    void loadData();
  }, []);

  useEffect(() => {
    void loadStageProgress(progressStart);
  }, [progressStart]);

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
      setStatusSummary(Array.isArray(statusRes.data) ? statusRes.data : []);

      const assigneeRes = await api.get<AssigneeSummary[]>('/dashboard/by-assignee');
      setAssigneeSummary(Array.isArray(assigneeRes.data) ? assigneeRes.data : []);
      setAssigneePage(1);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to load dashboard data'));
    }
  }

  async function loadStageProgress(start: Date) {
    try {
      const startDate = toIsoDate(start);
      const { data } = await api.get<StageProgressResponse>('/dashboard/stage-progress', {
        params: { start_date: startDate, days: PROGRESS_DAYS },
      });
      setStageProgress(data);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to load stage progress'));
    }
  }

  async function openDetail(day: string, stageKey: string) {
    if (!day || !stageKey) return;
    try {
      setDetailOpen(true);
      setDetailLoading(true);
      setDetailData(null);
      const { data } = await api.get<StageProgressDetailResponse>('/dashboard/stage-progress/details', {
        params: { day, stage_key: stageKey },
      });
      setDetailData(data);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to load details'));
      setDetailOpen(false);
    } finally {
      setDetailLoading(false);
    }
  }

  return (
    <ShellLayout>
      <section className="grid-cards">
        <Card title="Total Records" value={summary?.total_records ?? 0} tone="primary" icon={<IconStack />} />
        <Card
          title="Total Email Captured"
          value={summary?.with_client_email ?? 0}
          tone="success"
          icon={<IconMail />}
        />
        <Card
          title="Need Follow-up for Email (Excl. PO Received)"
          value={summary?.without_client_email ?? 0}
          tone="warning"
          icon={<IconBell />}
        />
        <Card
          title="Total PO Received"
          value={poReceivedCount}
          tone="danger"
          icon={<IconAlert />}
        />
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

      <section className="panel panel-accent">
        <div className="panel-head">
          <div className="panel-title">
            <h2>Daily Stage Progress</h2>
            <p className="muted">{formatWeekRange(stageProgress?.dates ?? [])}</p>
          </div>
          <ProgressControls start={progressStart} onChange={setProgressStart} />
        </div>
        <StageProgressTable progress={stageProgress} onCellClick={openDetail} />
      </section>

      {detailOpen ? (
        <DetailModal
          loading={detailLoading}
          data={detailData}
          onClose={() => {
            setDetailOpen(false);
            setDetailData(null);
          }}
        />
      ) : null}
    </ShellLayout>
  );
}

function StageProgressTable({
  progress,
  onCellClick,
}: {
  progress: StageProgressResponse | null;
  onCellClick: (day: string, stageKey: string) => void;
}) {
  if (!progress) {
    return <p className="muted">Loading…</p>;
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th style={{ width: 220 }}>Stage</th>
            {progress.dates.map((iso) => (
              <th key={iso} style={{ whiteSpace: 'nowrap' }}>
                {formatShortDate(iso)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {progress.rows.map((row) => (
            <tr key={row.key}>
              <td>{row.label}</td>
              {row.counts.map((count, idx) => (
                <td
                  key={`${row.key}:${progress.dates[idx]}`}
                  style={{ textAlign: 'center' }}
                  className={count > 0 ? 'cell-hot' : undefined}
                >
                  {count > 0 ? (
                    <button
                      type="button"
                      className="cell-btn"
                      onClick={() => onCellClick(progress.dates[idx], row.key)}
                      title="View details"
                    >
                      {count}
                    </button>
                  ) : (
                    <span className="cell-zero">{count}</span>
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DetailModal({
  loading,
  data,
  onClose,
}: {
  loading: boolean;
  data: StageProgressDetailResponse | null;
  onClose: () => void;
}) {
  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal-card">
        <div className="modal-head">
          <div>
            <h3 style={{ margin: 0 }}>Details</h3>
            <p className="muted" style={{ marginTop: 2 }}>
              {data ? `${data.stage_label} • ${data.date}` : 'Loading…'}
            </p>
          </div>
          <button className="btn btn-sm btn-outline" type="button" onClick={onClose}>
            Close
          </button>
        </div>

        {loading ? (
          <p className="muted">Loading…</p>
        ) : data && data.items.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Assignee</th>
                  <th style={{ width: 120, textAlign: 'right' }}>Records</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={`${item.assignee_id ?? 'unassigned'}:${item.assignee_name}`}>
                    <td>{item.assignee_name}</td>
                    <td style={{ textAlign: 'right' }}>{item.record_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">No details found.</p>
        )}
      </div>
    </div>
  );
}

function ProgressControls({ start, onChange }: { start: Date; onChange: (value: Date) => void }) {
  const years = useMemo(() => {
    const current = new Date().getFullYear();
    return [current - 1, current, current + 1];
  }, []);

  const month = start.getMonth();
  const year = start.getFullYear();

  function shiftDays(delta: number) {
    const next = new Date(start);
    next.setDate(next.getDate() + delta);
    onChange(getWeekStart(next));
  }

  function setToToday() {
    onChange(getWeekStart(new Date()));
  }

  function handleMonthChange(nextMonth: number) {
    const next = new Date(start);
    next.setFullYear(year);
    next.setMonth(nextMonth);
    next.setDate(1);
    onChange(getWeekStart(next));
  }

  function handleYearChange(nextYear: number) {
    const next = new Date(start);
    next.setFullYear(nextYear);
    next.setMonth(month);
    next.setDate(1);
    onChange(getWeekStart(next));
  }

  return (
    <div className="panel-actions">
      <button className="btn btn-sm btn-outline" type="button" onClick={() => shiftDays(-7)}>
        Prev Week
      </button>
      <button className="btn btn-sm btn-outline" type="button" onClick={setToToday}>
        This Week
      </button>
      <button className="btn btn-sm btn-outline" type="button" onClick={() => shiftDays(7)}>
        Next Week
      </button>
      <select className="control-sm" value={month} onChange={(e) => handleMonthChange(Number(e.target.value))}>
        {Array.from({ length: 12 }).map((_, idx) => (
          <option key={idx} value={idx}>
            {new Date(2000, idx, 1).toLocaleString(undefined, { month: 'short' })}
          </option>
        ))}
      </select>
      <select className="control-sm" value={year} onChange={(e) => handleYearChange(Number(e.target.value))}>
        {years.map((y) => (
          <option key={y} value={y}>
            {y}
          </option>
        ))}
      </select>
    </div>
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

function getWeekStart(value: Date) {
  const d = new Date(value);
  const day = d.getDay(); // 0=Sun
  const diff = (day === 0 ? -6 : 1) - day; // Monday as start
  d.setDate(d.getDate() + diff);
  d.setHours(0, 0, 0, 0);
  return d;
}

function toIsoDate(value: Date) {
  const y = value.getFullYear();
  const m = String(value.getMonth() + 1).padStart(2, '0');
  const d = String(value.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function formatShortDate(iso: string) {
  const [y, m, d] = iso.split('-').map(Number);
  const dt = new Date(y, m - 1, d);
  return dt.toLocaleDateString(undefined, { weekday: 'short', day: '2-digit' });
}

function formatWeekRange(dates: string[]) {
  if (!dates.length) return '';
  const start = dates[0];
  const end = dates[dates.length - 1];
  const startLabel = formatRangeDate(start);
  const endLabel = formatRangeDate(end);
  return `${startLabel} – ${endLabel}`;
}

function formatRangeDate(iso: string) {
  const [y, m, d] = iso.split('-').map(Number);
  const dt = new Date(y, m - 1, d);
  return dt.toLocaleDateString(undefined, { month: 'short', day: '2-digit' });
}
