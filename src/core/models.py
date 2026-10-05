from datetime import datetime, timezone
import uuid
from sqlalchemy import String, Float, Integer, Boolean, DateTime, Text, JSON, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

def uid():
    return str(uuid.uuid4())

def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class Base(DeclarativeBase):
    pass

class Tenant(Base):
    __tablename__ = 'tenants'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(10), default='PKR')
    timezone: Mapped[str] = mapped_column(String(60), default='Asia/Karachi')
    demo: Mapped[bool] = mapped_column(Boolean, default=False)
    external_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    web_search: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(Text, default='')
    oidc_subject: Mapped[str | None] = mapped_column(String(500), nullable=True, unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class Membership(Base):
    __tablename__ = 'memberships'
    __table_args__ = (UniqueConstraint('tenant_id', 'user_id'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    role: Mapped[str] = mapped_column(String(30), default='analyst')
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class Session(Base):
    __tablename__ = 'sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id'))
    expires_at: Mapped[datetime] = mapped_column(DateTime)

class LoginAttempt(Base):
    __tablename__ = 'login_attempts'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    identity_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Invite(Base):
    __tablename__ = 'invites'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id'))
    email: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30))
    expires_at: Mapped[datetime] = mapped_column(DateTime)

class Scoped:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(ForeignKey('tenants.id'), index=True)

class Dataset(Scoped, Base):
    __tablename__ = 'datasets'
    __table_args__ = (UniqueConstraint('tenant_id', 'file_hash'),)
    name: Mapped[str] = mapped_column(String(200))
    file_hash: Mapped[str] = mapped_column(String(64))
    file_path: Mapped[str] = mapped_column(Text)
    rows: Mapped[int] = mapped_column(Integer)
    quality: Mapped[dict] = mapped_column(JSON, default=dict)
    zero_days: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Sale(Scoped, Base):
    __tablename__ = 'sales'
    dataset_id: Mapped[str] = mapped_column(ForeignKey('datasets.id'), index=True)
    date: Mapped[datetime] = mapped_column(DateTime, index=True)
    sku: Mapped[str] = mapped_column(String(120), index=True)
    product: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(120), default='General')
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    customer_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    transaction_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    stockout: Mapped[bool] = mapped_column(Boolean, default=False)

class Product(Scoped, Base):
    __tablename__ = 'products'
    __table_args__ = (UniqueConstraint('tenant_id', 'sku'),)
    sku: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(120), default='General')
    price: Mapped[float] = mapped_column(Float, default=0)
    unit_cost: Mapped[float] = mapped_column(Float, default=0)
    on_hand: Mapped[float] = mapped_column(Float, default=0)
    reserved: Mapped[float] = mapped_column(Float, default=0)
    backorders: Mapped[float] = mapped_column(Float, default=0)
    lead_days: Mapped[int] = mapped_column(Integer, default=7)
    lead_std: Mapped[float] = mapped_column(Float, default=0)
    pack_size: Mapped[int] = mapped_column(Integer, default=1)
    moq: Mapped[int] = mapped_column(Integer, default=1)
    ordering_cost: Mapped[float] = mapped_column(Float, default=500)
    holding_rate: Mapped[float] = mapped_column(Float, default=0.2)
    shelf_days: Mapped[int] = mapped_column(Integer, default=365)
    supplier: Mapped[str] = mapped_column(String(200), default='Not specified')
    expiry_date: Mapped[str | None] = mapped_column(String(10), nullable=True)

class Movement(Scoped, Base):
    __tablename__ = 'inventory_movements'
    sku: Mapped[str] = mapped_column(String(120))
    delta: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Forecast(Scoped, Base):
    __tablename__ = 'forecasts'
    dataset_id: Mapped[str] = mapped_column(String(36))
    sku: Mapped[str] = mapped_column(String(120))
    model: Mapped[str] = mapped_column(String(80))
    horizon: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Approval(Scoped, Base):
    __tablename__ = 'approvals'
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    payload: Mapped[dict] = mapped_column(JSON)
    fingerprint: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(30), default='pending')
    created_by: Mapped[str] = mapped_column(String(36))
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decision_note: Mapped[str] = mapped_column(Text, default='')
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Expense(Scoped, Base):
    __tablename__ = 'expenses'
    date: Mapped[datetime] = mapped_column(DateTime)
    category: Mapped[str] = mapped_column(String(100))
    amount: Mapped[float] = mapped_column(Float)
    note: Mapped[str] = mapped_column(String(300), default='')

class Employee(Scoped, Base):
    __tablename__ = 'employees'
    name: Mapped[str] = mapped_column(String(120))
    position: Mapped[str] = mapped_column(String(120))
    weekly_hours: Mapped[int] = mapped_column(Integer, default=40)
    availability: Mapped[str] = mapped_column(String(200), default='Mon-Sat')

class KnowledgeDoc(Scoped, Base):
    __tablename__ = 'knowledge_documents'
    title: Mapped[str] = mapped_column(String(200))
    scope: Mapped[str] = mapped_column(String(30), default='general')
    content_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Research(Scoped, Base):
    __tablename__ = 'research'
    query: Mapped[str] = mapped_column(String(300))
    payload: Mapped[list] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(30), default='new')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class AgentRun(Scoped, Base):
    __tablename__ = 'agent_runs'
    user_id: Mapped[str] = mapped_column(String(36))
    question: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Report(Scoped, Base):
    __tablename__ = 'reports'
    title: Mapped[str] = mapped_column(String(200))
    scope: Mapped[str] = mapped_column(String(30), default='general')
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Audit(Scoped, Base):
    __tablename__ = 'audit_log'
    user_id: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(80))
    detail: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

class Job(Scoped, Base):
    __tablename__ = 'jobs'
    __table_args__ = (UniqueConstraint('tenant_id', 'dedupe_key'),)
    user_id: Mapped[str] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(30))
    payload: Mapped[dict] = mapped_column(JSON)
    dedupe_key: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(30), default='queued', index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class Schedule(Scoped, Base):
    __tablename__ = 'schedules'
    user_id: Mapped[str] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(30))
    payload: Mapped[dict] = mapped_column(JSON)
    interval_hours: Mapped[int] = mapped_column(Integer, default=24)
    next_run: Mapped[datetime] = mapped_column(DateTime, default=now)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

