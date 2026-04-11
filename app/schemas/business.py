"""Pydantic schemas for business model."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class BusinessBase(BaseModel):
    phone_number: str = Field(..., max_length=20)
    display_name: str = Field(..., max_length=255)
    city: Optional[str] = None
    hours: Optional[str] = None
    services: Optional[str] = None
    fallback_number: str = Field(..., max_length=20)

    # Slack
    nango_connection_id: Optional[uuid.UUID] = None
    slack_workspace: Optional[str] = None
    slack_live_channel: Optional[str] = None
    slack_summary_channel: Optional[str] = None

    # Voice
    voice_id: str = "pMsXgVXv3BLzUgSXRplE"

    # Outbound
    outbound_welcome_template: Optional[str] = None
    callback_trigger_phrase: str = "Would you like us to call you back?"
    max_call_duration_minutes: int = 10
    enable_voice_callbacks: bool = True
    inject_chat_context: bool = True
    post_call_summary_to_chat: bool = False

    # Inbound
    inbound_welcome_template: Optional[str] = None
    enable_inbound_call_handling: bool = True

    # Shared behavior
    human_transfer_on_escalation: bool = True
    check_with_owner_before_transfer: bool = True
    owner_check_method: str = "slack"
    owner_check_timeout_seconds: int = 30
    intent_based_transfer_detection: bool = True
    owner_initiated_handover: bool = True
    live_transcript_to_slack: bool = True
    whisper_coaching_via_slack: bool = True
    call_recording_enabled: bool = True


class BusinessCreate(BusinessBase):
    pass


class BusinessUpdate(BusinessBase):
    phone_number: Optional[str] = Field(None, max_length=20)
    display_name: Optional[str] = Field(None, max_length=255)
    fallback_number: Optional[str] = Field(None, max_length=20)


class BusinessResponse(BusinessBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
