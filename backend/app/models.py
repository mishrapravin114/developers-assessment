import decimal
import uuid
from datetime import datetime
from enum import Enum

from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel


# WorkLog Settlement System Enums
class TimeSegmentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REMOVED = "REMOVED"


class RemittanceStatus(str, Enum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)
    worklogs: list["WorkLog"] = Relationship(back_populates="user", cascade_delete=True)
    remittances: list["Remittance"] = Relationship(back_populates="user", cascade_delete=True)


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(ItemBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# WorkLog Settlement System Models
class Task(SQLModel, table=True):
    """A task that workers can log time against."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(max_length=255)
    hourly_rate: decimal.Decimal = Field(default=decimal.Decimal("0"), max_digits=10, decimal_places=2)
    worklogs: list["WorkLog"] = Relationship(back_populates="task", cascade_delete=True)


class WorkLog(SQLModel, table=True):
    """Container for all work done by a user against a task."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", nullable=False, ondelete="CASCADE")
    task_id: uuid.UUID = Field(foreign_key="task.id", nullable=False, ondelete="CASCADE")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user: User | None = Relationship(back_populates="worklogs")
    task: Task | None = Relationship(back_populates="worklogs")
    time_segments: list["TimeSegment"] = Relationship(back_populates="worklog", cascade_delete=True)
    adjustments: list["Adjustment"] = Relationship(back_populates="worklog", cascade_delete=True)
    remittance_worklogs: list["RemittanceWorkLog"] = Relationship(
        back_populates="worklog", cascade_delete=True
    )


class TimeSegment(SQLModel, table=True):
    """Individual time entry within a worklog. Can be removed or adjusted."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    worklog_id: uuid.UUID = Field(foreign_key="worklog.id", nullable=False, ondelete="CASCADE")
    minutes: int = Field(ge=0)
    status: TimeSegmentStatus = Field(default=TimeSegmentStatus.ACTIVE)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    worklog: WorkLog | None = Relationship(back_populates="time_segments")


class Adjustment(SQLModel, table=True):
    """Retroactive deduction or addition applied to a worklog."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    worklog_id: uuid.UUID = Field(foreign_key="worklog.id", nullable=False, ondelete="CASCADE")
    amount: decimal.Decimal = Field(max_digits=12, decimal_places=2)  # Negative for deductions
    reason: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    worklog: WorkLog | None = Relationship(back_populates="adjustments")


class Remittance(SQLModel, table=True):
    """Settlement/payout for a user. One per settlement run."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", nullable=False, ondelete="CASCADE")
    total_amount: decimal.Decimal = Field(default=decimal.Decimal("0"), max_digits=12, decimal_places=2)
    status: RemittanceStatus = Field(default=RemittanceStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user: User | None = Relationship(back_populates="remittances")
    remittance_worklogs: list["RemittanceWorkLog"] = Relationship(
        back_populates="remittance", cascade_delete=True
    )


class RemittanceWorkLog(SQLModel, table=True):
    """Links worklogs to remittances with amount snapshot at settlement time."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    remittance_id: uuid.UUID = Field(foreign_key="remittance.id", nullable=False, ondelete="CASCADE")
    worklog_id: uuid.UUID = Field(foreign_key="worklog.id", nullable=False, ondelete="CASCADE")
    amount: decimal.Decimal = Field(max_digits=12, decimal_places=2)
    remittance: Remittance | None = Relationship(back_populates="remittance_worklogs")
    worklog: WorkLog | None = Relationship(back_populates="remittance_worklogs")


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
