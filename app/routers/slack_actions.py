"""Slack Interactive Components handler (buttons)."""

import json

from fastapi import APIRouter, Request
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.models.business import Business
from app.models.call_log import CallLog
from app.services.vapi_service import vapi_client

router = APIRouter()


async def _get_db():
    async for session in get_db():
        return session


@router.post("")
async def slack_actions(request: Request):
    """Handle interactive button clicks from Slack."""
    body = await request.form()
    payload = json.loads(body.get("payload", "{}"))

    actions = payload.get("actions", [])
    if not actions:
        return {"status": "no_actions"}

    action = actions[0]
    action_id = action.get("action_id")
    value = action.get("value")  # vapi_call_id or call_log_id or phone

    db = await _get_db()

    if action_id in ("takeover", "transfer"):
        # Find call log by vapi_call_id
        result = await db.execute(select(CallLog).where(CallLog.vapi_call_id == value))
        call_log = result.scalar_one_or_none()

        if not call_log:
            return {"response_type": "ephemeral", "text": "⚠️ Call not found."}

        # Check if call still live
        status = await vapi_client.get_call_status(value)
        if status != "in-progress":
            return {"response_type": "ephemeral", "text": "⚠️ Call has already ended."}

        # Get business for fallback number
        biz_result = await db.execute(
            select(Business).where(Business.id == call_log.business_id)
        )
        business = biz_result.scalar_one_or_none()

        if not business:
            return {"response_type": "ephemeral", "text": "⚠️ Business not found."}

        # Transfer call
        destination = {
            "type": "sip",
            "sipUri": f"sip:{business.fallback_number}@{settings.VOBIZ_SIP_DOMAIN}",
        }
        await vapi_client.transfer_call(value, destination)

        return {
            "response_type": "in_channel",
            "text": "📞 Transferring call to owner...",
        }

    elif action_id == "end_call":
        # End the call
        try:
            await vapi_client.end_call(value)
            return {"response_type": "in_channel", "text": "🔇 Call ended."}
        except Exception as e:
            return {"response_type": "ephemeral", "text": f"Error: {e}"}

    elif action_id == "view_transcript":
        # Fetch full transcript from DB
        result = await db.execute(select(CallLog).where(CallLog.vapi_call_id == value))
        call_log = result.scalar_one_or_none()
        if call_log:
            transcript = call_log.transcript or "No transcript available."
            return {
                "response_type": "ephemeral",
                "text": f"*Full Transcript*\n```{transcript[:3000]}```",
            }
        return {"response_type": "ephemeral", "text": "Transcript not found."}

    elif action_id == "callback":
        # value is customer phone number
        return {
            "response_type": "ephemeral",
            "text": f"📞 Callback requested for {value}. (Feature: open callback form)",
        }

    elif action_id == "mark_resolved":
        # value is call_log_id
        result = await db.execute(select(CallLog).where(CallLog.id == value))
        call_log = result.scalar_one_or_none()
        if call_log:
            call_log.outcome = "resolved"
            await db.commit()
            return {"response_type": "in_channel", "text": "✅ Marked as resolved."}
        return {"response_type": "ephemeral", "text": "Call log not found."}

    return {"status": "unknown_action"}
