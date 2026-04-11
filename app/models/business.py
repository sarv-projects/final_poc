"""Business (tenant) model."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class Business(Base):
    __tablename__ = "businesses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_number = Column(String(20), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    city = Column(String(255))
    hours = Column(Text)
    services = Column(Text)
    fallback_number = Column(String(20), nullable=False)

    # Slack integration
    nango_connection_id = Column(UUID(as_uuid=True))
    slack_workspace = Column(String(255))
    slack_live_channel = Column(String(50))
    slack_summary_channel = Column(String(50))

    # Voice config (shared)
    voice_id = Column(String(100), default="pMsXgVXv3BLzUgSXRplE")

    # Outbound settings
    outbound_welcome_template = Column(Text)
    callback_trigger_phrase = Column(
        String(255), default="Would you like us to call you back?"
    )
    max_call_duration_minutes = Column(Integer, default=10)
    enable_voice_callbacks = Column(Boolean, default=True)
    inject_chat_context = Column(Boolean, default=True)
    post_call_summary_to_chat = Column(Boolean, default=False)

    # Inbound settings
    inbound_welcome_template = Column(Text)
    enable_inbound_call_handling = Column(Boolean, default=True)

    # Shared behavior
    human_transfer_on_escalation = Column(Boolean, default=True)
    check_with_owner_before_transfer = Column(Boolean, default=True)
    owner_check_method = Column(String(20), default="slack")  # slack | call | both
    owner_check_timeout_seconds = Column(Integer, default=30)
    intent_based_transfer_detection = Column(Boolean, default=True)
    owner_initiated_handover = Column(Boolean, default=True)
    live_transcript_to_slack = Column(Boolean, default=True)
    whisper_coaching_via_slack = Column(Boolean, default=True)
    call_recording_enabled = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
