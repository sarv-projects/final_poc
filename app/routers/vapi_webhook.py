"""VAPI webhook handler for inbound calls and call events."""

import asyncio
import re
from typing import Optional

from fastapi import APIRouter, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.business import Business
from app.models.call_log import CallLog
from app.services.groq_service import groq_service
from app.services.prompt_builder import prompt_builder
from app.services.slack_service import slack_service

router = APIRouter()


async def _get_db():
    """Helper to get DB session inside webhook."""
    async for session in get_db():
        return session


async def _get_shared_prompt(db: AsyncSession) -> str:
    from app.models.prompt_template import PromptTemplate

    result = await db.execute(select(PromptTemplate).limit(1))
    template = result.scalar_one_or_none()
    if template and hasattr(template, "shared_system_prompt"):
        value = template.shared_system_prompt
        # If it's a SQLAlchemy InstrumentedAttribute, get the value
        if hasattr(value, "__str__") and not isinstance(value, str):
            value = str(value)
        if isinstance(value, str):
            return value
        # If it's a SQLAlchemy column property, get the value
        if hasattr(value, "__get__"):
            return value.__get__(template, type(template))
        return str(value)
    return "You are a helpful assistant."


def extract_ani_from_diversion(diversion: str) -> Optional[str]:
    """Extract phone number from SIP Diversion header."""
    if not diversion:
        return None
    match = re.search(r"sip:(\+?\d+)", diversion)
    return match.group(1) if match else None


@router.post("")
async def vapi_webhook(request: Request):
    """Handle all VAPI call events."""
    payload = await request.json()
    message = payload.get("message", {})
    event_type = message.get("type")

    if event_type == "assistant-request":
        return await handle_assistant_request(payload)
    elif event_type == "transcript":
        return await handle_transcript(payload)
    elif event_type == "end-of-call-report":
        return await handle_end_of_call_report(payload)
    elif event_type == "hang":
        return {"status": "ok"}

    return {"status": "ignored"}


async def handle_assistant_request(payload: dict) -> dict:
    """Handle VAPI assistant-request for inbound calls."""
    message = payload.get("message", {})
    call_data = message.get("call", payload.get("call", {}))
    phone_data = call_data.get("phoneNumber", {})
    from_number = phone_data.get("number")
    diversion = phone_data.get("diversion")

    # E-1: PA → Inbound loop detection
    if from_number == settings.VAPI_OUTBOUND_PHONE:
        return {
            "assistant": {
                "model": {"provider": "openai", "model": "gpt-4o-mini"},
                "voice": {"provider": "11labs", "voiceId": "pMsXgVXv3BLzUgSXRplE"},
                "firstMessage": "This line is currently busy. Please try again later.",
                "endCallFunctionEnabled": True,
                "maxDurationSeconds": 3,
            }
        }

    # Extract ANI and lookup business
    ani = extract_ani_from_diversion(diversion) or from_number
    db = await _get_db()
    if db is None:
        return {"status": "db_unavailable"}

    result = await db.execute(select(Business).where(Business.phone_number == ani))
    business = result.scalar_one_or_none()

    # E-6: ANI lookup fails
    if not business:
        return {
            "assistant": {
                "model": {"provider": "openai", "model": "gpt-4o-mini"},
                "voice": {"provider": "11labs", "voiceId": "pMsXgVXv3BLzUgSXRplE"},
                "firstMessage": "This number is not configured for voice service. Please contact the business directly.",
                "endCallFunctionEnabled": True,
                "silenceTimeoutSeconds": 2,
                "maxDurationSeconds": 5,
            }
        }

    if not bool(getattr(business, "enable_inbound_call_handling", False)):
        return {
            "assistant": {
                "firstMessage": "Inbound calls are not enabled for this business.",
                "endCallFunctionEnabled": True,
            }
        }

    # Build prompts
    shared_prompt = await _get_shared_prompt(db)
    business_dict = {
        "display_name": getattr(business, "display_name", ""),
        "city": getattr(business, "city", ""),
        "hours": getattr(business, "hours", ""),
        "services": getattr(business, "services", ""),
        "fallback_number": getattr(business, "fallback_number", ""),
    }
    system_prompt = prompt_builder.build_system_prompt(
        shared_prompt, business_dict, is_outbound=False
    )

    first_message = prompt_builder.render(
        getattr(business, "inbound_welcome_template", None)
        or "Thank you for calling {{businessName}}! I'm Roo, how can I help?",
        {"businessName": getattr(business, "display_name", "")},
    )

    # Create call log
    vapi_call_id = call_data.get("id")
    call_log = CallLog(
        business_id=getattr(business, "id", None),
        call_type="inbound",
        vapi_call_id=vapi_call_id,
        customer_phone=from_number,
    )
    db.add(call_log)
    await db.commit()
    await db.refresh(call_log)

    # Send Slack notification and capture thread_ts for whisper/transcript
    if getattr(business, "nango_connection_id", None) and getattr(business, "slack_live_channel", None):
        try:
            slack_result = await slack_service.send_live_call_notification(
                connection_id=str(business.nango_connection_id),
                channel=str(business.slack_live_channel),
                call_type="inbound",
                call_log_id=str(call_log.id),
                vapi_call_id=vapi_call_id,
                business_name=getattr(business, "display_name", ""),
                customer_phone=from_number,
            )
            # Capture thread_ts so whisper/transcript can reply in the same thread
            thread_ts = slack_result.get("ts") if isinstance(slack_result, dict) else None
            if thread_ts:
                setattr(call_log, "slack_live_thread_ts", thread_ts)
                await db.commit()
        except Exception as e:
            print(f"Slack live notification failed (non-fatal): {e}")

    # Return assistant config
    assistant_config = {
        "model": {"provider": "openai", "model": "gpt-4o-mini"},
        "voice": {"provider": "11labs", "voiceId": getattr(business, "voice_id", "pMsXgVXv3BLzUgSXRplE")},
        "firstMessage": first_message,
        "systemPrompt": system_prompt,
        "maxDurationSeconds": getattr(business, "max_call_duration_minutes", 10) * 60,
        "serverMessages": ["transcript", "hang", "end-of-call-report"],
        "endCallFunctionEnabled": True,
    }

    if getattr(business, "human_transfer_on_escalation", False):
        assistant_config["tools"] = [
            {
                "type": "transferCall",
                "destinations": [
                    {
                        "type": "sip",
                        "sipUri": f"sip:{getattr(business, 'fallback_number', '')}@{settings.VOBIZ_SIP_DOMAIN}",
                    }
                ],
            }
        ]

    return {"assistant": assistant_config}


async def handle_transcript(payload: dict) -> dict:
    """Handle transcript events for live streaming to Slack."""
    call_id = payload.get("call", {}).get("id")
    message = payload.get("message", {})
    text = message.get("transcript", "")
    role = message.get("role", "assistant")

    if not text:
        return {"status": "no_text"}

    db = await _get_db()
    if db is None:
        return {"status": "db_unavailable"}
    result = await db.execute(select(CallLog).where(CallLog.vapi_call_id == call_id))
    call_log = result.scalar_one_or_none()
    if not call_log or not getattr(call_log, "slack_live_thread_ts", None):
        return {"status": "no_slack_thread"}

    # Append to transcript in DB (batch later in production)
    current = call_log.transcript or ""
    setattr(call_log, "transcript", f"{current}\n{role.capitalize()}: {text}".strip())
    await db.commit()

    # TODO: Implement batching for Slack updates
    return {"status": "processed"}


async def handle_end_of_call_report(payload: dict) -> dict:
    """Handle end-of-call-report: generate summary and post to Slack."""
    call_data = payload.get("call", {})
    vapi_call_id = call_data.get("id")
    duration = call_data.get("durationSeconds", 0)
    transcript = call_data.get("transcript", "")
    ended_reason = call_data.get("endedReason", "")

    db = await _get_db()
    if db is None:
        return {"status": "db_unavailable"}
    result = await db.execute(
        select(CallLog).where(CallLog.vapi_call_id == vapi_call_id)
    )
    call_log = result.scalar_one_or_none()
    if not call_log:
        return {"status": "call_log_not_found"}

    # Determine outcome
    if "transferred" in ended_reason:
        outcome = "transferred"
    elif "customer-ended-call" in ended_reason:
        outcome = "resolved"
    else:
        outcome = "abandoned"

    # Generate summary
    summary = groq_service.summarize_transcript(transcript, getattr(call_log, "call_type", "inbound"))
    credits_used = max(1, duration // 6)

    setattr(call_log, "duration_seconds", duration)
    setattr(call_log, "outcome", outcome)
    setattr(call_log, "transcript", transcript)
    setattr(call_log, "summary", summary)
    setattr(call_log, "credits_used", credits_used)
    await db.commit()

    # Send Slack summary
    result = await db.execute(
        select(Business).where(Business.id == call_log.business_id)
    )
    business = result.scalar_one_or_none()
    if business and getattr(business, "nango_connection_id", None) and getattr(business, "slack_summary_channel", None):
        transcript_lines = transcript.split("\n")[:3]
        preview = "\n".join(transcript_lines)
        asyncio.create_task(
            slack_service.send_post_call_summary(
                connection_id=str(business.nango_connection_id),
                channel=str(business.slack_summary_channel),
                call_type=getattr(call_log, "call_type", "inbound"),
                customer_phone=getattr(call_log, "customer_phone", ""),
                customer_name=getattr(call_log, "customer_name", None),
                duration_seconds=duration,
                outcome=outcome,
                summary=summary,
                transcript_preview=preview,
                credits_used=credits_used,
                vapi_call_id=vapi_call_id,
                call_log_id=str(call_log.id),
            )
        )

    return {"status": "summary_sent"}
