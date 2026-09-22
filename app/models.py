import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class APIKey(Base):
    """Represents an issued API key tied to a customer plan."""

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    key: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    plan: Mapped[str] = mapped_column(String(32), default="starter")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Stripe references (nullable — keys can also be created manually)
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, unique=True, index=True
    )

    daily_limit: Mapped[int] = mapped_column(Integer, default=100)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    usage_logs: Mapped[list["UsageLog"]] = relationship(
        back_populates="api_key", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<APIKey {self.key[:12]}... plan={self.plan} email={self.email}>"


class UsageLog(Base):
    """One row per API request — used for daily rate-limit enforcement."""

    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    api_key_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("api_keys.id"), nullable=False, index=True
    )
    endpoint: Mapped[str] = mapped_column(String(128), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )

    api_key: Mapped["APIKey"] = relationship(back_populates="usage_logs")
