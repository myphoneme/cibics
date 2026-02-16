export type Role = 'SUPER_ADMIN' | 'ASSIGNEE' | 'EMAIL_TEAM';

export interface User {
  id: number;
  full_name: string;
  email: string;
  role: Role;
  is_active: boolean;
  receive_alert: boolean;
  created_at: string;
  updated_at: string;
}

export interface StageItem {
  id: number;
  code: string;
  name: string;
  display_order: number;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface RecordStageItem {
  stage_id: number;
  stage_code: string;
  stage_name: string;
  display_order: number;
  is_completed: boolean;
  completed_at: string | null;
  notes: string | null;
}

export interface RecordItem {
  id: number;
  source_row: number;
  sl_no: string | null;
  short_name: string | null;
  custodian_organization: string | null;
  state: string | null;
  city: string | null;
  category_of_site: string | null;
  customer_name: string | null;
  mobile_no: string | null;
  client_email: string | null;
  status: string;
  assignee_id: number | null;
  assignee_name_hint: string | null;
  email_alert_pending: boolean;
  notes: string | null;
  assignee: User | null;
  stage_updates: RecordStageItem[];
  updated_at: string;
}

export interface PaginatedRecords {
  total: number;
  page: number;
  page_size: number;
  items: RecordItem[];
}

export interface DashboardSummary {
  total_records: number;
  with_client_email: number;
  without_client_email: number;
  alerts_pending: number;
  unassigned: number;
}

export interface AssigneeSummary {
  assignee_id: number | null;
  assignee_name: string;
  total: number;
  with_client_email: number;
  alerts_pending: number;
  po_received: number;
  proposal_sent: number;
  feasibility_pending: number;
}

export interface StatusSummary {
  status: string;
  count: number;
}
