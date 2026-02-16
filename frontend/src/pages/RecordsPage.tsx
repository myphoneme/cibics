import { useEffect, useMemo, useState } from 'react';

import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { ShellLayout } from '../components/ShellLayout';
import type { PaginatedRecords, RecordItem, StageItem, User } from '../types';

interface Draft {
  customer_name: string;
  mobile_no: string;
  client_email: string;
  notes: string;
  assignee_id: number | '';
  email_alert_pending: boolean;
  stage_states: Record<number, { is_completed: boolean; notes: string }>;
}

type ColumnKey =
  | 'source_row'
  | 'sl_no'
  | 'organization'
  | 'short_name'
  | 'custodian_organization'
  | 'state'
  | 'city'
  | 'category_of_site'
  | 'assignee'
  | 'assignee_hint'
  | 'customer_name'
  | 'mobile_no'
  | 'client_email'
  | 'status'
  | 'stage_progress'
  | 'alert'
  | 'notes'
  | 'updated_at';

const COLUMN_OPTIONS: Array<{ key: ColumnKey; label: string }> = [
  { key: 'source_row', label: 'Row' },
  { key: 'sl_no', label: 'Sl No' },
  { key: 'organization', label: 'Organization' },
  { key: 'short_name', label: 'Short Name' },
  { key: 'custodian_organization', label: 'Custodian Organization' },
  { key: 'state', label: 'State' },
  { key: 'city', label: 'City' },
  { key: 'category_of_site', label: 'Category Of Site' },
  { key: 'assignee', label: 'Assignee' },
  { key: 'assignee_hint', label: 'Assignee Hint' },
  { key: 'customer_name', label: 'Client Name' },
  { key: 'mobile_no', label: 'Mobile' },
  { key: 'client_email', label: 'Client Email' },
  { key: 'status', label: 'Status' },
  { key: 'stage_progress', label: 'Stage Progress' },
  { key: 'alert', label: 'Alert' },
  { key: 'notes', label: 'Notes' },
  { key: 'updated_at', label: 'Updated At' },
];

const DEFAULT_COLUMNS: ColumnKey[] = [
  'source_row',
  'organization',
  'state',
  'assignee',
  'customer_name',
  'mobile_no',
  'client_email',
  'status',
  'alert',
];

export function RecordsPage() {
  const { user } = useAuth();
  const [records, setRecords] = useState<RecordItem[]>([]);
  const [assignees, setAssignees] = useState<User[]>([]);
  const [stages, setStages] = useState<StageItem[]>([]);
  const [selected, setSelected] = useState<RecordItem | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);

  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [total, setTotal] = useState(0);

  const [q, setQ] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [assigneeFilter, setAssigneeFilter] = useState<number | ''>('');
  const [alertOnly, setAlertOnly] = useState(false);
  const [loading, setLoading] = useState(false);
  const [importPath, setImportPath] = useState('../Phoneme.xlsx');

  const [newStageCode, setNewStageCode] = useState('');
  const [newStageName, setNewStageName] = useState('');
  const [newStageOrder, setNewStageOrder] = useState(100);

  const [showAllColumns, setShowAllColumns] = useState(false);
  const [selectedColumns, setSelectedColumns] = useState<ColumnKey[]>(DEFAULT_COLUMNS);

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total, pageSize]);
  const allColumnKeys = useMemo(() => COLUMN_OPTIONS.map((column) => column.key), []);
  const columnLabelMap = useMemo(
    () => Object.fromEntries(COLUMN_OPTIONS.map((column) => [column.key, column.label])) as Record<ColumnKey, string>,
    [],
  );
  const visibleColumns = useMemo(
    () => (showAllColumns ? allColumnKeys : selectedColumns),
    [allColumnKeys, selectedColumns, showAllColumns],
  );

  const statusOptions = useMemo(() => {
    const options = ['NEW', 'EMAIL_CAPTURED', ...stages.map((s) => s.code)];
    return Array.from(new Set(options));
  }, [stages]);

  useEffect(() => {
    void loadAssignees();
    void loadStages();
  }, []);

  useEffect(() => {
    void loadRecords();
  }, [page, q, statusFilter, assigneeFilter, alertOnly]);

  async function loadAssignees() {
    const { data } = await api.get<User[]>('/users/assignees');
    setAssignees(data);
  }

  async function loadStages() {
    const { data } = await api.get<StageItem[]>('/records/stages');
    setStages(data);
  }

  async function loadRecords() {
    setLoading(true);
    try {
      const params: Record<string, string | number | boolean> = {
        page,
        page_size: pageSize,
      };
      if (q.trim()) params.q = q.trim();
      if (statusFilter) params.status = statusFilter;
      if (assigneeFilter !== '') params.assignee_id = assigneeFilter;
      if (alertOnly) params.alert_pending = true;

      const { data } = await api.get<PaginatedRecords>('/records', { params });
      setRecords(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }

  function openEditor(item: RecordItem) {
    const stageStates: Draft['stage_states'] = {};
    for (const stage of item.stage_updates) {
      stageStates[stage.stage_id] = {
        is_completed: stage.is_completed,
        notes: stage.notes || '',
      };
    }

    setSelected(item);
    setDraft({
      customer_name: item.customer_name || '',
      mobile_no: item.mobile_no || '',
      client_email: item.client_email || '',
      notes: item.notes || '',
      assignee_id: item.assignee_id ?? '',
      email_alert_pending: item.email_alert_pending,
      stage_states: stageStates,
    });
  }

  async function saveDraft() {
    if (!selected || !draft) return;

    const payload: Record<string, unknown> = {};

    if (user?.role === 'ASSIGNEE') {
      payload.customer_name = draft.customer_name;
      payload.mobile_no = draft.mobile_no;
      payload.client_email = draft.client_email;
      payload.notes = draft.notes;
    }

    if (user?.role === 'SUPER_ADMIN') {
      payload.customer_name = draft.customer_name;
      payload.mobile_no = draft.mobile_no;
      payload.client_email = draft.client_email;
      payload.notes = draft.notes;
      payload.assignee_id = draft.assignee_id === '' ? null : draft.assignee_id;
      payload.email_alert_pending = draft.email_alert_pending;
      payload.stage_updates = stages.map((stage) => ({
        stage_id: stage.id,
        is_completed: draft.stage_states[stage.id]?.is_completed || false,
        notes: draft.stage_states[stage.id]?.notes || null,
      }));
    }

    if (user?.role === 'EMAIL_TEAM') {
      payload.notes = draft.notes;
      payload.email_alert_pending = draft.email_alert_pending;
      payload.stage_updates = stages.map((stage) => ({
        stage_id: stage.id,
        is_completed: draft.stage_states[stage.id]?.is_completed || false,
        notes: draft.stage_states[stage.id]?.notes || null,
      }));
    }

    await api.patch(`/records/${selected.id}`, payload);
    setSelected(null);
    setDraft(null);
    await loadRecords();
  }

  async function acknowledgeAlert(recordId: number) {
    await api.post(`/records/${recordId}/acknowledge-alert`);
    await loadRecords();
  }

  async function importWorkbook() {
    await api.post('/records/import', null, { params: { filepath: importPath } });
    setPage(1);
    await loadAssignees();
    await loadStages();
    await loadRecords();
  }

  async function createStage() {
    if (!newStageCode.trim() || !newStageName.trim()) return;

    await api.post('/records/stages', {
      code: newStageCode.trim().toUpperCase(),
      name: newStageName.trim(),
      display_order: newStageOrder,
    });
    setNewStageCode('');
    setNewStageName('');
    setNewStageOrder(100);
    await loadStages();
  }

  function toggleAllColumns(checked: boolean) {
    setShowAllColumns(checked);
    setSelectedColumns(checked ? allColumnKeys : DEFAULT_COLUMNS);
  }

  function toggleColumn(column: ColumnKey) {
    setShowAllColumns(false);
    setSelectedColumns((current) => {
      const exists = current.includes(column);
      if (exists) {
        if (current.length === 1) {
          return current;
        }
        return current.filter((item) => item !== column);
      }
      return [...current, column];
    });
  }

  function renderCell(item: RecordItem, key: ColumnKey) {
    switch (key) {
      case 'source_row':
        return item.source_row;
      case 'sl_no':
        return item.sl_no || '-';
      case 'organization':
        return item.short_name || item.custodian_organization || '-';
      case 'short_name':
        return item.short_name || '-';
      case 'custodian_organization':
        return item.custodian_organization || '-';
      case 'state':
        return item.state || '-';
      case 'city':
        return item.city || '-';
      case 'category_of_site':
        return item.category_of_site || '-';
      case 'assignee':
        return item.assignee?.full_name || item.assignee_name_hint || 'Unassigned';
      case 'assignee_hint':
        return item.assignee_name_hint || '-';
      case 'customer_name':
        return item.customer_name || '-';
      case 'mobile_no':
        return item.mobile_no || '-';
      case 'client_email':
        return item.client_email || '-';
      case 'status':
        return item.status;
      case 'stage_progress': {
        const completed = item.stage_updates.filter((stage) => stage.is_completed).length;
        return item.stage_updates.length ? `${completed}/${item.stage_updates.length}` : '-';
      }
      case 'alert':
        return item.email_alert_pending ? 'Pending' : 'Done';
      case 'notes':
        return item.notes || '-';
      case 'updated_at':
        return new Date(item.updated_at).toLocaleString();
      default:
        return '-';
    }
  }

  return (
    <ShellLayout>
      <section className="panel">
        <div className="records-toolbar">
          <input
            placeholder="Search organization/code/email"
            value={q}
            onChange={(e) => {
              setPage(1);
              setQ(e.target.value);
            }}
          />

          <select
            value={statusFilter}
            onChange={(e) => {
              setPage(1);
              setStatusFilter(e.target.value || '');
            }}
          >
            <option value="">All Status</option>
            {statusOptions.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>

          <select
            value={assigneeFilter}
            onChange={(e) => {
              setPage(1);
              setAssigneeFilter(e.target.value ? Number(e.target.value) : '');
            }}
          >
            <option value="">All Assignees</option>
            {assignees.map((item) => (
              <option key={item.id} value={item.id}>
                {item.full_name}
              </option>
            ))}
          </select>

          <label className="checkbox-inline">
            <input
              type="checkbox"
              checked={alertOnly}
              onChange={(e) => {
                setPage(1);
                setAlertOnly(e.target.checked);
              }}
            />
            Pending Alerts
          </label>
        </div>

        {user?.role === 'SUPER_ADMIN' ? (
          <>
            <div className="import-row">
              <input value={importPath} onChange={(e) => setImportPath(e.target.value)} />
              <button className="btn btn-primary" type="button" onClick={importWorkbook}>
                Import Excel (Overwrite)
              </button>
            </div>

            <div className="records-toolbar">
              <input
                placeholder="Stage Code"
                value={newStageCode}
                onChange={(e) => setNewStageCode(e.target.value)}
              />
              <input
                placeholder="Stage Name"
                value={newStageName}
                onChange={(e) => setNewStageName(e.target.value)}
              />
              <input
                type="number"
                value={newStageOrder}
                onChange={(e) => setNewStageOrder(Number(e.target.value))}
              />
              <button className="btn btn-outline" type="button" onClick={createStage}>
                Add Stage
              </button>
            </div>
          </>
        ) : null}

        <div className="column-tools">
          <label className="checkbox-inline">
            <input
              type="checkbox"
              checked={showAllColumns}
              onChange={(e) => toggleAllColumns(e.target.checked)}
            />
            Show All Columns
          </label>
          <details className="column-picker">
            <summary>Choose Columns</summary>
            <div className="column-picker-grid">
              {COLUMN_OPTIONS.map((column) => (
                <label className="checkbox-inline" key={column.key}>
                  <input
                    type="checkbox"
                    checked={visibleColumns.includes(column.key)}
                    onChange={() => toggleColumn(column.key)}
                  />
                  {column.label}
                </label>
              ))}
            </div>
          </details>
        </div>

        <div className="table-wrap">
          <table style={{ minWidth: visibleColumns.length > 10 ? 1400 : 820 }}>
            <thead>
              <tr>
                {visibleColumns.map((column) => (
                  <th key={column}>{columnLabelMap[column]}</th>
                ))}
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {records.map((item) => (
                <tr key={item.id} className={item.email_alert_pending ? 'row-alert' : ''}>
                  {visibleColumns.map((column) => (
                    <td key={`${item.id}-${column}`}>{renderCell(item, column)}</td>
                  ))}
                  <td className="action-col">
                    <button className="btn btn-sm" type="button" onClick={() => openEditor(item)}>
                      Edit
                    </button>
                    {item.email_alert_pending && user?.role !== 'ASSIGNEE' ? (
                      <button
                        className="btn btn-sm btn-outline"
                        type="button"
                        onClick={() => acknowledgeAlert(item.id)}
                      >
                        Ack
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {loading ? <p>Loading...</p> : null}
        </div>

        <div className="pager">
          <button className="btn btn-sm" type="button" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            Prev
          </button>
          <span>
            Page {page} / {totalPages} ({total} records)
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

      {selected && draft ? (
        <section
          className="modal-backdrop"
          onClick={() => {
            setSelected(null);
            setDraft(null);
          }}
        >
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3>Edit Record #{selected.id}</h3>
            <div className="form-grid two-col">
              <label>
                Customer Name
                <input
                  value={draft.customer_name}
                  onChange={(e) => setDraft({ ...draft, customer_name: e.target.value })}
                />
              </label>
              <label>
                Mobile No
                <input value={draft.mobile_no} onChange={(e) => setDraft({ ...draft, mobile_no: e.target.value })} />
              </label>
              <label>
                Client Email
                <input
                  value={draft.client_email}
                  onChange={(e) => setDraft({ ...draft, client_email: e.target.value })}
                />
              </label>

              {(user?.role === 'SUPER_ADMIN' || user?.role === 'EMAIL_TEAM') && (
                <>
                  {stages.map((stage) => (
                    <label className="checkbox-inline" key={stage.id}>
                      <input
                        type="checkbox"
                        checked={draft.stage_states[stage.id]?.is_completed || false}
                        onChange={(e) =>
                          setDraft({
                            ...draft,
                            stage_states: {
                              ...draft.stage_states,
                              [stage.id]: {
                                is_completed: e.target.checked,
                                notes: draft.stage_states[stage.id]?.notes || '',
                              },
                            },
                          })
                        }
                      />
                      {stage.name}
                    </label>
                  ))}
                  <label className="checkbox-inline">
                    <input
                      type="checkbox"
                      checked={draft.email_alert_pending}
                      onChange={(e) => setDraft({ ...draft, email_alert_pending: e.target.checked })}
                    />
                    Email Alert Pending
                  </label>
                </>
              )}

              {user?.role === 'SUPER_ADMIN' ? (
                <label>
                  Assignee
                  <select
                    value={draft.assignee_id}
                    onChange={(e) =>
                      setDraft({ ...draft, assignee_id: e.target.value ? Number(e.target.value) : '' })
                    }
                  >
                    <option value="">Unassigned</option>
                    {assignees.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.full_name}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}

              <label className="full-width">
                Notes
                <textarea value={draft.notes} onChange={(e) => setDraft({ ...draft, notes: e.target.value })} />
              </label>
            </div>

            <div className="modal-actions">
              <button
                className="btn btn-outline"
                onClick={() => {
                  setSelected(null);
                  setDraft(null);
                }}
                type="button"
              >
                Cancel
              </button>
              <button className="btn btn-primary" onClick={saveDraft} type="button">
                Save
              </button>
            </div>
          </div>
        </section>
      ) : null}
    </ShellLayout>
  );
}
