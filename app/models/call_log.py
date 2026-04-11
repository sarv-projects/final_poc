"""Call log model for analytics and debugging."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class CallLog(Base):
    __tablename__ = "call_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(
        UUID(as_uuid=True), ForeignKey("businesses.id"), nullable=False
    )
    call_type = Column(String(20), nullable=False)  # inbound | outbound
    vapi_call_id = Column(String(255), unique=True, nullable=False)
    customer_phone = Column(String(20))
    customer_name = Column(String(255))
    duration_seconds = Column(Integer)
    outcome = Column(
        String(50)
    )  # resolved | transferred | abandoned | timeout | owner_declined
    transcript = Column(Text)
    summary = Column(Text)
    credits_used = Column(Integer)
    slack_live_thread_ts = Column(String(50))
    slack_summary_thread_ts = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
