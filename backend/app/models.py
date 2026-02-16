import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AuditMixin:
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Role(str, enum.Enum):
    SUPER_ADMIN = 'SUPER_ADMIN'
    ASSIGNEE = 'ASSIGNEE'
    EMAIL_TEAM = 'EMAIL_TEAM'


class User(AuditMixin, Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(180), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role), nullable=False, index=True)
    receive_alert: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    assigned_records: Mapped[list['Record']] = relationship('Record', back_populates='assignee')


class Record(AuditMixin, Base):
    __tablename__ = 'records'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_row: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)

    sl_no: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    list_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    po_status_raw: Mapped[str | None] = mapped_column(String(180), nullable=True)
    custodian_code: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    unlo_code: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    short_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    custodian_organization: Mapped[str | None] = mapped_column(String(300), nullable=True, index=True)
    state: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    site_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    category_of_site: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)

    custodian_contact_person_name: Mapped[str | None] = mapped_column(String(220), nullable=True)
    custodian_contact_person_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    custodian_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    customer_name: Mapped[str | None] = mapped_column(String(220), nullable=True)
    mobile_no: Mapped[str | None] = mapped_column(String(60), nullable=True)
    client_email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(120), default='NEW', nullable=False, index=True)

    assignee_name_hint: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)

    email_alert_pending: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    last_email_alert_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    assignee: Mapped[User | None] = relationship('User', back_populates='assigned_records')
    stage_statuses: Mapped[list['RecordStageStatus']] = relationship(
        'RecordStageStatus', back_populates='record', cascade='all, delete-orphan'
    )
    updates: Mapped[list['RecordUpdateLog']] = relationship(
        'RecordUpdateLog', back_populates='record', cascade='all, delete-orphan'
    )


class StageDefinition(AuditMixin, Base):
    __tablename__ = 'stage_definitions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    record_statuses: Mapped[list['RecordStageStatus']] = relationship('RecordStageStatus', back_populates='stage')


class RecordStageStatus(AuditMixin, Base):
    __tablename__ = 'record_stage_statuses'
    __table_args__ = (UniqueConstraint('record_id', 'stage_id', name='uq_record_stage'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    record_id: Mapped[int] = mapped_column(ForeignKey('records.id'), nullable=False, index=True)
    stage_id: Mapped[int] = mapped_column(ForeignKey('stage_definitions.id'), nullable=False, index=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    record: Mapped[Record] = relationship('Record', back_populates='stage_statuses')
    stage: Mapped[StageDefinition] = relationship('StageDefinition', back_populates='record_statuses')


class RecordUpdateLog(AuditMixin, Base):
    __tablename__ = 'record_update_logs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey('records.id'), nullable=False, index=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    field_name: Mapped[str] = mapped_column(String(120), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    record: Mapped[Record] = relationship('Record', back_populates='updates')
