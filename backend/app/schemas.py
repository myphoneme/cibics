from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import Role


class Token(BaseModel):
    access_token: str
    token_type: str = 'bearer'


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=180)
    password: str


class UserBase(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=180)
    role: Role
    is_active: bool = True
    receive_alert: bool = True


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    email: str | None = Field(default=None, min_length=3, max_length=180)
    role: Role | None = None
    is_active: bool | None = None
    receive_alert: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserSelfUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    current_password: str | None = None
    new_password: str | None = Field(default=None, min_length=8, max_length=128)


class UserOut(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StageOut(BaseModel):
    id: int
    code: str
    name: str
    display_order: int
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StageCreate(BaseModel):
    code: str = Field(min_length=2, max_length=120)
    name: str = Field(min_length=2, max_length=180)
    display_order: int = Field(ge=1, le=10000)


class StageUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    display_order: int | None = Field(default=None, ge=1, le=10000)
    is_active: bool | None = None


class RecordStagePatch(BaseModel):
    stage_id: int
    is_completed: bool
    notes: str | None = None


class RecordPatch(BaseModel):
    customer_name: str | None = None
    mobile_no: str | None = None
    client_email: str | None = None
    assignee_id: int | None = None
    email_alert_pending: bool | None = None
    notes: str | None = None
    stage_updates: list[RecordStagePatch] | None = None


class RecordStageOut(BaseModel):
    stage_id: int
    stage_code: str
    stage_name: str
    display_order: int
    is_completed: bool
    completed_at: datetime | None
    notes: str | None


class RecordOut(BaseModel):
    id: int
    source_row: int

    sl_no: str | None
    list_type: str | None
    type: str | None
    po_status_raw: str | None
    custodian_code: str | None
    unlo_code: str | None
    short_name: str | None
    custodian_organization: str | None
    state: str | None
    site_address: str | None
    city: str | None
    pincode: str | None
    category_of_site: str | None

    custodian_contact_person_name: str | None
    custodian_contact_person_number: str | None
    custodian_email: str | None

    customer_name: str | None
    mobile_no: str | None
    client_email: str | None

    status: str
    assignee_name_hint: str | None
    assignee_id: int | None
    email_alert_pending: bool
    notes: str | None
    is_active: bool
    updated_by: int | None
    deleted_by: int | None
    created_at: datetime
    updated_at: datetime

    assignee: UserOut | None
    stage_updates: list[RecordStageOut]


class PaginatedRecords(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[RecordOut]


class ImportResponse(BaseModel):
    imported: int
    created: int
    updated: int
    assignees_created: int


class ImportPreviewRow(BaseModel):
    source_row: int
    sl_no: str | None
    short_name: str | None
    custodian_organization: str | None
    state: str | None
    custodian_code: str | None
    unlo_code: str | None
    duplicate: bool
    duplicate_reasons: list[str]


class ImportPreviewResponse(BaseModel):
    total_rows: int
    duplicate_rows: int
    insertable_rows: int
    preview_rows: list[ImportPreviewRow]


class ImportUploadResponse(BaseModel):
    imported: int
    created: int
    updated: int
    assignees_created: int
    skipped_duplicates: int


class DashboardSummary(BaseModel):
    total_records: int
    with_client_email: int
    without_client_email: int
    alerts_pending: int
    unassigned: int
    unassigned_with_client_email: int
    recent_email_captured_24h: int
    recent_email_updated_24h: int


class AssigneeSummary(BaseModel):
    assignee_id: int | None
    assignee_name: str
    total: int
    with_client_email: int
    recent_email_captured_24h: int
    recent_email_updated_24h: int
    alerts_pending: int
    po_received: int
    proposal_sent: int
    feasibility_pending: int


class StatusSummary(BaseModel):
    status: str
    count: int


class StageProgressRow(BaseModel):
    key: str
    label: str
    counts: list[int]


class StageProgressResponse(BaseModel):
    start_date: str
    days: int
    dates: list[str]
    rows: list[StageProgressRow]


class StageProgressDetailItem(BaseModel):
    assignee_id: int | None
    assignee_name: str
    record_count: int


class StageProgressDetailResponse(BaseModel):
    date: str
    stage_key: str
    stage_label: str
    items: list[StageProgressDetailItem]
